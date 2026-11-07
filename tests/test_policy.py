"""§1.1 No prices, ever (user, 2026-10-11)."""

import pytest

from script_writer import NO_PRICE_RULE, price_mentions

PRICES = ["₺100", "$5", "20 €", "£3", "5 dolar", "Türk lirası", "ÜCRETSİZ", "Ücretli", "bedava", "FİYAT",
          "Fiyatlandırma", "Ödeme", "İndirim", "free", "pricing", "100 TL", "20 USD", "50 EUR",
          "Sıcak Simit 50 Kr", "50 kuruş", "20 GBP", "TRY 50", "50 TRY", "₹20", "¥300", "freemium", "paralı",
          "satın alın", "deneme sürümü", "tek seferlik", "5 milyon TL", "100 bin TL", "1.5 TL", "#ücretsiz", "at no cost", "cost-effective",
          "no charge"]
SAFE = ["freedom", "token", "GPT-4 Turbo", "Kral", "TLS bağlantısı", "Krita", "Kraken", "kuru", "15 Ekim'de",
        "1024 × 1024", "2 saniyede", "Galata Köprüsü", "costume", "Costa Rica",
        # D-32 (2026-10-18): plans, beta / limited access and credit use without amounts are allowed
        "Pro planında", "Plus abonelerine açıldı", "Premium sürüm", "abonelik gerekiyor", "subscribers",
        "beta olarak sınırlı kullanıcıda", "her üretim kredi harcıyor", "kullanım hakkından düşüyor"]


@pytest.mark.parametrize("text", PRICES)
def test_prices_are_caught(text):
    assert price_mentions(text), f"price not caught: {text!r}"


@pytest.mark.parametrize("text", SAFE)
def test_plain_words_pass(text):
    assert not price_mentions(text), f"false price hit: {text!r} -> {price_mentions(text)}"


def test_source_title_with_a_price_word_stays_out_of_the_caption():
    """11-07 real case: the Vids carousel caption carried the blog title "... at no cost."."""
    from script_writer import source_line

    url = "https://blog.google/products-and-platforms/products/workspace/omni-1-2-flash-google-vids/"
    line = source_line("Generate longer AI videos with Omni 1.2 Flash in Google Vids at no cost.", url)
    assert line == f"Kaynak haber: {url}" and not price_mentions(line)
    plain = source_line("WhatsApp Events Brings People Together Beyond the Group Chat", "https://about.fb.com/x")
    assert plain == "Kaynak haber: WhatsApp Events Brings People Together Beyond the Group Chat — https://about.fb.com/x"


def test_caption_uses_the_checked_source_line():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "carousel.py").read_text(encoding="utf-8")
    assert "source_line(script[\"title\"]" in src and "Kaynak haber: {script['title']}" not in src


def test_rule_is_in_every_writer_and_the_editor():
    import carousel_writer
    import editor_review
    import news_writer
    import script_writer

    assert NO_PRICE_RULE in news_writer.SYSTEM_PROMPT
    assert NO_PRICE_RULE in script_writer.SYSTEM_PROMPT
    assert NO_PRICE_RULE in carousel_writer.SYSTEM_PROMPT
    assert NO_PRICE_RULE in editor_review.SYSTEM


def test_news_carousel_with_a_price_is_invalid(news_script):
    from news_writer import NewsScript

    news_script["slides"][1]["body"] = news_script["slides"][1]["body"] + " Model **ücretsiz** kullanılıyor."
    with pytest.raises(Exception, match="price"):
        NewsScript.model_validate(news_script)


def test_price_in_a_hashtag_is_caught(news_script):
    from news_writer import NewsScript

    news_script["hashtags"] = ["#yapayzeka", "#ücretsiz", "#flux"]
    with pytest.raises(Exception, match="price"):
        NewsScript.model_validate(news_script)


def test_proof_crop_prompt_forbids_prices():
    import inspect

    import hyperframes_builder

    src = inspect.getsource(hyperframes_builder._ask_proof_choice)
    assert "price" in src and "currency" in src and "logo" in src


def test_our_test_images_forbid_prices_and_the_judge_drops_them():
    import model_trial

    for prompt in model_trial.IMAGE_TESTS:
        assert "no prices" in prompt and "no logos" in prompt
    assert "usable false" in model_trial.JUDGE_SYSTEM and "price" in model_trial.JUDGE_SYSTEM


@pytest.mark.parametrize("tags,caption,ok", [
    (["#yapayzeka", "#nvidia", "#nemotron"], "NVIDIA yeni modelini duyurdu, biz de iki soru sorduk.", True),
    (["#yapayzeka", "#İ#nvida", "#nemotron"], "NVIDIA yeni modelini duyurdu, biz de iki soru sorduk.", False),
    (["#yapayzeka", "#google", "#api"], "", False),  # went live 2026-10-14 with hashtags only
    (["#yapayzeka", "#google", "#api"], "Kısa #yapayzeka #google", False),
    (["#yapay-zeka", "#google", "#api"], "NVIDIA yeni modelini duyurdu, biz de iki soru sorduk.", False),
])
def test_captions_and_hashtags_are_checked(tags, caption, ok):
    from script_writer import caption_problems

    assert (not caption_problems(caption, tags)) is ok


def test_no_press_sites_as_news_sources():
    """User 2026-10-16: own visuals only, never press photos (Getty etc. via The Verge / TechCrunch)."""
    import json
    from pathlib import Path

    feeds = json.loads((Path(__file__).resolve().parent.parent / "news_sources.json").read_text(encoding="utf-8"))["feeds"]
    press = ("theverge", "techcrunch", "wired", "venturebeat", "engadget", "arstechnica", "zdnet", "cnbc", "reuters")
    assert not [f["url"] for f in feeds if any(p in f["url"] for p in press)]
