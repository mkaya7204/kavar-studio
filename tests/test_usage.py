"""D-48 (user 10-23: measure the Claude usage per step first, then move cheap steps to free open models)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CLI_OUT = json.dumps({"type": "result", "subtype": "success", "is_error": False, "duration_ms": 41200,
                      "num_turns": 3, "total_cost_usd": 0.1834,
                      "usage": {"input_tokens": 1200, "output_tokens": 800, "cache_creation_input_tokens": 9000,
                                "cache_read_input_tokens": 20000}})


def test_every_call_is_recorded_and_summed_per_step(monkeypatch, tmp_path):
    import claude_usage

    log = tmp_path / "usage.jsonl"
    monkeypatch.setattr(claude_usage, "LOG", log)
    claude_usage.record("editor", CLI_OUT)
    claude_usage.record("editor", CLI_OUT)
    claude_usage.record("agent", CLI_OUT.replace("0.1834", "1.5"))
    claude_usage.record("broken", "not json")  # never raises, never writes
    rows = claude_usage.summary(log=log)
    assert [r["stage"] for r in rows] == ["agent", "editor"]  # the costliest first
    editor = rows[1]
    assert editor["calls"] == 2 and editor["tokens"] == 2 * 31000 and editor["minutes"] == round(2 * 41.2 / 60, 1)


def test_every_claude_call_site_records_its_usage():
    for path in sorted((ROOT / "src").glob("*.py")):
        src = path.read_text(encoding="utf-8")
        if '"--output-format", "json"' in src:
            assert "record_usage(" in src, path.name
