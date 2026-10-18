"""Text-to-speech for the voiceover, with word timings, from several providers.

Providers are tried in the order of config.json "tts_providers" (default
elevenlabs -> azure -> edge); one without credentials in .env is skipped, and one
that fails hands over to the next:
  - elevenlabs: most natural voice (ELEVENLABS_API_KEY; always "George", CLAUDE.md §1.6)
  - azure:      official Microsoft Speech, same neural voices as edge but reliable
                (AZURE_SPEECH_KEY + AZURE_SPEECH_REGION, e.g. westeurope)
  - edge:       free Microsoft Edge online voices (edge-tts), no key, sometimes refuses with 403

Writes the MP3 plus per-word timings (JSON + SRT) that the video builders use for
captions and scene sync. Keeps the result within the video length by speeding up
the voice slightly, and refuses text that would need more.
"""

import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import aiohttp
import edge_tts
import requests
from dotenv import load_dotenv
from edge_tts.exceptions import EdgeTTSException

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "output" / "temp" / "voiceover.mp3"
load_dotenv(ROOT / ".env")  # provider keys

DEFAULT_VOICE = "en-US-AriaNeural"  # alt: "en-US-ChristopherNeural" (male)
VOICES = {"en": DEFAULT_VOICE, "tr": "tr-TR-AhmetNeural"}  # config.json "language" -> voice; alt tr: "tr-TR-EmelNeural"
DEFAULT_PROVIDERS = ["elevenlabs", "azure", "edge"]
ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # "George" (multilingual): the user chose to keep it for Reels, 2026-10-16
ELEVENLABS_MODEL = "eleven_multilingual_v2"  # best quality for Turkish
ELEVENLABS_SEED = 4242  # same seed every run, for a consistent delivery
MAX_SECONDS = 23.5  # the voice plus ~2 s of outro stays inside the editor's 14-26 s (refused BEFORE spending quota)
WORDS_PER_SECOND = 2.5  # neural voices at rate +0% ≈ 150 wpm
MAX_SPEEDUP_PCT = 15  # faster than this sounds rushed
RETRIES = 3
HTTP_TIMEOUT = 90


PRONUNCIATION_PATH = ROOT / "rules" / "pronunciation.json"  # checked by hand; always wins
LEARNED_PATH = ROOT / "state" / "pronunciations.json"  # names learned before voicing; the cloud run commits state/
SPOKEN_WORD = re.compile(r"^[A-Za-zÇĞİÖŞÜçğıöşüâîû]+$")  # one word, Turkish letters, nothing else


def _lexicon() -> dict[str, str]:
    """The names George is told how to say: learned ones, overridden by the hand-checked list."""
    words = {}
    for path in (LEARNED_PATH, PRONUNCIATION_PATH):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        words.update(data.get("words", data) if isinstance(data, dict) else {})
    return {k: v for k, v in words.items() if not k.startswith("_") and SPOKEN_WORD.match(str(v))}


LEARN_PROMPT = """A Turkish text-to-speech voice reads every word by Turkish spelling rules, so "Gemini" comes out \
as "ge-mi-ni" instead of "cemini". In the Turkish voiceover below, list EVERY word it would say wrong: foreign \
product, app, model, company and feature names (also new, unknown ones), English words, and abbreviations that \
Turkish tech people say as a word. Leave out Turkish words and names already said right by Turkish spelling.
For each: "written" = the word exactly as it is in the text, without a Turkish suffix after an apostrophe \
("Openbroca'yı" -> "Openbroca"); "spoken" = how Turkish tech people say it, written with Turkish letters as \
ONE word with no spaces, hyphens or digits (join the parts: "SpeechFast" -> "Spiçfest", "OpenAI" -> \
"Openeyay", "Korinotch" -> "Korinoç"). Already known, leave out: {known}

Voiceover:
{text}"""

LEARN_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["words"],
                "properties": {"words": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["written", "spoken"],
                    "properties": {"written": {"type": "string"}, "spoken": {"type": "string"}}}}}}


def learn_names(text: str) -> dict[str, str]:
    """D-34 (the user, 2026-10-18: "tanıtılan hangi isimde bir ürün olursa onun söylenişi doğru olacak ...
    sistemde kalıcı hale getir"): before George speaks, Claude gives the Turkish way to say every foreign
    name in the text that isn't known yet; valid answers are kept in state/pronunciations.json, so a name is
    said the same way every time. No Claude CLI or no answer = the known names only."""
    known = _lexicon()
    exe = shutil.which("claude") if not os.getenv("SCRIPT_WRITER_NO_CLI") else None
    if not exe:
        return {}
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run([exe, "-p", "--output-format", "json", "--json-schema", json.dumps(LEARN_SCHEMA),
                               "--tools", "", "--no-session-persistence"],
                              input=LEARN_PROMPT.format(known=", ".join(sorted(known)) or "-", text=text),
                              capture_output=True, text=True, encoding="utf-8", timeout=180, cwd=ROOT, env=env)
        answer = (json.loads(proc.stdout).get("structured_output") or {}).get("words", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return {}
    new = {}
    for w in answer:
        written = str(w.get("written", "")).strip()
        spoken = re.sub(r"[\s\-]+", "", str(w.get("spoken", "")))  # "Spiç Fest" -> "SpiçFest": one word for one
        if (written and written not in known and written != spoken and SPOKEN_WORD.match(spoken)
                and re.search(rf"(?<!\w){re.escape(written)}(?!\w)", text)):
            new[written] = spoken
    if new:
        try:
            learned = json.loads(LEARNED_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            learned = {}
        LEARNED_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEARNED_PATH.write_text(json.dumps({**learned, **new}, indent=1, ensure_ascii=False, sort_keys=True),
                                encoding="utf-8")
        print(f"[tts] learned how to say: {', '.join(f'{k} -> {v}' for k, v in new.items())}")
    return new


def spoken_text(text: str, learn: bool = False) -> str:
    """D-34 (the user, 2026-10-18: "gemini yazıldığı gibi okuyor"): the text George is sent, with each product
    name written as a Turkish reader says it (rules/pronunciation.json, then names learned by learn_names).
    One word for one word, suffixes kept ("Gemini'de" -> "Cemini'de"), so the word timings map back to the
    real spelling for the captions."""
    if learn:
        learn_names(text)
    lex = _lexicon()
    if not lex:
        return text
    names = "|".join(re.escape(k) for k in sorted(lex, key=len, reverse=True))
    return re.sub(rf"(?<!\w)({names})(?!\w)", lambda m: lex[m.group(1)], text)


def _clean_word(token: str) -> str:
    return re.sub(r"^[^\w]+|[^\w]+$", "", token)


def written_words(words: list[dict], text: str) -> list[dict]:
    """The spoken words' timings with the script's own spelling (captions show "Gemini", not "Cemini")."""
    shown = [w for w in (_clean_word(t) for t in text.split()) if w]
    if len(shown) != len(words):
        print(f"[tts] {len(words)} timed words for {len(shown)} written ones: captions keep the spoken spelling")
        return words
    return [{**w, "word": s} for w, s in zip(words, shown)]


def voice_for(language: str) -> str:
    return VOICES.get(language, DEFAULT_VOICE)


class TTSError(Exception):
    """Voiceover could not be produced (service failure or text unusable)."""


class _FatalTTSError(TTSError):
    """A failure retrying won't fix (bad key, no quota, unknown voice): go to the next provider."""


def estimate_seconds(text: str, rate_pct: int = 0) -> float:
    return len(text.split()) / (WORDS_PER_SECOND * (1 + rate_pct / 100))


def _rate_str(rate_pct: int) -> str:
    return f"{rate_pct:+d}%"


def _env(name: str) -> str:
    value = (os.getenv(name) or "").strip().lstrip("﻿")  # a BOM from a Windows pipe breaks HTTP headers
    return "" if value.endswith("...") else value  # untouched placeholder


def _probe_duration(path: Path) -> float | None:
    """Real MP3 duration via ffprobe; None if ffprobe is unavailable."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return float(out.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _srt_time(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _words_to_srt(words: list[dict], per_line: int = 6) -> str:
    blocks = []
    for i in range(0, len(words), per_line):
        chunk = words[i:i + per_line]
        text = " ".join(w["word"] for w in chunk)
        blocks.append(f"{len(blocks) + 1}\n{_srt_time(chunk[0]['start'])} --> {_srt_time(chunk[-1]['end'])}\n{text}\n")
    return "\n".join(blocks)


# ---------------------------------------------------------------- providers
# Each writes the MP3 to `audio_path` and returns [{"word", "start", "end"}] in seconds.

async def _edge(text: str, voice: str, rate_pct: int, audio_path: Path) -> list[dict]:
    communicate = edge_tts.Communicate(text, voice, rate=_rate_str(rate_pct), boundary="WordBoundary")
    words = []
    try:
        with open(audio_path, "wb") as audio:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 10_000_000  # 100-ns ticks -> seconds
                    words.append({"word": chunk["text"], "start": round(start, 3),
                                  "end": round(start + chunk["duration"] / 10_000_000, 3)})
    except (EdgeTTSException, aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise TTSError(f"{type(exc).__name__}: {exc}") from exc
    return words


ELEVENLABS_KEYS = ("ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY_2")  # two accounts, same George (D-23)


def _elevenlabs_keys() -> list[str]:
    return [k for k in (_env(n) for n in ELEVENLABS_KEYS) if k]


def _elevenlabs_sync(text: str, rate_pct: int, audio_path: Path) -> list[dict]:
    voice_id = ELEVENLABS_VOICE  # locked (CLAUDE.md §1.6): no env override, no other voice
    keys = _elevenlabs_keys()
    for n, key in enumerate(keys, 1):
        try:
            resp = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": key, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": _env("ELEVENLABS_MODEL") or ELEVENLABS_MODEL,
                    # Higher stability and a fixed seed keep the same voice sounding alike from video to video.
                    "seed": ELEVENLABS_SEED,
                    "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.15,
                                       "use_speaker_boost": True,
                                       "speed": max(0.7, min(1.2, 1 + rate_pct / 100))},
                },
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise TTSError(f"ElevenLabs request failed: {exc}") from exc
        if resp.status_code == 200:
            break
        detail = resp.text[:300]
        if resp.status_code in (401, 402, 403) and n < len(keys):  # this account's key or quota: next account
            print(f"[tts] ElevenLabs key {n} refused (HTTP {resp.status_code}); trying key {n + 1}")
            continue
        if resp.status_code in (400, 401, 402, 403, 404, 422):  # key / quota / voice problems
            raise _FatalTTSError(f"ElevenLabs HTTP {resp.status_code}: {detail}")
        raise TTSError(f"ElevenLabs HTTP {resp.status_code}: {detail}")
    else:
        raise _FatalTTSError("ElevenLabs: no API key set")
    data = resp.json()
    audio_path.write_bytes(base64.b64decode(data["audio_base64"]))
    align = data.get("alignment") or data.get("normalized_alignment") or {}
    return _words_from_characters(align.get("characters", []),
                                  align.get("character_start_times_seconds", []),
                                  align.get("character_end_times_seconds", []))


def _words_from_characters(chars: list[str], starts: list[float], ends: list[float]) -> list[dict]:
    """Character-level timings (ElevenLabs) -> word timings, punctuation stripped like edge-tts."""
    words, cur, t0, t1 = [], "", 0.0, 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append((cur, t0, t1))
            cur = ""
            continue
        if not cur:
            t0 = s
        cur += ch
        t1 = e
    if cur:
        words.append((cur, t0, t1))
    out = []
    for text, s, e in words:
        clean = re.sub(r"^[^\w]+|[^\w]+$", "", text)
        if clean:
            out.append({"word": clean, "start": round(s, 3), "end": round(e, 3)})
    return out


def _azure_sync(text: str, voice: str, rate_pct: int, audio_path: Path) -> list[dict]:
    import azure.cognitiveservices.speech as speechsdk  # imported here: only needed for azure
    from xml.sax.saxutils import escape

    config = speechsdk.SpeechConfig(subscription=_env("AZURE_SPEECH_KEY"), region=_env("AZURE_SPEECH_REGION"))
    config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3)
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    words = []

    def on_word(evt):
        if evt.boundary_type == speechsdk.SpeechSynthesisBoundaryType.Word:
            start = evt.audio_offset / 10_000_000
            words.append({"word": evt.text, "start": round(start, 3),
                          "end": round(start + evt.duration.total_seconds(), 3)})

    synth.synthesis_word_boundary.connect(on_word)
    lang = "-".join(voice.split("-")[:2])
    ssml = (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang}'>"
            f"<voice name='{voice}'><prosody rate='{_rate_str(rate_pct)}'>{escape(text)}</prosody></voice></speak>")
    result = synth.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = result.cancellation_details
        msg = f"Azure: {details.reason} {details.error_details or ''}".strip()
        if details.error_code in (speechsdk.CancellationErrorCode.AuthenticationFailure,
                                  speechsdk.CancellationErrorCode.Forbidden,
                                  speechsdk.CancellationErrorCode.BadRequest):
            raise _FatalTTSError(msg)
        raise TTSError(msg)
    audio_path.write_bytes(result.audio_data)
    return words


async def _elevenlabs(text: str, voice: str, rate_pct: int, audio_path: Path) -> list[dict]:
    return await asyncio.to_thread(_elevenlabs_sync, text, rate_pct, audio_path)


async def _azure(text: str, voice: str, rate_pct: int, audio_path: Path) -> list[dict]:
    return await asyncio.to_thread(_azure_sync, text, voice, rate_pct, audio_path)


PROVIDERS = {"elevenlabs": _elevenlabs, "azure": _azure, "edge": _edge}
NEEDS = {"elevenlabs": ["ELEVENLABS_API_KEY"], "azure": ["AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION"], "edge": []}


def available_providers() -> list[str]:
    """Configured order, keeping only providers whose credentials are in .env."""
    try:
        order = json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("tts_providers")
    except (OSError, json.JSONDecodeError):
        order = None
    order = [p for p in (order or DEFAULT_PROVIDERS) if p in PROVIDERS]
    return [p for p in order if (_elevenlabs_keys() if p == "elevenlabs" else all(_env(k) for k in NEEDS[p]))]


def _voice_label(provider: str, voice: str) -> str:
    if provider == "elevenlabs":
        return f"elevenlabs:{ELEVENLABS_VOICE}"
    return f"{provider}:{voice}"


async def _synthesize_once(provider: str, text: str, voice: str, rate_pct: int, out_path: Path) -> list[dict]:
    tmp_path = out_path.with_suffix(".part")
    try:
        words = await PROVIDERS[provider](text, voice, rate_pct, tmp_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)  # don't leave a half-written .part behind
        raise
    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        tmp_path.unlink(missing_ok=True)
        raise TTSError(f"{provider} returned no audio")
    if not words:
        tmp_path.unlink(missing_ok=True)
        raise TTSError(f"{provider} returned no word timings")
    tmp_path.replace(out_path)  # only replace the previous file once complete
    out_path.with_suffix(".srt").write_text(_words_to_srt(words), encoding="utf-8")
    return words


async def _synthesize_with_retry(provider: str, text: str, voice: str, rate_pct: int, out_path: Path) -> list[dict]:
    last_exc: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            return await _synthesize_once(provider, text, voice, rate_pct, out_path)
        except _FatalTTSError:
            raise
        except TTSError as exc:
            last_exc = exc
            print(f"[tts] {provider} attempt {attempt}/{RETRIES} failed: {exc}"[:300])
            if attempt < RETRIES:
                await asyncio.sleep(2 ** attempt)
    raise TTSError(f"{provider} failed after {RETRIES} attempts") from last_exc


async def _synthesize_provider(provider: str, text: str, out_path: Path, voice: str,
                               rate_pct: int, max_seconds: float) -> tuple[list[dict], float, int]:
    words = await _synthesize_with_retry(provider, text, voice, rate_pct, out_path)
    duration = _probe_duration(out_path) or (words[-1]["end"] if words else 0.0)

    # The estimate can be off; if the real audio overruns, re-render once faster.
    if duration > max_seconds and rate_pct < MAX_SPEEDUP_PCT:
        new_rate = min(MAX_SPEEDUP_PCT, rate_pct + int(100 * (duration / max_seconds - 1)) + 1)
        print(f"[tts] {duration:.1f}s > {max_seconds:.0f}s; re-rendering at {_rate_str(new_rate)}")
        rate_pct = new_rate
        words = await _synthesize_with_retry(provider, text, voice, rate_pct, out_path)
        duration = _probe_duration(out_path) or (words[-1]["end"] if words else 0.0)
    return words, duration, rate_pct


async def synthesize_async(
    text: str,
    out_path: Path | str = OUTPUT_PATH,
    voice: str = DEFAULT_VOICE,
    max_seconds: float = MAX_SECONDS,
    providers: list[str] | None = None,
) -> dict:
    """`voice` is the Microsoft voice name (azure / edge); ElevenLabs always uses George."""
    text = " ".join(text.split())
    if not text:
        raise TTSError("voiceover text is empty")

    # Pick the smallest speed-up that should fit; refuse text that can't fit.
    rate_pct = 0
    if estimate_seconds(text) > max_seconds:
        rate_pct = min(MAX_SPEEDUP_PCT, int(100 * (estimate_seconds(text) / max_seconds - 1)) + 1)
        if estimate_seconds(text, rate_pct) > max_seconds:
            raise TTSError(
                f"text has {len(text.split())} words (~{estimate_seconds(text):.1f}s); "
                f"too long for {max_seconds:.0f}s even at {_rate_str(MAX_SPEEDUP_PCT)} speed"
            )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    said = spoken_text(text, learn=True)  # D-34: names as a Turkish reader says them; the captions keep `text`
    for provider in providers or available_providers():
        try:
            words, duration, used_rate = await _synthesize_provider(provider, said, out_path, voice,
                                                                    rate_pct, max_seconds)
        except TTSError as exc:
            errors.append(f"{provider}: {exc}")
            print(f"[tts] {provider} unavailable, trying the next provider. ({exc})"[:300])
            continue
        if duration > max_seconds:
            # Don't leave an over-length voiceover behind for the video builder to pick up.
            out_path.unlink(missing_ok=True)
            out_path.with_suffix(".srt").unlink(missing_ok=True)
            raise TTSError(f"voiceover is {duration:.1f}s, over the {max_seconds:.0f}s limit; shorten the script")
        if said != text:
            words = written_words(words, text)
            out_path.with_suffix(".srt").write_text(_words_to_srt(words), encoding="utf-8")
        words_path = out_path.with_name(out_path.stem + "_words.json")
        words_path.write_text(json.dumps(words, indent=2), encoding="utf-8")
        return {
            "audio_path": str(out_path),
            "srt_path": str(out_path.with_suffix(".srt")),
            "words_path": str(words_path),
            "provider": provider,
            "voice": _voice_label(provider, voice),
            "rate": _rate_str(used_rate),
            "duration_sec": round(duration, 2),
            "word_count": len(text.split()),
        }
    raise TTSError("no TTS provider succeeded: " + " | ".join(errors)[:600])


def synthesize(text: str, **kwargs) -> dict:
    """Sync wrapper: render `text` to MP3 and return paths, duration and settings."""
    return asyncio.run(synthesize_async(text, **kwargs))


# The user, 2026-10-18 (D-30): no voice credits on attempts. The editor reviews a Reel built on a silent
# stand-in; only the Reel it approves is rendered again with George (src/voice_final.py).
DRAFT_ENV = "KAVAR_DRAFT_VOICE"
DRAFT_CHARS_PER_SECOND = 13.1  # George's measured pace: 259 letters in 19.7 s (voiceover_words.json, 2026-10-12)


def draft_words(text: str, max_seconds: float = MAX_SECONDS) -> list[dict]:
    """Estimated per-word timings at George's pace, squeezed like the real voice's speed-up (max 15%)."""
    words, t = [], 0.0
    for w in " ".join(text.split()).split(" "):
        d = len(w) / DRAFT_CHARS_PER_SECOND
        words.append({"word": w, "start": round(t, 3), "end": round(t + d * 0.9, 3)})
        t += d
    if not words or not words[0]["word"]:
        raise TTSError("voiceover text is empty")
    end = words[-1]["end"]
    if end > max_seconds:
        if end > max_seconds * (1 + MAX_SPEEDUP_PCT / 100):
            raise TTSError(f"voiceover is ~{end:.1f}s, over the {max_seconds:.0f}s limit; shorten the script")
        k = max_seconds / end
        words = [{**w, "start": round(w["start"] * k, 3), "end": round(w["end"] * k, 3)} for w in words]
    return words


def draft_voice(text: str, out_path: Path | str = OUTPUT_PATH, max_seconds: float = MAX_SECONDS) -> dict:
    """Silent MP3 + estimated timings in the same shape as synthesize(); spends no credits."""
    words = draft_words(text, max_seconds)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = round(words[-1]["end"] + 0.3, 2)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", str(duration), "-q:a", "9", str(out_path)], check=True)
    out_path.with_suffix(".srt").write_text(_words_to_srt(words), encoding="utf-8")
    words_path = out_path.with_name(out_path.stem + "_words.json")
    words_path.write_text(json.dumps(words, indent=2), encoding="utf-8")
    return {"audio_path": str(out_path), "srt_path": str(out_path.with_suffix(".srt")),
            "words_path": str(words_path), "provider": "draft", "voice": "draft:silent", "rate": "+0%",
            "duration_sec": duration, "word_count": len(words)}


def reel_voice(text: str, **kwargs) -> dict:
    """The Reel pipelines' voice: the silent draft while KAVAR_DRAFT_VOICE is set (daily.py), else George."""
    if os.getenv(DRAFT_ENV):
        print("   [tts] draft: silent voice with estimated timings (George only after the editor approves)")
        return draft_voice(text)
    return synthesize(text, **kwargs)


if __name__ == "__main__":
    import sys

    # python src/tts_engine.py [provider]  -> test one provider (default: the configured chain)
    only = sys.argv[1:] or None
    print(f"providers: {only or available_providers()}")
    sample = (
        "Still writing compliance reports by hand? Meet Regunow. "
        "Ask it a regulatory question and it turns hours of research into a clear, "
        "actionable audit in minutes. Founders use it to check what stands between them "
        "and their next market before they launch. Try it free with the link in bio."
    )
    result = synthesize(sample, providers=only)
    audio = Path(result["audio_path"])
    assert audio.exists() and audio.stat().st_size > 10_000, "MP3 missing or too small"
    assert 0 < result["duration_sec"] <= MAX_SECONDS, result
    words = json.loads(Path(result["words_path"]).read_text(encoding="utf-8"))
    assert len(words) >= result["word_count"] * 0.8, "word timings look incomplete"
    print(json.dumps(result, indent=2))
    print(f"MP3 size: {audio.stat().st_size / 1024:.0f} KB, first words: "
          + ", ".join(f"{w['word']}@{w['start']}s" for w in words[:4]))

    # Error handling: empty text and text far too long for 30s must raise TTSError.
    for bad, label in (("   ", "empty"), ("word " * 200, "too long")):
        try:
            synthesize(bad, out_path=audio.with_name("should_not_exist.mp3"))
        except TTSError as exc:
            print(f"OK ({label}) -> TTSError: {exc}")
        else:
            raise AssertionError(f"{label} text did not raise")
    print("All tts_engine checks passed.")
