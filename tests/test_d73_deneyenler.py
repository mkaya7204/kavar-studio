"""D-73 (2026-11-14, the user): "A da bizim gerçekten deneme şansımız yok ama denenmiş olunmuş hallerini
bulabilirmişiz, kullanıcı deneyimleri veya bunları denenmiş kurumlar veya platformlar". A tool Reel may carry what
real users / reviewers found when they tried the tool: attributed, in our words, never the maker's own claims, never
prices, never "denedik"."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import experiences  # noqa: E402
import script_writer as sw  # noqa: E402


def test_only_real_attributed_price_free_findings_from_others_are_kept():
    found = [
        {"source": "Product Hunt yorumları", "url": "https://www.producthunt.com/products/yogurt/reviews",
         "finding": "Kullananlar notların toplantı biter bitmez hazır olduğunu söylüyor.", "tone": "positive"},
        {"source": "Yogurt", "url": "https://www.yogurt.so/blog/launch", "finding": "Çok hızlı.", "tone": "positive"},
        {"source": "Reddit", "url": "https://reddit.com/r/x", "finding": "Aylık 10 dolara değer diyorlar.",
         "tone": "positive"},
        {"source": "", "url": "https://news.ycombinator.com/item?id=1", "finding": "x", "tone": "mixed"},
        {"source": "Hacker News", "url": "news.ycombinator.com/item?id=2", "finding": "y", "tone": "mixed"},
        {"source": "Hacker News", "url": "https://news.ycombinator.com/item?id=3",
         "finding": "Bazı kullanıcılar Türkçe toplantılarda hata yaptığını yazıyor.", "tone": "negative"},
    ]
    kept = experiences.clean(found, "https://www.yogurt.so/")
    assert [k["source"] for k in kept] == ["Product Hunt yorumları", "Hacker News"]
    assert kept[1]["tone"] == "negative"  # an honest negative report is content too


def test_the_writer_and_editor_get_them_and_never_say_denedik():
    tool = sw.Tool(tool_name="Yogurt", tag_line="Toplantı notu", website_url="https://www.yogurt.so/",
                   description="x", experiences=[{"source": "Product Hunt yorumları", "url": "https://p.h/x",
                                                  "finding": "Hızlı.", "tone": "positive"}])
    assert "Product Hunt yorumları" in sw._user_message(tool, "tr")
    assert "People who tried it (D-73)" in sw.SYSTEM_PROMPT and 'no "denedik / denedim / kullandık"' in sw.SYSTEM_PROMPT
    assert "tool_data_source.experiences are real users'" in (ROOT / "src" / "editor_review.py").read_text(
        encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert main.index('"experiences": find_experiences(tool)') < main.index('(TEMP_DIR / "tool.json").write_text(')
    src = (ROOT / "src" / "experiences.py").read_text(encoding="utf-8")
    assert '"WebSearch,WebFetch"' in src and 'record_usage("tool_experiences"' in src
