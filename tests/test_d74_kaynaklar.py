"""D-74 (2026-11-14, the user): "A için ... başka kaynaklardan da baksan, tek bir kaynakta sürekli olmayabilir veya
başka kaynaklarda daha iyi kaliteli içerik yakalarsın". Tool candidates also come from Hacker News Show HN (tools
people voted up and discussed), and the experiences search starts from that discussion."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import fetcher  # noqa: E402


def test_a_show_hn_ai_post_becomes_a_tool_with_its_discussion():
    t = fetcher._show_hn_tool({"title": "Show HN: Atticus – Hold-to-talk voice assistant for macOS",
                               "url": "https://atticus.app/?ref=hn", "objectID": "123"})
    assert t.tool_name == "Atticus" and t.source == "Hacker News"
    assert t.discussion_url == "https://news.ycombinator.com/item?id=123" and "ref=" not in str(t.website_url)
    for title in ("Show HN: A faster grep written in Rust", "Show HN: Made an open-source Lego AI generator"):
        assert fetcher._show_hn_tool({"title": title, "url": "https://x.dev", "objectID": "1"}) is None


def test_show_hn_is_a_second_source_and_the_search_starts_from_its_thread(monkeypatch):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"hits": [
                {"title": "Show HN: Notely – AI meeting notes", "url": "https://notely.app", "objectID": "1",
                 "num_comments": 40},
                {"title": "Show HN: Kai – AI agent for spreadsheets", "url": "https://kai.dev", "objectID": "2",
                 "num_comments": 90}]}
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: R())
    tools = fetcher.fetch_show_hn(5, skip={fetcher._fold("Notely")})
    assert [t.tool_name for t in tools] == ["Kai"]  # already used tools are skipped
    src = (ROOT / "src" / "fetcher.py").read_text(encoding="utf-8")
    assert "tools += fetch_show_hn(HN_TOOLS" in src
    assert 'tool.get("discussion_url")' in (ROOT / "src" / "experiences.py").read_text(encoding="utf-8")
    assert 't.get("source") or "Product Hunt"' in (ROOT / "main.py").read_text(encoding="utf-8")
