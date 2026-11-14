"""D-56 (user 2026-11-03): a run makes the NEXT day's posts; the morning "yükle" schedules what the day before
made and keeps the new run for tomorrow. Posts must not say "bugün" / "dün", they go out a day later."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import daily
from news_writer import news_problems
from script_writer import NO_PRICE_RULE, caption_problems, day_words

ROOT = Path(__file__).resolve().parent.parent
TOMORROW = date.today() + timedelta(days=1)
SLOTS = {"publish_lag_days": 1, "slots": [{"time": "12:30", "kind": "carousel"}, {"time": "20:30", "kind": "reel"}]}


@pytest.fixture
def lagged(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(daily, "schedule", lambda: SLOTS)
    monkeypatch.setattr(daily, "_PRODUCING", False)
    monkeypatch.delenv("KAVAR_FORCE", raising=False)
    monkeypatch.setattr(daily, "rank", lambda c, *a, **k: c)
    return tmp_path


def test_the_live_schedule_makes_tomorrows_posts():
    cfg = json.loads((ROOT / "schedule.json").read_text(encoding="utf-8"))
    assert cfg["publish_lag_days"] == 1


def test_the_cloud_guard_checks_the_day_the_posts_are_for():
    wf = (ROOT / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
    assert "publish_lag_days" in wf and "timedelta(days=lag)" in wf


def test_a_run_writes_tomorrows_queue_and_marker(monkeypatch, lagged):
    monkeypatch.setattr(daily, "produce_news_items", lambda n: [{"kind": "carousel", "folder": "c", "title": "C"}])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", lambda **_: None)
    monkeypatch.setattr(daily, "produce_guide_reel", lambda: None)
    daily.produce("rest")
    assert (lagged / "queue" / f"{TOMORROW.isoformat()}.json").exists()
    assert not (lagged / "queue" / f"{date.today().isoformat()}.json").exists()
    marker = json.loads((lagged / "state" / "last_produce.json").read_text(encoding="utf-8"))
    assert marker["date"] == TOMORROW.isoformat()
    assert "rest" in daily.stages_done()


def test_todays_posts_on_the_pc_are_the_queue_made_yesterday(lagged):
    daily.save_queue([{"kind": "carousel", "time": "12:30", "status": "ready", "title": "made yesterday"}])
    assert (lagged / "queue" / f"{date.today().isoformat()}.json").exists()  # not producing: today's file
    assert daily.load_queue()[0]["title"] == "made yesterday"


def test_a_marker_for_today_does_not_stop_tomorrows_run(lagged):
    (lagged / "state").mkdir()
    (lagged / "state" / "last_produce.json").write_text(json.dumps({"date": date.today().isoformat()}))
    assert daily.stages_done() == []  # 11-03: today's run made 11-03; the 11-04 run must still go


def test_day_words_are_caught_but_dunya_is_not():
    assert day_words("Google bugün duyurdu", "Dün açıkladı", "yarına kadar", "Bugünden itibaren") == \
        ["Bugünden", "Dün", "bugün", "yarına"]
    assert day_words("dünya modeli", "6 Ekim'de yeni duyurdu", "Dündar") == []


def test_a_caption_with_bugun_is_refused_and_writers_are_told():
    problems = caption_problems("OpenAI bugün yeni bir model duyurdu, herkes deneyebilir artık.", ["#a", "#b", "#c"])
    assert any("D-56" in p for p in problems)
    assert "'bugün'" in NO_PRICE_RULE  # every writer prompt and the editor load NO_PRICE_RULE


def test_news_slides_with_dun_are_refused():
    slide = type("S", (), {"role": "body", "title": "Ne oldu?", "body": "Şirket dün yeni modeli açtı.", "alt_text": "",
                           "visual": "none", "visual_index": 0})()
    script = type("N", (), {"caption": "Şirket yeni modelini açtı ve herkes deneyebilir artık.", "hashtags": ["#a", "#b", "#c"],
                            "slides": [slide], "story": [], "figures": 0, "videos": 0})()
    assert any("D-56" in p for p in news_problems(script))
