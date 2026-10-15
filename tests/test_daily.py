"""The daily run: what goes in the queue, in which order, and that one failure never empties the day."""

import json
import sys
import types

import pytest

import daily

SLOTS = {"slots": [{"time": "12:30", "kind": "carousel"}, {"time": "18:00", "kind": "carousel"},
                   {"time": "20:30", "kind": "reel"}]}


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    """daily.py writing into tmp_path; no Instagram, no real production."""
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(daily, "schedule", lambda: SLOTS)
    monkeypatch.setitem(sys.modules, "ig_publisher", types.SimpleNamespace(refresh_token=lambda: False))
    monkeypatch.delenv("KAVAR_FORCE", raising=False)
    return tmp_path


CAROUSELS = [{"kind": "carousel", "folder": "output/carousel/a", "title": "A", "tested": True},
             {"kind": "carousel", "folder": "output/carousel/b", "title": "B", "tested": False}]
REEL = {"kind": "reel", "folder": "output/reels/r", "title": "R"}


def _queue(sandbox):
    return json.loads(next((sandbox / "queue").glob("*.json")).read_text(encoding="utf-8"))


def test_trial_reel_comes_before_the_tool_reel(monkeypatch, sandbox):
    calls = []
    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: calls.append("trial") or REEL)
    monkeypatch.setattr(daily, "produce_reel", lambda: calls.append("tool") or None)
    daily.produce()
    assert calls == ["trial"]
    assert [q["status"] for q in _queue(sandbox)] == ["ready", "ready", "ready"]
    assert (sandbox / "state" / "last_produce.json").exists()


def test_tool_reel_is_the_fallback(monkeypatch, sandbox):
    calls = []
    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: calls.append("trial") or None)
    monkeypatch.setattr(daily, "produce_reel", lambda: calls.append("tool") or REEL)
    daily.produce()
    assert calls == ["trial", "tool"]
    assert _queue(sandbox)[2]["title"] == "R"


def test_a_reel_crash_keeps_the_carousels(monkeypatch, sandbox):
    def boom():
        raise RuntimeError("render died")

    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", boom)
    daily.produce()
    q = _queue(sandbox)
    assert [x["status"] for x in q] == ["ready", "ready", "empty"]
    assert q[0]["title"] == "A"


def test_carousels_are_saved_before_the_reel_stage(monkeypatch, sandbox):
    seen = {}

    def reel_stage(news):
        seen["queue"] = _queue(sandbox)
        return None

    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", reel_stage)
    monkeypatch.setattr(daily, "produce_reel", lambda: None)
    daily.produce()
    assert [x["status"] for x in seen["queue"]] == ["ready", "ready", "empty"]


def test_an_empty_day_is_not_marked_done(monkeypatch, sandbox):
    """Later scheduled runs (produce.yml) may then try again."""
    monkeypatch.setattr(daily, "produce_news_items", lambda n: [])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", lambda: None)
    daily.produce()
    assert not (sandbox / "state" / "last_produce.json").exists()


def test_a_done_day_is_skipped(monkeypatch, sandbox):
    from datetime import date

    (sandbox / "state").mkdir()
    (sandbox / "state" / "last_produce.json").write_text(json.dumps({"date": date.today().isoformat()}))
    monkeypatch.setattr(daily, "produce_news_items", lambda n: pytest.fail("ran twice"))
    daily.produce()


def test_tested_carousel_takes_the_first_slot_and_one_bad_story_never_stops_the_day(monkeypatch, sandbox):
    items = [{"title": "plain", "url": "u1", "source": "s"}, {"title": "broken", "url": "u2", "source": "s"},
             {"title": "tested", "url": "u3", "source": "s"}]
    monkeypatch.setattr(daily, "fetch_news", lambda n: items)
    monkeypatch.setattr(daily, "testable_first", lambda c: c)
    monkeypatch.setattr(daily, "mark_used", lambda url: None)

    def produce_news(item):
        if item["title"] == "broken":
            raise KeyError("something unexpected")
        folder = sandbox / item["title"]
        (folder / "article").mkdir(parents=True)
        art = {"trial_note": "KAVAR TEST"} if item["title"] == "tested" else {}
        (folder / "article" / "article.json").write_text(json.dumps(art))
        return folder

    monkeypatch.setattr(daily, "produce_news", produce_news)
    monkeypatch.setattr(daily, "_reviewed_news", lambda folder: (True, []))
    news = daily.produce_news_items(2)
    assert [n["title"] for n in news] == ["tested", "plain"]


def test_daily_uses_the_ranking():
    import inspect

    assert "testable_first(fetch_news(" in inspect.getsource(daily.produce_news_items)
