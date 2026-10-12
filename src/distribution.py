"""Affiliate links and per-platform upload metadata for a finished video.

Reads affiliates.json:
  - tools.<domain>.url   your affiliate URL for that tool (used as-is, marked affiliate)
  - default_params       added to the tool's real URL when no affiliate entry exists
                         (tracking only, e.g. UTM; "{slug}" becomes the tool slug)
  - disclosure           appended to captions whenever an affiliate URL is used
  - platforms            caption_mode ('link_in_bio' | 'link'), hashtag and length limits
"""

import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "affiliates.json"

DEFAULT_CONFIG = {
    "default_params": {},
    "tools": {},
    "disclosure": "#ad · affiliate link",
    "link_in_bio_text": "🔗 Link in bio",
    "platforms": {"tiktok": {"caption_mode": "link_in_bio", "max_hashtags": 8, "max_caption_chars": 2200}},
}


def load_config(path: Path = CONFIG_PATH) -> dict:
    try:
        return {**DEFAULT_CONFIG, **json.loads(path.read_text(encoding="utf-8"))}
    except FileNotFoundError:
        return DEFAULT_CONFIG
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} is not valid JSON: {exc}") from exc


def _domain(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.").lower()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "tool"


def _add_params(url: str, params: dict) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update({k: v for k, v in params.items() if k not in query})  # never override existing
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), parts.fragment))


def build_affiliate_link(tool_name: str, website_url: str, config: dict | None = None) -> dict:
    """Return {'url', 'is_affiliate', 'source'} for a tool."""
    config = config or load_config()
    domain = _domain(website_url)
    tools = {k.removeprefix("www.").lower(): v for k, v in config.get("tools", {}).items()}
    if domain in tools and tools[domain].get("url"):
        return {"url": tools[domain]["url"], "is_affiliate": True, "source": "affiliates.json"}
    params = {k: str(v).replace("{slug}", _slug(tool_name)) for k, v in config.get("default_params", {}).items()}
    if params:
        return {"url": _add_params(website_url, params), "is_affiliate": False, "source": "default_params"}
    return {"url": website_url, "is_affiliate": False, "source": "website"}


def format_caption(caption: str, hashtags: list[str], link: dict, platform: dict, disclosure: str,
                   bio_text: str = "🔗 Link in bio") -> str:
    """Caption + link line (or 'Link in bio') + disclosure + hashtags, within the platform's limits."""
    lines = [caption.strip()]
    if platform.get("caption_mode") == "link":
        lines.append(f"🔗 {link['url']}")
    else:
        lines.append(bio_text)
    if link["is_affiliate"] and disclosure:
        lines.append(disclosure)
    tags = " ".join(hashtags[: platform.get("max_hashtags", len(hashtags))])
    text = "\n\n".join(lines + ([tags] if tags else []))
    limit = platform.get("max_caption_chars")
    if limit and len(text) > limit:
        # Trim the free-text caption, never the link, disclosure or tags.
        overflow = len(text) - limit + 1
        lines[0] = lines[0][: max(0, len(lines[0]) - overflow)].rstrip() + "…"
        text = "\n\n".join(lines + ([tags] if tags else []))
    return text


def build_post(script: dict, video: dict, config: dict | None = None) -> dict:
    """Assemble post.json: tool info, affiliate link and ready-to-paste captions per platform."""
    config = config or load_config()
    link = build_affiliate_link(script["tool_name"], script["website_url"], config)
    platforms = {
        name: {
            "caption_mode": settings.get("caption_mode", "link_in_bio"),
            "caption": format_caption(script["caption"], script["hashtags"], link, settings,
                                      config.get("disclosure", ""),
                                      config.get("link_in_bio_text", DEFAULT_CONFIG["link_in_bio_text"])),
        }
        for name, settings in config.get("platforms", {}).items()
    }
    if "youtube_shorts" in platforms:
        platforms["youtube_shorts"]["title"] = f"{script['hook']} #shorts"[:100]
    return {
        "tool_name": script["tool_name"],
        "website_url": script["website_url"],
        "affiliate_link": link["url"],
        "affiliate_link_source": link["source"],
        "is_affiliate": link["is_affiliate"],
        "bio_link": link["url"],  # put this in the profile bio for 'link_in_bio' platforms
        "hook": script["hook"],
        "caption": script["caption"],
        "hashtags": script["hashtags"],
        "platforms": platforms,
        "script_source": script["source"],
        "video_path": video["video_path"],
        "duration_sec": video["duration_sec"],
    }


if __name__ == "__main__":
    script = {
        "tool_name": "Kitbar", "website_url": "https://kitbar.io/", "hook": "Stop opening 10 tabs",
        "caption": "All your dev tools in one bar 🟢", "source": "claude_code",
        "hashtags": ["#devtools", "#saas", "#developer", "#vercel", "#github", "#indiehacker", "#productivity", "#kitbar"],
    }
    video = {"video_path": "output/final/final_video.mp4", "duration_sec": 24.0}
    config = load_config()

    # 1) No affiliate entry -> real site + tracking params, no disclosure.
    post = build_post(script, video, config)
    assert post["affiliate_link"].startswith("https://kitbar.io/?utm_source="), post["affiliate_link"]
    assert "utm_campaign=kitbar" in post["affiliate_link"] and not post["is_affiliate"]
    assert config.get("link_in_bio_text", "🔗 Link in bio") in post["platforms"]["tiktok"]["caption"]
    assert post["affiliate_link"] in post["platforms"]["youtube_shorts"]["caption"]
    assert config["disclosure"] not in post["platforms"]["tiktok"]["caption"]
    assert post["platforms"]["youtube_shorts"]["caption"].count("#") == 3
    print(json.dumps(post, indent=2, ensure_ascii=False))

    # 2) Affiliate entry (www. ignored) -> that URL, disclosure added everywhere.
    config_aff = {**config, "tools": {"www.kitbar.io": {"url": "https://kitbar.io/?via=TEST123"}}}
    post_aff = build_post(script, video, config_aff)
    assert post_aff["affiliate_link"] == "https://kitbar.io/?via=TEST123" and post_aff["is_affiliate"]
    assert all(config["disclosure"] in p["caption"] for p in post_aff["platforms"].values())

    # 3) Existing query params are kept, not overwritten.
    assert build_affiliate_link("X", "https://x.com/?utm_source=keep", config)["url"].count("utm_source=keep") == 1

    # 4) Over-long captions are trimmed, link and tags kept.
    long_cfg = {**config, "platforms": {"tiktok": {"caption_mode": "link", "max_hashtags": 2, "max_caption_chars": 120}}}
    cap = build_post({**script, "caption": "x" * 500}, video, long_cfg)["platforms"]["tiktok"]["caption"]
    assert len(cap) <= 120 and "kitbar.io" in cap and "#devtools" in cap, cap
    print("All distribution checks passed.")
