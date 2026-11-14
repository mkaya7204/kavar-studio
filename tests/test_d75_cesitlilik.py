"""D-75 (2026-11-14, the user): "diğer paylaşım saatleri içinde başka kaynaklardan da faydalan, bir de aynı haberin
onaydan geçmesi veya aynı haberin başka yerde de bulup yayına onay çıkması konusunda da önlem al ... hep Gemini
olması kendimizi tekrara ve aynı şeyleri yayınlıyoruz gibi oluyor"."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import news_fetcher as nf  # noqa: E402
import recent_posts as rp  # noqa: E402


def test_the_same_story_in_other_words_on_another_blog_is_caught():
    # 11-14: the developers blog's post was queued, the Gemini blog's post of the same model passed D-66
    assert nf.same_story("Introducing Gemini 4 Hydrogen",
                         "Gemini 4 Hydrogen: everyday coding and agentic workflows for developers")
    assert nf.same_story("MiniMax H3-Image: Bringing 4K Image Generation into the 10-Second Era",
                         "MiniMax H3 Image open weights")
    # different stories of one brand stay different
    assert not nf.same_story("Expanding Gemini in Gmail to more Google Workspace users",
                             "Get quick answers from Gemini on any website.")
    assert not nf.same_story("Gemini 4 Carbon is now available", "Introducing Gemini 4 Hydrogen")
    assert nf.seen_story("Introducing Gemini 4 Hydrogen", [nf.title_key("Gemini 4 Hydrogen: everyday coding")])


def test_brand_families_and_the_days_record(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "PATH", tmp_path / "recent_posts.json")
    monkeypatch.setattr(rp, "QUEUE_DIR", tmp_path / "queue")
    assert rp.brand_of("Introducing Gemini 4 Hydrogen") == "google" == rp.brand_of("YouTube'da yeni özet")
    assert rp.brand_of("ChatGPT'de grup sohbeti") == "openai" and rp.brand_of("Yogurt") == ""
    rp.record([{"time": "07:30", "kind": "reel", "title": "Gemini in Chrome", "status": "ready"},
               {"time": "12:30", "kind": "carousel", "title": "Gemini 4 Hydrogen", "status": "ready"},
               {"time": "18:00", "kind": "carousel", "status": "empty"}], date(2026, 11, 15))
    (tmp_path / "queue").mkdir()
    (tmp_path / "queue" / "2026-11-16.json").write_text(json.dumps(
        [{"time": "07:30", "kind": "reel", "title": "Android 17 ipucu", "status": "ready"}]), encoding="utf-8")
    counts = rp.brand_counts(today=date(2026, 11, 16))
    assert counts["google"] == 3  # two recorded + the day being made
    assert rp.brand_penalty("google", counts) == rp.MAX_PENALTY and rp.brand_penalty("openai", counts) == 0


def test_the_ranker_lowers_a_brand_seen_lately_and_marks_a_queued_story_a_repeat(tmp_path, monkeypatch):
    import carousel_writer
    import content_ranker as cr
    monkeypatch.setattr(rp, "PATH", tmp_path / "recent_posts.json")
    monkeypatch.setattr(rp, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(cr, "recent_titles", lambda days=3: [])
    rp.record([{"time": "12:30", "kind": "carousel", "title": "Gemini 4 Hydrogen: everyday coding", "status": "ready"},
               {"time": "07:30", "kind": "reel", "title": "Gemini in Chrome", "status": "ready"}], date.today())
    item = {"company": "Google", "category": "model_release", "audience": 4, "interest": 4, "clarity": 4,
            "usefulness": 4, "fits_concept": True, "repeats_recent": False, "reason": "r"}
    draft = {"items": [{**item, "index": 0}, {**item, "index": 1, "company": "OpenAI"},
                       {**item, "index": 2}]}
    monkeypatch.setattr(carousel_writer, "_ask", lambda *a, **k: (draft, "m", "claude_code"))
    out = cr.rank([{"title": "Introducing Gemini 4 Hydrogen"}, {"title": "ChatGPT gets group chats"},
                   {"title": "Gemini in Gmail for everyone"}], "news_carousel")
    by = {c["title"]: c["rank"] for c in out}
    assert by["Introducing Gemini 4 Hydrogen"]["repeat"]  # queued yesterday, other words: a repeat
    assert by["Gemini in Gmail for everyone"]["brand_penalty"] == 2 * rp.PENALTY
    assert out[0]["title"] == "ChatGPT gets group chats"  # another brand goes first at equal quality


def test_more_companies_feed_the_slots():
    c = json.loads((ROOT / "news_sources.json").read_text(encoding="utf-8"))
    names = {f["name"] for f in c["feeds"] + c["guide_feeds"]}
    assert {"Microsoft 365", "Windows", "Character.AI", "Opera", "Grammarly", "Duolingo", "Dropbox",
            "Mozilla"} <= names
    google = [f for f in c["feeds"] if rp.brand_of(f["name"], f["url"]) == "google"]
    assert len(google) / len(c["feeds"]) < 0.35
    daily = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert "recent_posts.record(queue, queue_day())" in daily and 'r.get("brand") or r.get("company")' in daily
