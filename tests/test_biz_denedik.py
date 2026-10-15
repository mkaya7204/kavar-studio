"""§1.4 "Biz denedik" (user, 2026-10-15/16: permanent): our own test of a new model leads the post."""

from pathlib import Path

import pytest

import model_trial
from model_trial import TrialPick


# --- ranking ------------------------------------------------------------------------------------

def test_testable_first_moves_releases_to_the_front(monkeypatch):
    import carousel_writer

    cands = [{"source": "s", "title": f"t{i}"} for i in range(4)]
    monkeypatch.setattr(carousel_writer, "_ask", lambda *a, **k: ({"indices": [2, 2, 9, 0]}, None, "claude"))
    assert [c["title"] for c in model_trial.testable_first(cands)] == ["t2", "t0", "t1", "t3"]


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
