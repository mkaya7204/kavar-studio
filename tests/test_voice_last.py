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


def test_a_rejected_draft_is_not_sent_to_the_fixer(monkeypatch, reel_sandbox):
    """D-38 (user 2026-10-22) switched D-33 off: the fixer cropped the proof picture (cut text in 12 of 14 fix
    rounds, 10-19..10-21). A rejected draft is rejected; no fixer run, no voice."""
    daily, calls = reel_sandbox
    assert daily.REEL_FIX_ROUNDS == 0
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "reject", "problems": ["kanıt yok"]})
    assert daily._reel_attempt() == (None, True)
    assert not any("src/reel_fixer.py" in cmd or "src/voice_final.py" in cmd for cmd, _ in calls)


def test_the_fixer_never_crops_a_picture(tmp_path, monkeypatch):
    """D-36/D-38: ImageOps.fit cut 'todo.is' to 'odo.is' (10-21). A wide picture keeps its edges, whole."""
    import reel_fixer
    from PIL import Image, ImageDraw

    from hyperframes_builder import PROOF_SIZE

    wide = Image.new("RGB", (1600, 900), "white")
    draw = ImageDraw.Draw(wide)
    draw.rectangle((0, 0, 19, 899), fill=(255, 0, 0))  # left edge
    draw.rectangle((1580, 0, 1599, 899), fill=(0, 0, 255))  # right edge
    wide.save(tmp_path / "wide.png")
    monkeypatch.setattr(reel_fixer, "TEMP_DIR", tmp_path)
    cap = reel_fixer.apply_pictures({"proof_path": str(tmp_path / "proof.png")}, [tmp_path / "wide.png"], 0, [])
    with Image.open(cap["proof_path"]) as proof:
        assert proof.size == PROOF_SIZE
        row = [proof.getpixel((x, PROOF_SIZE[1] // 2)) for x in range(PROOF_SIZE[0])]
        assert any(p[0] > 200 and p[1] < 80 for p in row) and any(p[2] > 200 and p[0] < 80 for p in row)  # both edges
        assert proof.getpixel((PROOF_SIZE[0] // 2, 3)) == (10, 16, 32)  # letterboxed, not cropped


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


def test_george_hears_names_the_turkish_way_and_captions_keep_the_spelling():
    """D-34 (the user, 2026-10-18): "gemini yazıldığı gibi okuyor ... AI isimlerini de yazıyla nasıl yazıldıysa
    öyle okuyor" - the 11:45 Reel was deleted for it."""
    import tts_engine

    text = "Gemini'de görevler var. ChatGPT, Claude ve Copilot da öyle; iPhone'da Google Gemini."
    said = tts_engine.spoken_text(text)
    assert said == "Cemini'de görevler var. Çetcipiti, Klod ve Kopaylıt da öyle; Ayfon'da Gugıl Cemini."
    assert len(said.split()) == len(text.split())  # one word for one word: the timings map back
    assert tts_engine.spoken_text("Gemicilik ve Googleplex") == "Gemicilik ve Googleplex"  # whole words only
    lex = tts_engine._lexicon()
    assert all(len(v.split()) == 1 for v in lex.values())  # never two words for one
    timed = [{"word": w.strip(".,;"), "start": i, "end": i + 0.5} for i, w in enumerate(said.split())]
    shown = tts_engine.written_words(timed, text)
    assert [w["word"] for w in shown][:3] == ["Gemini'de", "görevler", "var"] and shown[3]["word"] == "ChatGPT"
    assert shown[5]["start"] == 5  # timings unchanged


def test_any_new_name_is_learned_before_george_speaks(monkeypatch, tmp_path):
    """D-34, made permanent (the user, 2026-10-18): "tanıtılan hangi isimde bir ürün olursa onun söylenişi
    doğru olacak, ekranda nasıl yazılıyorsa öyle yazılsın ... sistemde kalıcı hale getir"."""
    import tts_engine

    learned = tmp_path / "pronunciations.json"
    monkeypatch.setattr(tts_engine, "LEARNED_PATH", learned)
    monkeypatch.delenv("SCRIPT_WRITER_NO_CLI", raising=False)
    monkeypatch.setattr(tts_engine.shutil, "which", lambda name: "claude")
    answer = {"structured_output": {"words": [
        {"written": "Openbroca", "spoken": "Openbroka"},
        {"written": "SpeechFast", "spoken": "Spiç Fest"},  # two parts: joined, one word for one
        {"written": "Gemini", "spoken": "Gemini"},  # already known (hand-checked list wins)
        {"written": "Nowhere", "spoken": "Novher"},  # not in the text: refused
        {"written": "Krea", "spoken": "Kri-ya 3"},  # a digit: refused
    ]}}
    monkeypatch.setattr(tts_engine.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps(answer)))
    text = "Openbroca'yı SpeechFast ile Gemini'de dene."
    said = tts_engine.spoken_text(text, learn=True)
    assert said == "Openbroka'yı SpiçFest ile Cemini'de dene."
    assert json.loads(learned.read_text(encoding="utf-8")) == {"Openbroca": "Openbroka", "SpeechFast": "SpiçFest"}
    monkeypatch.setattr(tts_engine.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="not json"))
    assert tts_engine.spoken_text("Openbroca hazır.", learn=True) == "Openbroka hazır."  # remembered


def test_tools_with_no_ai_never_reach_a_render(monkeypatch):
    """10-18: MeetPaw (meeting launcher) and Tower (git client) were rendered and rejected as "not AI"."""
    import content_ranker
    import main

    tools = [{"tool_name": "MeetPaw", "tag_line": "Join meetings from the menu bar", "description": ""},
             {"tool_name": "Openbroca", "tag_line": "AI dictation", "description": ""}]
    monkeypatch.setattr(content_ranker, "rank", lambda items, concept, kind_prefix="": [
        {**items[1], "rank": {"score": 30, "fits": True}}, {**items[0], "rank": {"score": 20, "fits": False}}])
    assert [t["tool_name"] for t in main.ai_tools_first(tools)] == ["Openbroca"]
    assert "no AI in them" in content_ranker.CONCEPTS["tool_reel"]


def test_ai_tools_put_off_by_the_ranker_are_still_tried_last(monkeypatch):
    """10-23 (D-42): the ranker put Claude Duet, Bits, Kalender Sync, Playad and Concierge OFF; only Notif was
    tried and every Reel slot stayed empty. An OFF tool that says AI is tried after the fitting ones."""
    import content_ranker
    import main

    tools = [{"tool_name": "Notif", "tag_line": "AI for your Apple Reminders", "description": ""},
             {"tool_name": "Claude Duet", "tag_line": "Proactive agent that understands what needs your attention",
              "description": ""},
             {"tool_name": "Playad", "tag_line": "Hire your AI Marketing Team", "description": ""},
             {"tool_name": "MeetPaw", "tag_line": "Join meetings from the menu bar", "description": ""}]
    monkeypatch.setattr(content_ranker, "rank", lambda items, concept, kind_prefix="": [
        {**items[0], "rank": {"score": 30, "fits": True}}, {**items[1], "rank": {"score": 20, "fits": False}},
        {**items[2], "rank": {"score": 17, "fits": False}}, {**items[3], "rank": {"score": 9, "fits": False}}])
    assert [t["tool_name"] for t in main.ai_tools_first(tools)] == ["Notif", "Claude Duet", "Playad"]


def test_captions_step_aside_while_a_site_picture_is_shown():
    """10-18: in most rejected Reels the captions sat on the site picture's own text; no picture choice fixes
    that, so the template hides the captions during the two shots."""
    html = (ROOT / "templates" / "hyperframes_news" / "index.html").read_text(encoding="utf-8")
    shots = html[html.index("// site shots:"):html.index("// why:")]
    assert 'tl.to("#captions", { autoAlpha: 0' in shots and 'tl.to("#captions", { autoAlpha: 1' in shots


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
