"""D-72 (2026-11-12, the user): "D onay veriyorum olsun". The 18:00 carousel is a saveable GUIDE to an AI feature of
a known product (D-31's guide carousel, never built until now), not news. If no guide carousel is made, a news
carousel fills the slot: a slot is never left empty for it."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import daily  # noqa: E402

SLOTS = json.loads((ROOT / "schedule.json").read_text(encoding="utf-8"))["slots"]
NEWS = {"kind": "carousel", "folder": "output/carousel/x_haber-a", "title": "Haber", "tested": False}
GUIDE = {"kind": "carousel", "folder": "output/carousel/x_rehber-b", "title": "Rehber", "tested": False,
         "concept": "guide"}
MORNING = {"kind": "reel", "folder": "output/reels/x_gemini", "title": "Gemini", "concept": "guide"}


def test_the_18_00_carousel_slot_is_the_guide_one():
    by_time = {s["time"]: s for s in SLOTS}
    assert by_time["18:00"] == {"time": "18:00", "kind": "carousel", "concept": "guide"}
    assert by_time["07:30"].get("concept") == "guide" and by_time["07:30"]["kind"] == "reel"
    assert by_time["12:30"].get("concept") is None


def test_guide_carousel_goes_to_18_00_news_to_12_30_and_the_guide_reel_stays_at_07_30():
    q = {i["time"]: i for i in daily._build_queue(SLOTS, [GUIDE, NEWS], [], MORNING)}
    assert q["18:00"]["title"] == "Rehber" and q["12:30"]["title"] == "Haber"
    assert q["07:30"]["title"] == "Gemini"
    assert q["11:45"]["status"] == q["20:30"]["status"] == "empty"  # the guide carousel never fills a Reel slot


def test_a_missing_kind_is_filled_by_the_other_never_left_empty():
    q = {i["time"]: i for i in daily._build_queue(SLOTS, [dict(NEWS), dict(NEWS, title="Haber 2")], [], None)}
    assert q["12:30"]["title"] == "Haber" and q["18:00"]["title"] == "Haber 2"
    q = {i["time"]: i for i in daily._build_queue(SLOTS, [dict(GUIDE)], [], None)}
    assert q["18:00"]["status"] == "empty" or q["12:30"]["title"] == "Rehber"


def test_the_writer_editor_and_ranker_know_the_guide_carousel():
    import news_writer
    article = {"publisher": "Google", "domain": "blog.google", "published": "", "title": "t", "figures": [],
               "videos": [], "text": "x", "guide_note": news_writer.GUIDE_NOTE}
    msg = news_writer._user_message(article)
    assert "GUIDE CAROUSEL" in msg and "Kaydet" in msg
    assert "GUIDE CAROUSEL" not in news_writer._user_message({**article, "guide_note": ""})
    from content_ranker import CONCEPTS
    assert "guide_carousel" in CONCEPTS and "SAVE" in CONCEPTS["guide_carousel"]
    src = (ROOT / "carousel.py").read_text(encoding="utf-8")
    assert 'article["guide_note"] = GUIDE_NOTE' in src and "if not guide and (trial := run_trial(" in src
    assert "18:00 GUIDE carousel (D-72" in (ROOT / "src" / "editor_review.py").read_text(encoding="utf-8")
    d = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert 'rank(fetch_guide(), "guide_carousel")' in d and "if guide := produce_guide_carousel():" in d
    assert 'q.get("concept") == "guide" and q["kind"] == "reel"' in d  # the guide carousel is not the morning Reel
