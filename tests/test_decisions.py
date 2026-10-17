"""§1.2, 1.6-1.9: editor gate numbers, voice, schedule, outro, brand (all user decisions)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_voice_is_george(monkeypatch):
    """User 2026-10-16: "ses iyi, onu kullan"."""
    import tts_engine

    assert tts_engine.ELEVENLABS_VOICE == "JBFqnCBsd6RMkjVDRZzb"
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["tts_providers"][0] == "elevenlabs"


def test_schedule_slots():
    """User 2026-10-16: two Reels a day, 11:45 and 20:30 ("bunu artık standart hale getirelim")."""
    slots = json.loads((ROOT / "schedule.json").read_text(encoding="utf-8"))["slots"]
    assert [(s["time"], s["kind"]) for s in slots] == [("11:45", "reel"), ("12:30", "carousel"), ("18:00", "carousel"),
                                                          ("20:30", "reel")]


def test_brand_handle():
    assert json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))["handle"] == "@thekavar.ai"


def test_editor_gate_numbers():
    import daily

    assert daily.FIX_ROUNDS == 2
    assert daily.REEL_ATTEMPTS == 3


def test_reel_outro_keeps_handle_and_follow_pill():
    """Removed once without asking (2026-10-14); brought back in 11dcfdc."""
    import hyperframes_builder

    html = (ROOT / "templates" / "hyperframes_news" / "index.html").read_text(encoding="utf-8")
    for needle in ('id="outro-follow"', 'id="outro-handle"', 'id="outro-follow-label"', 'tl.fromTo("#outro-follow"'):
        assert needle in html, needle
    assert hyperframes_builder.LABELS["tr"]["follow_label"] == "TAKİP ET"


def test_editor_rejects_when_it_cannot_review(monkeypatch, tmp_path):
    """No editor = nothing goes out."""
    import editor_review

    monkeypatch.setattr(editor_review, "_claude_cli", lambda: None)
    assert editor_review._ask(tmp_path, "x")["verdict"] == "reject"


def test_editor_fix_rounds(monkeypatch, tmp_path):
    import daily

    verdicts = iter([{"verdict": "fix", "problems": [], "fixes": [{"slide": 1, "title": "a", "body": ""}]},
                     {"verdict": "fix", "problems": [], "fixes": [{"slide": 1, "title": "a", "body": ""}]},
                     {"verdict": "fix", "problems": [], "fixes": [{"slide": 1, "title": "a", "body": ""}]}])
    monkeypatch.setattr(daily, "review_carousel", lambda folder: next(verdicts))
    monkeypatch.setattr(daily, "_apply_fixes", lambda folder, fixes: True)
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path)
    ok, _ = daily._reviewed_news(tmp_path)
    assert ok is False  # still "fix" after 2 rounds: not published


def test_only_george_ever_speaks(monkeypatch):
    """Audit 2026-10-16: a quota error fell through to edge-tts (another voice); an env var could override George."""
    import tts_engine

    monkeypatch.setenv("ELEVENLABS_API_KEY", "x")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "someone-else")
    assert tts_engine.available_providers() == ["elevenlabs"]
    assert tts_engine._voice_label("elevenlabs", "tr-TR-AhmetNeural") == "elevenlabs:JBFqnCBsd6RMkjVDRZzb"
    assert "ELEVENLABS_VOICE_ID" not in (ROOT / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")


def test_second_elevenlabs_account_takes_over_with_george(monkeypatch, tmp_path):
    """D-23/D-26: when the first account's quota is gone, the second key is used, same George voice."""
    import tts_engine

    calls = []

    class Resp:
        def __init__(self, code):
            self.status_code, self.text = code, "quota_exceeded" if code == 401 else ""

        def json(self):
            return {"audio_base64": "", "alignment": {}}

    def post(url, headers, **kw):
        calls.append((url, headers["xi-api-key"]))
        return Resp(401 if headers["xi-api-key"] == "first" else 200)

    monkeypatch.setenv("ELEVENLABS_API_KEY", "first")
    monkeypatch.setenv("ELEVENLABS_API_KEY_2", "second")
    monkeypatch.setattr(tts_engine.requests, "post", post)
    tts_engine._elevenlabs_sync("merhaba", 0, tmp_path / "a.mp3")
    assert [k for _, k in calls] == ["first", "second"]
    assert all("JBFqnCBsd6RMkjVDRZzb" in u for u, _ in calls)

    monkeypatch.delenv("ELEVENLABS_API_KEY")  # only the second account set: still ElevenLabs
    assert tts_engine.available_providers() == ["elevenlabs"]
    for wf in ("produce.yml", "news-test.yml", "rerender.yml", "trial-rerender.yml"):
        assert "secrets.ELEVENLABS_API_KEY_2" in (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")


def test_voice_length_is_capped_before_spending_quota():
    import tts_engine

    assert tts_engine.MAX_SECONDS <= 24


def test_decision_log_exists_and_claude_md_points_to_it():
    """User 2026-10-16: every decision is written down (DECISIONS.md)."""
    log = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    assert "D-01" in log and "No prices" in log
    assert "DECISIONS.md" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_editor_knows_the_agreed_opening_and_cover():
    """User 2026-10-16: "Bunları editör de biliyor mu, sonra çakışma olmasın"."""
    import editor_review

    assert "KAVAR denemesi" in editor_review.REEL_RULES and "D-17" in editor_review.REEL_RULES
    assert "KAYDIR" in editor_review.SYSTEM and "3-6" in editor_review.SYSTEM


def test_hook_subject_rule_is_loaded():
    """D-10: the model / tool is the clear subject of the headline."""
    import script_writer

    assert "Clear subject" in script_writer.SYSTEM_PROMPT


def test_reel_editor_sees_the_middle_frame_and_one_second_later(monkeypatch, tmp_path):
    """10-17: the single middle frame fell on card 2's entrance (Ultracite), so the editor called it empty."""
    import editor_review

    seen = {}
    monkeypatch.setattr(editor_review, "first_frame_report", lambda v, f: {"ok": True})
    monkeypatch.setattr(editor_review, "pacing_report", lambda v: {"duration_sec": 24.0})
    monkeypatch.setattr(editor_review, "video_frames", lambda v, f, times: seen.setdefault("times", times) and [])
    monkeypatch.setattr(editor_review, "contact_sheet", lambda imgs, out, **kw: out)
    monkeypatch.setattr(editor_review, "make_cover", lambda v, f: {"grid": str(f / "g.jpg")})
    monkeypatch.setattr(editor_review, "_ask", lambda folder, msg: {"verdict": "publish", "problems": [], "fixes": []})
    editor_review.review_reel(tmp_path / "v.mp4", {}, {})
    assert 12.0 in seen["times"] and 13.0 in seen["times"]


def test_cards_must_match_the_voice_under_them():
    """10-17: Ultracite's card 2 said "preset" while the voice said "consistent code" (point1 covered two cards)."""
    from script_writer import VideoScript, card_voice_mismatch, reel_rule_problems

    def load(name):
        return VideoScript.model_validate(json.loads((ROOT / "rerender" / name).read_text(encoding="utf-8")))

    bad = load("2026-10-17_ultracite-v8.json")
    assert card_voice_mismatch(bad) == [2, 3]
    assert any("don't match the voiceover" in p for p in reel_rule_problems(bad))
    for good in ("2026-10-17_train-with-pasta.json", "2026-10-17_craft-agents.json", "2026-10-15_retriever-ai.json"):
        assert card_voice_mismatch(load(good)) == [], good
