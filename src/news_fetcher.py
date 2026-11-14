"""Find fresh AI news in the RSS feeds of news_sources.json.

Items already turned into a post (state/news_history.json) are skipped, so the
same story never runs twice. Order: newest day first, then source priority
(official company blogs before press), then time.
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

import buzz  # noqa: E402  D-59: what is talked about (ranking only)
import page_sources  # noqa: E402  D-59: labs with no RSS

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "news_sources.json"
HISTORY_PATH = ROOT / "state" / "news_history.json"  # state/ is kept in git (the cloud run commits it)
TITLES_PATH = ROOT / "state" / "news_titles.json"  # D-66: titles of used news, so a second blog's copy is skipped
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


def title_key(title: str) -> str:
    """The title without case, punctuation or spacing: one announcement posted on two blogs has the same key."""
    return " ".join(re.sub(r"[^\w]+", " ", (title or "").lower()).split())


# D-75 (user 2026-11-14: "aynı haberin onaydan geçmesi veya aynı haberin başka yerde de bulup yayına onay çıkması
# konusunda da önlem al"): 11-14 "Introducing Gemini 4 Hydrogen" (Gemini blog) passed after "Gemini 4 Hydrogen:
# everyday coding ..." (developers blog) was already queued, because D-66 only caught identical titles. Two titles are
# the same story when they share a DISTINCTIVE word (not a brand or a filler word) and most of the shorter one.
COMMON_WORDS = set("""introducing introduces announcing announces launch launches launching meet new now today
available update updates updated more with from your what into using across about their this that over how help
helps make makes made built build first next latest model models google gemini deepmind openai chatgpt anthropic
claude microsoft copilot meta apple nvidia samsung amazon youtube android workspace chrome gmail search blog news
coming rolling expanding expands bring brings tool tools feature features plus pro ultra flash lite mini team
teams people users developers everyone""".split())


def story_words(title: str) -> set[str]:
    return {w for w in title_key(title).split() if len(w) > 3 and w not in COMMON_WORDS}


def same_story(a: str, b: str) -> bool:
    wa, wb = story_words(a), story_words(b)
    if not wa or not wb:
        return title_key(a) == title_key(b) != ""
    shared = wa & wb
    return bool(shared) and len(shared) / min(len(wa), len(wb)) >= 0.5


def seen_story(title: str, keys: list[str] | None = None) -> str:
    """The used / queued title this one repeats, or ""."""
    for k in (load_titles() if keys is None else keys)[-150:]:
        if same_story(title, k):
            return k
    return ""


def load_titles() -> list[str]:
    try:
        return json.loads(TITLES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def mark_used(url: str, title: str = "") -> None:
    urls = (load_history() + [url])[-300:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(urls, indent=1), encoding="utf-8")
    if title_key(title):  # D-66: the same news on another blog (blog.google + deepmind.google) is used too
        keys = (load_titles() + [title_key(title)])[-300:]
        TITLES_PATH.write_text(json.dumps(keys, indent=1, ensure_ascii=False), encoding="utf-8")


def unmark(url: str, title: str = "") -> None:
    """D-67: a story whose carousel was made but never judged (the editor gave no answer) is not used up."""
    HISTORY_PATH.write_text(json.dumps([u for u in load_history() if u != url], indent=1), encoding="utf-8")
    if key := title_key(title):
        TITLES_PATH.write_text(json.dumps([k for k in load_titles() if k != key], indent=1, ensure_ascii=False),
                               encoding="utf-8")


def fetch_news(limit: int = 5) -> list[dict]:
    """Fresh, unused news items, best first: [{title, url, date, source, summary}].

    D-35 (2026-10-19): when fewer than min_fresh unused items are left inside max_age_hours (the
    companies post little over a weekend; 10-19 had 0 carousels, its one fresh item was an SSD ad),
    the unused items of the last fallback_age_hours fill the list after the fresh ones.
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
    for page in config.get("pages", []):  # D-59: labs with no RSS, read from their own news page
        try:
            got = page_sources.items(page, used)
            print(f"[news] {page['name']}: {len(got)} posts from its news page")
            items += got
        except requests.RequestException as exc:
            print(f"[news] {page['name']} skipped: {type(exc).__name__}")
    used_titles, unused = load_titles()[-150:], []
    for i in items:  # D-66/D-75: a used story (any wording, any blog), or one story twice in one fetch, is skipped
        key = title_key(i.get("title", ""))
        if i["date"] and i["url"] not in used and not (key and seen_story(key, used_titles)):
            unused.append(i)
            used_titles.append(key)
    recent = [i for i in unused if i["date"] >= now - timedelta(hours=config.get("fallback_age_hours", 168))]
    buzz.annotate(recent)  # D-59: what is talked about right now goes first (ranking only, never the source)
    fresh = [i for i in unused if i["date"] >= now - timedelta(hours=config.get("max_age_hours", 72))]
    fresh.sort(key=lambda i: (i.get("buzz", 0) > 0, i["date"].date(), i["priority"], i["date"]), reverse=True)
    if len(fresh) < config.get("min_fresh", 6):
        hours = config.get("fallback_age_hours", 168)
        older = [i for i in unused if i not in fresh and i["date"] >= now - timedelta(hours=hours)]
        older.sort(key=lambda i: (i.get("buzz", 0) > 0, i["date"].date(), i["priority"], i["date"]), reverse=True)
        print(f"[news] {len(fresh)} unused in {config.get('max_age_hours', 72)} h; "
              f"adding {len(older)} unused from the last {hours} h")
        fresh += older
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
