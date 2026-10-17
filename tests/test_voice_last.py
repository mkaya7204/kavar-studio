"""D-30 (the user, 2026-10-18): "her denemede ses kullanma; önce reel doğru yaptıktan sonra editör onay
verince ses kullan". Attempts are built on a silent draft voice; only the approved Reel is voiced."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def reel_sandbox(monkeypatch, tmp_path):
    import daily

    temp = tmp_path / "output" / "temp"
    final = tmp_path / "output" / "final"
    temp.mkdir(parents=True)
    final.mkdir(parents=True)
    (temp / "script.json").write_text(json.dumps({"tool_name": "Tool", "hook": "h"}), encoding="utf-8")
    (temp / "tool.json").write_text("{}", encoding="utf-8")
    calls = []

    def run(cmd, **kw):
        calls.append((cmd, (kw.get("env") or {}).get("KAVAR_DRAFT_VOICE")))
        (final / "final_video.mp4").write_bytes(b"v")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "REELS_DIR", tmp_path / "reels")
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(daily.subprocess, "run", run)
    monkeypatch.setattr(daily, "log_reel", lambda *a, **k: None)
    monkeypatch.setattr(daily, "update_metrics", lambda *a, **k: None)
    monkeypatch.setattr(daily, "make_cover", lambda v, o: {})
    monkeypatch.setattr(daily, "first_frame_report", lambda v, o: {"ok": True})
    monkeypatch.setattr(daily, "pacing_report", lambda v: {"duration_sec": 22.0})
    return daily, calls


def test_attempt_is_silent_and_only_the_approved_reel_is_voiced(monkeypatch, reel_sandbox):
    daily, calls = reel_sandbox
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "publish", "problems": []})
    item, rendered = daily._reel_attempt(["python", "src/guide_reel.py"])
    assert item and rendered
    assert calls[0][1] == "1"  # the attempt: draft voice, no credits
    assert "src/voice_final.py" in calls[1][0] and calls[1][1] is None  # George, once, after approval
    assert len(calls) == 2


def test_a_rejected_draft_spends_no_voice(monkeypatch, reel_sandbox):
    daily, calls = reel_sandbox
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "reject", "problems": ["x"]})
    item, rendered = daily._reel_attempt()
    assert item is None and rendered
    assert len(calls) == 1 and calls[0][1] == "1"


def test_no_voice_means_no_reel_and_no_more_attempts(monkeypatch, reel_sandbox):
    """CLAUDE.md §1.6: if both ElevenLabs accounts fail, no Reel is made."""
    daily, calls = reel_sandbox
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "publish", "problems": []})
    real_run = daily.subprocess.run
    monkeypatch.setattr(daily.subprocess, "run", lambda cmd, **kw: SimpleNamespace(returncode=2, stdout="✖ no voice")
                        if "src/voice_final.py" in cmd else real_run(cmd, **kw))
    assert daily._reel_attempt() == (None, False)


def test_draft_timings_follow_georges_pace_and_length_cap():
    import tts_engine

    text = "Üniversite hocalarından yapay zekâ dersi ister misin? " * 3
    words = tts_engine.draft_words(text)
    assert len(words) == len(text.split()) and words[-1]["end"] <= tts_engine.MAX_SECONDS
    with pytest.raises(tts_engine.TTSError):
        tts_engine.draft_words(text * 4)  # too long even with the speed-up: shorten, like the real voice


def test_the_pipelines_never_call_the_paid_voice_directly():
    for path in ("main.py", "src/trial_reel.py", "src/guide_reel.py"):
        src = (ROOT / path).read_text(encoding="utf-8")
        assert "reel_voice(" in src and "synthesize(" not in src, path
