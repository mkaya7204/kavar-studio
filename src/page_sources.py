"""D-59 (user 2026-11-03, "onay veriyorum"): news from AI labs whose own site has no RSS (Anthropic, xAI, DeepSeek,
MiniMax, Kimi, Black Forest Labs, Runway). Their own news page lists the posts; each post's own page gives the title,
the date and its own image (locked rule 9: the companies' own pages only). news_sources.json "pages".

A post page is read once and remembered in state/page_posts.json, so a run fetches only the new links.
"""

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "state" / "page_posts.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/130.0 Safari/537.36"}
MAX_NEW_PER_PAGE = 8  # post pages read per source and run (the newest links come first on these pages)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                      "dec"], 1)}
DATE_TAGS = (r'article:published_time"\s+content="([^"]+)"', r'"datePublished"\s*:\s*"([^"]+)"',
             r'<time[^>]*datetime="([^"]+)"')
TEXT_DATE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}), (20\d\d)\b")


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def post_links(page_html: str, base: str, pattern: str) -> list[str]:
    """The post links of a news page, in page order, each once."""
    out = []
    for href in re.findall(r'href="([^"#?]+)[^"]*"', page_html):
        url = urljoin(base, html.unescape(href))
        path = re.sub(r"^https?://[^/]+", "", url)
        if re.fullmatch(pattern, path) and url not in out:
            out.append(url)
    return out


def _meta(page_html: str, name: str) -> str:
    m = re.search(rf'<meta[^>]+(?:property|name)="{name}"[^>]+content="([^"]*)"', page_html) or \
        re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="{name}"', page_html)
    return html.unescape(m.group(1)).strip() if m else ""


def post_date(page_html: str) -> datetime | None:
    """The publish date from the page's own tags, else the first written date ("Oct 31, 2026")."""
    for pat in DATE_TAGS:
        if m := re.search(pat, page_html):
            try:
                d = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    if m := TEXT_DATE.search(page_html):
        return datetime(int(m.group(3)), MONTHS[m.group(1).lower()[:3]], int(m.group(2)), 12, tzinfo=timezone.utc)
    return None


def clean_title(og_title: str, site: str) -> str:
    """"Runway News | Introducing Solaris" -> "Introducing Solaris"; "MiniMax H3: ... - MiniMax" -> "MiniMax H3: ...":
    the longest part that is not the site's own name."""
    parts = [p.strip() for p in re.split(r"\s+[|–]\s+|\s+-\s+", og_title) if p.strip()]
    site_words = set(re.findall(r"\w+", site.lower())) | {"news", "blog"}
    named = [p for p in parts if not set(re.findall(r"\w+", p.lower())) <= site_words]
    return max(named or parts or [""], key=len)


def read_post(url: str, site: str = "") -> dict | None:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    title = clean_title(_meta(r.text, "og:title"), site)
    date = post_date(r.text)
    if not title or not date or len(title.split()) < 2:  # "Announcements": a category page, not a post
        return None
    return {"title": title, "date": date.isoformat(), "summary": _meta(r.text, "og:description")[:500]}


def items(source: dict, used: set[str]) -> list[dict]:
    """A page source's posts in the RSS item shape of news_fetcher: title, url, date, summary, source, priority."""
    r = requests.get(source["url"], headers=HEADERS, timeout=20)
    r.raise_for_status()
    cache = _load_cache()
    new = 0
    out = []
    for url in post_links(r.text, source["url"], source["pattern"]):
        if url in used:
            continue
        if url not in cache:
            if new >= MAX_NEW_PER_PAGE:
                continue
            new += 1
            try:
                cache[url] = read_post(url, source["name"])
            except requests.RequestException:
                continue
        post = cache[url]
        if post:
            out.append({**post, "url": url, "date": datetime.fromisoformat(post["date"]),
                        "source": source["name"], "priority": source.get("priority", 1)})
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(dict(list(cache.items())[-600:]), indent=1, ensure_ascii=False), encoding="utf-8")
    return out
