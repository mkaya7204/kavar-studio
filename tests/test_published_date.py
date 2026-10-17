"""The slide date comes from the news feed, not the page (10-17: HF pages gave wrong dates)."""
import ast
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _feed_published():
    # carousel.py imports the render stack; load only this function
    src = (ROOT / "carousel.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "feed_published")
    ns: dict = {}
    exec(compile(ast.Module([fn], []), "carousel.py", "exec"), ns)
    return ns["feed_published"]


def test_feed_date_wins_over_page():
    f = _feed_published()
    d = datetime(2026, 10, 16, 9, 0, tzinfo=timezone.utc)
    assert f({"date": d}, "2026-09-07T00:00:00Z").startswith("2026-10-16")


def test_feed_date_as_iso_string():  # fetch_news() hands dates over as ISO strings
    assert _feed_published()({"date": "2026-10-15T12:00:00+00:00"}, "2026-10-02").startswith("2026-10-15")


def test_page_date_when_feed_has_none():
    f = _feed_published()
    assert f({"date": None}, "2026-10-15") == "2026-10-15"
    assert f({}, "2026-10-15") == "2026-10-15"


def test_produce_news_uses_it():
    assert 'article["published"] = feed_published(item, article["published"])' in \
        (ROOT / "carousel.py").read_text(encoding="utf-8")


def test_refused_article_pages_are_read_through_the_reader():
    """User 10-17: OpenAI's pages refuse the cloud (403); get them another way, from OpenAI's own page."""
    src = (ROOT / "src" / "article_capture.py").read_text(encoding="utf-8")
    assert 'READER = "https://r.jina.ai/"' in src and "REFUSED = (401, 403, 429)" in src
    assert "resp.status in REFUSED and (html := _reader_html(url))" in src
    assert "page.route(url" in src


def test_cover_headline_never_climbs_into_a_wide_cover_image():
    """10-17: a 4-line headline ran into OpenAI's wide cover image (editor rejected the Itaú carousel)."""
    html = (ROOT / "templates" / "carousel" / "index.html").read_text(encoding="utf-8")
    assert "top = Math.max(boxTop, Math.round(imgTop + 1080 / D.news.cover_ratio + 12));" in html
    assert 'c.style.height = boxBottom - top + "px";' in html
    # overflow above a bottom-aligned box counts too (scrollHeight alone missed it)
    assert "function tooTall(c)" in html and "if (tooTall(c) > 1) return true;" in html
