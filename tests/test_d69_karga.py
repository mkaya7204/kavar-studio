"""D-69 (2026-11-12, the user): "Karga iyi benzetme ... karga her gün yeni şeyler getirir ... reelde sonda takip
etmeyi ya da şuna gönder vs var ya, ondan sonrasına bu karga ve düşünce yapısını ekleyelim."
Every Reel ends, after the send / follow outro, with KAVAR's crow bringing a new shiny thing."""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import hyperframes_builder as hb  # noqa: E402

TEMPLATE = ROOT / "templates" / "hyperframes_news"


def test_the_sign_off_comes_after_the_outro_and_keeps_the_follow_pill():
    html = (TEMPLATE / "index.html").read_text(encoding="utf-8")
    assert html.index('<section id="outro"') < html.index('<section id="signoff"')
    for needle in ('src="assets/karga.svg"', 'id="signoff-glint"', "YARIN <span class=\"accent\">YENİSİNİ</span> GETİRİRİM.",
                   'id="signoff-handle"', 'id="signoff-follow-label"', 'tl.fromTo("#signoff-follow"',
                   "signoff: [30, 1.6]"):
        assert needle in html, needle
    # §1.8 stays: the outro itself still has the handle and the follow pill
    for needle in ('id="outro-follow"', 'id="outro-handle"', 'tl.fromTo("#outro-follow"'):
        assert needle in html, needle


def test_the_crow_is_its_own_file_an_illustrator_can_replace():
    svg = (TEMPLATE / "assets" / "karga.svg").read_text(encoding="utf-8")
    assert 'viewBox="0 0 420 400"' in svg


def test_every_reel_gets_the_sign_off_and_is_that_much_longer(tmp_path):
    plan, total = hb.with_signoff(dict(hb.DEFAULT_PLAN), 21.4)
    assert plan["signoff"] == [21.4, hb.SIGNOFF] and total == round(21.4 + hb.SIGNOFF, 3)
    assert plan["outro"] == hb.DEFAULT_PLAN["outro"]
    shutil.copy(TEMPLATE / "index.html", tmp_path / "index.html")
    hb._apply_plan_to_html(tmp_path / "index.html", plan, total)
    out = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<section id="signoff"[^>]*data-start="21.4"[^>]*data-duration="1.6"', out)
    assert hb.sfx_events(plan)[-2:] == [(21.4 + 0.5, "pop"), (21.4 + 0.58, "ding")]
    src = (ROOT / "src" / "hyperframes_builder.py").read_text(encoding="utf-8")
    assert src.index("plan, total = with_signoff(plan, total)") < src.index("captions = caption_groups(words")


def test_the_length_checks_allow_the_sign_off():
    assert hb.MAX_SECONDS == 26.0 + hb.SIGNOFF
    for f in ("daily.py", "src/agent_tools.py", "src/voice_kept.py"):
        src = (ROOT / f).read_text(encoding="utf-8")
        assert re.search(r"REEL_SECONDS = \(14\.0, 27\.6\)", src), f
    rules = (ROOT / ".claude" / "skills" / "reel-retention-editor" / "SKILL.md").read_text(encoding="utf-8")
    assert "crow sign-off" in rules and "never a reason to reject" in rules
