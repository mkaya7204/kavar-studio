"""D-37: approved posts that never went out are kept ready for an empty slot, files and all."""

import json
import sys
import types
from datetime import date

import pytest

import daily
import reserve


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(reserve, "ROOT", tmp_path)
    monkeypatch.setattr(reserve, "INDEX", tmp_path / "state" / "reserve.json")
    monkeypatch.setattr(reserve, "STORE", tmp_path / "reserve")
    return tmp_path


def _reel(root, name="2026-10-21_stella"):
    d = root / "output" / "reels" / name
    (d / "_frames").mkdir(parents=True)
    for f in ("upload.mp4", "cover.jpg", "post.json", "script.json", "final_video.mp4"):
        (d / f).write_text("x", encoding="utf-8")
    return {"kind": "reel", "folder": f"output/reels/{name}", "title": "Stella"}


def test_a_kept_post_is_ready_to_schedule_and_listed_once(store):
    item = _reel(store)
    entry = reserve.add(item, "2026-10-21")
    kept = store / entry["folder"]
    assert (kept / "upload.mp4").exists() and (kept / "cover.jpg").exists() and (kept / "post.json").exists()
    assert not (kept / "_frames").exists() and not (kept / "final_video.mp4").exists()  # only what posting needs
    assert reserve.add(item, "2026-10-21") is None  # never twice
    assert [r["title"] for r in reserve.load()] == ["Stella"]
    assert entry["editor"] == "publish" and entry["concept"] == "tool"


def test_a_posted_item_leaves_the_reserve_with_its_files(store):
    entry = reserve.add(_reel(store), "2026-10-21")
    reserve.used(1)
    assert reserve.load() == [] and not (store / entry["folder"]).exists()


def test_old_news_is_marked_not_current():
    news = {"kind": "carousel", "made": "2026-10-17"}
    assert reserve.current(news, date(2026, 10, 21)) and not reserve.current(news, date(2026, 10, 22))
    assert reserve.current({"kind": "reel", "made": "2026-10-10"}, date(2026, 10, 22))


SLOTS = {"slots": [{"time": "11:45", "kind": "reel"}, {"time": "12:30", "kind": "carousel"},
                   {"time": "18:00", "kind": "carousel"}, {"time": "20:30", "kind": "reel"}]}


def test_approved_posts_without_a_slot_go_to_the_reserve(monkeypatch, store):
    monkeypatch.setattr(daily, "ROOT", store)
    monkeypatch.setattr(daily, "QUEUE_DIR", store / "output" / "queue")
    monkeypatch.setattr(daily, "LOG_DIR", store / "output" / "logs")
    monkeypatch.setattr(daily, "SURPLUS_DIR", store / "output" / "reserve")
    monkeypatch.setattr(daily, "schedule", lambda: SLOTS)
    monkeypatch.setitem(sys.modules, "ig_publisher", types.SimpleNamespace(refresh_token=lambda: False))
    monkeypatch.delenv("KAVAR_FORCE", raising=False)
    news = [{"kind": "carousel", "folder": f"output/carousel/{n}", "title": n, "tested": False} for n in "abc"]
    for n in news:
        (store / n["folder"] / "carousel").mkdir(parents=True)
        (store / n["folder"] / "caption.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(daily, "produce_news_items", lambda n: list(news))
    monkeypatch.setattr(daily, "produce_trial_reel", lambda news: None)
    monkeypatch.setattr(daily, "produce_reel", lambda: None)
    daily.produce()
    queue = json.loads(next((store / "output" / "queue").glob("*.json")).read_text(encoding="utf-8"))
    assert [q.get("title") for q in queue if q["kind"] == "carousel"] == ["a", "b"]
    daily._import_surplus()  # what `fetch` does after unpacking
    kept = reserve.load()
    assert [r["title"] for r in kept] == ["c"] and kept[0]["concept"] == "news"
    assert (store / kept[0]["folder"] / "caption.txt").exists()


def test_nothing_spare_writes_no_surplus(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "SURPLUS_DIR", tmp_path / "reserve")
    daily._save_surplus([])
    assert not (tmp_path / "reserve").exists()
