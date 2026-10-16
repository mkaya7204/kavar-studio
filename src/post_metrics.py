"""What every published post did on Instagram: the page's only feedback loop (audit 2026-10-16).

state/metrics/posts.json holds one row per published post, carousels AND Reels. Until the
Instagram API token exists, Claude copies the numbers from Meta Business Suite (Content ->
Published, the table with Reach / Views / Follows / Shares / Saves / Watch time) during every
morning "yükle", for the posts that are at least one day old:

    python src/post_metrics.py add rows.json     # rows: [{"published": "2026-10-15 21:22", "kind": "reel", ...}]
    python src/post_metrics.py summary           # per format: posts, mean reach / views / avg watch / follows

A row is keyed by its publish time and kind; adding it again updates the numbers.
"""

import json
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "state" / "metrics" / "posts.json"
KINDS = ("reel", "trial_reel", "carousel", "trial_carousel", "story")
NUMBERS = ("reach", "views", "follows", "likes", "comments", "shares", "saves", "avg_watch_sec", "skip_rate")


def load() -> list[dict]:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def add(rows: list[dict]) -> list[dict]:
    """Merge rows (by published + kind); unknown kinds or non-numeric numbers are refused."""
    entries = {(e["published"], e["kind"]): e for e in load()}
    for r in rows:
        if r.get("kind") not in KINDS or not r.get("published"):
            raise ValueError(f"row needs published and kind in {KINDS}: {r}")
        for k in NUMBERS:
            if k in r and r[k] is not None and not isinstance(r[k], (int, float)):
                raise ValueError(f"{k} must be a number: {r}")
        key = (r["published"], r["kind"])
        entries[key] = {**entries.get(key, {}), **r}
    out = sorted(entries.values(), key=lambda e: e["published"])
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def summary(entries: list[dict] | None = None) -> dict:
    by_kind: dict[str, dict] = {}
    for kind in KINDS:
        rows = [e for e in (entries if entries is not None else load()) if e["kind"] == kind]
        if not rows:
            continue
        by_kind[kind] = {"posts": len(rows)} | {
            k: round(mean(v), 1) for k in ("reach", "views", "avg_watch_sec", "follows", "shares", "saves")
            if (v := [r[k] for r in rows if isinstance(r.get(k), (int, float))])}
    return by_kind


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "add":
        add(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    print(json.dumps(summary(), indent=2, ensure_ascii=False))
