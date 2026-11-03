"""D-59 (user 2026-11-03, "onay veriyorum"): news also from AI labs with no RSS, read from their own news page,
and "what is talked about" (Hacker News, Hugging Face trending) used only to put those stories first."""

import json
from datetime import datetime, timezone
from pathlib import Path

import buzz
import page_sources

ROOT = Path(__file__).resolve().parent.parent


def test_the_labs_with_no_rss_are_read_from_their_own_pages():
    cfg = json.loads((ROOT / "news_sources.json").read_text(encoding="utf-8"))
    names = {p["name"] for p in cfg["pages"]}
    assert {"Anthropic", "xAI", "DeepSeek", "MiniMax", "Kimi (Moonshot AI)", "Black Forest Labs"} <= names
    assert {"Mistral AI", "Ai2", "Ollama"} <= {f["name"] for f in cfg["feeds"]}  # D-58


def test_post_links_title_and_date_come_from_the_labs_own_page():
    listing = '<a href="/news/claude-5">x</a><a href="/news/claude-5">x</a><a href="/careers">c</a>' \
              '<a href="https://www.anthropic.com/news/announcements?x=1">a</a>'
    assert page_sources.post_links(listing, "https://www.anthropic.com/news", r"/news/[a-z0-9-]+") == \
        ["https://www.anthropic.com/news/claude-5", "https://www.anthropic.com/news/announcements"]
    # 11-03 og:titles as the labs write them
    assert page_sources.clean_title("Runway News | Introducing Solaris", "Runway") == "Introducing Solaris"
    assert page_sources.clean_title("MiniMax H3: An Open Model - MiniMax", "MiniMax") == "MiniMax H3: An Open Model"
    tagged = '<meta property="article:published_time" content="2026-10-14T00:00:00.000Z"/>'
    assert page_sources.post_date(tagged) == datetime(2026, 10, 14, tzinfo=timezone.utc)
    assert page_sources.post_date('<p>Published Oct 31, 2026 by DeepSeek</p>').date().isoformat() == "2026-10-31"


def test_a_versioned_model_that_is_trending_goes_first():
    stories = [{"title": "Open weights are winning", "points": 2911, "url": ""},  # 11-03: matched MiniMax by "open"
               {"title": "Anthropic files S-1 with the SEC", "points": 236, "url": ""}]
    trending = ["deepseek-ai/DeepSeek-V4.1-Flash-1017", "black-forest-labs/flux-3-image-klein-comfy"]
    deepseek = {"source": "DeepSeek", "title": "DeepSeek-V4.1-Flash-1017: Wish-Driven Programming Made Real"}
    minimax = {"source": "MiniMax", "title": "MiniMax Music 3.0: Next-Generation Open-Weights, Production-Ready"}
    flash = {"source": "MiniMax", "title": "MiniMax M3.1 Flash: Redefining Agent Performance"}  # "Flash" alone: no
    bfl = {"source": "Black Forest Labs", "title": "Martin Scorsese x Black Forest Labs"}  # company name alone: no
    anthropic = {"source": "Anthropic", "title": "Anthropic files S-1 with the SEC for proposed IPO"}
    assert buzz.score(deepseek, stories, trending)[0] == 100
    assert buzz.score(minimax, stories, trending)[0] == 0
    assert buzz.score(flash, stories, trending)[0] == 0
    assert buzz.score(bfl, stories, trending)[0] == 0
    assert buzz.score(anthropic, stories, trending)[0] == 236


def test_the_talked_about_note_reaches_the_ranker_and_a_failure_never_stops_the_news(monkeypatch):
    item = {"source": "DeepSeek", "title": "DeepSeek-V4.1-Flash-1017 is out", "summary": "s"}
    monkeypatch.setattr(buzz, "hn_stories", lambda: [])
    monkeypatch.setattr(buzz, "hf_trending", lambda: ["deepseek-ai/DeepSeek-V4.1-Flash-1017"])
    buzz.annotate([item])
    assert item["buzz"] == 100 and item["summary"].startswith("[Şu an konuşuluyor:")

    def down():
        raise buzz.requests.ConnectionError("down")

    monkeypatch.setattr(buzz, "hn_stories", down)
    assert buzz.annotate([{"title": "x"}]) == [{"title": "x"}]
