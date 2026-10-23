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


GUIDE_SLOTS = [{"time": "07:30", "kind": "reel", "concept": "guide"}] + SLOTS["slots"]


def test_morning_stage_makes_only_the_guide_reel_and_next_runs_the_rest(monkeypatch, sandbox):
    """D-29/D-31: the 07:30 guide Reel first, on its own; the rest after it (cron-job.org 06:17 and 08:00 "next")."""
    monkeypatch.setattr(daily, "schedule", lambda: {"slots": GUIDE_SLOTS})
    monkeypatch.setattr(daily, "produce_guide_reel", lambda: {"kind": "reel", "folder": "g", "title": "Guide", "concept": "guide"})
    calls = []
    monkeypatch.setattr(daily, "produce_news_items", lambda n: calls.append("news") or [])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", lambda: {"kind": "reel", "folder": "t", "title": "Tool"})
    daily.produce("next")
    assert calls == [] and daily.stages_done() == ["morning"]
    q = daily.load_queue()
    assert q[0]["time"] == "07:30" and q[0]["status"] == "ready" and q[0]["title"] == "Guide"
    daily.produce("next")
    assert calls == ["news"] and daily.stages_done() == ["morning", "rest"]
    q = daily.load_queue()
    assert q[0]["title"] == "Guide"  # the morning Reel stays when the rest is made
    assert all(x.get("concept") != "guide" for x in q[1:])  # the guide Reel never lands in another slot
    daily.produce("next")  # both done: nothing runs
    assert calls == ["news"]


def test_no_guide_reel_still_lets_the_rest_start(monkeypatch, sandbox):
    monkeypatch.setattr(daily, "schedule", lambda: {"slots": GUIDE_SLOTS})
    monkeypatch.setattr(daily, "produce_guide_reel", lambda: None)
    daily.produce("morning")
    assert daily.stages_done() == ["morning"] and daily.load_queue()[0]["status"] == "empty"


def test_guide_candidates_are_unused_company_posts_of_two_weeks(monkeypatch, tmp_path):
    """D-31: guide Reels come from the companies' own blogs; a feature stays worth explaining for 14 days."""
    import sys
    from datetime import datetime, timedelta, timezone
    sys.path.insert(0, str(daily.ROOT / "src"))
    import guide_reel

    now = datetime.now(timezone.utc)
    posts = [{"title": "New in Gemini", "url": "https://g/1", "date": now - timedelta(days=9), "summary": "", "source": "Gemini"},
             {"title": "Old", "url": "https://g/2", "date": now - timedelta(days=20), "summary": "", "source": "Gemini"},
             {"title": "Used", "url": "https://g/3", "date": now - timedelta(days=1), "summary": "", "source": "Gemini"}]
    sources = tmp_path / "news_sources.json"
    sources.write_text('{"feeds": [{"name": "Gemini", "url": "u"}]}', encoding="utf-8")
    monkeypatch.setattr(guide_reel, "SOURCES_PATH", sources)
    monkeypatch.setattr(guide_reel, "_items", lambda feed: [dict(i) for i in posts])
    monkeypatch.setattr(guide_reel, "load_history", lambda: ["https://g/3"])
    assert [i["url"] for i in guide_reel.fetch_guide()] == ["https://g/1"]


def test_guide_only_sources_feed_the_guide_reel_and_not_the_news(monkeypatch, tmp_path):
    """D-41 (user 2026-10-22, "a"): 10-22 had 0 guide topics in 40 company posts three times; Google Workspace
    Updates (22 feature posts in 14 days) is read for the guide Reel only, more of its posts, no weekly recaps."""
    import sys
    from datetime import datetime, timedelta, timezone
    sys.path.insert(0, str(daily.ROOT / "src"))
    import guide_reel
    import news_fetcher

    now = datetime.now(timezone.utc)
    blog = [{"title": f"Blog {n}", "url": f"https://b/{n}", "date": now - timedelta(hours=n), "summary": "",
             "source": "Gemini", "priority": 3} for n in range(8)]
    ws = [{"title": f"Feature {n}", "url": f"https://w/{n}", "date": now - timedelta(hours=n), "summary": "",
           "source": "Google Workspace Updates", "priority": 2} for n in range(12)]
    ws.append({"title": "Google Workspace Weekly Recap - October 16, 2026", "url": "https://w/recap",
               "date": now, "summary": "", "source": "Google Workspace Updates", "priority": 2})
    sources = tmp_path / "news_sources.json"
    sources.write_text('{"max_age_hours": 72, "feeds": [{"name": "Gemini", "url": "g"}], '
                       '"guide_feeds": [{"name": "Google Workspace Updates", "url": "w"}]}', encoding="utf-8")
    by_feed = {"g": blog, "w": ws}
    for mod in (guide_reel, news_fetcher):
        monkeypatch.setattr(mod, "SOURCES_PATH", sources)
        monkeypatch.setattr(mod, "_items", lambda feed: [dict(i) for i in by_feed[feed["url"]]])
        monkeypatch.setattr(mod, "load_history", lambda: [])
    urls = [i["url"] for i in guide_reel.fetch_guide()]
    assert sum(u.startswith("https://w/") for u in urls) == 12 and "https://w/recap" not in urls
    assert sum(u.startswith("https://b/") for u in urls) == guide_reel.PER_FEED
    assert not any(i["url"].startswith("https://w/") for i in news_fetcher.fetch_news(50))  # never a news carousel


def test_guide_pictures_are_the_features_own_never_the_page(tmp_path):
    """10-18 dry runs: the shrunk page top was unreadable twice and an abstract cover proved nothing. The
    article's figures come first, the cover last, and the page screenshot is never a shot."""
    import sys
    sys.path.insert(0, str(daily.ROOT / "src"))
    import guide_reel
    from PIL import Image

    def pic(name, color, size=(1600, 900)):
        Image.new("RGB", size, color).save(tmp_path / name)
        return str(tmp_path / name)

    page = {"url": "https://blog.google/x", "page_path": pic("page.png", "white", (1350, 6000)),
            "cover_path": pic("cover.jpg", "blue"), "figures": [{"path": pic("fig_1.png", "red")}], "videos": []}
    cap = guide_reel._frames(page, tmp_path / "f")
    with Image.open(cap["proof_path"]) as proof:
        assert proof.getpixel((460, 330)) == (255, 0, 0)  # the feature's figure, not the cover
        assert proof.getpixel((460, 3)) == (10, 16, 32)  # D-38: whole (letterboxed), never cropped
    for shot in (cap["screenshot_path"], cap["fullpage_path"]):
        with Image.open(shot) as img:
            assert img.getpixel((540, 840)) != (255, 255, 255)  # never the page


def test_guide_shots_never_crop_a_picture(tmp_path):
    """10-23: the Meet Reel's only picture was cut to its middle for the second shot ("in Google Mee", editor
    reject). A shot shows a whole picture, also when the page has just one (D-42)."""
    import sys
    sys.path.insert(0, str(daily.ROOT / "src"))
    import guide_reel
    from PIL import Image

    fig = Image.new("RGB", (1600, 900), "white")
    for x in range(0, 40):  # text-like marks at the far left and right edges of the picture
        for y in range(400, 500):
            fig.putpixel((x, y), (255, 0, 0))
            fig.putpixel((1599 - x, y), (0, 0, 255))
    fig.save(tmp_path / "fig.png")
    page = {"url": "https://workspaceupdates.googleblog.com/x", "cover_path": None,
            "figures": [{"path": str(tmp_path / "fig.png")}], "videos": []}
    cap = guide_reel._frames(page, tmp_path / "f")
    for shot in (cap["screenshot_path"], cap["fullpage_path"]):
        with Image.open(shot) as img:
            colors = {img.getpixel((x, y)) for x in range(img.width) for y in range(600, 900, 3)}
            assert any(r > 200 and g < 60 and b < 60 for r, g, b in colors)  # left edge still there
            assert any(b > 200 and r < 60 and g < 60 for r, g, b in colors)  # right edge still there
    assert not hasattr(guide_reel, "_detail")


def test_trial_proof_shows_a_picture_whole(tmp_path):
    """D-42: the Biz denedik proof box cropped a picture to fill it (ImageOps.fit); it is shown whole now."""
    import sys
    sys.path.insert(0, str(daily.ROOT / "src"))
    import trial_reel
    from PIL import Image

    img = Image.new("RGB", (1600, 900), "white")
    for x in range(0, 40):
        for y in range(0, 900):
            img.putpixel((x, y), (255, 0, 0))
            img.putpixel((1599 - x, y), (0, 0, 255))
    proof = trial_reel._proof(img)
    colors = {proof.getpixel((x, 330)) for x in range(proof.width)}
    assert any(r > 200 and g < 60 and b < 60 for r, g, b in colors)
    assert any(b > 200 and r < 60 and g < 60 for r, g, b in colors)


def _feeds(monkeypatch, tmp_path, ages_hours, used=()):
    """news_fetcher over one fake feed whose items are ages_hours old; `used` urls already posted."""
    from datetime import datetime, timedelta, timezone

    import news_fetcher
    cfg = tmp_path / "sources.json"
    cfg.write_text(json.dumps({"max_age_hours": 72, "fallback_age_hours": 168, "min_fresh": 2,
                               "feeds": [{"name": "F", "url": "x"}]}), encoding="utf-8")
    now = datetime.now(timezone.utc)
    items = [{"title": f"T{h}", "url": f"https://e/{h}", "date": now - timedelta(hours=h), "summary": "",
              "source": "F", "priority": 1} for h in ages_hours]
    monkeypatch.setattr(news_fetcher, "SOURCES_PATH", cfg)
    monkeypatch.setattr(news_fetcher, "_items", lambda feed: [dict(i) for i in items])
    monkeypatch.setattr(news_fetcher, "load_history", lambda: list(used))
    return news_fetcher


def test_enough_fresh_news_keeps_the_72_hour_window(monkeypatch, tmp_path):
    nf = _feeds(monkeypatch, tmp_path, [10, 20, 100])
    assert [i["title"] for i in nf.fetch_news(20)] == ["T10", "T20"]


def test_thin_weekend_news_is_topped_up_from_7_days(monkeypatch, tmp_path):
    # D-35: 10-19 (Monday) had one unused item in 72 h (an SSD ad) and the day got 0 carousels
    nf = _feeds(monkeypatch, tmp_path, [10, 100, 150, 200], used=["https://e/150"])
    assert [i["title"] for i in nf.fetch_news(20)] == ["T10", "T100"]  # fresh first; used, >168 h out


D38 = {"guide_reel": True, "tool_reels": False,
       "slots": [{"time": "12:30", "kind": "carousel"}, {"time": "20:30", "kind": "reel"}]}
GUIDE = {"kind": "reel", "folder": "output/reels/g", "title": "Guide", "concept": "guide"}


def test_d38_guide_reel_fills_the_evening_and_no_tool_reel_is_made(monkeypatch, sandbox):
    """D-38 (user 2026-10-22): one carousel + one Reel; the guide Reel fills 20:30 when there is no
    "Biz denedik" Reel, and Product Hunt tool Reels are paused."""
    monkeypatch.setattr(daily, "schedule", lambda: D38)
    monkeypatch.setattr(daily, "SURPLUS_DIR", sandbox / "output" / "reserve")
    monkeypatch.setattr(daily, "produce_guide_reel", lambda: dict(GUIDE))
    monkeypatch.setattr(daily, "produce_news_items", lambda n: [dict(CAROUSELS[1])])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", lambda: pytest.fail("tool Reels are paused"))
    daily.produce()
    assert [(q["time"], q.get("title"), q["status"]) for q in _queue(sandbox)] == [
        ("12:30", "B", "ready"), ("20:30", "Guide", "ready")]
    assert not (sandbox / "output" / "reserve").exists()  # nothing spare
    assert not daily.empty_day()


def test_d38_biz_denedik_keeps_the_evening_and_the_guide_reel_is_kept(monkeypatch, sandbox):
    """§1.4 stays: the "Biz denedik" Reel takes 20:30; the approved guide Reel goes to the reserve (D-37)."""
    monkeypatch.setattr(daily, "schedule", lambda: D38)
    monkeypatch.setattr(daily, "SURPLUS_DIR", sandbox / "output" / "reserve")
    monkeypatch.setattr(daily, "produce_guide_reel", lambda: dict(GUIDE))
    monkeypatch.setattr(daily, "produce_news_items", lambda n: [dict(CAROUSELS[0])])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: dict(REEL))
    daily.produce()
    q = _queue(sandbox)
    assert (q[1]["time"], q[1]["title"]) == ("20:30", "R")
    spare = json.loads(next((sandbox / "output" / "reserve").glob("*.json")).read_text(encoding="utf-8"))
    assert [s["title"] for s in spare] == ["Guide"]


def test_d38_an_empty_day_is_reported(monkeypatch, sandbox):
    """D-38: 10-22 made 0/5 and GitHub showed success; an empty queue now ends the run with exit 1."""
    monkeypatch.setattr(daily, "schedule", lambda: D38)
    monkeypatch.setattr(daily, "produce_guide_reel", lambda: None)
    monkeypatch.setattr(daily, "produce_news_items", lambda n: [])
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    daily.produce()
    assert daily.empty_day()
