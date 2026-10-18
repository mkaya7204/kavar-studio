"""D-29: the selection step orders candidates inside a slot's concept by how many people they reach."""
import content_ranker as cr


def _items(*scores):
    return {"items": [dict(index=i, company=c, category=cat, audience=a, interest=b, clarity=3, usefulness=u,
                           fits_concept=fit, repeats_recent=rep, reason="r")
                      for i, (c, cat, a, b, u, fit, rep) in enumerate(scores)]}


def test_the_story_more_people_care_about_comes_first(monkeypatch):
    cands = [{"title": "Bank builds internal AI"}, {"title": "ChatGPT gets a new free feature"},
             {"title": "Data centre chip"}]
    monkeypatch.setattr("carousel_writer._ask", lambda p, s, f: (_items(
        ("Itau", "enterprise_customer", 1, 2, 0, True, False),
        ("OpenAI", "everyday_ai_product", 5, 4, 4, True, False),
        ("NVIDIA", "chips_infrastructure", 1, 2, 0, True, False)), None, "claude"))
    monkeypatch.setattr(cr, "category_bonus", lambda k: {})
    out = cr.rank(cands, "news_carousel")
    assert out[0]["title"] == "ChatGPT gets a new free feature"
    assert out[0]["rank"]["company"] == "OpenAI"


def test_biz_denedik_stays_first_and_off_concept_or_repeats_go_last(monkeypatch):
    cands = [{"title": "Tested model", "testable": True}, {"title": "Repeat of yesterday"},
             {"title": "Off concept"}, {"title": "Good one"}]
    monkeypatch.setattr("carousel_writer._ask", lambda p, s, f: (_items(
        ("A", "model_release", 1, 1, 0, True, False),
        ("B", "everyday_ai_product", 5, 5, 5, True, True),
        ("C", "everyday_ai_product", 5, 5, 5, False, False),
        ("D", "model_release", 3, 3, 3, True, False)), None, "claude"))
    monkeypatch.setattr(cr, "category_bonus", lambda k: {})
    assert [c["title"] for c in cr.rank(cands, "news_carousel")] == \
        ["Tested model", "Good one", "Repeat of yesterday", "Off concept"]


def test_a_failed_call_keeps_the_order(monkeypatch):
    cands = [{"title": "a"}, {"title": "b"}]
    monkeypatch.setattr("carousel_writer._ask", lambda p, s, f: (None, None, "mock"))
    assert cr.rank(cands, "news_carousel") == cands


def test_our_numbers_give_a_small_bonus(monkeypatch, tmp_path):
    rows = [{"kind": "carousel", "reach": r, "category": c} for r, c in
            [(140, "everyday_ai_product"), (120, "everyday_ai_product"), (130, "everyday_ai_product"),
             (20, "chips_infrastructure"), (25, "chips_infrastructure"), (30, "chips_infrastructure")]]
    p = tmp_path / "posts.json"
    p.write_text(__import__("json").dumps(rows), encoding="utf-8")
    monkeypatch.setattr(cr, "METRICS", p)
    bonus = cr.category_bonus("carousel")
    assert bonus["everyday_ai_product"] > 0 > bonus["chips_infrastructure"]
    assert all(-2 <= b <= 2 for b in bonus.values())
