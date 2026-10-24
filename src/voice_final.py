"""The approved Reel gets its real voice (the user, 2026-10-18, D-30: "önce reel doğru yaptıktan sonra
editör onay verince ses kullan").

daily.py runs the Reel pipelines (main.py, trial_reel.py, tr_reel.py) with KAVAR_DRAFT_VOICE set, so
the editor reviews a Reel built on a silent voice with estimated timings and no credits are spent on
attempts. When the editor says "publish", this script re-renders the same script and pictures with
George once and rewrites output/final (video, post.json, reel_qa.json).

With KAVAR_DRAFT_VOICE set it rebuilds the draft instead (D-42: daily.py rebuilds a draft whose pictures
were measured cut, with capture["still"], on the silent voice).

    python src/voice_final.py        # heavy (render): cloud only
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
TEMP_DIR = ROOT / "output" / "temp"
CAPTURE_PATH = TEMP_DIR / "capture.json"
# D-49 (10-24: an approved Reel was voiced, then dropped for a cut): George's audio is kept, and a still rebuild
# with KAVAR_REUSE_VOICE set uses it again for the same words instead of spending credits twice
KEPT_VOICE = TEMP_DIR / "george"
REUSE_VOICE_ENV = "KAVAR_REUSE_VOICE"


def keep_voice(voice: dict, text: str) -> dict:
    """George's mp3, srt and word timings copied out of the way of the next draft voice."""
    import shutil

    KEPT_VOICE.mkdir(parents=True, exist_ok=True)
    kept = {**voice, "text": text}
    for key in ("audio_path", "srt_path", "words_path"):
        if voice.get(key) and Path(voice[key]).exists():
            kept[key] = str(shutil.copy(voice[key], KEPT_VOICE / Path(voice[key]).name))
    (KEPT_VOICE / "voice.json").write_text(json.dumps(kept, indent=1, ensure_ascii=False), encoding="utf-8")
    return kept


def kept_voice(text: str) -> dict | None:
    """The kept George voice of exactly these words, or None."""
    try:
        kept = json.loads((KEPT_VOICE / "voice.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    files_there = all(Path(kept.get(k) or "").exists() for k in ("audio_path", "srt_path", "words_path"))
    return kept if kept.get("text") == text and kept.get("provider") != "draft" and files_there else None


def save_capture(capture: dict) -> None:
    """The pipelines save the pictures they used, so the voiced render shows exactly what was approved."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_PATH.write_text(json.dumps(capture, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def main() -> int:
    from distribution import build_post
    from hyperframes_builder import FINAL_PATH, build_video_hyperframes
    from tts_engine import TTSError, reel_voice, voice_for

    script = json.loads((TEMP_DIR / "script.json").read_text(encoding="utf-8"))
    capture = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    language = json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("language", "en")
    voice = kept_voice(script["voiceover"]) if os.getenv(REUSE_VOICE_ENV) else None
    if voice:
        print("   voice: the George audio already made for these words (D-49)")
    elif os.getenv(REUSE_VOICE_ENV):
        print("✖ no kept George voice for these words; not voicing again")
        return 2
    else:
        try:
            # George; with KAVAR_DRAFT_VOICE set (D-42: a draft rebuilt still after a measured cut) the silent draft
            voice = reel_voice(script["voiceover"], voice=voice_for(language))
        except TTSError as exc:
            print(f"✖ no voice: {exc}"[:600])
            return 2
        if voice.get("provider") != "draft":
            voice = keep_voice(voice, script["voiceover"])
    print(f"   voice {voice['duration_sec']}s at {voice['rate']} ({voice['voice']})")
    video = build_video_hyperframes(script, capture, voice["audio_path"], FINAL_PATH)
    print(f"   {video['duration_sec']}s, {video['scenes']}")
    post = build_post(script, video)
    (FINAL_PATH.parent / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ voiced Reel: {FINAL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
