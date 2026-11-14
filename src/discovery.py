"""D-76 (user 2026-11-14): "bir çok haber kanalı takip edilecek, ilgili haberin kaynağına gidip o şirketin kendi
sayfasından ... görsel olarak da uygun bulunmazsa da ilgili şirketin herhangi görselleri alınarak haber yapılacak".

News channels (tech press, Turkish tech sites, Reddit, Google News) are used to FIND stories, also of companies we
don't follow. A found story is never written from the channel: Claude finds the company's own announcement page
(blog, newsroom, docs, release notes), and that page is the source of the text and the pictures (CLAUDE.md §1.9:
no press-site photos). No own page = the story is skipped.

    discover() -> [{"title", "summary", "url" (the channel's article), "source", "date", "discovered": True,
                    "mentions": channels that ran it}]
    company_page(item) -> {"url", "company"} | None
"""

import html
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

from claude_usage import record as record_usage
from news_fetcher import HEADERS, SOURCES_PATH, _items, load_history, load_titles, same_story, seen_story, story_words

MAX_AGE_HOURS = 48
TIMEOUT = 240
AI_WORDS = re.compile(r"\b(ai|a\.i\.|yapay zek|llms?|gpt|chatgpt|claude|gemini|copilot|agents?|model|chatbot|"
                      r"openai|anthropic|deepmind|mistral|grok|llama|qwen|deepseek|perplexity|midjourney|runway|"
                      r"suno|elevenlabs|sora|veo|machine learning|neural|robot)\b", re.I)


def channels() -> list[dict]:
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8")).get("discovery_feeds", [])


def media_hosts() -> set[str]:
    """Every channel's own host (and big platforms): never a company's own page."""
    hosts = {(urlsplit(c["url"]).hostname or "").removeprefix("www.") for c in channels()}
    return hosts | {"news.google.com", "reddit.com", "x.com", "twitter.com", "youtube.com", "medium.com",
                    "linkedin.com", "facebook.com", "techmeme.com", "theverge.com", "techcrunch.com",
                    "venturebeat.com", "arstechnica.com", "technologyreview.com", "wired.com", "engadget.com",
                    "the-decoder.com", "marktechpost.com", "webtekno.com", "shiftdelete.net", "donanimhaber.com",
                    "bloomberg.com", "reuters.com", "cnbc.com", "theinformation.com", "9to5google.com", "9to5mac.com",
                    "zdnet.com", "cnet.com", "tomsguide.com", "businessinsider.com", "forbes.com", "nytimes.com"}


def _media(url: str, hosts: set[str]) -> bool:
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in hosts if h)


def discover(limit: int = 30, now: datetime | None = None) -> list[dict]:
    """AI stories the channels ran in the last MAX_AGE_HOURS, unused, one per story, most channels first."""
    since = (now or datetime.now(timezone.utc)) - timedelta(hours=MAX_AGE_HOURS)
    used, titles = set(load_history()), load_titles()
    found: list[dict] = []
    for ch in channels():
        try:
            items = _items(ch)
        except Exception as exc:  # noqa: BLE001  one closed channel never stops the day
            print(f"[discovery] {ch['name']} skipped: {type(exc).__name__}")
            continue
        for i in items:
            text = f"{i['title']} {re.sub(r'<[^>]+>', ' ', i.get('summary') or '')}"
            if not i["date"] or i["date"] < since or i["url"] in used or not AI_WORDS.search(text):
                continue
            if seen_story(i["title"], titles):
                continue
            twin = next((f for f in found if same_story(f["title"], i["title"])), None)
            if twin:
                twin["mentions"] += 1
                continue
            found.append({**i, "title": html.unescape(i["title"]),
                          "summary": html.unescape(re.sub(r"<[^>]+>", " ", i.get("summary") or ""))[:400].strip(),
                          "discovered": True, "mentions": 1})
    found.sort(key=lambda f: (f["mentions"], f["date"]), reverse=True)
    for f in found:
        f["date"] = f["date"].isoformat()
    print(f"[discovery] {len(found)} stories from {len(channels())} channels")
    return found[:limit]


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["url", "company"],
          "properties": {"url": {"type": "string"}, "company": {"type": "string"}}}
PROMPT = """A news channel ran this story:
title: {title}
summary: {summary}
channel article: {url}

Find the OWN page of the company / organisation the story is about where it announced or documented this \
(its blog, newsroom, press release on its own domain, product docs, release notes, model card, GitHub repository). \
Open the page (WebFetch) and check it is about this exact news. Return its URL and the company's name. \
Never a news site, a newsletter, social media, Reddit, YouTube or Medium. Return url "" if the company has no own \
page about it (for example a rumour, a lawsuit or a report about the company)."""


def company_page(item: dict) -> dict | None:
    exe = None if os.getenv("SCRIPT_WRITER_NO_CLI") else shutil.which("claude")
    if not exe:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run([exe, "-p", "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
                               "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch",
                               "--no-session-persistence"],
                              input=PROMPT.format(title=item["title"], summary=item.get("summary", ""), url=item["url"]),
                              capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT, env=env)
        record_usage("news_company_page", proc.stdout)
        out = json.loads(proc.stdout).get("structured_output") or {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None
    return checked_page(out, item)


def checked_page(out: dict, item: dict) -> dict | None:
    """The company page only if it is not a channel and really carries the story's distinctive words."""
    url = (out.get("url") or "").strip()
    if not url.startswith("http") or _media(url, media_hosts()):
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return None
    words = story_words(item["title"])
    page = r.text.lower()
    if words and not any(w in page for w in words):
        return None  # the page doesn't even mention the story
    return {"url": r.url, "company": (out.get("company") or "").strip()}
