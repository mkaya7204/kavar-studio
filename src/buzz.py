"""D-59 (user 2026-11-03: "önemli ve yerlerde ses getiren yeni AI modelleri de var", "onay veriyorum"): what is
being talked about right now, used ONLY to rank the news. Hacker News front stories of the last 48 h and the Hugging
Face trending models; a news item from a company's own blog that matches one gets a "talked about" note and goes
first. The story itself, its text and images still come only from the company's own page (locked rule 9).
"""

import re
import time

import requests

HN_URL = "https://hn.algolia.com/api/v1/search"
HF_URL = "https://huggingface.co/api/models"
MIN_POINTS = 80
GENERIC = {"the", "and", "for", "with", "new", "how", "our", "your", "from", "into", "now", "today", "introducing",
           "model", "models", "open", "release", "launch", "update", "updates", "news", "blog", "research", "data",
           "agent", "agents", "about", "more", "what", "why", "using", "use", "build", "faster", "better", "first",
           "available", "announcing", "meet", "series", "program", "years", "year", "people", "world", "work",
           # product-line words many companies use ("MiniMax M3.1 Flash" is not "DeepSeek-V4.1-Flash")
           "flash", "pro", "mini", "max", "ultra", "lite", "turbo", "plus", "image", "video", "audio", "voice", "code",
           "chat", "tech", "large", "small", "base", "instruct", "preview", "beta", "studio", "labs", "team", "teams",
           "next", "generation", "part", "giving", "every", "expanding", "partnership", "inside", "behind"}


def _distinctive(name: str, company: str) -> bool:
    """A name that points at ONE product: it carries a version number ("kimi k3 1 pro", "flux 3", "gpt 5"), or it
    starts with the company's own name ("minimax music"). Plain English words ("open weights") never count."""
    words = name.split()
    if any(c.isdigit() for c in name):
        return any(not w.isdigit() and w not in GENERIC for w in words)
    return len(words) >= 2 and words[0] in company.split()


def hn_stories(hours: int = 48) -> list[dict]:
    since = int(time.time()) - hours * 3600
    r = requests.get(HN_URL, params={"tags": "story", "numericFilters": f"created_at_i>{since},points>{MIN_POINTS}",
                                     "hitsPerPage": 100}, timeout=20)
    r.raise_for_status()
    return [{"title": h.get("title") or "", "points": h.get("points") or 0, "url": h.get("url") or ""}
            for h in r.json().get("hits", [])]


def hf_trending(limit: int = 40) -> list[str]:
    r = requests.get(HF_URL, params={"sort": "trendingScore", "direction": -1, "limit": limit}, timeout=20)
    r.raise_for_status()
    return [m.get("id") or m.get("modelId") or "" for m in r.json()]


def _fold(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def keys(item: dict) -> list[str]:
    """What identifies a news item: its company (the source name) and the names in its title ("Kimi K3", "FLUX 3",
    "Olmo")."""
    company = _fold(item.get("source", ""))
    out = [company]
    for m in re.finditer(r"\b([A-Z][\w.-]*[A-Za-z0-9](?:\s+[A-Z0-9][\w.-]*)?)", item.get("title", "")):
        name = _fold(m.group(1))
        words = name.split()
        while words and words[0] in GENERIC:  # "The Next Generation" -> "generation" -> dropped below
            words = words[1:]
        name = " ".join(words)  # a product name keeps its own words ("deepseek v4 1 flash 1017")
        if len(name) >= 3 and _distinctive(name, company):
            out.append(name)
    return [k for k in dict.fromkeys(out) if k]


def score(item: dict, stories: list[dict], trending: list[str]) -> tuple[int, str]:
    """(points, note): HN points of the stories that name the item's product / model, plus 100 per trending
    Hugging Face model of it. The company name alone never counts: the big companies would always win."""
    item_keys = keys(item)
    company = item_keys[0] if item_keys else ""
    names = [n for n in item_keys[1:] if n != company and n not in company.split()]
    points, notes = 0, []
    for s in stories:
        title = f" {_fold(s['title'])} "
        if any(f" {n} " in title for n in names):
            points += s["points"]
            notes.append(f"HN {s['points']}")
    for model in trending:
        folded = _fold(model.replace("/", " "))
        # a model id starts with its company ("black-forest-labs/..."): only a versioned product name counts here
        if any(f" {n} " in f" {folded} " for n in names if any(c.isdigit() for c in n)):
            points += 100
            notes.append(f"HF trend {model}")
    return points, ", ".join(notes[:3])


def annotate(items: list[dict]) -> list[dict]:
    """Adds item["buzz"] (points) and a note in front of the summary the ranker reads; never fails the news."""
    try:
        stories, trending = hn_stories(), hf_trending()
    except (requests.RequestException, ValueError) as exc:
        print(f"[news] buzz signal skipped: {type(exc).__name__}")
        return items
    for item in items:
        points, note = score(item, stories, trending)
        item["buzz"] = points
        if points:
            item["summary"] = f"[Şu an konuşuluyor: {note}] " + str(item.get("summary", ""))
            print(f"[news] talked about ({note}): {item['title']}")
    return items
