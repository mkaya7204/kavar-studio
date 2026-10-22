"""The failure ledger and its automatic reactions (D-39, user 2026-10-22: "kendini geliştirip hataları
düzeltip kendiliğinden doğrusunu yapamadıktan sonra herşey boşuna bir çaba").

Before D-39 a failure was free text in the day log: nothing counted it, so the same fault came back
(18 Reels rejected for a missing proof; the system tried the same kind of site the 18th time). Now:

1. record() keeps every failure as data in state/failures.json (committed by the cloud run): date,
   stage (news / reel), kind (news, guide, trial, tool), item, host, categories (classify()).
2. react() reads the last WINDOW_DAYS and changes behaviour by fixed rules, never by a guess:
   - a news host that failed REPEAT times is skipped for WINDOW_DAYS (state/self_correct.json);
   - a Reel kind with REPEAT rendered-and-rejected drafts and no approval is paused for WINDOW_DAYS,
     then tried again (a morning with no candidate or no answer from Claude never pauses a kind).
   Every change is logged ("self-correct: ...") and listed for the user in the morning report.
3. Approvals are recorded too (ok()), so a kind that works is never paused.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "state" / "failures.json"
ACTIONS = ROOT / "state" / "self_correct.json"
WINDOW_DAYS = 7
REPEAT = 3
KEEP_DAYS = 60

# first match wins per category; a failure can carry several categories (a rejection lists many problems)
CATEGORIES = [
    ("claude_empty", r"returned no |gave no verdict|no ranking from Claude|no choice from Claude"),
    ("no_proof", r"kanıt|proof|vaadi göstermiyor|slogan|maskot|no product screens|no clean proof"),
    ("cut_text", r"kesik|kırp|yarım|cut off|truncat"),
    ("source_refused", r"HTTP (401|403|429)|refuses this machine|no cover image or too little text"),
    ("off_concept", r"off-concept|yapay zekâ değil|not about AI|no company post fit|No candidate"),
    ("facts", r"kaynakta (yok|olmayan)|desteklenmiyor|not in the source|abartı"),
    ("price", r"fiyat|price|ücretsiz|bedava"),
    ("voice", r"ElevenLabs|no voice|voiced"),
    ("timeout", r"timed out"),
]


def classify(text: str) -> list[str]:
    found = [name for name, pattern in CATEGORIES if re.search(pattern, text or "", re.IGNORECASE)]
    return found or ["other"]


def _load(path: Path, empty):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def _entry(stage: str, kind: str, item: str, url: str, outcome: str, text: str, today: date,
           rendered: bool = True) -> dict:
    return {"date": today.isoformat(), "stage": stage, "kind": kind, "item": item[:120], "rendered": rendered,
            "host": (urlsplit(url).hostname or "").removeprefix("www.") if url else "",
            "outcome": outcome, "categories": classify(text) if outcome == "failed" else [],
            "detail": (text or "")[:300]}


def _append(entry: dict, today: date) -> None:
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    _save(LEDGER, [e for e in _load(LEDGER, []) if e["date"] >= cutoff] + [entry])


def record(stage: str, kind: str, item: str, reason: str, url: str = "", today: date | None = None,
           rendered: bool = True) -> dict:
    """A failure: `reason` is the error or the editor's problems, joined. rendered=False: nothing was made
    (no candidate, Claude gave nothing); it is kept and counted, but never pauses a kind."""
    entry = _entry(stage, kind, item, url, "failed", reason, today or date.today(), rendered)
    _append(entry, today or date.today())
    return entry


def ok(stage: str, kind: str, item: str, url: str = "", today: date | None = None) -> None:
    """An approval: a kind that works is never paused."""
    _append(_entry(stage, kind, item, url, "approved", "", today or date.today()), today or date.today())


def recent(today: date | None = None) -> list[dict]:
    since = ((today or date.today()) - timedelta(days=WINDOW_DAYS)).isoformat()
    return [e for e in _load(LEDGER, []) if e["date"] >= since]


def react(today: date | None = None) -> list[str]:
    """Apply the rules to the last WINDOW_DAYS; returns the new actions as lines for the log."""
    today = today or date.today()
    entries = recent(today)
    actions = _load(ACTIONS, {"blocked_hosts": {}, "paused_kinds": {}})
    until = (today + timedelta(days=WINDOW_DAYS)).isoformat()
    lines = []
    hosts: dict[str, int] = {}
    for e in entries:
        if e["stage"] == "news" and e["outcome"] == "failed" and e["host"] and "source_refused" in e["categories"]:
            hosts[e["host"]] = hosts.get(e["host"], 0) + 1
    for host, n in hosts.items():
        if n >= REPEAT and actions["blocked_hosts"].get(host, "") < today.isoformat():
            actions["blocked_hosts"][host] = until
            lines.append(f"news from {host} skipped until {until}: refused or unreadable {n} times in {WINDOW_DAYS} days")
    for kind in ("guide", "trial", "tool"):
        mine = [e for e in entries if e["stage"] == "reel" and e["kind"] == kind]
        failed = [e for e in mine if e["outcome"] == "failed" and e.get("rendered", True)]
        if len(failed) >= REPEAT and not any(e["outcome"] == "approved" for e in mine) \
                and actions["paused_kinds"].get(kind, "") < today.isoformat():
            actions["paused_kinds"][kind] = until
            top = max({c for e in failed for c in e["categories"]},
                      key=lambda c: sum(c in e["categories"] for e in failed))
            lines.append(f"{kind} Reels paused until {until}: {len(failed)} failures and no approval in "
                         f"{WINDOW_DAYS} days (most often: {top})")
    _save(ACTIONS, actions)
    return lines


def blocked_hosts(today: date | None = None) -> set[str]:
    now = (today or date.today()).isoformat()
    return {h for h, until in _load(ACTIONS, {}).get("blocked_hosts", {}).items() if until >= now}


def paused(kind: str, today: date | None = None) -> bool:
    return _load(ACTIONS, {}).get("paused_kinds", {}).get(kind, "") >= (today or date.today()).isoformat()


def summary(today: date | None = None) -> dict:
    """Counts of the last WINDOW_DAYS for the morning report: per kind approved / failed, top categories."""
    out: dict = {}
    for e in recent(today):
        k = out.setdefault(e["kind"], {"approved": 0, "failed": 0, "categories": {}})
        k[e["outcome"]] += 1
        for c in e["categories"]:
            k["categories"][c] = k["categories"].get(c, 0) + 1
    return out
