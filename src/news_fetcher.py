"""Find fresh AI news in the RSS feeds of news_sources.json.

Items already turned into a post (state/news_history.json) are skipped, so the
same story never runs twice. Order: newest day first, then source priority
(official company blogs before press), then time.
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "news_sources.json"
HISTORY_PATH = ROOT / "state" / "news_history.json"  # state/ is kept in git (the cloud run commits it)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"}
ATOM = "{http://www.w3.org/2005/Atom}"


def _date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        d = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _items(feed: dict) -> list[dict]:
    r = requests.get(feed["url"], headers=HEADERS, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.findall(".//item"):
        out.append({"title": (it.findtext("title") or "").strip(), "url": (it.findtext("link") or "").strip(),
                    "date": _date(it.findtext("pubDate")), "summary": (it.findtext("description") or "")[:500]})
    for it in root.findall(f".//{ATOM}entry"):
        link = it.find(f"{ATOM}link[@rel='alternate']")
        if link is None:
            link = it.find(f"{ATOM}link")
        out.append({"title": (it.findtext(f"{ATOM}title") or "").strip(),
                    "url": link.get("href", "") if link is not None else "",
                    "date": _date(it.findtext(f"{ATOM}published") or it.findtext(f"{ATOM}updated")),
                    "summary": (it.findtext(f"{ATOM}summary") or "")[:500]})
    for o in out:
        o["source"], o["priority"] = feed["name"], feed.get("priority", 1)
    return [o for o in out if o["title"] and o["url"].startswith("http")]


def load_history() -> list[str]:
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def mark_used(url: str) -> None:
    urls = (load_history() + [url])[-300:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(urls, indent=1), encoding="utf-8")


def fetch_news(limit: int = 5) -> list[dict]:
    """Fresh, unused news items, best first: [{title, url, date, source, summary}].

    D-35 (2026-10-19): when nothing unused is left inside max_age_hours (the companies post little
    over a weekend; 10-19 had 0 carousels), the unused items of the last fallback_age_hours are used.
    """
    config = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    used = set(load_history())
    items = []
    for feed in config["feeds"]:
        try:
            items += _items(feed)
        except (requests.RequestException, ET.ParseError) as exc:
            print(f"[news] {feed['name']} skipped: {type(exc).__name__}")
    unused = [i for i in items if i["date"] and i["url"] not in used]
    fresh = [i for i in unused if i["date"] >= now - timedelta(hours=config.get("max_age_hours", 72))]
    if not fresh:
        hours = config.get("fallback_age_hours", 168)
        fresh = [i for i in unused if i["date"] >= now - timedelta(hours=hours)]
        print(f"[news] nothing unused in {config.get('max_age_hours', 72)} h; "
              f"{len(fresh)} unused from the last {hours} h")
    fresh.sort(key=lambda i: (i["date"].date(), i["priority"], i["date"]), reverse=True)
    for i in fresh:
        i["date"] = i["date"].isoformat()
    return fresh[:limit]


def feed_item(url: str) -> dict | None:
    """The feed entry for one article URL, used or not (its date is the real publish date)."""
    config = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    for feed in config["feeds"]:
        try:
            for i in _items(feed):
                if i["url"].rstrip("/") == url.rstrip("/"):
                    return {**i, "date": i["date"].isoformat() if i["date"] else None}
        except (requests.RequestException, ET.ParseError):
            continue
    return None


if __name__ == "__main__":
    for n in fetch_news(10):
        print(f"{n['date'][:16]}  [{n['source']}]  {n['title']}\n    {n['url']}")
