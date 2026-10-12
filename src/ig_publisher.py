"""Publish to Instagram with the official API (Instagram API with Instagram Login).

Needs in .env (never printed): IG_USER_ID and IG_ACCESS_TOKEN, a long-lived token of the
@thekavar.ai professional account with instagram_business_basic and
instagram_business_content_publish. The token lasts 60 days; refresh_token() renews it
(daily.py calls it every morning) and rewrites .env.

Flow per post (Meta's content publishing docs): one container per media item ->
a CAROUSEL / REELS / STORIES container -> wait until FINISHED -> media_publish.
Media is fetched by Instagram from temporary public URLs (media_host.public_files).
Link and poll stickers can't be added through the API.
"""

import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from media_host import public_files

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
API = "https://graph.instagram.com/v25.0"
POLL_SECONDS = 8
POLL_LIMIT = 75  # x 8 s = 10 minutes for video processing


class PublishError(RuntimeError):
    pass


def _creds() -> tuple[str, str]:
    load_dotenv(ENV_PATH, override=True)
    uid, token = os.getenv("IG_USER_ID", ""), os.getenv("IG_ACCESS_TOKEN", "")
    if not uid or not token:
        raise PublishError("IG_USER_ID / IG_ACCESS_TOKEN missing in .env")
    return uid, token


def _call(method: str, path: str, **params) -> dict:
    _, token = _creds()
    r = requests.request(method, f"{API}/{path}", params={**params, "access_token": token}, timeout=60)
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        raise PublishError(f"{path}: {err.get('message') or r.text[:200]} (code {err.get('code')})")
    return data


def _wait(container: str) -> None:
    for _ in range(POLL_LIMIT):
        status = _call("GET", container, fields="status_code,status").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            detail = _call("GET", container, fields="status").get("status", "")
            raise PublishError(f"container {container} {status}: {detail}")
        time.sleep(POLL_SECONDS)
    raise PublishError(f"container {container} not ready after {POLL_LIMIT * POLL_SECONDS}s")


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in (".mp4", ".mov")


def _publish(container: str) -> str:
    _wait(container)
    uid, _ = _creds()
    media_id = _call("POST", f"{uid}/media_publish", creation_id=container)["id"]
    return media_id


def account() -> dict:
    uid, _ = _creds()
    return _call("GET", uid, fields="id,username,account_type,media_count")


def publishing_quota() -> dict:
    uid, _ = _creds()
    return _call("GET", f"{uid}/content_publishing_limit", fields="quota_usage,config")


def publish_carousel(files: list[Path], caption: str, alt_texts: list[str] | None = None) -> str:
    """2-10 images / videos in order; returns the published media id."""
    files = [Path(f) for f in files]
    if not 2 <= len(files) <= 10:
        raise PublishError(f"a carousel takes 2-10 items, got {len(files)}")
    uid, _ = _creds()
    alt_texts = alt_texts or [""] * len(files)
    with public_files(files) as urls:
        children = []
        for f, url, alt in zip(files, urls, alt_texts):
            if _is_video(f):
                params = {"media_type": "VIDEO", "video_url": url, "is_carousel_item": "true"}
            else:
                params = {"image_url": url, "is_carousel_item": "true"}
                if alt:
                    params["alt_text"] = alt[:1000]
            children.append(_call("POST", f"{uid}/media", **params)["id"])
        for c in children:  # Instagram must fetch every item while the tunnel is up
            _wait(c)
        parent = _call("POST", f"{uid}/media", media_type="CAROUSEL", children=",".join(children),
                       caption=caption)["id"]
        return _publish(parent)


def publish_reel(video: Path, caption: str, cover: Path | None = None, cover_offset_ms: int = 300) -> str:
    """cover: a 9:16 JPEG (cover.jpg from the builder) sent as cover_url; without it the frame at
    cover_offset_ms is used. Frame 0 is designed as the cover either way."""
    uid, _ = _creds()
    files = [video] + ([Path(cover)] if cover else [])
    with public_files(files) as urls:
        params = {"media_type": "REELS", "video_url": urls[0], "caption": caption, "share_to_feed": "true"}
        if cover:
            params["cover_url"] = urls[1]
        else:
            params["thumb_offset"] = str(cover_offset_ms)
        container = _call("POST", f"{uid}/media", **params)["id"]
        return _publish(container)


def publish_story(file: Path) -> str:
    uid, _ = _creds()
    file = Path(file)
    with public_files([file]) as (url,):
        key = "video_url" if _is_video(file) else "image_url"
        container = _call("POST", f"{uid}/media", media_type="STORIES", **{key: url})["id"]
        return _publish(container)


def permalink(media_id: str) -> str:
    return _call("GET", media_id, fields="permalink").get("permalink", "")


def refresh_token() -> bool:
    """Renew the 60-day token (allowed once it is >24 h old) and store it in .env."""
    _, token = _creds()
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30)
    new = r.json().get("access_token") if r.ok else None
    if not new:
        return False
    text = ENV_PATH.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^IG_ACCESS_TOKEN=.*$", f"IG_ACCESS_TOKEN={new}", text)
    ENV_PATH.write_text(text, encoding="utf-8")
    return True


if __name__ == "__main__":
    info = account()
    print(f"@{info.get('username')} ({info.get('account_type')}), {info.get('media_count')} posts")
    print("quota:", publishing_quota())
