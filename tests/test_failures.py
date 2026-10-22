"""D-39 (user 2026-10-22: "kendini geliştirip hataları düzeltip kendiliğinden doğrusunu yapamadıktan sonra
herşey boşuna bir çaba"): failures are data, and repeated ones change the next run by fixed rules."""

from datetime import date, timedelta

import failures

DAY = date(2026, 10, 22)


def test_failures_are_classified_from_real_texts():
    # editor problems and errors copied from the 10-21 / 10-22 logs
    assert failures.classify("Kanıt görseli vaadi göstermiyor: başlık ...") == ["no_proof"]
    assert "cut_text" in failures.classify("Kapak ve 0-5 sn kanıt kutusu soldan kesik: 'odo.is'")
    assert failures.classify("CaptureError: article has no cover image or too little text") == ["source_refused"]
    assert failures.classify("editor gave no verdict (success, is_error=True: limit)") == ["claude_empty"]
    assert failures.classify("something new") == ["other"]


def test_a_host_that_keeps_failing_is_skipped_for_a_week():
    for i in range(3):
        failures.record("news", "news", f"story {i}", "CaptureError: article has no cover image or too little text",
                        "https://openai.com/index/x", today=DAY - timedelta(days=i), rendered=False)
    lines = failures.react(DAY)
    assert any("openai.com" in line for line in lines)
    assert "openai.com" in failures.blocked_hosts(DAY)
    assert "openai.com" not in failures.blocked_hosts(DAY + timedelta(days=8))  # tried again after a week
    assert failures.react(DAY) == []  # an action is taken once, not every run


def test_a_reel_kind_that_keeps_being_rejected_is_paused_then_retried():
    for i in range(3):
        failures.record("reel", "tool", f"tool {i}", "Kanıt görseli vaadi göstermiyor", today=DAY - timedelta(days=i))
    lines = failures.react(DAY)
    assert failures.paused("tool", DAY) and "most often: no_proof" in lines[0]
    assert not failures.paused("tool", DAY + timedelta(days=8))
    assert not failures.paused("guide", DAY)


def test_a_kind_that_also_works_is_never_paused():
    for i in range(4):
        failures.record("reel", "guide", f"g {i}", "kesik metin", today=DAY - timedelta(days=i))
    failures.ok("reel", "guide", "Google", today=DAY - timedelta(days=1))
    failures.react(DAY)
    assert not failures.paused("guide", DAY)


def test_empty_mornings_never_pause_a_kind():
    """No candidate or no answer from Claude (10-22) is not the kind's fault: logged, never a pause."""
    for i in range(5):
        failures.record("reel", "guide", "-", "no company post fit", today=DAY - timedelta(days=i), rendered=False)
    failures.react(DAY)
    assert not failures.paused("guide", DAY)
    assert failures.summary(DAY)["guide"]["failed"] == 5


def test_old_failures_drop_out_of_the_window():
    for i in range(3):
        failures.record("reel", "trial", "t", "kanıt yok", today=DAY - timedelta(days=10 + i))
    assert failures.react(DAY) == [] and not failures.paused("trial", DAY)


def test_daily_records_a_rejected_reel_and_honours_a_pause(monkeypatch, tmp_path):
    import daily

    monkeypatch.setattr(daily, "LOG_DIR", tmp_path)
    failures.ACTIONS.parent.mkdir(parents=True, exist_ok=True)
    failures.ACTIONS.write_text('{"blocked_hosts": {}, "paused_kinds": {"guide": "2999-01-01"}}', encoding="utf-8")
    monkeypatch.setattr(daily, "_reel_attempt", lambda cmd=None: (_ for _ in ()).throw(AssertionError("ran")))
    assert daily.produce_guide_reel() is None  # paused: no Claude call, no render


def test_daily_writes_a_rejected_reel_into_the_ledger(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace

    import daily

    temp = tmp_path / "output" / "temp"
    temp.mkdir(parents=True)
    (tmp_path / "output" / "final").mkdir(parents=True)
    (temp / "script.json").write_text(json.dumps({"tool_name": "ToDo.is", "hook": "h"}), encoding="utf-8")
    (temp / "tool.json").write_text("{}", encoding="utf-8")
    for name, value in {"ROOT": tmp_path, "REELS_DIR": tmp_path / "reels", "LOG_DIR": tmp_path / "logs"}.items():
        monkeypatch.setattr(daily, name, value)
    monkeypatch.setattr(daily.subprocess, "run", lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=""))
    for name in ("log_reel", "update_metrics"):
        monkeypatch.setattr(daily, name, lambda *a, **k: None)
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "reject", "problems": ["'todo.is' 'odo.is' kesik"]})
    assert daily._reel_attempt() == (None, True)
    entry = failures.recent()[-1]
    assert (entry["kind"], entry["item"], entry["rendered"]) == ("tool", "ToDo.is", True)
    assert "cut_text" in entry["categories"]
