"""D-75 (user 2026-11-14): "kaynak çoğalınca hep aynı isimlerin haberlerini yapmayalım ... hep Gemini olması
kendimizi tekrara ve aynı şeyleri yayınlıyoruz gibi oluyor" (Gemini itself is fine; always Gemini is not).

What the page queued for its last days, with the brand family each post is about, kept in state/recent_posts.json
(committed by the cloud run), plus the queue files of this run. content_ranker lowers a candidate whose brand family
was posted in the last days, so the slots spread over many products instead of Google every time.
"""

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "state" / "recent_posts.json"
QUEUE_DIR = ROOT / "output" / "queue"
KEEP_DAYS = 14
WINDOW_DAYS = 3  # brands of the last 3 publish days count
PENALTY = 3  # ranker points off per recent post of the same brand family
MAX_PENALTY = 9

# brand families: Gemini, YouTube, Android, Workspace ... are all Google for the viewer's sense of "always the same"
BRANDS = [
    ("google", r"google|gemini|deepmind|android|youtube|workspace|gmail|chrome|pixel|notebooklm|\bveo\b|imagen|"
               r"\bflow\b|\bdocs\b|\bsheets\b"),
    ("openai", r"openai|chatgpt|\bsora\b|\bgpt"),
    ("anthropic", r"anthropic|claude"),
    ("microsoft", r"microsoft|copilot|windows|\bbing\b|github|\bedge\b|outlook|teams"),
    ("meta", r"\bmeta\b|llama|whatsapp|instagram|facebook"),
    ("apple", r"\bapple\b|iphone|\bsiri\b|macos|\bios\b|\bipad"),
    ("nvidia", r"nvidia|geforce"),
    ("samsung", r"samsung|galaxy"),
    ("amazon", r"amazon|alexa|\baws\b"),
    ("xai", r"\bxai\b|\bgrok\b"),
    ("mistral", r"mistral|\ble chat\b"),
    ("qwen", r"\bqwen|alibaba"),
    ("deepseek", r"deepseek"),
    ("elevenlabs", r"elevenlabs"),
    ("adobe", r"adobe|firefly|photoshop"),
]


def brand_of(*texts: str) -> str:
    text = " ".join(t for t in texts if t).lower()
    for name, pattern in BRANDS:
        if re.search(pattern, text):
            return name
    return ""


def _load() -> list[dict]:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def record(queue: list[dict], day: date) -> None:
    """The ready posts of one publish day (replacing that day's earlier record)."""
    rows = [r for r in _load() if r.get("day") != day.isoformat()
            and r.get("day", "") >= (day - timedelta(days=KEEP_DAYS)).isoformat()]
    rows += [{"day": day.isoformat(), "time": q.get("time", ""), "kind": q.get("kind", ""),
              "title": q.get("title", ""), "brand": brand_of(q.get("title", ""), q.get("company", ""))}
             for q in queue if q.get("status") == "ready"]
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


def recent(days: int = WINDOW_DAYS, today: date | None = None) -> list[dict]:
    """Posts of the last `days` publish days: the record plus this run's queue files (the day being made)."""
    since = ((today or date.today()) - timedelta(days=days)).isoformat()
    rows = {(r["day"], r.get("time", ""), r.get("title", "")): r for r in _load() if r.get("day", "") >= since}
    for f in sorted(QUEUE_DIR.glob("*.json")) if QUEUE_DIR.exists() else []:
        if f.stem < since:
            continue
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for q in items:
            if q.get("status") == "ready" and q.get("title"):
                rows[(f.stem, q.get("time", ""), q["title"])] = {
                    "day": f.stem, "time": q.get("time", ""), "kind": q.get("kind", ""), "title": q["title"],
                    "brand": brand_of(q["title"], q.get("company", ""))}
    return list(rows.values())


def brand_counts(days: int = WINDOW_DAYS, today: date | None = None) -> Counter:
    return Counter(r["brand"] for r in recent(days, today) if r.get("brand"))


def brand_penalty(brand: str, counts: Counter) -> int:
    return min(MAX_PENALTY, PENALTY * counts.get(brand, 0)) if brand else 0
