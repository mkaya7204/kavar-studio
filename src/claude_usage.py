"""How much of the Claude usage limit each step spends (D-48, the user 2026-10-23: measure first, then move the
cheap repeated steps to free open models; "haftalık token yetersiz kalır").

Every `claude -p --output-format json` call passes its stdout to `record(stage, stdout)`: one row per call in
state/claude_usage.jsonl (committed with the day's state by produce.yml; test runs are marked). `python daily.py
usage` prints the last 7 days per step. cost_usd is the CLI's API-price estimate: on the subscription nothing is
billed, but it is the best common measure of how much of the limit a call used.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "state" / "claude_usage.jsonl"


def record(stage: str, stdout: str) -> None:
    """One row for one call; never raises (measuring must not break production)."""
    try:
        out = json.loads(stdout)
        if not isinstance(out, dict):
            return
        usage = out.get("usage") or {}
        tokens = sum(int(usage.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                                       "cache_creation_input_tokens", "cache_read_input_tokens"))
        row = {"at": datetime.now().isoformat(timespec="seconds"), "stage": stage,
               "seconds": round((out.get("duration_ms") or 0) / 1000, 1), "turns": out.get("num_turns"),
               "tokens": tokens, "output_tokens": int(usage.get("output_tokens") or 0),
               "cost_usd": round(float(out.get("total_cost_usd") or 0), 4), "ok": not out.get("is_error"),
               "test": bool(os.getenv("KAVAR_DRY"))}
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:  # noqa: BLE001
        return


def summary(days: int = 7, log: Path | None = None) -> list[dict]:
    """Per step over the last `days`: calls, minutes, tokens, cost; the costliest first."""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    steps: dict[str, dict] = {}
    try:
        lines = (log or LOG).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("at", "") < since:
            continue
        s = steps.setdefault(r["stage"], {"stage": r["stage"], "calls": 0, "minutes": 0.0, "tokens": 0, "cost_usd": 0.0})
        s["calls"] += 1
        s["minutes"] += (r.get("seconds") or 0) / 60
        s["tokens"] += r.get("tokens") or 0
        s["cost_usd"] += r.get("cost_usd") or 0
    rows = sorted(steps.values(), key=lambda s: -s["cost_usd"])
    for s in rows:
        s["minutes"], s["cost_usd"] = round(s["minutes"], 1), round(s["cost_usd"], 2)
    return rows
