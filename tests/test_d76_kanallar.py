"""D-76 (2026-11-14, the user): "bir çok haber kanalı takip edilecek, ilgili haberin kaynağına gidip o şirketin kendi
sayfasından ... görsel olarak da uygun bulunmazsa da ilgili şirketin herhangi görselleri alınarak haber yapılacak".
Channels FIND stories; the text and pictures come only from the company's own page (§1.9)."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import discovery  # noqa: E402

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)


def _feed(items):
    return lambda ch: [{**i, "source": ch["name"], "priority": 1} for i in items[ch["name"]]]


def test_channels_find_ai_stories_once_most_reported_first(monkeypatch):
    monkeypatch.setattr(discovery, "channels", lambda: [{"name": "A", "url": "https://a.news/f"},
                                                       {"name": "B", "url": "https://b.news/f"}])
    d = NOW.replace(hour=8)
    items = {"A": [{"title": "Perplexity launches Comet Plus agent", "url": "https://a.news/1", "date": d, "summary": ""},
                   {"title": "Best laptop deals this week", "url": "https://a.news/2", "date": d, "summary": ""}],
             "B": [{"title": "Comet Plus: Perplexity&#8217;s new agent", "url": "https://b.news/9", "date": d,
                    "summary": "AI browser"},
                   {"title": "Suno adds stems to its AI music app", "url": "https://b.news/3", "date": d,
                    "summary": ""}]}
    monkeypatch.setattr(discovery, "_items", _feed(items))
    monkeypatch.setattr(discovery, "load_history", lambda: [])
    monkeypatch.setattr(discovery, "load_titles", lambda: [])
    found = discovery.discover(10, now=NOW)
    assert [f["title"] for f in found] == ["Perplexity launches Comet Plus agent", "Suno adds stems to its AI music app"]
    assert found[0]["mentions"] == 2 and found[0]["discovered"]  # the same story on two channels, kept once


def test_only_the_companys_own_page_is_a_source(monkeypatch):
    item = {"title": "Suno adds stems to its AI music app", "url": "https://b.news/3"}
    assert discovery.checked_page({"url": "https://techcrunch.com/2026/11/14/suno", "company": "Suno"}, item) is None
    assert discovery.checked_page({"url": "", "company": "Suno"}, item) is None

    class R:
        url = "https://suno.com/blog/stems"
        text = "<h1>Stems are here</h1> split any song"

        def raise_for_status(self):
            pass
    monkeypatch.setattr(discovery.requests, "get", lambda *a, **k: R())
    assert discovery.checked_page({"url": "https://suno.com/blog/stems", "company": "Suno"}, item) == \
        {"url": "https://suno.com/blog/stems", "company": "Suno"}
    R.text = "<h1>Our team</h1>"
    assert discovery.checked_page({"url": "https://suno.com/about", "company": "Suno"}, item) is None


def test_production_uses_channels_and_the_companys_own_picture():
    cfg = json.loads((ROOT / "news_sources.json").read_text(encoding="utf-8"))
    assert len(cfg["discovery_feeds"]) >= 12
    assert any("webtekno" in f["url"] for f in cfg["discovery_feeds"])  # Turkish channels too
    d = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert "+ found, \"news_carousel\")" in d and "page = company_page(item)" in d
    assert 'item = {**item, "url": page["url"]' in d  # the story is written from the company's page
    c = (ROOT / "carousel.py").read_text(encoding="utf-8")
    assert "company_cover(item[\"url\"]" in c
