"""The daily run: what goes in the queue, in which order, and that one failure never empties the day."""

import json
import sys
import types

import pytest

import daily

SLOTS = {"slots": [{"time": "11:45", "kind": "reel"}, {"time": "12:30", "kind": "carousel"},
                   {"time": "18:00", "kind": "carousel"}, {"time": "20:30", "kind": "reel"}]}


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    """daily.py writing into tmp_path; no Instagram, no real production."""
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(daily, "schedule", lambda: SLOTS)
    monkeypatch.setitem(sys.modules, "ig_publisher", types.SimpleNamespace(refresh_token=lambda: False))
    monkeypatch.delenv("KAVAR_FORCE", raising=False)
    monkeypatch.setattr(daily, "rank", lambda c, *a, **k: c)  # no Claude call in tests
    return tmp_path


CAROUSELS = [{"kind": "carousel", "folder": "output/carousel/a", "title": "A", "tested": True},
             {"kind": "carousel", "folder": "output/carousel/b", "title": "B", "tested": False}]
REEL = {"kind": "reel", "folder": "output/reels/r", "title": "R"}
TOOL = {"kind": "reel", "folder": "output/reels/t", "title": "T"}


def _queue(sandbox):
    return json.loads(next((sandbox / "queue").glob("*.json")).read_text(encoding="utf-8"))


def test_trial_reel_comes_before_the_tool_reel(monkeypatch, sandbox):
    calls = []
    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: calls.append("trial") or REEL)
    monkeypatch.setattr(daily, "produce_reel", lambda: calls.append("tool") or TOOL)
    daily.produce()
    assert calls == ["trial", "tool"]
    q = _queue(sandbox)
    assert [x["status"] for x in q] == ["ready"] * 4
    assert (q[0]["time"], q[0]["title"]) == ("11:45", "T")  # tool Reel at noon
    assert (q[3]["time"], q[3]["title"]) == ("20:30", "R")  # Biz denedik in the evening
    assert (sandbox / "state" / "last_produce.json").exists()


def test_tool_reel_is_the_fallback(monkeypatch, sandbox):
    calls = []
    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: calls.append("trial") or None)
    tools = iter([REEL, TOOL])
    monkeypatch.setattr(daily, "produce_reel", lambda: calls.append("tool") or next(tools))
    daily.produce()
    assert calls == ["trial", "tool", "tool"]
    q = _queue(sandbox)
    assert (q[3]["title"], q[0]["title"]) == ("R", "T")


def test_a_reel_crash_keeps_the_carousels(monkeypatch, sandbox):
    def boom():
        raise RuntimeError("render died")

    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", boom)
    daily.produce()
    q = _queue(sandbox)
    assert [x["status"] for x in q] == ["empty", "ready", "ready", "empty"]
    assert q[1]["title"] == "A"


def test_carousels_are_saved_before_the_reel_stage(monkeypatch, sandbox):
    seen = {}

    def reel_stage(news):
        seen["queue"] = _queue(sandbox)
        return None

    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", reel_stage)
    monkeypatch.setattr(daily, "produce_reel", lambda: None)
    daily.produce()
    assert [x["status"] for x in seen["queue"]] == ["empty", "ready", "ready", "empty"]


def test_an_empty_day_is_not_marked_done(monkeypatch, sandbox):
    """Later scheduled runs (produce.yml) may then try again."""
    monkeypatch.setattr(daily, "produce_news_items", lambda n: [])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", lambda: None)
    daily.produce()
    assert "rest" not in daily.stages_done()  # the 08:00 run and the backups may try the rest again


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


def test_one_reel_goes_to_the_evening(monkeypatch, sandbox):
    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(CAROUSELS))
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    tools = iter([TOOL, None])
    monkeypatch.setattr(daily, "produce_reel", lambda: next(tools))
    daily.produce()
    q = _queue(sandbox)
    assert [(x["time"], x["status"]) for x in q] == [("11:45", "empty"), ("12:30", "ready"), ("18:00", "ready"),
                                                     ("20:30", "ready")]


def test_no_reel_render_starts_without_time_left(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "LOG_DIR", tmp_path)  # never write into the real day log
    monkeypatch.setattr(daily, "_STARTED", daily.time.monotonic() - daily.JOB_BUDGET)
    monkeypatch.setattr(daily, "_reel_attempt", lambda cmd=None: pytest.fail("render started"))
    assert daily.produce_reel() is None


def test_a_second_run_of_the_day_keeps_the_first_runs_queue_and_log():
    """10-17: the Reel-only run's archive replaced the morning queue (carousels showed "empty")."""
    old = [{"kind": "reel", "time": "11:45", "status": "empty"},
           {"kind": "carousel", "time": "12:30", "status": "ready", "folder": "a", "title": "Beam"},
           {"kind": "reel", "time": "20:30", "status": "empty"}]
    new = [{"kind": "reel", "time": "11:45", "status": "empty"},
           {"kind": "carousel", "time": "12:30", "status": "empty"},
           {"kind": "reel", "time": "20:30", "status": "ready", "folder": "b", "title": "Earnote"}]
    merged = daily._merge_queue(old, new)
    assert [q["status"] for q in merged] == ["empty", "ready", "ready"]
    assert merged[1]["title"] == "Beam" and merged[2]["title"] == "Earnote"


def test_a_site_that_refuses_the_cloud_does_not_eat_the_news_tries(monkeypatch, sandbox):
    """10-17: three openai.com stories failed with HTTP 403 and used half of the six tries."""
    news = [{"title": f"OpenAI story {i}", "url": f"https://openai.com/index/{i}", "source": "OpenAI"} for i in range(4)]
    news += [{"title": f"Other {i} unrelated words", "url": f"https://huggingface.co/blog/{i}", "source": "HF"}
             for i in range(3)]
    monkeypatch.setattr(daily, "fetch_news", lambda n: news)
    monkeypatch.setattr(daily, "testable_first", lambda c: c)
    monkeypatch.setattr(daily, "mark_used", lambda url: None)
    tried = []

    def produce_news(item):
        tried.append(item["url"])
        if "openai.com" in item["url"]:
            raise RuntimeError(f"capture of {item['url']} returned HTTP 403")
        raise RuntimeError("render failed")

    monkeypatch.setattr(daily, "produce_news", produce_news)
    daily.produce_news_items(2)
    assert sum("openai.com" in u for u in tried) == 1
    assert sum("huggingface.co" in u for u in tried) == 3


def test_off_concept_and_repeat_stories_are_never_used(monkeypatch, sandbox):
    """10-17 dry run: a gaming promotion reached the 18:00 slot because it was only moved down."""
    news = [{"title": "DLSS on GeForce NOW", "url": "https://blogs.nvidia.com/a", "source": "NVIDIA",
             "rank": {"score": 17, "category": "gaming_hardware", "company": "NVIDIA", "reason": "", "fits": False,
                      "repeat": False}},
            {"title": "Same as yesterday", "url": "https://x.com/b", "source": "X",
             "rank": {"score": 25, "category": "model_release", "company": "X", "reason": "", "fits": True,
                      "repeat": True}},
            {"title": "Tested model", "url": "https://hf.co/c", "source": "HF", "testable": True,
             "rank": {"score": 10, "category": "model_release", "company": "Y", "reason": "", "fits": False,
                      "repeat": False}}]
    monkeypatch.setattr(daily, "fetch_news", lambda n: news)
    monkeypatch.setattr(daily, "testable_first", lambda c: c)
    monkeypatch.setattr(daily, "mark_used", lambda url: None)
    tried = []
    monkeypatch.setattr(daily, "produce_news", lambda item: tried.append(item["title"]) or (_ for _ in ()).throw(RuntimeError("x")))
    daily.produce_news_items(2)
    assert tried == ["Tested model"]


TR_SLOTS = [{"time": "07:30", "kind": "reel", "concept": "tr"}] + SLOTS["slots"]


def test_morning_stage_makes_only_the_turkey_reel_and_next_runs_the_rest(monkeypatch, sandbox):
    """D-29: the 07:30 Turkey Reel first, on its own; the rest after it (cron-job.org 06:17 and 08:00 "next")."""
    monkeypatch.setattr(daily, "schedule", lambda: {"slots": TR_SLOTS})
    monkeypatch.setattr(daily, "produce_tr_reel", lambda: {"kind": "reel", "folder": "tr", "title": "TR", "concept": "tr"})
    calls = []
    monkeypatch.setattr(daily, "produce_news_items", lambda n: calls.append("news") or [])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", lambda: {"kind": "reel", "folder": "t", "title": "Tool"})
    daily.produce("next")
    assert calls == [] and daily.stages_done() == ["morning"]
    q = daily.load_queue()
    assert q[0]["time"] == "07:30" and q[0]["status"] == "ready" and q[0]["title"] == "TR"
    daily.produce("next")
    assert calls == ["news"] and daily.stages_done() == ["morning", "rest"]
    q = daily.load_queue()
    assert q[0]["title"] == "TR"  # the morning Reel stays when the rest is made
    assert all(x.get("concept") != "tr" for x in q[1:])  # the Turkey Reel never lands in another slot
    daily.produce("next")  # both done: nothing runs
    assert calls == ["news"]


def test_no_turkey_story_still_lets_the_rest_start(monkeypatch, sandbox):
    monkeypatch.setattr(daily, "schedule", lambda: {"slots": TR_SLOTS})
    monkeypatch.setattr(daily, "produce_tr_reel", lambda: None)
    daily.produce("morning")
    assert daily.stages_done() == ["morning"] and daily.load_queue()[0]["status"] == "empty"


def test_turkey_reel_pictures_come_from_the_institution(tmp_path):
    """User 10-17: the news site's picture only if it is the institution's own image; otherwise any picture
    from the institution's own site. Never a press photo."""
    import sys
    sys.path.insert(0, str(daily.ROOT / "src"))
    import tr_reel
    from PIL import Image

    def pic(name, color, size=(400, 300)):
        p = tmp_path / name
        img = Image.new("RGB", size, color)
        for x in range(0, size[0], 40):  # a pattern, so the hash has something to see
            for y in range(size[1]):
                img.putpixel((x, y), (255, 255, 255))
        img.save(p)
        return str(p)

    own_home = pic("home.jpg", (200, 30, 30))
    same_as_home = pic("press_same.jpg", (200, 30, 30), (800, 600))  # the institution's image, re-sized
    press_photo = pic("press_other.jpg", (10, 10, 10))
    press_photo_img = Image.new("RGB", (400, 300), (10, 10, 10))
    for y in range(0, 300, 30):
        for x in range(400):
            press_photo_img.putpixel((x, y), (255, 255, 255))
    press_photo_img.save(press_photo)
    home = {"cover_path": own_home, "figures": []}
    assert tr_reel.pictures_for({"cover_path": same_as_home}, [home])[0] == same_as_home
    got = tr_reel.pictures_for({"cover_path": press_photo}, [home])
    assert press_photo not in got and got == [own_home]
    assert tr_reel.pictures_for({"cover_path": press_photo}, []) == []
