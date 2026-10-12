"""Assemble the final 9:16 video with FFmpeg (one filter graph, one encode).

Scenes (stills from scene_composer, animated here; lengths derived from the voiceover):
  1..n   up to 4 sections of the site (cut from fullpage.png), each in a browser
         mockup over a blurred backdrop, with a Ken Burns move that changes per scene
         (zoom in, pan down, zoom out, pan up); the hook title sits on the first scene
  last   outro card with the site's logo, tool name and domain
Scenes are joined with varied xfade transitions. Throughout: word-by-word captions
from tts_engine's timings (white on black, spoken word in yellow).
Audio is the TTS voiceover. Output: H.264 / AAC, config.json size and fps.
"""

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from scene_composer import browser_scene, outro_scene, pick_sections

ROOT = Path(__file__).resolve().parent.parent
TEMP_DIR = ROOT / "output" / "temp"
FINAL_PATH = ROOT / "output" / "final" / "final_video.mp4"

HOOK_SECONDS = 3.0
MAX_SECTIONS = 4
OUTRO_SECONDS = 2.8
TRANSITION = 0.45
KEN_BURNS = 0.06  # zoom / pan travel per scene (must stay below the mockup's top/bottom margin)
TRANSITIONS = ["smoothup", "slideleft", "circleopen", "smoothleft"]
TAIL_SECONDS = 0.6  # silence after the last word so the video doesn't end abruptly
MAX_SECONDS = 30.0
WORDS_PER_CAPTION = 3
CAPTION_GAP_BREAK = 0.25  # a pause this long (end of sentence/comma) starts a new caption
FONT_FILE = Path("C:/Windows/Fonts/seguibl.ttf")
FONT_NAME = "Segoe UI Black"

# ASS colours are &HAABBGGRR (alpha 00 = opaque). The box is fully opaque: busy page
# text can't show through, and per-line boxes overlap without visible seams.
WHITE, YELLOW, BOX = "&H00FFFFFF", "&H0000E5FF", "&H00000000"


class BuildError(Exception):
    """The video could not be rendered."""


def _load_config() -> tuple[int, int, int]:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    return cfg["video_width"], cfg["video_height"], cfg.get("fps", 30)


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _ass_text(text: str) -> str:
    return re.sub(r"[{}\\]", "", text).strip()


def _group_captions(words: list[dict]) -> list[list[dict]]:
    """Split word timings into short on-screen chunks, breaking at pauses."""
    chunks, current = [], []
    for word in words:
        if current and (len(current) >= WORDS_PER_CAPTION
                        or word["start"] - current[-1]["end"] > CAPTION_GAP_BREAK):
            chunks.append(current)
            current = []
        current.append(word)
    if current:
        chunks.append(current)
    return chunks


def build_ass(hook: str, words: list[dict], width: int, height: int, hook_seconds: float) -> str:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,{FONT_NAME},92,{WHITE},{WHITE},{BOX},{BOX},0,0,0,0,100,100,0,0,3,26,0,8,90,90,{int(height * 0.27)},1
Style: Caption,{FONT_NAME},84,{WHITE},{WHITE},{BOX},{BOX},0,0,0,0,100,100,0,0,3,18,0,2,70,70,{int(height * 0.25)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    # Hook: pops in (scale 80% -> 100%) and fades out at the end of the intro.
    hook_text = _ass_text(hook).upper()
    events.append(
        f"Dialogue: 1,{_ass_time(0)},{_ass_time(hook_seconds)},Hook,,0,0,0,,"
        f"{{\\fad(120,250)\\fscx80\\fscy80\\t(0,180,\\fscx100\\fscy100)}}{hook_text}"
    )

    # Captions: one event per spoken word, so the active word turns yellow.
    chunks = _group_captions(words)
    for ci, chunk in enumerate(chunks):
        next_start = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else chunk[-1]["end"] + 0.4
        chunk_end = min(next_start, chunk[-1]["end"] + 0.4)
        for wi, word in enumerate(chunk):
            start = word["start"]
            end = chunk[wi + 1]["start"] if wi + 1 < len(chunk) else chunk_end
            parts = [
                (f"{{\\c{YELLOW}}}" if j == wi else f"{{\\c{WHITE}}}") + _ass_text(w["word"]).upper()
                for j, w in enumerate(chunk)
            ]
            events.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{' '.join(parts)}"
            )
    return header + "\n".join(events) + "\n"


def _ken_burns(move: str, frames: int, w: int, h: int, fps: int) -> str:
    """zoompan expression for one scene; input is pre-scaled 2x so motion is smooth."""
    n = max(frames - 1, 1)
    p = f"(1-cos(PI*on/{n}))/2"  # eased progress 0 -> 1
    centre = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    z_pan = 1 + KEN_BURNS
    expr = {
        "zoom_in": f"z='1+{KEN_BURNS}*{p}':{centre}",
        "zoom_out": f"z='{z_pan}-{KEN_BURNS}*{p}':{centre}",
        "pan_down": f"z='{z_pan}':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*{p}'",
        "pan_up": f"z='{z_pan}':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-{p})'",
    }[move]
    return f"zoompan={expr}:d=1:s={w}x{h}:fps={fps}"


def build_video(
    hook: str,
    tool_name: str,
    website_url: str,
    audio_path: Path | str = TEMP_DIR / "voiceover.mp3",
    words_path: Path | str = TEMP_DIR / "voiceover_words.json",
    screenshot_path: Path | str = TEMP_DIR / "screenshot.png",
    fullpage_path: Path | str | None = TEMP_DIR / "fullpage.png",
    logo_path: Path | str | None = TEMP_DIR / "logo.png",
    out_path: Path | str = FINAL_PATH,
) -> dict:
    """Render the final video and return its path, duration, size and render time."""
    width, height, fps = _load_config()
    audio_path, words_path, screenshot_path = Path(audio_path), Path(words_path), Path(screenshot_path)
    out_path = Path(out_path)
    for p in (audio_path, words_path, screenshot_path):
        if not p.exists():
            raise BuildError(f"missing input: {p}")
    if not FONT_FILE.exists():
        raise BuildError(f"caption font not found: {FONT_FILE}")

    t0 = time.perf_counter()
    audio_seconds = _probe_duration(audio_path)
    total = min(audio_seconds + TAIL_SECONDS, MAX_SECONDS)
    words = json.loads(words_path.read_text(encoding="utf-8"))

    # Work in TEMP_DIR with relative names: FFmpeg filter args choke on "C:\..." paths.
    work = TEMP_DIR / "build"
    work.mkdir(parents=True, exist_ok=True)
    (work / "fonts").mkdir(exist_ok=True)
    shutil.copy2(FONT_FILE, work / "fonts" / FONT_FILE.name)
    for old in work.glob("scene_*.png"):
        old.unlink()

    # Scene stills: site sections in a browser mockup, then the logo outro card.
    sections = pick_sections(Path(fullpage_path) if fullpage_path else None, screenshot_path,
                             width, height, MAX_SECTIONS)
    outro_seconds = min(OUTRO_SECONDS, total * 0.2)
    # Keep each section on screen >= ~4s: fewer sections for short videos.
    n = max(1, min(len(sections), int((total - outro_seconds) // 4)))
    scenes = [browser_scene(s, website_url, width, height) for s in sections[:n]]
    logo = Path(logo_path) if logo_path and Path(logo_path).exists() else None
    scenes.append(outro_scene(sections[0], logo, tool_name, website_url, width, height))
    scene_files = []
    for i, img in enumerate(scenes):
        f = work / f"scene_{i}.png"
        img.save(f)
        scene_files.append(f)

    # Durations: n sections share the time left after the outro; transitions overlap.
    section_seconds = (total - outro_seconds + n * TRANSITION) / n
    durations = [section_seconds] * n + [outro_seconds]  # sum - n * TRANSITION == total
    hook_seconds = min(HOOK_SECONDS, section_seconds - TRANSITION)
    (work / "captions.ass").write_text(build_ass(hook, words, width, height, hook_seconds), encoding="utf-8")

    moves = ["zoom_in", "pan_down", "zoom_out", "pan_up"]
    parts, inputs = [], []
    for i, (f, dur) in enumerate(zip(scene_files, durations)):
        frames = int(round(dur * fps))
        move = "zoom_in" if i == len(scene_files) - 1 else moves[i % len(moves)]
        inputs += ["-i", f.name]
        parts.append(
            f"[{i}:v]scale={width * 2}:{height * 2},loop=loop={frames - 1}:size=1,setpts=N/{fps}/TB,"
            f"{_ken_burns(move, frames, width, height, fps)},setsar=1,format=yuv420p,"
            f"fps={fps},settb=1/{fps}[s{i}]"
        )
    # Chain xfades; each offset is where the next scene starts fading in.
    prev, offset = "[s0]", 0.0
    for i in range(1, len(scene_files)):
        offset += durations[i - 1] - TRANSITION
        transition = "fade" if i == len(scene_files) - 1 else TRANSITIONS[(i - 1) % len(TRANSITIONS)]
        out = f"[x{i}]"
        parts.append(f"{prev}[s{i}]xfade=transition={transition}:duration={TRANSITION}:offset={offset:.3f}{out}")
        prev = out
    audio_index = len(scene_files)
    inputs += ["-i", str(audio_path)]

    filter_complex = ";".join(parts) + f";{prev}ass=captions.ass:fontsdir=fonts[v]"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", f"{audio_index}:a",
        "-t", f"{total:.3f}", "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-af", f"apad=whole_dur={total:.3f}",  # pad the tail with silence
        "-movflags", "+faststart", str(out_path),
    ]
    try:
        subprocess.run(cmd, cwd=work, check=True, capture_output=True, text=True, timeout=600)
    except FileNotFoundError as exc:
        raise BuildError("ffmpeg not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise BuildError(f"ffmpeg failed: {exc.stderr.strip()[-800:]}") from exc

    return {
        "video_path": str(out_path),
        "duration_sec": round(_probe_duration(out_path), 2),
        "size_mb": round(out_path.stat().st_size / 1_048_576, 2),
        "render_seconds": round(time.perf_counter() - t0, 1),
        "scenes": f"{n} site sections + outro" + (" (with logo)" if logo else " (no logo)"),
        "caption_events": len(words),
    }


if __name__ == "__main__":
    # Reuses the latest pipeline outputs in output/temp (script.json, voiceover, captures).
    script = json.loads((TEMP_DIR / "script.json").read_text(encoding="utf-8"))
    hook = script["hook"]
    result = build_video(hook, script["tool_name"], script["website_url"])
    print(json.dumps(result, indent=2, ensure_ascii=False))

    width, height, fps = _load_config()
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt", "-of", "json", result["video_path"]],
        capture_output=True, text=True, check=True,
    ).stdout)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert (video["width"], video["height"]) == (width, height), video
    assert video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p", video
    assert video["r_frame_rate"] == f"{fps}/1", video
    assert audio["codec_name"] == "aac", audio
    assert 0 < result["duration_sec"] <= MAX_SECONDS, result
    print(f"Video: {video['codec_name']} {video['width']}x{video['height']} @ {video['r_frame_rate']} fps, "
          f"audio: {audio['codec_name']}")

    # Error handling: a missing input must raise BuildError.
    try:
        build_video(hook, script["tool_name"], script["website_url"], audio_path=TEMP_DIR / "missing.mp3")
    except BuildError as exc:
        print(f"OK (missing input) -> BuildError: {exc}")
    else:
        raise AssertionError("missing audio did not raise")
    print("All video_builder checks passed.")
