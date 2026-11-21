"""D-87 (user 2026-11-21 "Yapılsın, ölçelim"): a tool the ranker marked OFF may still fill a Reel slot (tried after
the ranker's picks), and it is marked so its numbers can be compared."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def test_off_tools_come_last_and_are_marked(monkeypatch):
    import content_ranker
    import main

    def fake_rank(listing, concept, kind_prefix=""):
        return [{**c, "rank": {"score": 5, "fits": "Dev" not in c["title"], "reason": "x", "repeat": False}}
                for c in listing]

    monkeypatch.setattr(content_ranker, "rank", fake_rank)
    tools = [{"tool_name": "DevThing", "tag_line": "AI agent for developers", "description": "AI"},
             {"tool_name": "Notes", "tag_line": "AI notes", "description": "AI notes app"}]
    ranked = main.ai_tools_first(tools)
    assert [t["tool_name"] for t in ranked] == ["Notes", "DevThing"]
    assert ranked[1].get("ranker_off") is True and not ranked[0].get("ranker_off")


def test_news_skips_the_guide_carousels_company():
    """D-88: a Reel + a carousel of one company is fine; two carousels of one company never."""
    import inspect

    import daily
    assert "taken" in inspect.signature(daily.produce_news_items).parameters
    src = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert 'taken = {n["company"] for n in news if n.get("company")}' in src
    assert "produce_news_items(wanted, taken)" in src
    assert '"company": (r.get("brand") or r.get("company") or "").strip().lower()' in src


def test_the_queue_marks_an_off_reel():
    src = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert '"ranker_off": True' in src and "ranker OFF tool queued" in src
