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
    monkeypatch.setattr(daily, "cut_frames", lambda v, o=None: [])
    monkeypatch.setattr(daily, "_agent_sessions", 0)  # a fresh production run
    return daily, calls


def test_no_agent_session_after_the_runs_cap(monkeypatch, reel_sandbox):
    """D-47: at most AGENT_SESSIONS_PER_RUN agent sessions per run; then the next candidate is tried."""
    daily, calls = reel_sandbox
    monkeypatch.setattr(daily, "_agent_sessions", daily.AGENT_SESSIONS_PER_RUN)
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "reject", "problems": ["kanıt yok"]})
    assert daily._reel_attempt() == (None, True)
    assert not any("src/reel_agent.py" in cmd for cmd, _ in calls)


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


def test_a_rejected_draft_goes_to_the_fixer_on_the_silent_voice(monkeypatch, reel_sandbox):
    """D-42 (user 10-23: "düzeltilerek uygun hale getirilecek varsa yapmayıp boş denilmesinden bıktım") turns the
    D-33 fixer on again (D-38 had switched it off for its crops, which are gone). Two rounds, no voice spent."""
    daily, calls = reel_sandbox
    assert daily.REEL_FIX_ROUNDS == 1  # D-45: the agent renders and looks up to 4 times inside its one round
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "reject", "problems": ["kanıt yok"]})
    assert daily._reel_attempt() == (None, True)
    fixes = [draft for cmd, draft in calls if "src/reel_agent.py" in cmd]
    assert fixes == ["1"]
    assert not any("src/voice_final.py" in cmd for cmd, _ in calls)


def test_a_test_run_never_spends_the_voice_and_keeps_the_reel_for_later(monkeypatch, reel_sandbox, tmp_path):
    """D-46 (user 10-23): "deneme veya işte reel ararken yada reel de düzenleme ekleme yapılırken seslendirme
    kullanılmayacak". Dry runs voiced approved Reels on 10-22 and 10-23 (credits gone). Now an approved Reel of a
    test run stays silent and keeps its words and exact pictures for voice.yml."""
    daily, calls = reel_sandbox
    temp = tmp_path / "output" / "temp"
    (temp / "proof.png").write_bytes(b"png")
    (temp / "capture.json").write_text(json.dumps({"proof_path": str(temp / "proof.png"), "still": True}),
                                       encoding="utf-8")
    monkeypatch.setenv("KAVAR_DRY", "1")
    monkeypatch.setattr(daily, "review_reel", lambda *a: {"verdict": "publish", "problems": []})
    item, rendered = daily._reel_attempt()
    assert item["needs_voice"] and rendered
    assert not any("src/voice_final.py" in cmd and draft is None for cmd, draft in calls)  # George never ran
    kit = tmp_path / item["folder"] / "_voice"
    capture = json.loads((kit / "capture.json").read_text(encoding="utf-8"))
    assert (kit / "script.json").exists() and capture["still"] is True
    assert (tmp_path / capture["proof_path"]).read_bytes() == b"png"  # the exact picture, kept with the Reel


def test_voicing_later_restores_the_kept_reel(monkeypatch, tmp_path):
    import voice_kept

    reel = tmp_path / "output" / "reels" / "r"
    kit = reel / "_voice"
    kit.mkdir(parents=True)
    (kit / "script.json").write_text("{}", encoding="utf-8")
    (kit / "tool.json").write_text("{}", encoding="utf-8")
    (kit / "capture.json").write_text('{"proof_path": "output/reels/r/_voice/proof_path.png"}', encoding="utf-8")
    monkeypatch.setattr(voice_kept, "ROOT", tmp_path)
    monkeypatch.setattr(voice_kept, "TEMP_DIR", tmp_path / "output" / "temp")
    voice_kept.restore(reel)
    cap = json.loads((tmp_path / "output" / "temp" / "capture.json").read_text(encoding="utf-8"))
    assert cap["proof_path"] == str(tmp_path / "output/reels/r/_voice/proof_path.png")


def test_no_test_workflow_spends_george():
    wf = ROOT / ".github" / "workflows"
    news = (wf / "news-test.yml").read_text(encoding="utf-8")
    reel_step = news[news.index("Biz denedik Reel + editor review"):]
    assert 'KAVAR_DRAFT_VOICE: "1"' in reel_step.split("- uses:")[0]
    assert 'default: "yes"' in (wf / "rerender.yml").read_text(encoding="utf-8").split("draft:")[1][:200]
    assert "KAVAR_DRY: ${{ github.event.inputs.dry == 'yes'" in (wf / "produce.yml").read_text(encoding="utf-8")
    assert "src/voice_kept.py" in (wf / "voice.yml").read_text(encoding="utf-8")


def test_a_third_voice_account_speaks_george_too():
    import tts_engine

    assert tts_engine.ELEVENLABS_KEYS[-1] == "ELEVENLABS_API_KEY_3"
    for name in ("produce.yml", "voice.yml", "rerender.yml", "news-test.yml"):
        assert "secrets.ELEVENLABS_API_KEY_3" in (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_a_fixed_draft_the_editor_approves_is_voiced(monkeypatch, reel_sandbox):
    daily, calls = reel_sandbox
    verdicts = iter([{"verdict": "reject", "problems": ["kanıt yok"]}, {"verdict": "publish", "problems": []}])
    monkeypatch.setattr(daily, "review_reel", lambda *a: next(verdicts))
    item, rendered = daily._reel_attempt()
    assert item and rendered
    assert [c for c, _ in calls if "src/reel_agent.py" in c] and calls[-1][1] is None  # George once, at the end


def test_a_measured_cut_is_rebuilt_still_before_the_editor(monkeypatch, reel_sandbox, tmp_path):
    """D-42: the editor rejected cut pictures on 10-19, 10-21, 10-22 and 10-23. The draft is measured first; a cut
    rebuilds the same Reel without the shot zoom (capture "still") on the silent voice, then the editor sees it."""
    daily, calls = reel_sandbox
    (tmp_path / "output" / "temp" / "capture.json").write_text("{}", encoding="utf-8")
    cuts = iter([[10.5, 11.0], []])
    monkeypatch.setattr(daily, "cut_frames", lambda v, o=None: next(cuts, []))
    seen = []
    monkeypatch.setattr(daily, "review_reel", lambda *a: seen.append(1) or {"verdict": "publish", "problems": []})
    item, _ = daily._reel_attempt()
    assert item and seen == [1]
    rebuild = calls[1]
    assert "src/voice_final.py" in rebuild[0] and rebuild[1] == "1"  # the still rebuild: silent voice
    assert json.loads((tmp_path / "output" / "temp" / "capture.json").read_text(encoding="utf-8"))["still"] is True


def test_a_cut_the_rebuild_cannot_remove_never_reaches_the_editor(monkeypatch, reel_sandbox, tmp_path):
    daily, calls = reel_sandbox
    (tmp_path / "output" / "temp" / "capture.json").write_text('{"still": true}', encoding="utf-8")
    monkeypatch.setattr(daily, "cut_frames", lambda v, o=None: [10.5, 11.0])
    monkeypatch.setattr(daily, "review_reel", lambda *a: pytest.fail("the editor saw a cut Reel"))
    assert daily._reel_attempt() == (None, True)
    assert [c for c, _ in calls if "src/reel_agent.py" in c]  # the fixer chooses whole pictures instead


def test_cut_pictures_are_measured_on_the_real_rejected_frames():
    """D-42: the frames the editor called cut ("in Google Mee" 10-22 11.6 s, 10-23 10.7 s) are found; a clean frame
    and a card sliding in (one frame) are not."""
    from reel_qa import CUT_DETAIL, cut_in, edge_detail
    from PIL import Image

    fx = ROOT / "tests" / "fixtures"
    for name, cut in (("reel_cut_frame_1022.jpg", True), ("reel_cut_frame_1023.jpg", True),
                      ("reel_clean_frame_1022.jpg", False), ("reel_card_sliding_1023.jpg", False)):
        with Image.open(fx / name) as img:
            assert (max(edge_detail(img)) >= CUT_DETAIL) is cut, name
    clean, cut, card = fx / "reel_clean_frame_1022.jpg", fx / "reel_cut_frame_1022.jpg", fx / "reel_card_sliding_1023.jpg"
    entering = fx / "reel_card_entering_voxelo_1023.jpg"  # an approved Reel's card sliding in: 3.58 at the edge
    with Image.open(entering) as img:
        assert max(edge_detail(img)) >= CUT_DETAIL  # it does touch the edge...
    assert cut_in([clean, cut, cut, cut, clean]) == [0.75]  # a cut stays (3 frames = 0.75 s at 4 a second)
    assert cut_in([clean, entering, entering, clean, card, clean]) == []  # ...but a card passes in under 0.75 s


def test_shots_never_reach_the_frame_edge_at_full_zoom(tmp_path):
    """D-42: a 960 px shot at the 1.12 zoom was 1075 of 1080 px; its text touched the edges and read as cut."""
    from PIL import Image

    from hyperframes_builder import SHOT_MARGIN, SHOT_ZOOM, _shot_frame

    pic = Image.new("RGB", (1600, 900), (255, 0, 0))
    _shot_frame(pic, tmp_path / "s.png")
    with Image.open(tmp_path / "s.png") as frame:
        row = [frame.getpixel((x, 1920 // 2 - 120)) for x in range(1080)]
    red = [x for x, p in enumerate(row) if p[0] > 230 and p[1] < 40]
    width = red[-1] - red[0] + 1
    assert width * SHOT_ZOOM <= 1080 - 2 * SHOT_MARGIN + 2
    html = (ROOT / "templates" / "hyperframes_news" / "index.html").read_text(encoding="utf-8")
    assert "scale: 1.12, y: 120" in html and '{"id":"still"' in html and "if (v.still)" in html


def test_a_long_domain_shrinks_to_fit_its_tag():
    """D-43: "workspaceupdates.googleb…" was cut at the shot tag's right edge (editor 10-23, both guide drafts)."""
    html = (ROOT / "templates" / "hyperframes_news" / "index.html").read_text(encoding="utf-8")
    fit = html[html.index("const fitDomains"):html.index("// Full-page pan distance")]
    assert '"[data-domain], #outro-domain"' in fit and "nowrap" in fit and "document.fonts.ready.then(fitDomains)" in fit
    assert html.index("const fitDomains") > html.index('$("outro-domain").textContent = v.tool_name')  # after the text
    # 2nd 10-23 case: the centred outro line is as wide as its text; it is measured against the parent's padding
    assert "paddingLeft" in fit and "el.scrollWidth > room()" in fit


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
