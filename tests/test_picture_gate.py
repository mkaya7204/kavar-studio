"""D-90 (user 2026-11-23: "notlarla dikkat edilmesini beklemek büyük bir hata ... kodla ... katmanlar"): the fixing
agent's repeated fixes (state/agent_log.jsonl, 56 sessions) are gates in code. Each test is a real recorded case."""

import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import picture_gate  # noqa: E402


def _info(path, kind, money="", readable=True, shows="x"):
    return {"path": str(path), "kind": kind, "money": money, "readable": readable, "shows": shows}


def _png(folder, name, color):
    p = folder / name
    Image.new("RGB", (800, 500), color).save(p)
    return p


# ---- layer 1: code decides which pictures may be proof --------------------------------------------------------------

def test_stills_faces_mascots_money_and_unreadable_pictures_are_never_proof():
    assert picture_gate.usable(_info("a.png", "product_ui"))
    assert picture_gate.usable(_info("a.png", "text_panel"))
    for kind in ("video_still", "person", "mascot", "logo", "header_photo", "stock_photo", "blank", "other_brand"):
        assert not picture_gate.usable(_info("a.png", kind))  # teaserkit / squint 11-23, rox 11-21, Google 11-14
    assert not picture_gate.usable(_info("a.png", "diagram", money="$ cost per 1M"))  # DeepMind 11-19 chart axis
    assert not picture_gate.usable(_info("a.png", "product_ui", readable=False))  # kika 11-22 small dark screens
    order = picture_gate.order([_info("1", "text_panel"), _info("2", "video_still"), _info("3", "output")])
    assert [i["path"] for i in order] == ["3", "1"]


# ---- layer 2: the guide Reel no longer takes the first picture unseen -----------------------------------------------

def test_guide_reel_puts_the_product_screen_under_the_hook_not_the_video_still(tmp_path, monkeypatch):
    import guide_reel

    still = _png(tmp_path, "video_1.png", "black")  # Google 10-30: a presenter's video frame was the proof
    screen = _png(tmp_path, "figure_2.png", "white")
    monkeypatch.setattr(picture_gate, "inspect", lambda paths, folder, topic: [
        _info(still, "video_still", shows="a presenter talking"), _info(screen, "product_ui", shows="the Gemini app")])
    cap = guide_reel._frames({"figures": [{"path": str(still)}, {"path": str(screen)}], "url": "https://blog.google/x"},
                             tmp_path / "frames")
    assert cap["pictures"] == [str(screen)]
    assert [m["shows"] for m in cap["menu"]] == ["the Gemini app"]
    with Image.open(tmp_path / "frames" / "proof.png") as proof:
        assert proof.getpixel((proof.width // 2, proof.height // 2)) == (255, 255, 255)


def test_guide_topic_with_no_usable_picture_is_dropped_before_writing(tmp_path, monkeypatch):
    import guide_reel

    header = _png(tmp_path, "cover.png", "blue")  # Google 11-14: only the header / badge collage
    monkeypatch.setattr(picture_gate, "inspect", lambda paths, folder, topic: [_info(header, "header_photo")])
    assert guide_reel._frames({"figures": [{"path": str(header)}], "url": "https://blog.google/x"}, tmp_path / "f") is None


def test_the_writer_sees_the_pictures_before_it_writes():
    text = picture_gate.menu([{"shows": "the Gemini app's skills menu"}, {"shows": "a diagram of the steps"}])
    assert "0. (UNDER THE HEADLINE) the Gemini app's skills menu" in text and "ONLY about what picture 0 shows" in text


# ---- layer 4: the written script against its pictures and its source ----------------------------------------------

SOURCE = "Opera Neon now lets you run agents in the browser. The feature is available on desktop in the US."
SCRIPT = {"hook": "Tarayıcın işi kendi yapıyor", "voiceover": "Opera Neon ajanları tarayıcıda çalıştırıyor.",
          "voiceover_segments": {"hook": "Tarayıcın işi kendi yapıyor."}, "key_points": [], "why_it_matters": "",
          "caption": "Opera Neon ajanları tarayıcıya getirdi.", "hashtags": ["opera", "yapayzeka"]}


def test_a_date_the_source_does_not_give_is_refused(monkeypatch):
    monkeypatch.setattr(picture_gate, "_run", lambda *a: None)
    problems, _ = picture_gate.check({**SCRIPT, "caption": "Opera 19 Kasım'da duyurdu."}, [], SOURCE)  # opera 11-19
    assert problems and "Kasım" in problems[0]
    ok, _ = picture_gate.check({**SCRIPT, "caption": "Opera kasımda duyurdu."}, [], SOURCE + " November 19, 2026")
    assert ok == []


def test_a_headline_no_picture_shows_and_an_unquoted_claim_go_back_to_the_writer(monkeypatch):
    monkeypatch.setattr(picture_gate, "_run", lambda *a: {"hook_picture": -1, "claims": [
        {"claim": "ajanları tarayıcıda çalıştırıyor", "source_quote": "lets you run agents in the browser"},
        {"claim": "tüm sohbet botlarından hızlı", "source_quote": "faster than all chatbots"}]})  # rox 11-21
    problems, proof = picture_gate.check(SCRIPT, [{"shows": "the Opera logo"}], SOURCE)
    assert any("no picture shows" in p for p in problems)
    assert any("tüm sohbet botlarından hızlı" in p for p in problems)
    assert not any("ajanları tarayıcıda" in p for p in problems)  # a real quote passes
    assert proof == 0


def test_the_headline_proven_by_another_picture_moves_that_picture_under_it(monkeypatch):
    monkeypatch.setattr(picture_gate, "_run", lambda *a: {"hook_picture": 1, "claims": []})
    problems, proof = picture_gate.check(SCRIPT, [{"shows": "a diagram"}, {"shows": "agents in the browser"}], SOURCE)
    assert problems == [] and proof == 1


def test_quotes_are_checked_in_code_not_trusted():
    assert picture_gate.in_source("lets you run agents in the browser", SOURCE)
    assert picture_gate.in_source("Lets you run agents in the browser.", SOURCE)
    assert not picture_gate.in_source("works on every phone", SOURCE)
    assert not picture_gate.in_source("agents", SOURCE)  # too short to prove anything


def test_ai_hashtags_only_when_the_source_says_ai():
    non_ai = "Sequence is a calendar for teams."  # sequence 11-08, any-video-to-text 11-07
    assert picture_gate.drop_ai_tags(SCRIPT, non_ai)["hashtags"] == ["opera"]
    assert picture_gate.drop_ai_tags(SCRIPT, SOURCE)["hashtags"] == ["opera", "yapayzeka"]


# ---- the gates are wired into every Reel path -----------------------------------------------------------------------

def test_guide_script_refused_once_is_rewritten_with_the_reasons_then_dropped_if_still_wrong(monkeypatch):
    import guide_reel

    calls = []
    monkeypatch.setattr(guide_reel, "write_script", lambda p, page, menu, fb: calls.append(fb) or dict(SCRIPT))
    monkeypatch.setattr(guide_reel, "judge_hooks", lambda s, t: s)
    monkeypatch.setattr(picture_gate, "check", lambda s, m, src: (["'x' is not in the source"], 0))
    assert guide_reel._gated_script("Opera", {"text": SOURCE}, {}, {"menu": [{"shows": "a"}]}) is None
    assert calls == ["", "'x' is not in the source"]
    monkeypatch.setattr(picture_gate, "check", lambda s, m, src: ([], 0))
    assert guide_reel._gated_script("Opera", {"text": SOURCE}, {}, {"menu": []})["hook"] == SCRIPT["hook"]


def test_tool_reel_without_ai_in_its_own_words_is_skipped_before_writing(monkeypatch):
    import main
    from media_capturer import CaptureError

    monkeypatch.setattr(main, "generate_script", lambda *a, **k: pytest.fail("a script was written"))
    with pytest.raises(CaptureError):  # papermark 10-26, savorapp 10-28, mo 11-01
        main.gated_script({"tool_name": "Mo", "tag_line": "Your notes, simple.", "description": "", "page_text": ""})


def test_tool_reel_script_goes_through_the_gate(monkeypatch):
    import main
    from media_capturer import CaptureError

    seen = []
    monkeypatch.setattr(main, "generate_script", lambda tool, feedback="": seen.append(feedback) or dict(SCRIPT))
    monkeypatch.setattr(picture_gate, "check", lambda s, m, src: (["the headline promises something no picture shows"], 0))
    with pytest.raises(CaptureError):
        main.gated_script({"tool_name": "Opera", "description": SOURCE, "proof_shows": "the Opera logo"})
    assert seen == ["", "the headline promises something no picture shows"]


def test_the_fixing_agent_cannot_put_a_refused_picture_under_the_hook(tmp_path):
    import agent_tools

    pics = [tmp_path / "video_1.png", tmp_path / "figure_2.png"]
    base = {"picture_check": [_info(pics[0], "video_still"), _info(pics[1], "product_ui")]}
    assert agent_tools.refused_pictures(base, {"proof": 0, "shots": [1, 1]}, pics) == ["video_1.png (video_still)"]
    assert agent_tools.refused_pictures(base, {"proof": 1, "shots": [1, -1]}, pics) == []
