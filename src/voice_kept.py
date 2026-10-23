"""Voice one approved, silent Reel of a test run, once, when it is chosen to go out (D-46, the user 2026-10-23:
"yayınlanmaya uygun hazır olan reel tekrardan seslendirme ile birlikte yapılacak").

daily.py keeps the Reel's words, facts and exact pictures in <reel>/_voice; this rebuilds the same Reel with
George (src/voice_final.py) and applies the same measured checks as production (first frame, 14-26 s, no
picture running off the frame).

    python src/voice_kept.py output/reels/<reel>     # heavy (render, George): cloud only, voice.yml
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
TEMP_DIR = ROOT / "output" / "temp"
REEL_SECONDS = (14.0, 26.0)


def restore(folder: Path) -> None:
    """<reel>/_voice back where voice_final reads it (paths made absolute again)."""
    kit = folder / "_voice"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("script.json", "tool.json"):
        shutil.copy(kit / name, TEMP_DIR / name)
    capture = json.loads((kit / "capture.json").read_text(encoding="utf-8"))
    for key in ("proof_path", "screenshot_path", "fullpage_path", "logo_path"):
        if capture.get(key) and not Path(capture[key]).is_absolute():
            capture[key] = str(ROOT / capture[key])
    (TEMP_DIR / "capture.json").write_text(json.dumps(capture, indent=2, ensure_ascii=False), encoding="utf-8")


def main(folder: Path) -> int:
    import voice_final
    from reel_qa import cut_frames, first_frame_report, make_cover, pacing_report

    restore(folder)
    if (code := voice_final.main()) != 0:
        print("✖ no voice (both ElevenLabs accounts refused?): nothing changed")
        return code
    final = ROOT / "output" / "final"
    for name in ("final_video.mp4", "post.json"):
        shutil.copy(final / name, folder / name)
    make_cover(folder / "final_video.mp4", folder)
    first = first_frame_report(folder / "final_video.mp4", folder)
    dur = pacing_report(folder / "final_video.mp4")["duration_sec"]
    cut = cut_frames(folder / "final_video.mp4", folder)
    if not first["ok"] or not REEL_SECONDS[0] <= dur <= REEL_SECONDS[1] or cut:
        print(f"✖ voiced Reel failed the measured checks: first frame ok={first['ok']}, {dur:.1f}s, cut at {cut[:6]}")
        return 1
    print(f"✅ voiced with George: {folder} ({dur:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
