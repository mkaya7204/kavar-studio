"""D-57 (user 2026-11-03): "markanın yazılışı farklı okunuşu farklı olmasına rağmen bazen okunuşu yazıldığı gibi
yapıyorsun bazen de yazılışını yanlış şekilde okunuşu gibi yazıyorsun ... keskin kesin net hata yapılmayacak
önlemler alarak". Each direction is checked by code: George never meets a foreign word without its pronunciation,
and no screen, caption or post shows the spoken form."""

import json
from types import SimpleNamespace

import pytest

import names
import tts_engine
from script_writer import written_name_problems

LEX = {"Gemini": "Cemini", "Google": "Gugıl", "Claude": "Klod", "Code": "Kod", "AI": "Eyay"}


def test_foreign_words_are_found_by_their_letters_not_by_a_prompt():
    text = "Yeni görevde AI Quests açılıyor. Hera.video ile motion grafik yap. Veri temizliyor, GPT5 de var."
    assert names.foreign_words(text, LEX) == ["Quests", "Hera.video", "motion", "GPT5"]
    # Turkish words, also capitalised at a sentence start, and known names are not asked
    assert names.foreign_words("Yeni sürüm Gemini'de. Veri temizliyor, kod yazıyor.", LEX) == []


def test_george_never_speaks_a_foreign_word_without_its_pronunciation(monkeypatch, tmp_path):
    monkeypatch.setattr(tts_engine, "LEARNED_PATH", tmp_path / "learned.json")
    monkeypatch.delenv("SCRIPT_WRITER_NO_CLI", raising=False)
    monkeypatch.setattr(tts_engine.shutil, "which", lambda name: "claude")
    prompts = []

    def claude(*a, **k):  # Claude forgets one of the two names, twice
        prompts.append(k["input"])
        return SimpleNamespace(stdout=json.dumps({"structured_output": {"words": [
            {"written": "Openbroca", "spoken": "Openbroka"}]}}))

    monkeypatch.setattr(tts_engine.subprocess, "run", claude)
    with pytest.raises(tts_engine.MissingPronunciation, match="Zyphra"):
        tts_engine.ensure_pronunciations("Openbroca ile yeni Zyphra modelini dene.")
    assert "Zyphra" in prompts[-1] and "MUST answer" in prompts[-1]  # the missing word is named, not hoped for


def test_a_word_said_right_as_written_is_kept_and_never_asked_again(monkeypatch, tmp_path):
    learned = tmp_path / "learned.json"
    monkeypatch.setattr(tts_engine, "LEARNED_PATH", learned)
    monkeypatch.delenv("SCRIPT_WRITER_NO_CLI", raising=False)
    monkeypatch.setattr(tts_engine.shutil, "which", lambda name: "claude")
    monkeypatch.setattr(tts_engine.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps(
        {"structured_output": {"words": [{"written": "Ankara", "spoken": "Ankara"}]}})))
    tts_engine.ensure_pronunciations("Yeni merkez Ankara'da açıldı.")
    assert json.loads(learned.read_text(encoding="utf-8"))["Ankara"] == "Ankara"


def test_captions_show_the_written_name_even_when_the_word_counts_differ():
    said, text = "Cemini'de yeni mod. Gugıl açıkladı.", "Gemini'de yeni mod. Google açıkladı."
    timed = [{"word": w, "start": i, "end": i + 0.4} for i, w in
             enumerate(["Cemini'de", "yeni", "mod", "Gugıl", "açık", "ladı"])]  # 6 timed words for 5 written
    shown = names.written_captions(timed, said, text, LEX)
    assert [w["word"] for w in shown][:4] == ["Gemini'de", "yeni", "mod", "Google"]
    assert names.phonetic_spellings(" ".join(w["word"] for w in shown), lex=LEX) == []
    assert shown[3]["start"] == 3  # timings unchanged


def test_no_written_text_carries_the_spoken_form():
    assert names.phonetic_spellings("Klod ile Cemini karşılaştırması", lex=LEX) == \
        ["Cemini (yazılışı: Gemini)", "Klod (yazılışı: Claude)"]
    assert names.phonetic_spellings("Claude Code ile kod yaz, Gemini'de dene.", lex=LEX) == []  # "kod" is Turkish
    assert written_name_problems("Klod artık daha hızlı.")  # the writers refuse it (live lexicon)


def test_the_live_lexicon_has_no_spoken_form_that_is_another_names_spelling():
    lex = names.lexicon()
    forms = names._spoken_forms(lex)
    assert not set(forms) & set(lex)  # "Cemini" is never itself a written name
