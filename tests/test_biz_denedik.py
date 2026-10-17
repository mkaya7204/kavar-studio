"""§1.4 "Biz denedik" (user, 2026-10-15/16: permanent): our own test of a new model leads the post."""

from pathlib import Path

import pytest

import model_trial
from model_trial import TrialPick


# --- ranking ------------------------------------------------------------------------------------

def test_testable_first_moves_releases_to_the_front(monkeypatch):
    import carousel_writer

    cands = [{"source": "s", "title": f"t{i}"} for i in range(5)]
    items = [{"index": 2, "kind": "llm"}, {"index": 9, "kind": "image"}, {"index": 4, "kind": "image"},
             {"index": 0, "kind": "llm"}, {"index": 2, "kind": "llm"}]
    monkeypatch.setattr(carousel_writer, "_ask", lambda *a, **k: ({"items": items}, None, "claude"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # without the OpenRouter key only the image release can be tested now: it goes first
    assert [c["title"] for c in model_trial.testable_first(cands)] == ["t4", "t2", "t0", "t1", "t3"]
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    assert [c["title"] for c in model_trial.testable_first(cands)] == ["t2", "t4", "t0", "t1", "t3"]


def test_testable_first_keeps_the_order_when_claude_fails(monkeypatch):
    import carousel_writer

    cands = [{"source": "s", "title": f"t{i}"} for i in range(3)]

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(carousel_writer, "_ask", boom)
    assert model_trial.testable_first(cands) == cands


# --- only official Spaces ----------------------------------------------------------------------

class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_only_official_spaces_are_called(monkeypatch):
    spaces = [
        {"id": "Animacustoms/flux-3-something", "sdk": "gradio"},     # random user: never
        {"id": "black-forest-labs/flux-3-image-klein", "sdk": "gradio"},  # the company in the article
        {"id": "multimodalart/flux-3-nsfw", "sdk": "gradio"},          # trusted owner, unsafe name: never
        {"id": "black-forest-labs/flux-3-static", "sdk": "static"},    # not runnable
        {"id": "hysts/flux-3-demo", "sdk": "gradio"},                  # HF demo account
        {"id": "multimodalart/flux-3-a", "sdk": "gradio"},
    ]
    monkeypatch.setattr(model_trial.requests, "get", lambda *a, **k: _Resp(spaces))
    found = model_trial._spaces(["flux-3"], "Black Forest Labs released FLUX.3")
    assert found == ["black-forest-labs/flux-3-image-klein", "hysts/flux-3-demo", "multimodalart/flux-3-a"]


def test_unsafe_words_and_trusted_owners_are_pinned():
    for w in ("nsfw", "nude", "porn"):
        assert w in model_trial.BLOCKED_SPACE_WORDS
    assert model_trial.TRUSTED_SPACE_OWNERS == {"huggingface", "multimodalart", "hysts", "gradio"}


def test_short_model_names_never_match(monkeypatch):
    models = [{"id": "openai/gpt-5-nano:free", "name": "GPT-5 nano"}]
    monkeypatch.setattr(model_trial.requests, "get", lambda *a, **k: _Resp({"data": models}))
    assert model_trial._free_llm(["gpt"]) is None


# --- what reaches the post ---------------------------------------------------------------------

def _trial(n=2):
    return {"model": "org/space", "route": "huggingface space org/space",
            "figures": [{"path": f"/x/trial_{i}.png", "credit": "KAVAR denemesi", "caption": f"KAVAR TEST {i}: x"}
                        for i in range(1, n + 1)],
            "notes": [f"Test {i} prompt: p" for i in range(1, n + 1)]}


@pytest.fixture
def image_pick(monkeypatch):
    monkeypatch.setattr(model_trial, "_pick", lambda a: TrialPick(kind="image", model_name="M", search_terms=["mmmm"]))
    monkeypatch.setattr(model_trial, "_run_image", lambda *a: _trial())


ART = {"title": "t", "text": "x", "publisher": "p"}


def test_unchecked_outputs_are_never_used(monkeypatch, image_pick, tmp_path):
    monkeypatch.setattr(model_trial, "_judge", lambda *a: None)
    assert model_trial.run_trial(ART, tmp_path) is None


def test_unusable_outputs_are_dropped_and_the_cover_follows(monkeypatch, image_pick, tmp_path):
    judged = {"results": [{"test": 1, "assessment": "ok", "usable": True},
                          {"test": 2, "assessment": "shows a price", "usable": False}], "cover": 2}
    monkeypatch.setattr(model_trial, "_judge", lambda *a: judged)
    t = model_trial.run_trial(ART, tmp_path)
    assert [f["path"] for f in t["figures"]] == ["/x/trial_1.png"]
    assert t["cover_figure"] == 0  # the cover pick was the dropped output
    assert "shows a price" not in t["note"]


def test_all_unusable_means_no_test(monkeypatch, image_pick, tmp_path):
    judged = {"results": [{"test": 1, "assessment": "a", "usable": False},
                          {"test": 2, "assessment": "b", "usable": False}], "cover": 1}
    monkeypatch.setattr(model_trial, "_judge", lambda *a: judged)
    assert model_trial.run_trial(ART, tmp_path) is None


def test_any_error_means_no_test_never_a_crash(monkeypatch, tmp_path):
    def boom(a):
        raise RuntimeError("x")

    monkeypatch.setattr(model_trial, "_pick", boom)
    assert model_trial.run_trial(ART, tmp_path) is None


# --- writer rules -------------------------------------------------------------------------------

def test_a_passing_test_carousel_has_no_problems(news_script, trial_article):
    from news_writer import NewsScript, _trial_problems

    assert _trial_problems(NewsScript.model_validate(news_script), trial_article) == []


def test_jargon_and_too_many_detail_slides_are_flagged(news_script, trial_article):
    from news_writer import NewsScript, _trial_problems

    s = NewsScript.model_validate(news_script)
    detail = next(x for x in s.slides if x.role == "news" and x.visual == "figure" and x.visual_index <= 6)
    detail.body = detail.body + " Bir H100 GPU'da çalışıyor."
    extra = detail.model_copy()
    s.slides.insert(-2, extra)
    probs = " ".join(_trial_problems(s, trial_article))
    assert "jargon" in probs and "detail slides" in probs


def test_the_test_must_be_shown(news_script, trial_article):
    from news_writer import NewsScript, _trial_problems

    s = NewsScript.model_validate(news_script)
    for x in s.slides:
        if x.visual == "figure" and x.visual_index in (7, 8):
            x.visual, x.visual_index = "none", 0
    assert any("KAVAR TEST" in p for p in _trial_problems(s, trial_article))


def test_writer_rules_are_in_the_prompt():
    import news_writer

    for needle in ('"Biz denedik"', "Never mention our internal checks", "at most 2 slides", "kendiniz bakın"):
        assert needle in news_writer.SYSTEM_PROMPT, needle
    assert news_writer.MAX_DETAIL_SLIDES == 2


# --- Reel -----------------------------------------------------------------------------------------

def test_reel_hook_is_about_the_picture_behind_it(trial_article):
    import trial_reel

    outs = trial_reel._outputs(trial_article)
    assert str(outs[0]) == str(Path(trial_article["cover_path"]))  # the cover output opens the Reel
    assert trial_reel._output_order(trial_article).startswith("output 1: KAVAR TEST 2")
    assert "EVERY hook candidate is about OUTPUT 1" in trial_reel.TRIAL_RULES


def test_reel_labels_our_outputs_as_ours(tmp_path):
    from PIL import Image

    import trial_reel

    img = tmp_path / "o.png"
    Image.new("RGB", (800, 800), "gray").save(img)
    cap = trial_reel._frames([img], tmp_path / "f")
    assert cap["domain_label"] == "KAVAR denemesi"
    assert Path(cap["proof_path"]).exists() and Path(cap["screenshot_path"]).exists()


def test_reel_uses_short_names_and_stays_under_26_seconds():
    """2026-10-16: 50 words -> 27.9 s (rule 14-26 s); 'ADI FLUX.3 IMAGE' broken captions."""
    import trial_reel

    assert trial_reel.short_name("FLUX.3 Image Klein") == "FLUX.3"
    assert trial_reel.short_name("Gemma 4") == "Gemma 4"
    assert trial_reel.WORDS[1] <= 38


def test_an_answer_cut_by_our_token_limit_is_never_shown(monkeypatch):
    """2026-10-16: Nemotron's proverb answer was cut by our 600-token cap and the post said the model "left it half"."""
    class Resp:
        status_code = 200

        def __init__(self, reason):
            self.reason = reason

        def json(self):
            return {"choices": [{"finish_reason": self.reason, "message": {"content": "Bu atasözü, küçük ama"}}]}

    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(model_trial.requests, "post", lambda *a, **k: Resp("length"))
    assert model_trial._ask_llm("m:free", "soru") is None
    monkeypatch.setattr(model_trial.requests, "post", lambda *a, **k: Resp("stop"))
    assert model_trial._ask_llm("m:free", "soru") == "Bu atasözü, küçük ama"


def test_reel_proof_shows_a_whole_answer_card(tmp_path):
    """2026-10-16: the Nemotron Reel's proof box cropped the answer card mid-sentence; editor rejected it."""
    from PIL import Image, ImageChops, ImageDraw

    import trial_reel

    # an answer card's shape (1080x760, text from top to bottom) without fonts: checks.yml has none
    img = Image.new("RGB", (1080, 760), trial_reel.ImageColor.getrgb(trial_reel.CARD_BG))
    ImageDraw.Draw(img).rectangle((70, 60, 1010, 650), fill="white")
    assert trial_reel._is_answer_card(img)
    proof = trial_reel._proof(img)
    assert proof.size == trial_reel.PROOF_SIZE
    # the whole card was scaled in, and it stays visible at the hook's end zoom (2nd rejection, same day)
    bg = Image.new("RGB", proof.size, trial_reel.ImageColor.getrgb(trial_reel.CARD_BG))
    left, top, right, bottom = ImageChops.difference(proof, bg).getbbox()
    s_left, s_top, s_right, s_bottom = trial_reel.PROOF_SAFE
    assert s_left <= left and s_top <= top and right <= s_right and bottom <= s_bottom


def test_proof_safe_box_matches_the_template_zoom():
    """If the hook zoom in the template changes, trial_reel._safe_box must change with it."""
    html = (Path(__file__).resolve().parent.parent / "templates" / "hyperframes_news" / "index.html").read_text(
        encoding="utf-8")
    assert 'tl.fromTo("#hook-proof-img", { scale: 1.0 }, { scale: 1.12' in html
    assert "transform-origin: 50% 30%;" in html


def test_hook_box_never_rises_into_the_headline():
    """10-17: a fixed 150 px lift put a two-line headline under the proof box, and the domain stamp
    sat on the proof's text (editor rejected Train with Pasta and Craft Agents)."""
    html = (Path(__file__).resolve().parent.parent / "templates" / "hyperframes_news" / "index.html").read_text(
        encoding="utf-8")
    assert 'const LIFT = Math.min(150, Math.round(0.38 * $("hook-title").offsetHeight + 54));' in html
    assert 'tl.to("#hook-proof", { y: -LIFT' in html and 'y: -150' not in html
    assert '<div id="hook-proof-clip"><img id="hook-proof-img"' in html
    assert "top: calc(100% + 18px)" in html


def test_answer_card_never_cuts_an_answer(tmp_path):
    """Lesson 2026-10-16: a cut answer looks like the model's mistake. Until 10-17 the card cut long
    answers with "…"; now the font shrinks, and an answer that still can't fit is not shown at all."""
    if not (model_trial.FONTS / "seguisb.ttf").exists():
        pytest.skip("fonts are installed by the workflows")
    short = model_trial._answer_card("x/model:free", "Soru?", "Kısa bir cevap.", tmp_path / "a.png")
    assert short is not None and short.exists()
    longer = model_trial._answer_card("x/model:free", "Soru?", "kelime " * 120, tmp_path / "b.png")
    assert longer is not None  # fits with a smaller font
    huge = model_trial._answer_card("x/model:free", "Soru?", "kelime " * 900, tmp_path / "c.png")
    assert huge is None
    assert "…" not in Path(model_trial.__file__).read_text(encoding="utf-8").split("def _answer_card")[1].split("def ")[0]
