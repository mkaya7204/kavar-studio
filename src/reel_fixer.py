"""A rejected silent draft is fixed, not thrown away (D-33, the user, 2026-10-18: "editör red derse sen devreye
giriyorsun, düzeltilecek bir yanı varsa düzelt ... editör haklı deyip düzeltmeden reel iptal edip başka reel
aramıyorsun ... kalıcı çözüm").

daily.py runs this after the editor rejects a draft Reel (the draft has no voice yet, D-30, so a fix costs no
credits). One Claude call reads the editor's problems, the script, the tool's facts, the rejected frames and
a numbered sheet of every picture we have of the product, and either:
  - fixes it: rewrites the text (overstated claims, facts, hashtags, caption, hook) and picks the pictures
    that really show the promise (or rewrites the promise to match what the pictures show), or
  - says it can't be fixed: the topic itself is wrong (no AI in it, off the slot's concept, nothing honest
    to say), or no picture of the product shows anything usable.
A fix is checked like any script (VideoScript, word limit, Reel rules, no prices), rendered again on the
draft voice and goes back to the editor (daily.REEL_FIX_ROUNDS times at most).

    python src/reel_fixer.py <reel folder>      # heavy (render): cloud only; exit 0 fixed, 3 unfixable
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
TEMP_DIR = ROOT / "output" / "temp"
WORK = TEMP_DIR / "fix"
UNFIXABLE = 3
MAX_WORDS = 38  # the Reels' voiceover limit (under 26 s)
TILE = (300, 300)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fixable", "reason", "proof", "shots", "hook", "segments", "key_points", "why_it_matters",
                 "caption", "hashtags"],
    "properties": {
        "fixable": {"type": "boolean"},
        "reason": {"type": "string"},
        "proof": {"type": "integer"},
        "shots": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
        "hook": {"type": "string"},
        "segments": {
            "type": "object", "additionalProperties": False,
            "required": ["hook", "point1", "point2", "point3", "why", "cta"],
            "properties": {k: {"type": "string"} for k in ("hook", "point1", "point2", "point3", "why", "cta")},
        },
        "key_points": {
            "type": "array", "minItems": 3, "maxItems": 3,
            "items": {"type": "object", "additionalProperties": False, "required": ["title", "detail"],
                      "properties": {"title": {"type": "string"}, "detail": {"type": "string"}}},
        },
        "why_it_matters": {"type": "string"},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM = """You fix rejected Reels for KAVAR (@thekavar.ai), a Turkish Instagram page about AI. The editor \
rejected this silent draft. Your job is to make it publishable, not to agree with the editor and give up. \
Use the Read tool to open the files named in the message (images included).
Decide first: can it be fixed?
- NOT fixable only when the topic itself is wrong: the product has no AI in it, it is off the slot's concept, \
the source is too thin for one honest claim, or not one of the numbered pictures shows the product's real \
interface, output or result (no logo cards, slogans, marketing tables, empty forms).
- Everything else IS fixable, and you fix every problem the editor listed:
  * a claim stronger than the source: say exactly what the source says ("şirkete göre", "yardımcı oluyor").
  * a picture that doesn't show the promise: choose another numbered picture that does, OR rewrite the hook \
and cards so they promise what the best picture really shows. The proof picture (first) must prove the hook.
  * cut-off, tiny or unreadable picture text: choose a picture whose text is whole and big.
  * caption/hashtags off topic: rewrite them (product and feature first, #yapayzeka only for AI).
  * subtitles over the picture's text: choose a picture with a calm area at the bottom, or another one.
Rules for the text: Turkish, natural, uppercase dotted İ correct; hook 3-6 words (at most 32 characters); \
segments are the voiceover in order (hook, point1, point2, point3, why, cta), together at most 38 words; \
key_points follow point1-3 (title under 6 words, detail under 14 words); facts only from the tool's source; \
"""


def _ask(message: str, system: str) -> dict | None:
    from script_writer import CLI_TIMEOUT, _claude_cli

    exe = _claude_cli()
    if not exe:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run(
            [exe, "-p", "--output-format", "json", "--json-schema", json.dumps(SCHEMA), "--system-prompt", system,
             "--tools", "Read", "--allowedTools", "Read", "--no-session-persistence"],
            input=message, capture_output=True, text=True, encoding="utf-8", timeout=CLI_TIMEOUT * 2,
            cwd=WORK, env=env)
        return json.loads(proc.stdout).get("structured_output")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def candidates(capture: dict) -> list[Path]:
    """Every picture we have of the product, as files: the pipeline's own pictures (guide / trial Reels list
    them in capture["pictures"]), else proof-shaped windows over the site's full page (tool Reels)."""
    from hyperframes_builder import PROOF_SIZE, _proof_windows

    WORK.mkdir(parents=True, exist_ok=True)
    out = []
    if capture.get("pictures_locked"):  # "Biz denedik": our own outputs stay as they are
        return out
    pictures =[Path(p) for p in capture.get("pictures", []) if Path(p).exists()]
    if pictures:
        for i, p in enumerate(pictures):
            dst = WORK / f"cand_{i}.png"
            with Image.open(p) as img:
                img.convert("RGB").save(dst)
            out.append(dst)
        return out
    page = Path(capture.get("fullpage_path") or capture.get("screenshot_path") or "")
    if not page.exists():
        return out
    with Image.open(page) as img:
        img = img.convert("RGB")
        win_h = round(img.width * PROOF_SIZE[1] / PROOF_SIZE[0])
        for i, top in enumerate(_proof_windows(img, screens=6)):
            dst = WORK / f"cand_{i}.png"
            img.crop((0, top, img.width, min(img.height, top + win_h))).save(dst)
            out.append(dst)
    return out


def sheet(pictures: list[Path]) -> Path:
    """A numbered contact sheet of the candidates (the number is what the fixer answers with)."""
    cols = 4
    rows = (len(pictures) + cols - 1) // cols
    board = Image.new("RGB", (cols * TILE[0], rows * (TILE[1] + 8)), "white")
    draw = ImageDraw.Draw(board)
    for i, p in enumerate(pictures):
        with Image.open(p) as img:
            tile = ImageOps.contain(img.convert("RGB"), TILE)
        x, y = (i % cols) * TILE[0], (i // cols) * (TILE[1] + 8)
        board.paste(tile, (x + (TILE[0] - tile.width) // 2, y + (TILE[1] - tile.height) // 2))
        draw.rectangle((x, y, x + 46, y + 40), fill="red")
        draw.text((x + 16, y + 12), str(i), fill="white")
    path = WORK / "candidates.jpg"
    board.save(path, quality=88)
    return path


def apply_text(script: dict, fix: dict) -> dict:
    """The fixer's text in the script: voiceover = the segments in order, cards and the on-screen hook."""
    seg = fix["segments"]
    out = {**script, "hook": fix["hook"], "voiceover_segments": seg,
           "voiceover": " ".join(seg[k].strip() for k in ("hook", "point1", "point2", "point3", "why", "cta")
                                 if seg[k].strip()),
           "key_points": fix["key_points"], "why_it_matters": fix["why_it_matters"], "caption": fix["caption"],
           "hashtags": fix["hashtags"]}
    return out


def text_problems(script: dict) -> list[str]:
    """The same checks every Reel script passes (VideoScript, word limit, Reel rules, no prices)."""
    from script_writer import VideoScript, _script_price_mentions, reel_rule_problems

    try:
        checked = VideoScript.model_validate(script)
    except ValueError as exc:
        return [str(exc)[:500]]
    problems = []
    if checked.voiceover_words > MAX_WORDS:
        problems.append(f"voiceover has {checked.voiceover_words} words; max {MAX_WORDS}")
    if bad := _script_price_mentions(checked):
        problems.append(f"price words: {', '.join(bad)}")
    return problems + reel_rule_problems(checked)


def apply_pictures(capture: dict, pictures: list[Path], proof: int, shots: list[int]) -> dict:
    """proof.png and the two shot frames from the chosen candidates, where the builder reads them."""
    from hyperframes_builder import PROOF_SIZE, SHOT_NAMES, _shot_frame

    if not pictures:
        return capture
    pick = lambda i: pictures[i] if 0 <= i < len(pictures) else None  # noqa: E731
    folder = Path(capture.get("proof_path") or TEMP_DIR / "proof.png").parent
    folder.mkdir(parents=True, exist_ok=True)
    if src := pick(proof):
        with Image.open(src) as img:
            ImageOps.fit(img.convert("RGB"), PROOF_SIZE, Image.LANCZOS, centering=(0.5, 0.4)).save(folder / "proof.png")
    for name, i in zip(SHOT_NAMES, shots):
        if src := pick(i):
            with Image.open(src) as img:
                img = img.convert("RGB")
                if img.width < 960:
                    img = img.resize((960, round(img.height * 960 / img.width)), Image.LANCZOS)
                img.thumbnail((960, 1300), Image.LANCZOS)
                _shot_frame(img, folder / name)
    # the builder takes the shots next to proof.png; a tool Reel keeps its full page (the next fix's candidates)
    shot2 = str(folder / SHOT_NAMES[1]) if capture.get("pictures") else capture.get("fullpage_path")
    return {**capture, "proof_path": str(folder / "proof.png"), "screenshot_path": str(folder / SHOT_NAMES[0]),
            "fullpage_path": shot2}


def main(folder: Path) -> int:
    from distribution import build_post
    from hyperframes_builder import FINAL_PATH, build_video_hyperframes
    from script_writer import _load_language
    from skill_rules import editor_lessons
    from tts_engine import reel_voice, voice_for
    from voice_final import CAPTURE_PATH, save_capture

    verdict = json.loads((folder / "_verdict.json").read_text(encoding="utf-8"))
    script = json.loads((TEMP_DIR / "script.json").read_text(encoding="utf-8"))
    tool = json.loads((TEMP_DIR / "tool.json").read_text(encoding="utf-8"))
    capture = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    pictures = candidates(capture)
    WORK.mkdir(parents=True, exist_ok=True)
    board = sheet(pictures) if pictures else None
    rejected = folder / "_review_sheet.jpg"
    if rejected.exists():
        rejected = Path(shutil.copy(rejected, WORK / "rejected_frames.jpg"))
    (WORK / "reel.json").write_text(json.dumps({"editor_problems": verdict.get("problems", []), "script": script,
                                                "tool_data_source": tool}, indent=2, ensure_ascii=False,
                                               default=str), encoding="utf-8")
    system = SYSTEM + "never prices or free / paid (plans, beta and credit use may be named when the source says so)."
    if lessons := editor_lessons():
        system += "\n\nThe editor's lessons (follow them too):\n" + lessons
    message = (f"Fix this rejected Reel.\n- The editor's problems, the current script and the tool's source: reel.json\n"
               f"- The rejected draft's frames: {rejected.name if rejected.exists() else '(none)'}\n"
               + (f"- Every picture we have of the product, numbered 0-{len(pictures) - 1}: {board.name}. proof is "
                  f"the hook's picture, shots the two later ones (-1 keeps the current picture).\n" if board else
                  "- No other pictures exist: keep proof -1 and shots [-1, -1].\n")
               + "Return the complete fixed text (unchanged parts copied as they are).")
    for attempt in (1, 2):
        fix = _ask(message, system)
        if not fix:
            print("✖ fixer gave no answer")
            return UNFIXABLE
        if not fix["fixable"]:
            print(f"✖ not fixable: {fix['reason']}")
            return UNFIXABLE
        fixed = apply_text(script, fix)
        problems = text_problems(fixed)
        if not problems:
            break
        print(f"   fix {attempt} broke the script rules: {'; '.join(problems)[:300]}")
        message += f"\n\nYour last answer broke these rules, fix them too: {'; '.join(problems)}"
    else:
        return UNFIXABLE
    print(f"   fix: {fix['reason'][:300]}")
    print(f"   hook: \"{fixed['hook']}\", proof {fix['proof']}, shots {fix['shots']}")
    capture = apply_pictures(capture, pictures, fix["proof"], fix["shots"])
    voice = reel_voice(fixed["voiceover"], voice=voice_for(_load_language()))
    (TEMP_DIR / "script.json").write_text(json.dumps(fixed, indent=2, ensure_ascii=False), encoding="utf-8")
    save_capture(capture)
    video = build_video_hyperframes(fixed, capture, voice["audio_path"], FINAL_PATH)
    print(f"   {video['duration_sec']}s, {video['scenes']}")
    post = build_post(fixed, video)
    (FINAL_PATH.parent / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ fixed draft: {FINAL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
