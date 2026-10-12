"""Reel results log: which hook pattern kept viewers, so the next scripts can learn from it.

state/metrics/reels.json holds one entry per produced Reel (written by daily.py), and the
Instagram numbers are filled in later (from Meta Business Suite / Insights):

    python -m reel_metrics list
    python -m reel_metrics update 2026-10-13_kodlo --views 340 --skip-rate 38 --avg-watch-pct 52 --sends 3
    python -m reel_metrics summary

(run from src/, or import). summary_for_prompt() is what the script writer sees.
"""

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "state" / "metrics" / "reels.json"
NUMBERS = ("views", "reach", "skip_rate", "avg_watch_pct", "avg_watch_sec", "sends", "saves", "likes",
           "follows")


def load() -> list[dict]:
    try:
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save(entries: list[dict]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def log_reel(reel_id: str, script: dict, duration_sec: float, kind: str = "tool") -> dict:
    """Add (or replace) the entry for a freshly produced Reel."""
    seg = script.get("voiceover_segments") or {}
    entry = {
        "id": reel_id,
        "date": date.today().isoformat(),
        "kind": kind,
        "tool": script.get("tool_name", ""),
        "hook_pattern": script.get("hook_pattern", ""),
        "headline": script.get("hook", ""),
        "spoken_hook": seg.get("hook", ""),
        "cta": seg.get("cta", ""),
        "duration_sec": duration_sec,
        "words": script.get("voiceover_words", 0),
        "status": "produced",
    }
    entries = [e for e in load() if e["id"] != reel_id] + [entry]
    save(entries)
    return entry


def update(reel_id: str, **fields) -> dict:
    entries = load()
    for e in entries:
        if e["id"] == reel_id:
            e.update({k: v for k, v in fields.items() if v is not None})
            if any(k in fields for k in NUMBERS):
                e["measured_at"] = date.today().isoformat()
            save(entries)
            return e
    raise KeyError(f"no Reel with id {reel_id!r} in {LOG_PATH}")


def by_pattern(entries: list[dict] | None = None) -> dict[str, dict]:
    """Average results per hook pattern, over Reels that have numbers."""
    out: dict[str, dict] = {}
    for e in entries if entries is not None else load():
        if e.get("views") is None:
            continue
        p = out.setdefault(e.get("hook_pattern") or "?", {"reels": 0, "views": 0, "skip": [], "watch": [],
                                                         "sends": 0})
        p["reels"] += 1
        p["views"] += e.get("views") or 0
        p["sends"] += e.get("sends") or 0
        if e.get("skip_rate") is not None:
            p["skip"].append(e["skip_rate"])
        if e.get("avg_watch_pct") is not None:
            p["watch"].append(e["avg_watch_pct"])
    for p in out.values():
        p["avg_skip_rate"] = round(sum(p["skip"]) / len(p["skip"]), 1) if p["skip"] else None
        p["avg_watch_pct"] = round(sum(p["watch"]) / len(p["watch"]), 1) if p["watch"] else None
        p["views_per_reel"] = round(p["views"] / p["reels"])
        del p["skip"], p["watch"]
    return out


def summary_for_prompt(min_reels: int = 3) -> str:
    """A few lines for the script writer, once there is enough measured data ("" before that)."""
    entries = [e for e in load() if e.get("views") is not None]
    if len(entries) < min_reels:
        return ""
    lines = [f"- {pat}: {s['reels']} Reels, {s['views_per_reel']} views/Reel, skip rate "
             f"{s['avg_skip_rate']}%, avg watch {s['avg_watch_pct']}%, {s['sends']} sends"
             for pat, s in sorted(by_pattern(entries).items(), key=lambda kv: -kv[1]["views_per_reel"])]
    best = sorted(entries, key=lambda e: -(e.get("views") or 0))[:3]
    lines += [f'- top Reel: "{e["headline"]}" / "{e["spoken_hook"]}" ({e["views"]} views)' for e in best]
    return ("Results of this page's earlier Reels by hook pattern (prefer what kept viewers, but keep "
            "trying other patterns now and then):\n" + "\n".join(lines))


def _main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("summary")
    up = sub.add_parser("update")
    up.add_argument("id")
    for name in NUMBERS:
        up.add_argument("--" + name.replace("_", "-"), type=float)
    up.add_argument("--permalink")
    up.add_argument("--status")
    args = ap.parse_args()
    if args.cmd == "list":
        for e in load():
            nums = ", ".join(f"{k}={e[k]}" for k in NUMBERS if e.get(k) is not None) or "no numbers yet"
            print(f"{e['id']:32} {e.get('hook_pattern', ''):10} {e['duration_sec']:>5}s  {nums}")
    elif args.cmd == "summary":
        print(json.dumps(by_pattern(), indent=2, ensure_ascii=False))
        print(summary_for_prompt(min_reels=1) or "(no measured Reels yet)")
    else:
        fields = {k: getattr(args, k) for k in (*NUMBERS, "permalink", "status")}
        print(json.dumps(update(args.id, **fields), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
