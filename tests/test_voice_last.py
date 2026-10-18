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
    assert all(draft == "1" for _, draft in calls)  # the attempt and its fixes: draft voice only
    assert not any("src/voice_final.py" in cmd for cmd, _ in calls)


def test_a_rejected_draft_is_fixed_and_reviewed_again(monkeypatch, reel_sandbox):
    """D-33 (the user, 2026-10-18): "editör red derse sen devreye giriyorsun, düzeltilecek bir yanı varsa
    düzelt" - the rejected draft goes to src/reel_fixer.py, silently, and back to the editor."""
    daily, calls = reel_sandbox
    verdicts = iter([{"verdict": "reject", "problems": ["kanıt görseli vaadi göstermiyor"]},
                     {"verdict": "publish", "problems": []}])
    monkeypatch.setattr(daily, "review_reel", lambda *a: next(verdicts))
    item, rendered = daily._reel_attempt()
    assert item and rendered
    cmds = [cmd for cmd, _ in calls]
    assert "src/reel_fixer.py" in cmds[1] and calls[1][1] == "1"  # the fix: still silent
    assert "src/voice_final.py" in cmds[2]  # George only after the fixed draft is approved
    assert json.loads((daily.REELS_DIR / next(daily.REELS_DIR.iterdir()).name / "_verdict.json")
                      .read_text(encoding="utf-8"))["problems"] == ["kanıt görseli vaadi göstermiyor"]


def test_an_unfixable_topic_moves_on_without_more_fixes(monkeypatch, reel_sandbox):
    daily, calls = reel_sandbox
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "reject", "problems": ["yapay zekâ değil"]})
    real_run = daily.subprocess.run
    monkeypatch.setattr(daily.subprocess, "run", lambda cmd, **kw: SimpleNamespace(
        returncode=3, stdout="✖ not fixable: no AI", stderr="") if "src/reel_fixer.py" in cmd else real_run(cmd, **kw))
    assert daily._reel_attempt() == (None, True)


def test_the_fixer_keeps_the_script_rules():
    import reel_fixer

    script = json.loads((ROOT / "rerender" / "2026-10-17_craft-agents.json").read_text(encoding="utf-8"))
    seg = script["voiceover_segments"]
    answer = {"hook": script["hook"], "segments": seg, "why_it_matters": script["why_it_matters"],
              "key_points": script["key_points"], "caption": script["caption"], "hashtags": script["hashtags"]}
    fixed = reel_fixer.apply_text(script, answer)
    assert fixed["voiceover"].startswith(seg["hook"].strip()) and fixed["voiceover_segments"] == seg
    assert reel_fixer.text_problems(fixed) == []  # an unchanged, valid script passes (40 words: the writers' limit)
    long = reel_fixer.apply_text(script, {**answer, "segments": {**seg, "point2": "kelime " * 40}})
    assert any("max 42" in p for p in reel_fixer.text_problems(long))
    assert reel_fixer.candidates({"pictures_locked": True}) == []  # "Biz denedik": our outputs stay


def test_the_fixer_sees_the_whole_page_of_a_tool(tmp_path, monkeypatch):
    """10-18: the fixer saw one picture of Inbox Zero's site and gave up; a tall page gives many windows."""
    import reel_fixer
    from PIL import Image, ImageDraw

    page = Image.new("RGB", (540, 4000), "white")
    draw = ImageDraw.Draw(page)
    for y in range(0, 4000, 40):
        draw.line((0, y, 540, y + 20), fill="black", width=3)
    page.save(tmp_path / "fullpage.png")
    monkeypatch.setattr(reel_fixer, "WORK", tmp_path / "fix")
    found = reel_fixer.candidates({"fullpage_path": str(tmp_path / "fullpage.png")})
    assert 6 <= len(found) <= reel_fixer.MAX_CANDIDATES and all(p.exists() for p in found)


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
