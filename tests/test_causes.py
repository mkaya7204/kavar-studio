"""D-40 (user 2026-10-22: "Evet diyorum derin araştırma yap ... varsayım yapmadan"): the causes of the recorded
rejections are fixed, each tested on the real example that failed (fixtures from the 10-20 / 10-22 runs)."""

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

FIX = Path(__file__).resolve().parent / "fixtures"


# --- empty pictures (10-20 OpenAI gradient page, 10-22 VocabX empty animation frame, the abstract "4") -----------

def test_a_picture_that_shows_nothing_is_recognised():
    from article_capture import informative

    assert not informative(FIX / "empty_animation_frame.png")  # VocabX fig 5, rejected 10-22
    assert informative(FIX / "sparse_illustration.png")  # FairStress fig 1: sparse but real, kept


def test_blank_and_gradient_are_empty_and_a_chart_is_not(tmp_path):
    from article_capture import informative

    Image.new("RGB", (1400, 800), "white").save(tmp_path / "blank.png")
    grad = Image.new("RGB", (1400, 800))
    grad.putdata([(40, 120 + x // 12, 90 + y // 10) for y in range(800) for x in range(1400)])
    grad.save(tmp_path / "gradient.png")
    chart = Image.new("RGB", (1400, 800), "white")
    d = ImageDraw.Draw(chart)
    for i in range(12):
        d.rectangle((80 + i * 105, 700 - i * 45, 150 + i * 105, 700), fill=(30, 90, 200))
        d.text((80 + i * 105, 720), f"M{i}", fill="black")
    for y in range(100, 700, 50):
        d.line((60, y, 1340, y), fill=(200, 200, 200))
    chart.save(tmp_path / "chart.png")
    assert not informative(tmp_path / "blank.png")
    assert not informative(tmp_path / "gradient.png")
    assert informative(tmp_path / "chart.png")


# --- the picture must be the one the slide talks about (10-22 FairStress) ---------------------------------------

def _fairstress():
    from news_writer import NewsScript

    article = json.loads((FIX / "fairstress_article.json").read_text(encoding="utf-8"))
    script = NewsScript.model_validate(json.loads((FIX / "fairstress_carousel.json").read_text(encoding="utf-8")))
    return script, article


def _with(script, changes):
    data = script.model_dump()
    for n, (index, quote) in changes.items():
        data["slides"][n - 1].update(visual="figure", visual_index=index, visual_quote=quote)
    return type(script).model_validate(data)


def test_the_rejected_fairstress_slides_are_caught():
    """As written on 10-22 (slide 5 -> figure 2, slide 6 -> figure 3, figure 1 twice), with the quotes the
    slides' own text points to: every wrong picture and the repeat are named, with the right figure."""
    from news_writer import _visual_problems

    script, article = _fairstress()
    wrong = _with(script, {3: (1, "balance surrounded by hiring, lending"),
                           5: (2, "Mean demographic gaps across 15 models"),
                           6: (3, "minority-coded candidate selection rates"),
                           7: (1, "Paired Claude Opus 5 explanations")})
    problems = " | ".join(_visual_problems(wrong, article))
    assert "slide 5: figure 2" in problems and "fits figure 3" in problems
    assert "slide 6: figure 3" in problems and "fits figure 4" in problems
    assert "slide 7: figure 1 is already on slide 3" in problems


def test_the_right_fairstress_pictures_pass():
    from news_writer import _visual_problems

    script, article = _fairstress()
    right = _with(script, {3: (1, "balance surrounded by hiring, lending"),
                           5: (3, "Mean demographic gaps across 15 models"),
                           6: (4, "minority-coded candidate selection rates"),
                           7: (5, "Paired Claude Opus 5 explanations")})
    assert _visual_problems(right, article) == []


def test_an_empty_page_screenshot_is_never_a_visual():
    """10-20 OpenAI: slide 2 showed the page screenshot, an empty green gradient."""
    from news_writer import _user_message, _visual_problems

    script, article = _fairstress()
    article = {**article, "page_blank": True}
    assert script.slides[1].visual == "page"
    assert any("slide 2: the page screenshot shows nothing" in p for p in _visual_problems(script, article))
    assert "NOT available" in _user_message(article)


# --- the editor's "fix" is done by the writer, inside the rules (10-22 YouTube) ------------------------------------

def test_the_editor_fix_is_rewritten_by_the_writer_and_a_bad_picture_stays_out(monkeypatch):
    import news_writer

    script, article = _fairstress()
    data = script.model_dump(mode="json")
    seen = {}

    def ask(prompt, system, fmt):
        seen["prompt"] = prompt
        draft = news_writer.NewsDraft.model_validate(data).model_dump()
        draft["slides"][2]["visual_quote"] = "balance surrounded by hiring, lending"
        draft["slides"][5].update(visual_index=3, visual_quote="Mean demographic gaps across 15 models")
        draft["slides"][6].update(visual_index=5, visual_quote="Paired Claude Opus 5 explanations")
        draft["slides"][4].update(visual="figure", visual_index=2)  # the writer tries to bring it back
        return draft, "m", "claude_code"

    monkeypatch.setattr(news_writer, "_ask", ask)
    verdict = {"verdict": "fix", "problems": ["Slayt 5: görsel metinle uyuşmuyor"], "fixes": [],
               "bad_visual_slides": [5]}
    out = news_writer.revise_for_editor(data, verdict, article)
    assert out["slides"][4]["visual"] == "none"
    assert "Slayt 5: görsel metinle uyuşmuyor" in seen["prompt"] and "story and caption" in seen["prompt"]


def test_an_editor_revision_that_breaks_a_rule_is_sent_back(monkeypatch):
    """10-31 Gemini immersive explorations (10-30 Gemini docs the same): the writer's one revision cut slide 5 to
    15 words (needs 20-75), the editor's short text was pasted in and the post was lost."""
    import news_writer

    article = json.loads((FIX / "immersive_article_1031.json").read_text(encoding="utf-8"))
    data = json.loads((FIX / "immersive_carousel_1031.json").read_text(encoding="utf-8"))
    prompts = []

    def ask(prompt, system, fmt):
        prompts.append(prompt)
        draft = news_writer.NewsDraft.model_validate(data).model_dump()
        if len(prompts) == 1:  # as on 10-31: the repeated sentence dropped, slide 5 left with 15 words
            draft["slides"][4]["body"] = " ".join(draft["slides"][4]["body"].split()[:15])
        return draft, "m", "claude_code"

    monkeypatch.setattr(news_writer, "_ask", ask)
    verdict = {"verdict": "fix", "problems": ["Slayt 5: son cümle slayt 4'ün tekrarı"], "fixes": [],
               "bad_visual_slides": []}
    out = news_writer.revise_for_editor(data, verdict, article)
    assert out is not None and len(prompts) == 2
    assert "slide 5 (news): body has 15 words, needs 20-75" in prompts[1]


def test_daily_sends_a_fix_verdict_to_the_writer(monkeypatch, tmp_path):
    import daily

    (tmp_path / "article").mkdir()
    (tmp_path / "article" / "article.json").write_text((FIX / "fairstress_article.json").read_text(encoding="utf-8"),
                                                       encoding="utf-8")
    (tmp_path / "carousel.json").write_text((FIX / "fairstress_carousel.json").read_text(encoding="utf-8"),
                                            encoding="utf-8")
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(daily, "revise_for_editor", lambda s, v, a: calls.append(v["bad_visual_slides"]) or s)
    monkeypatch.setattr(daily.subprocess, "run", lambda *a, **k: type("P", (), {"returncode": 0})())
    verdicts = iter([{"verdict": "fix", "problems": ["x"], "fixes": [], "bad_visual_slides": [5]},
                     {"verdict": "publish", "problems": [], "fixes": [], "bad_visual_slides": []}])
    monkeypatch.setattr(daily, "review_carousel", lambda folder: next(verdicts))
    ok, _ = daily._reviewed_news(tmp_path)
    assert ok and calls == [[5]]


# --- Reels: the proof box never cuts text (10-21 ToDo.is 'odo.is', Composio half buttons) ------------------------

def test_the_proof_window_ends_in_a_gap_not_through_a_line():
    from hyperframes_builder import _row_activity, _snap_window

    page = Image.new("RGB", (1080, 4000), "white")
    d = ImageDraw.Draw(page)
    for y in range(300, 4000, 260):  # cards of text 180 px tall with 80 px gaps
        for line in range(y, y + 180, 30):
            d.line((80, line, 1000, line), fill="black", width=8)
    rows = _row_activity(page)
    win_h = round(1080 * 660 / 920)
    top, bottom = _snap_window(rows, page.height, 400, win_h)  # 400 is inside a card
    for y in (top, bottom - 1):
        assert all(page.getpixel((x, y)) == (255, 255, 255) for x in range(0, 1080, 20)), y


def test_a_proof_picture_is_whole_and_clear_of_the_hook_zoom(tmp_path):
    from hyperframes_builder import HOOK_ZOOM, PROOF_SIZE, _fit_whole

    wide = Image.new("RGB", (1600, 900), "white")
    ImageDraw.Draw(wide).rectangle((0, 0, 19, 899), fill=(255, 0, 0))
    ImageDraw.Draw(wide).rectangle((1580, 0, 1599, 899), fill=(0, 0, 255))
    out = _fit_whole(wide)
    assert out.size == PROOF_SIZE
    mid = PROOF_SIZE[1] // 2
    row = [out.getpixel((x, mid)) for x in range(PROOF_SIZE[0])]
    reds = [x for x, p in enumerate(row) if p[0] > 200 and p[1] < 80]
    blues = [x for x, p in enumerate(row) if p[2] > 200 and p[0] < 80]
    assert reds and blues  # both edges kept
    margin = PROOF_SIZE[0] * (1 - 1 / HOOK_ZOOM) / 2  # what the 1.12 zoom pushes out of the box
    assert min(reds) >= margin - 2 and max(blues) <= PROOF_SIZE[0] - margin + 2


def test_the_site_shot_zoom_keeps_a_960px_shot_whole():
    html = (Path(__file__).resolve().parent.parent / "templates" / "hyperframes_news" / "index.html").read_text(
        encoding="utf-8")
    assert "scale: 1.3" not in html  # 1.3 left 831 px of 1080 in frame


# --- the day: five slots back, and the morning Reel on its own (10-21: ready 06:28, downloadable 07:34) ----------

def test_the_two_step_day_never_makes_a_stage_twice(monkeypatch, tmp_path):
    import daily

    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path / "logs")
    monkeypatch.delenv("KAVAR_FORCE", raising=False)
    monkeypatch.setattr(daily, "schedule", lambda: {"guide_reel": True, "tool_reels": False, "slots": [
        {"time": "07:30", "kind": "reel", "concept": "guide"}, {"time": "12:30", "kind": "carousel"}]})
    made = []
    monkeypatch.setattr(daily, "produce_guide_reel", lambda: made.append("guide") or
                        {"kind": "reel", "folder": "g", "title": "G", "concept": "guide"})
    monkeypatch.setattr(daily, "produce_news_items", lambda n: made.append("news") or [])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    assert daily.produce("morning") is False  # the morning step: no exit 1 even before the carousels exist
    assert daily.produce("rest") is True
    assert daily.produce("morning") is False and daily.produce("rest") is False  # a backup run
    assert made == ["guide", "news"]
    monkeypatch.setenv("KAVAR_FORCE", "1")  # a manual run makes it again
    daily.produce("morning")
    assert made == ["guide", "news", "guide"]


def test_fetch_takes_the_morning_artifact_of_a_run_still_going(monkeypatch, tmp_path):
    import io
    import zipfile

    import daily

    (tmp_path / "morning-x.tgz").write_bytes(b"tgz")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.write(tmp_path / "morning-x.tgz", "morning-x.tgz")
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        if cmd[1:3] == ["run", "download"]:
            return type("P", (), {"stderr": "no valid artifacts found to download", "stdout": ""})()
        if "--jq" in cmd:
            return type("P", (), {"stdout": "123\n", "stderr": ""})()
        return type("P", (), {"stdout": buf.getvalue(), "stderr": b""})()

    monkeypatch.setattr(daily.subprocess, "run", run)
    archive, error = daily._download_archive(42, "kavar-morning", tmp_path / "dl")
    assert archive and archive.name == "morning-x.tgz" and error == ""
    assert any("actions/artifacts/123/zip" in " ".join(c) for c in calls)


@pytest.mark.parametrize("name", ["produce.yml"])
def test_the_workflow_uploads_the_morning_reel_before_the_rest(name):
    import yaml

    wf = yaml.safe_load((Path(__file__).resolve().parent.parent / ".github" / "workflows" / name).read_text(
        encoding="utf-8"))
    steps = [s.get("name") or s.get("uses", "") for s in wf["jobs"]["produce"]["steps"]]
    morning = steps.index("Produce the morning guide Reel (07:30)")
    upload = next(i for i, s in enumerate(wf["jobs"]["produce"]["steps"])
                  if "kavar-morning" in str(s.get("with", {}).get("name", "")))
    rest = steps.index("Produce the rest of the day (news carousels + Reels, each reviewed by the editor)")
    assert morning < upload < rest
