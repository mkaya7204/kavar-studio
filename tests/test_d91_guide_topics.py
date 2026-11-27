"""D-91 (user 2026-11-27 "İkisi birlikte yapalım"): the guide topics never run dry. 11-25..11-27 the guide pool had
100 company posts and 0 that fit (dry run 45954300422): (a) the official help centres' how-to pages join the pool,
(b) the 18:00 guide carousel first takes the topic of the morning's approved 07:30 guide Reel."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import daily  # noqa: E402
import guide_reel  # noqa: E402

GEMINI_INDEX = """
<a class="x" href="/gemini/answer/15274899?hl=en&amp;ref_topic=15280100">Talk naturally with Gemini Live</a>
<a href="/gemini/answer/16316416?hl=en&amp;ref_topic=13194540"><span>Schedules in</span> Gemini Apps</a>
<a href="/gemini/answer/15274899?hl=en&amp;ref_topic=13194540">Talk naturally with Gemini Live</a>
<a href="/gemini/community?hl=en">Community</a>
"""
CHATGPT_INDEX = '<a href="/en/articles/11487532-chatgpt-record">ChatGPT Record Capture and summarize meetings</a>'


def test_help_centre_links_are_read_cleaned_and_once():
    links = guide_reel.help_links(GEMINI_INDEX, "https://support.google.com/gemini/?hl=en")
    assert links == [("https://support.google.com/gemini/answer/15274899?hl=en", "Talk naturally with Gemini Live"),
                     ("https://support.google.com/gemini/answer/16316416?hl=en", "Schedules in Gemini Apps")]
    links = guide_reel.help_links(CHATGPT_INDEX, "https://help.openai.com/en/collections/3742473-chatgpt")
    assert links == [("https://help.openai.com/en/articles/11487532-chatgpt-record",
                      "ChatGPT Record Capture and summarize meetings")]


def test_help_pages_join_the_pool_unused_only(monkeypatch):
    class Resp:
        text = GEMINI_INDEX

        def raise_for_status(self):
            return None

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp())
    used = {"https://support.google.com/gemini/answer/15274899?hl=en"}
    items = guide_reel.help_topics([{"name": "Gemini Help", "url": "https://support.google.com/gemini/?hl=en"}],
                                   used, [])
    assert [i["url"] for i in items] == ["https://support.google.com/gemini/answer/16316416?hl=en"]
    assert items[0]["source"] == "Gemini Help" and items[0]["help_page"] and items[0]["date"]
    names = {p["name"] for p in __import__("json").loads((ROOT / "news_sources.json").read_text(
        encoding="utf-8"))["guide_pages"]}
    assert {"Gemini Help", "ChatGPT Help"} <= names


def test_the_guide_carousel_takes_the_morning_reels_topic_first(monkeypatch):
    queue = [{"kind": "reel", "concept": "guide", "status": "ready", "time": "07:30", "title": "Gemini",
              "post_url": "https://blog.google/products/gemini/canvas-tips/",
              "post_title": "Here are 4 things you didn't know you could do with Gemini Canvas",
              "post_source": "Google Blog"},
             {"kind": "carousel", "time": "12:30", "status": "ready"}]
    monkeypatch.setattr(daily, "load_queue", lambda day=None: queue)
    topic = daily._morning_guide_topic()
    assert topic and topic[0]["url"].endswith("canvas-tips/") and topic[0]["source"] == "Google Blog"
    monkeypatch.setattr(daily, "load_queue", lambda day=None: [{**queue[0], "status": "empty"}])
    assert daily._morning_guide_topic() == []
    src = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert 'candidates = morning + rank(fetch_guide(), "guide_carousel")' in src
    assert src.count('for k in ("post_url", "post_title", "post_source") if tool.get(k)') == 2  # dry and production
