"""Which candidate reaches more people: the selection step for every slot (D-29, user 2026-10-17:
"hangi haberin daha fazla kitleye hitap ettiği, ilgi çekici olması ... daha akıllı seçim").

The slot concepts don't change here; this only orders the candidates INSIDE a slot's concept.
One Claude call scores each candidate on:
  audience    how many Turkish internet users it touches (products they know and use: ChatGPT,
              Gemini, WhatsApp, iPhone, Android...; everyday life, work, school)
  interest    would a stranger stop scrolling: new, surprising, "bunu duymalıyım"
  clarity     can it be told simply in Turkish, without jargon
  usefulness  can the reader do or try something because of it
and flags what doesn't fit the slot's concept or repeats a post of the last 3 days.
Our own numbers feed back in: categories that did better on our page get a small bonus.
"Biz denedik" stays first (locked, CLAUDE.md §1.4): tested candidates are never moved down.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "state" / "metrics" / "posts.json"

CATEGORIES = ("everyday_ai_product", "model_release", "ai_tool", "research_science", "enterprise_customer",
              "chips_infrastructure", "gaming_hardware", "policy_business", "turkey_tech")
Category = Literal["everyday_ai_product", "model_release", "ai_tool", "research_science", "enterprise_customer",
                   "chips_infrastructure", "gaming_hardware", "policy_business", "turkey_tech"]

CONCEPTS = {
    "news_carousel": "12:30 / 18:00 news carousel: a fresh AI news story, explained for Turkish readers (what "
                     "happened, why it matters to them). The sources are companies' own blogs; a company's post "
                     "on the Hugging Face blog counts as its own. Off concept: gaming or hardware promotions, "
                     "launch events, sales, and stories with no AI in them.",
    "tool_reel": "11:45 tool Reel: one AI tool a Turkish viewer could use today, shown working.",
    "guide_reel": "07:30 guide Reel (D-31): a feature of a known AI product (ChatGPT, Gemini, Claude, Copilot, "
                  "YouTube, Android, WhatsApp, Google Search, Workspace...) that a Turkish viewer can use today, "
                  "and how to use it right: where it is, what to ask, which mode fits which job. Off concept: "
                  "research papers, company or business news, partnerships, events, chips and data centres, "
                  "enterprise-only or developer-only APIs, anything the viewer cannot try themselves.",
}

SYSTEM = """You choose content for KAVAR (@thekavar.ai), a Turkish Instagram page about AI. The page \
grows only if people who don't follow it yet stop, watch, save and send the post to a friend. \
You get the slot's concept and a numbered list of candidates. Score every candidate 0-5:
- audience: how many Turkish internet users it touches. 5 = products most Turks use or know \
(ChatGPT, Gemini, WhatsApp, Instagram, YouTube, iPhone, Android, Google Search) or everyday life, \
school and work; 1 = only specialists (chip design, data centres, enterprise back offices, a foreign \
bank's internal project, gaming hardware promotions).
- interest: would a stranger stop scrolling (new, surprising, a clear "vay" or "bunu duymalıyım").
- clarity: can it be told simply in Turkish in a few sentences without jargon.
- usefulness: can the reader do or try something because of it.
fits_concept false if it doesn't belong to the slot's concept. repeats_recent true if it is the same \
story or product as one of the page's recent posts (listed). company: the main company or institution. \
category: one of the listed values. reason: one short English sentence. Judge only from the titles \
and summaries; don't invent facts."""


class Scores(BaseModel):
    class Item(BaseModel):
        index: int
        company: str
        category: Category
        audience: int
        interest: int
        clarity: int
        usefulness: int
        fits_concept: bool
        repeats_recent: bool
        reason: str

    items: list[Item]


def recent_titles(days: int = 3) -> list[str]:
    """Titles of the page's posts of the last few days (state/metrics/posts.json)."""
    try:
        rows = json.loads(METRICS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return [r["title"] for r in rows if r.get("published", "") >= since and r.get("title")]


def category_bonus(kind_prefix: str) -> dict[str, int]:
    """-2..+2 per category from our own reach: a category with 3+ posts that reached more than the
    page's average for that format gets a bonus. Small on purpose: the data is young."""
    try:
        rows = [r for r in json.loads(METRICS.read_text(encoding="utf-8"))
                if r.get("kind", "").endswith(kind_prefix) and isinstance(r.get("reach"), (int, float))]
    except (OSError, json.JSONDecodeError):
        return {}
    if len(rows) < 6:
        return {}
    overall = sum(r["reach"] for r in rows) / len(rows)
    out = {}
    for cat in CATEGORIES:
        mine = [r["reach"] for r in rows if r.get("category") == cat]
        if len(mine) >= 3:
            out[cat] = max(-2, min(2, round(2 * (sum(mine) / len(mine) / overall - 1))))
    return out


def score(item: dict, bonus: dict[str, int]) -> int:
    s = 3 * item["audience"] + 2 * item["interest"] + item["clarity"] + 2 * item["usefulness"]
    return s + bonus.get(item["category"], 0)


def rank(candidates: list[dict], concept: str, kind_prefix: str = "carousel") -> list[dict]:
    """Candidates in the order to try, each with a "rank" dict (score, category, company, reason).
    Off-concept and recent repeats go last; tested ("Biz denedik") candidates stay first in their order.
    The input order is kept if the call fails."""
    from carousel_writer import _ask

    if len(candidates) < 2:
        return candidates
    recent = recent_titles()
    listing = "\n".join(f"{i}. [{c.get('source', '')}] {c['title']} - {str(c.get('summary', ''))[:300]}"
                        for i, c in enumerate(candidates))
    prompt = (f"Slot concept: {CONCEPTS[concept]}\n\nThe page's posts of the last 3 days:\n"
              + ("\n".join(f"- {t}" for t in recent) or "- none") + f"\n\nCandidates:\n{listing}")
    try:
        draft, _, _ = _ask(prompt, SYSTEM, Scores)
        items = Scores(**draft).items if draft else []
    except Exception as exc:  # noqa: BLE001  ranking is an improvement, never a reason to stop
        print(f"[ranker] failed: {type(exc).__name__}: {str(exc)[:200]}")
        return candidates
    bonus = category_bonus(kind_prefix)
    by_index = {it.index: it.model_dump() for it in items if 0 <= it.index < len(candidates)}
    out = []
    for i, c in enumerate(candidates):
        it = by_index.get(i)
        if it:
            c = {**c, "rank": {"score": score(it, bonus), "category": it["category"], "company": it["company"],
                               "reason": it["reason"], "fits": it["fits_concept"], "repeat": it["repeats_recent"]}}
        out.append(c)

    def key(c):
        r = c.get("rank") or {}
        demoted = (not r.get("fits", True)) or r.get("repeat", False)
        return (not c.get("testable"), demoted, -r.get("score", 0))

    return sorted(out, key=key)  # sorted() is stable: unscored candidates keep their place among equals
