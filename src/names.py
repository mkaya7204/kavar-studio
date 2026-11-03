"""Product / company names: how they are WRITTEN (screens, captions, posts) and how George SAYS them (D-34, D-57).

The user (2026-11-03): "markanın yazılışı farklı okunuşu farklı olmasına rağmen bazen okunuşu yazıldığı gibi
yapıyorsun bazen de yazılışını yanlış şekilde okunuşu gibi yazıyorsun ... keskin kesin net hata yapılmayacak
önlemler alarak düzenleme yap". Three rules, each checked by code, not left to a prompt:
  1. every foreign word George would say is in the lexicon before he speaks (`foreign_words` finds them by
     their letters, Claude gives the Turkish way to say them, a missing one stops the voicing);
  2. captions always show the written name, whatever the timed words look like (`written_captions`);
  3. no written text ever carries the spoken form ("Klod", "Cemini"): `phonetic_spellings` refuses it.
No heavy imports: the writers, the TTS and the tests all load this file.
"""

import difflib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRONUNCIATION_PATH = ROOT / "rules" / "pronunciation.json"  # checked by hand; always wins
LEARNED_PATH = ROOT / "state" / "pronunciations.json"  # names learned before voicing; the cloud run commits state/
SPOKEN_WORD = re.compile(r"^[A-Za-zÇĞİÖŞÜçğıöşüâîû]+$")  # one word, Turkish letters, nothing else

# Letters and letter pairs Turkish spelling never has: a word with one of them is said wrong if George reads it
# letter by letter ("Gemini" has none, so known names are also found by the lexicon itself).
FOREIGN_LETTERS = re.compile(r"[qwxQWX]|th|sh|ch|ph|ck|ee|oo|ou|ea|gh|wh|qu|tion|ght|[a-z][A-Z]|[A-Za-z]\d|\d[A-Za-z]")
TURKISH_LETTERS = re.compile(r"[çğıöşüÇĞİÖŞÜâîû]")
WORD = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüâîû0-9][\w.+]*[\w+]|[A-Za-zÇĞİÖŞÜçğıöşüâîû]")


def lexicon(paths: tuple[Path, ...] | None = None) -> dict[str, str]:
    """written -> spoken: learned names, overridden by the hand-checked list."""
    words = {}
    for path in paths or (LEARNED_PATH, PRONUNCIATION_PATH):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        words.update(data.get("words", data) if isinstance(data, dict) else {})
    return {k: v for k, v in words.items() if not k.startswith("_") and SPOKEN_WORD.match(str(v))}


def _base(token: str) -> str:
    """The name without a Turkish suffix after an apostrophe ("Gemini'de" -> "Gemini")."""
    return re.split(r"['’]", token, maxsplit=1)[0].rstrip(".")


def foreign_words(text: str, known: dict[str, str] | None = None) -> list[str]:
    """Words of a Turkish voiceover that George would say wrong by Turkish spelling and that the lexicon doesn't
    cover yet: acronyms (AI, MCP), CamelCase (ChatGPT), letters / pairs Turkish never writes (Quests, Hera.video),
    letters with digits (GPT5), and capitalised words in mid-sentence with no Turkish letter (Polar, Stanford)."""
    known = lexicon() if known is None else known
    out = []
    for sentence in re.split(r"(?<=[.!?:])\s+", text):
        for i, m in enumerate(WORD.finditer(sentence)):
            word = _base(m.group(0))
            if not word or word in known or word in out or word.isdigit():
                continue
            caps = len(word) >= 2 and word.isupper() and not word.isdigit()
            mid_capital = i > 0 and word[0].isupper() and not TURKISH_LETTERS.search(word)
            if caps or mid_capital or FOREIGN_LETTERS.search(word) or "." in word:
                out.append(word)
    return out


# spoken forms that are also ordinary Turkish words ("kod yaz", "oto", "slayt"): never a wrong spelling of a name
TURKISH_WORDS = {"bay", "dek", "eposta", "fil", "ked", "kod", "kraft", "lama", "mit", "nora", "oto", "parametrik",
                 "slayt", "stela", "veb", "vit", "yor", "zum", "mek", "plas", "sora", "meta", "siri", "grok"}


def _spoken_forms(lex: dict[str, str]) -> dict[str, str]:
    """spoken -> written, for names only (the written form has a capital or a digit: "Claude" -> "Klod"), where
    the spoken form is not itself a Turkish word ("Kod" for Code stays allowed: "kod yaz")."""
    return {v: k for k, v in lex.items()
            if v.lower() != k.lower() and re.search(r"[A-Z0-9]", k) and v.lower() not in TURKISH_WORDS}


def phonetic_spellings(*texts: str, lex: dict[str, str] | None = None) -> list[str]:
    """Spoken forms found in written text ("Klod" for Claude): screens and captions keep the real spelling."""
    forms = _spoken_forms(lexicon() if lex is None else lex)
    if not forms:
        return []
    pat = re.compile(r"(?<!\w)(" + "|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True)) + r")(?!\w)")
    return sorted({f"{m.group(1)} (yazılışı: {forms[m.group(1)]})" for t in texts for m in pat.finditer(t or "")})


def _clean(token: str) -> str:
    return re.sub(r"^[^\w]+|[^\w]+$", "", token)


def written_captions(timed: list[dict], said: str, text: str, lex: dict[str, str] | None = None) -> list[dict]:
    """Timed words (what George said: "Cemini'de") back to the script's spelling ("Gemini'de"), without needing
    the two word counts to match (they used to, and a single mismatch left the whole caption in spoken form)."""
    said_words = [w for w in (_clean(t) for t in said.split()) if w]
    shown = [w for w in (_clean(t) for t in text.split()) if w]
    out = [dict(w) for w in timed]
    if len(said_words) == len(shown):  # spoken_text swaps one word for one word: align the timings to the text
        sm = difflib.SequenceMatcher(None, [w["word"].lower() for w in timed], [s.lower() for s in said_words],
                                     autojunk=False)
        for block in sm.get_matching_blocks():
            for k in range(block.size):
                out[block.a + k]["word"] = shown[block.b + k]
    # whatever is left in spoken form (a word the alignment missed): back to the written name used in the text
    forms = {v: k for k, v in (lexicon() if lex is None else lex).items() if v != k}
    in_text = {_base(s) for s in shown}
    for w in out:
        base = _base(w["word"])
        if base in forms and forms[base] in in_text:
            w["word"] = forms[base] + w["word"][len(base):]
    return out
