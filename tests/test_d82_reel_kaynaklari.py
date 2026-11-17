"""D-82 / COMMITMENTS #26 (user 11-14 "bütün o haber kaynaklarından beslensek", 11-15 "Reel kaynağı yapalım"):
tool Reels also come from GitHub (new AI projects people starred) and from the news channels' launch stories."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fetcher  # noqa: E402


def repo(**kw):
    base = {"name": "deskmate", "description": "An open-source AI assistant that drafts your email replies",
            "topics": ["ai", "llm"], "homepage": "https://deskmate.app", "html_url": "https://github.com/x/deskmate",
            "fork": False, "archived": False}
    return {**base, **kw}


def test_a_starred_ai_project_becomes_a_tool_with_its_own_site():
    tool = fetcher._github_tool(repo())
    assert tool and tool.source == "GitHub" and str(tool.website_url).startswith("https://deskmate.app")
    assert tool.discussion_url == "https://github.com/x/deskmate"


def test_without_a_homepage_the_repository_is_the_site():
    tool = fetcher._github_tool(repo(homepage=""))
    assert tool and "github.com/x/deskmate" in str(tool.website_url)


def test_lists_courses_papers_and_non_ai_projects_are_not_tools():
    assert fetcher._github_tool(repo(name="awesome-llm-apps", description="A curated list of LLM apps")) is None
    assert fetcher._github_tool(repo(description="Course: learn to build AI agents in 10 lessons")) is None
    assert fetcher._github_tool(repo(description="A fast static site generator", topics=["web"])) is None
    assert fetcher._github_tool(repo(fork=True)) is None


def test_github_search_failure_never_stops_the_day(monkeypatch):
    def boom(*a, **k):
        raise fetcher.requests.RequestException("down")
    monkeypatch.setattr(fetcher.requests, "get", boom)
    assert fetcher.fetch_github(3) == []


def test_used_tools_are_skipped(monkeypatch):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"items": [repo(), repo(name="notetaker", description="AI meeting notes that write themselves")]}
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: R())
    names = [t.tool_name for t in fetcher.fetch_github(3, skip={fetcher._fold("deskmate")})]
    assert names == ["notetaker"]


def test_only_launch_stories_from_the_channels_are_looked_up():
    stories = [{"title": "OpenAI launches a new shopping assistant in ChatGPT"},
               {"title": "Anthropic raises funding at a new valuation"},
               {"title": "Google, Gemini için yeni bir uygulama tanıttı"}]
    assert [s["title"] for s in fetcher.launch_candidates(stories)] == [stories[0]["title"], stories[2]["title"]]


def test_a_news_launch_needs_the_products_own_page(monkeypatch):
    story = {"title": "Acme launches Pal, an AI travel planner", "url": "https://techcrunch.com/x", "source": "TechCrunch"}
    assert fetcher.news_tool_from({"product": "Pal", "url": "https://techcrunch.com/pal"}, story) is None  # news site
    assert fetcher.news_tool_from({"product": "", "url": ""}, story) is None

    class R:
        url = "https://pal.acme.com/"
        text = "<html><meta name='description' content='Pal plans your trip with AI'>Pal by Acme</html>"

        def raise_for_status(self):
            pass
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: R())
    tool = fetcher.news_tool_from({"product": "Pal", "url": "https://pal.acme.com"}, story)
    assert tool and tool.tool_name == "Pal" and tool.source == "TechCrunch" and tool.discussion_url == ""


def test_the_daily_tool_list_asks_all_four_sources():
    src = Path(fetcher.__file__).read_text(encoding="utf-8")
    body = src[src.index("def fetch_latest_tools("):]
    for call in ("fetch_show_hn(", "fetch_github(", "fetch_news_tools("):
        assert call in body


def test_the_guide_carousel_never_picks_a_shopping_or_payment_page():
    """11-14 dry run 43571295790: the Edge shopping guide carried prices on its cover (§1.1)."""
    import daily
    for title in ("Shop smarter with Copilot in Edge", "Pay with ChatGPT Wallet", "Find deals with Gemini"):
        assert daily.MONEY_TOPIC.search(title), title
    for title in ("Turn notes into interactive sites with Gemini Notebook", "Regional voices in the Gemini app"):
        assert not daily.MONEY_TOPIC.search(title), title


def test_the_news_channels_are_asked_once_per_run(monkeypatch):
    """11-17 dry run 44045532487: 4 look-ups instead of 2 (each Reel attempt fetched the tools again)."""
    import discovery
    calls = []
    monkeypatch.setattr(fetcher, "_NEWS_TOOLS_CACHE", None)
    monkeypatch.setattr(discovery, "discover", lambda n: [{"title": "Acme launches Pal", "url": "u", "source": "X"}])
    monkeypatch.setattr(fetcher, "_news_tool", lambda s: calls.append(s) or None)
    fetcher.fetch_news_tools(2)
    fetcher.fetch_news_tools(2)
    assert len(calls) == 1
