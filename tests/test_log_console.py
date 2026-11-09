"""11-09: `daily.py fetch` crashed half way on a Windows cp1254 console printing the title
"GPT‑6 Cyber" (non-breaking hyphen U+2011). The log line must print and the log file keep the real text."""
import io
import sys

import daily


def test_log_survives_a_console_that_cannot_print_the_title(tmp_path, monkeypatch):
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path)
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1254", errors="strict")
    monkeypatch.setattr(sys, "stdout", console)
    title = "GPT‑6 Cyber: Advancing the frontier of aligned cybersecurity agents"
    daily.log(f"   3. 12:30 carousel ready     {title}")
    console.flush()
    assert b"Cyber" in raw.getvalue()
    written = next(tmp_path.glob("*.log")).read_text(encoding="utf-8")
    assert title in written
