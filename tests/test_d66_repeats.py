"""D-66 (2026-11-12): two posts of 13 Nov repeated posts of 12 Nov.
- "Gemini 4 Carbon is now available" was on blog.google (used 11-11) and deepmind.google (picked 11-12):
  the news history held URLs only.
- Kippy AI was made in a test run and posted; Mister Blocks sat in the reserve. Production made both again:
  test runs commit no state, and the reserve was not counted as used."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import news_fetcher  # noqa: E402
import script_writer  # noqa: E402

CARBON = "Gemini 4 Carbon is now available"


def _news(monkeypatch, tmp_path, items, used_urls=()):
    cfg = tmp_path / "sources.json"
    cfg.write_text(json.dumps({"max_age_hours": 72, "fallback_age_hours": 168, "min_fresh": 1,
                               "feeds": [{"name": "F", "url": "x"}]}), encoding="utf-8")
    hist = tmp_path / "news_history.json"
    hist.write_text(json.dumps(list(used_urls)), encoding="utf-8")
    monkeypatch.setattr(news_fetcher, "SOURCES_PATH", cfg)
    monkeypatch.setattr(news_fetcher, "HISTORY_PATH", hist)
    monkeypatch.setattr(news_fetcher, "TITLES_PATH", tmp_path / "news_titles.json")
    monkeypatch.setattr(news_fetcher.buzz, "annotate", lambda items: None)
    now = datetime.now(timezone.utc)
    rows = [{"title": t, "url": u, "date": now - timedelta(hours=h), "summary": "", "source": "F", "priority": 1}
            for t, u, h in items]
    monkeypatch.setattr(news_fetcher, "_items", lambda feed: [dict(r) for r in rows])


def test_the_same_news_on_a_second_blog_is_skipped_after_it_was_used(monkeypatch, tmp_path):
    _news(monkeypatch, tmp_path, [(CARBON, "https://deepmind.google/blog/gemini-4-carbon-is-now-available/", 20),
                                  ("Try Tabletop", "https://blog.google/tabletop/", 10)])
    news_fetcher.mark_used("https://blog.google/gemini-4-carbon-now-available/", CARBON)  # the 11-11 carousel
    assert [i["title"] for i in news_fetcher.fetch_news(10)] == ["Try Tabletop"]


def test_the_same_title_twice_in_one_fetch_is_one_item(monkeypatch, tmp_path):
    _news(monkeypatch, tmp_path, [(CARBON, "https://blog.google/carbon/", 20),
                                  (CARBON.upper() + "!", "https://deepmind.google/carbon/", 21)])
    assert len(news_fetcher.fetch_news(10)) == 1


def test_a_reserve_reel_and_a_voiced_test_reel_count_as_used(monkeypatch, tmp_path):
    reserve = tmp_path / "reserve.json"
    reserve.write_text(json.dumps([{"kind": "reel", "title": "Mister Blocks"},
                                   {"kind": "carousel", "title": "Some news"}]), encoding="utf-8")
    monkeypatch.setattr(script_writer, "RESERVE_PATH", reserve)
    monkeypatch.setattr(script_writer, "USED_TOOLS_PATH", tmp_path / "used_tools.json")
    monkeypatch.setattr(script_writer, "_load_history", lambda: [])
    assert script_writer.used_tools() == ["Mister Blocks"]
    script_writer.remember_tool("Kippy AI")  # voice.yml, a test-run Reel going out
    script_writer.remember_tool("Kippy AI")
    assert json.loads((tmp_path / "used_tools.json").read_text(encoding="utf-8")) == ["Kippy AI"]
    assert set(script_writer.used_tools()) == {"Mister Blocks", "Kippy AI"}


def test_voice_yml_records_the_tool_and_commits_it():
    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "voice.yml").read_text(encoding="utf-8")
    assert "remember_tool" in wf and "git add state/used_tools.json" in wf and "git push" in wf
