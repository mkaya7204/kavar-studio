"""11-19 run 44450359526: after "You've hit your weekly limit" the run made 36 more Claude calls, all failed, and
the failures were filed as empty / off-concept. The limit answer is noticed, the run stops trying, and it is filed as
claude_limit."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import claude_usage  # noqa: E402
import failures  # noqa: E402

LIMIT = json.dumps({"is_error": True, "result": "You've hit your weekly limit · resets 1pm (Europe/Istanbul)",
                    "usage": {}, "total_cost_usd": 0})


def test_the_limit_answer_is_kept_for_the_run(monkeypatch, tmp_path):
    monkeypatch.setattr(claude_usage, "LOG", tmp_path / "u.jsonl")
    monkeypatch.setattr(claude_usage, "LIMIT_FLAG", tmp_path / "limit.json")
    assert claude_usage.limit_reached() == ""
    claude_usage.record("editor", json.dumps({"is_error": True, "result": "some other error"}))
    assert claude_usage.limit_reached() == ""
    claude_usage.record("editor", LIMIT)
    assert "weekly limit" in claude_usage.limit_reached()
    assert claude_usage.limit_reached(datetime.now() + timedelta(hours=7)) == ""  # a later run is not stopped


def test_every_retry_loop_stops_after_the_limit():
    src = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert src.count("if _claude_limit():") >= 4


def test_a_limit_failure_is_filed_as_such():
    assert "claude_limit" in failures.classify("claude -p returned no carousel (You've hit your weekly limit)")
