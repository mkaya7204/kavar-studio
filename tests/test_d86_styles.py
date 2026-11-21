"""D-85 / D-86 (user 2026-11-21): the carousel style is chosen per story (E screen + hand notes, F headline + wit,
G Kavar explains); the neon look is gone from the new template; the editor knows the styles."""

import re
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import news_writer  # noqa: E402
from news_writer import style_problems  # noqa: E402

V2 = ROOT / "templates" / "carousel_v2" / "index.html"


def slide(role, visual="page", title="Başlık", body="kısa metin", note="", crow=""):
    return NS(role=role, visual=visual, visual_index=1 if visual == "figure" else 0, title=title, body=body,
              note=note, crow=crow, alt_text="")


def script(style, slides, kicker="", reason="çünkü ekranda görünüyor"):
    return NS(style=style, slides=slides, kicker=kicker, style_reason=reason)


def base(**news_kw):
    return [slide("cover", "cover", "Model 4 kat hızlanıyor"), slide("news", "page", **news_kw),
            slide("news", "figure"), slide("why", "none", "Evdeki bilgisayara yetiyor"), slide("cta", "none", "Takip et")]


def test_style_e_needs_two_screens_and_a_note():
    ok = script("E", base(note="4 kat!"))
    assert style_problems(ok) == []
    no_note = script("E", base())
    assert any("hand note" in p for p in style_problems(no_note))
    one_screen = base(note="bak")
    one_screen[2].visual = "video"
    assert any("at least 2 news slides" in p for p in style_problems(script("E", one_screen)))


def test_style_f_needs_a_kicker_and_others_do_not_take_one():
    assert any("witty kicker" in p for p in style_problems(script("F", base())))
    assert style_problems(script("F", base(), kicker="Küçük ama kodu büyük")) == []
    assert any("only for style F" in p for p in style_problems(script("G", base(crow="Bak şuna"), kicker="Espri")))


def test_style_g_asks_a_question_and_kavar_speaks():
    s = base(crow="Getirdim, bak şuna!")
    assert any("question" in p for p in style_problems(script("G", s)))
    s[0].title = "Bu model nasıl 4 kat hızlanıyor?"
    assert style_problems(script("G", s)) == []


def test_a_slide_without_a_picture_needs_kavar_and_why_is_no_label():
    s = base(note="bak")
    s.insert(2, slide("news", "none"))
    assert any("crow line" in p for p in style_problems(script("E", s)))
    s[2].crow = "Bunu bil."
    s[-2].title = "Neden önemli?"
    assert any("not 'Neden önemli?'" in p for p in style_problems(script("E", s)))


def test_a_style_needs_a_reason_and_notes_stay_short():
    assert any("style_reason" in p for p in style_problems(script("E", base(note="bak"), reason="")))
    assert any("note max" in p for p in style_problems(script("E", base(note="bu not çok uzun bir not oldu"))))


def test_short_slides_for_styled_drafts_old_lengths_for_the_old_template():
    assert news_writer.STYLE_BODY_WORDS["news"][1] <= 35  # D-85: <= 35 words a slide
    assert news_writer.BODY_WORDS["news"] == (20, 75)  # a draft with no style keeps the old template's rules


def test_the_writer_is_told_the_three_styles():
    p = news_writer.SYSTEM_PROMPT
    for needle in ('"E" (real screen', '"F" (headline + wit', '"G" (Kavar explains', "never the label"):
        assert needle in p, needle
    assert "drawn bold in neon" not in p  # the old look's wording (older editor lessons may still say "neon")


def test_styled_news_uses_the_new_template():
    import carousel_renderer as r
    assert r.template_dir({"kind": "news", "style": "G"}) == r.TEMPLATE_V2_DIR
    assert r.template_dir({"kind": "news", "style": ""}) == r.TEMPLATE_DIR
    assert r.template_dir({"kind": "tool", "style": "E"}) == r.TEMPLATE_DIR


def test_the_new_template_has_no_neon_glow_or_eyebrow():
    html = V2.read_text(encoding="utf-8")
    code = re.sub(r"<!--.*?-->|/\*.*?\*/", "", html, flags=re.S)  # the comments say what is NOT used
    css = code.split("</style>")[0]
    assert "text-shadow" not in css  # no glow
    assert "#1fd5ff" not in html.lower() and "neon" not in css.lower()
    assert "background-clip: text" not in css  # no gradient text
    assert "NEDEN ÖNEMLİ" not in html
    assert (V2.parent / "assets" / "karga.svg").exists()  # Kavar on every style
    for contract in ("window.__show", "window.__qa", "window.__ready", "videoSlot"):
        assert contract in html, contract


def test_the_editor_knows_the_styles_and_judges_the_kicker():
    import editor_review
    assert "D-86 styles" in editor_review.SYSTEM and "kicker zayıf" in editor_review.SYSTEM


def test_the_design_detector_runs_in_the_cloud():
    ci = (ROOT / ".github" / "workflows" / "checks.yml").read_text(encoding="utf-8")
    assert re.search(r"impeccable@\d+\.\d+\.\d+ detect", ci)  # pinned version
    assert "templates/carousel_v2" in ci
