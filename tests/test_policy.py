"""§1.1 No prices, ever (user, 2026-10-11)."""

import pytest

from script_writer import NO_PRICE_RULE, price_mentions

PRICES = ["₺100", "$5", "20 €", "£3", "5 dolar", "Türk lirası", "ÜCRETSİZ", "Ücretli", "bedava", "FİYAT",
          "Fiyatlandırma", "ABONELİK", "Ödeme", "İndirim", "free", "pricing", "100 TL", "20 USD", "50 EUR",
          "Sıcak Simit 50 Kr", "50 kuruş", "20 GBP", "TRY 50", "50 TRY", "₹20", "¥300", "freemium", "paralı",
          "satın alın", "deneme sürümü", "tek seferlik", "5 milyon TL", "100 bin TL", "1.5 TL", "#ücretsiz"]
SAFE = ["freedom", "token", "GPT-4 Turbo", "Kral", "TLS bağlantısı", "Krita", "Kraken", "kuru", "15 Ekim'de",
        "1024 × 1024", "2 saniyede", "Galata Köprüsü"]


@pytest.mark.parametrize("text", PRICES)
def test_prices_are_caught(text):
    assert price_mentions(text), f"price not caught: {text!r}"


@pytest.mark.parametrize("text", SAFE)
def test_plain_words_pass(text):
    assert not price_mentions(text), f"false price hit: {text!r} -> {price_mentions(text)}"


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
