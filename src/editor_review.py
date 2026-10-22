"""Editor-in-chief check before anything is published automatically.

Claude (local `claude -p`, Read tool only, limited to the run folder) looks at a
contact sheet of the rendered slides / video frames and reads the text and the
source, then returns a verdict:
  publish  - ready
  fix      - small text fixes listed per slide (applied, re-rendered, checked once more)
  reject   - don't publish (wrong facts, misleading cover, broken layout, policy breach)
"""

import json
import os
import subprocess
from pathlib import Path

from PIL import Image

from reel_qa import first_frame_report, make_cover, pacing_report
from script_writer import CLI_TIMEOUT, NO_PRICE_RULE, _claude_cli
from skill_rules import editor_lessons, skill_rules

REEL_RULES = skill_rules("reel-retention-editor")

VERDICT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "problems", "fixes"],
    "properties": {
        "verdict": {"type": "string", "enum": ["publish", "fix", "reject"]},
        "problems": {"type": "array", "items": {"type": "string"}},
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["slide", "title", "body"],
                "properties": {"slide": {"type": "integer"}, "title": {"type": "string"},
                               "body": {"type": "string"}},
            },
        },
    },
}

SYSTEM = f"""You are the editor-in-chief of KAVAR (@thekavar.ai), a Turkish Instagram page about \
AI news and tools. Nothing reaches the page without your approval, and nobody else reviews it. \
Use the Read tool to open the files named in the message (images included), then judge like a \
strict news editor and senior designer:
- Facts: every claim, number, date and name on the slides must be supported by the source text. \
Anything not in the source (guesses, "when it comes to Turkey", invented benefits) is a problem.
- Honesty: the cover / hook must not mislead (e.g. promising readers a product they can't use: \
region or age limits). Quotes attributed correctly.
- Policy: {NO_PRICE_RULE} No political campaigning. No other creators' content.
- Relevance: the page covers AI and tech. Reject stories that are not about AI / tech (e.g. entertainment or politics with no AI angle) or that are too thin to be worth a post.
- Turkish: natural and grammatical; uppercase dotted İ correct.
- Design (contact sheet): text cut off, overlapping, unreadable, broken images, a still with a \
play button that doesn't play, wrong brand. The handle must be @thekavar.ai.
- Agreed design (DECISIONS.md D-17/D-20), never a problem: the cover headline is 3-6 big words, and the feed cover has a "KAYDIR →" pill at the bottom right (a swipe cue, not an ad button).
Verdict: "publish" if it is ready; "fix" only for text problems you can fix by rewriting a slide's \
title/body (give each fix with the 1-based slide number and the complete new title and body, \
keeping **highlight** marks and similar length); "reject" for anything else that is wrong. \
List every problem you found in Turkish, short."""
if _lessons := editor_lessons():  # rules/editor_lessons.md: hand-fixed rejections
    SYSTEM += "\n\n" + _lessons


def contact_sheet(images: list[Path], out: Path, cols: int = 5, w: int = 432) -> Path:
    tiles = [Image.open(p).convert("RGB") for p in images]
    h = round(w * tiles[0].height / tiles[0].width)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(out, quality=88)
    return out


def video_frames(video: Path, out_dir: Path, times: list[float]) -> list[Path]:
    frames = []
    for t in times:
        f = out_dir / f"_frame_{t:.1f}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                        str(f)], timeout=120)
        if f.exists():
            frames.append(f)
    return frames


def _ask(folder: Path, message: str) -> dict:
    exe = _claude_cli()
    if not exe:
        return {"verdict": "reject", "problems": ["editor unavailable (claude CLI missing)"], "fixes": []}
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run(
            [exe, "-p", "--output-format", "json", "--json-schema", json.dumps(VERDICT_SCHEMA),
             "--system-prompt", SYSTEM, "--tools", "Read", "--allowedTools", "Read",
             "--no-session-persistence"],
            input=message, capture_output=True, text=True, encoding="utf-8",
            timeout=CLI_TIMEOUT * 2, cwd=folder, env=env,
        )
        out = json.loads(proc.stdout)
        verdict = out.get("structured_output")
        why = f"{out.get('subtype')}, is_error={out.get('is_error')}: {str(out.get('result'))[:200]}"
    except subprocess.TimeoutExpired:
        verdict, why = None, f"timed out after {CLI_TIMEOUT * 2}s"
    except json.JSONDecodeError:
        verdict, why = None, f"exit {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:200]}"
    if not verdict:  # D-38: the reason is logged, so a usage limit never looks like a real rejection
        return {"verdict": "reject", "problems": [f"editor gave no verdict ({why})"], "fixes": []}
    return verdict


def review_carousel(folder: Path) -> dict:
    """folder: a run folder from carousel.py (carousel.json, carousel/, story/, article/)."""
    slides = sorted((folder / "carousel").glob("*"))
    images = []
    for s in slides:
        if s.suffix == ".mp4":
            images += video_frames(s, folder, [5.0])[:1]
        else:
            images.append(s)
    sheet = contact_sheet(images, folder / "_review_sheet.jpg")
    story = contact_sheet(sorted((folder / "story").glob("*.jpg")), folder / "_review_story.jpg", cols=5, w=324)
    source = "article/article.json" if (folder / "article" / "article.json").exists() else "carousel.json"
    msg = (f"Review this carousel before publishing.\n"
           f"- Slides in order (contact sheet, left to right, top to bottom): {sheet.name}\n"
           f"- Story frames: {story.name}\n"
           f"- The text (slides, story, caption): carousel.json\n"
           f"- The source: {source} (field 'text' is the article; field 'trial_note', when present, "
           f"is our own test of the model: the 'Biz denedik' slides must match it, and the figures "
           f"credited 'KAVAR denemesi' are its real outputs)\n")
    return _ask(folder, msg)


def review_reel(video: Path, script: dict, tool: dict) -> dict:
    """Retention-editor review (reel-retention-editor skill): measured first-frame / pacing checks
    first, then Claude looks at frame 0, the opening seconds, later frames and the cover."""
    folder = video.parent
    first = first_frame_report(video, folder)
    pace = pacing_report(video)
    if not first["ok"]:  # no need to ask anyone: a blank first frame never goes out
        return {"verdict": "reject", "problems": [f"ilk kare boş / okunaksız: {first}"], "fixes": []}
    dur = pace["duration_sec"]
    # the middle frame plus one 1 s later: a single middle frame can fall on a card's first moment, when
    # its box is in but its text is still arriving (Ultracite 10-17: "empty card" at 12.1 s, full at 12.5 s)
    mid = round(dur * 0.5, 1)
    times = [0.0, 1.0, 2.5, 5.0, mid, round(min(mid + 1.0, max(0.0, dur - 1.5)), 1), round(max(0.0, dur - 1.0), 1)]
    sheet = contact_sheet(video_frames(video, folder, times), folder / "_review_sheet.jpg", cols=7, w=270)
    cover = make_cover(video, folder)
    work = folder / "_review_script.json"
    work.write_text(json.dumps({"tool_data_source": tool, "script": script, "measured": {
        "first_frame": first, "pacing": pace}}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    msg = (f"Review this {dur:.0f}-second Reel before publishing, as its retention editor.\n"
           f"- Frames at {'/'.join(f'{t:g}' for t in times)} s (frame 0 first): {sheet.name}. Scenes animate "
           f"in over ~1 s, so judge a half-built card by the frame 1 s later before calling it empty.\n"
           f"- The cover as the profile grid crops it: {Path(cover['grid']).name}\n"
           f"- Script (hook candidates, chosen hook, voiceover), caption, hashtags, tool facts and the "
           f"measured first-frame / pacing numbers: {work.name}\n"
           f"Judge the facts against tool_data_source. Apply these rules:\n{REEL_RULES}\n"
           f"Slide numbers in fixes are not used for Reels, so use 'reject' for real problems."
           + ("\nThis is a 'Biz denedik' Reel: the page ran the new model itself. Its pictures are our own "
              "unedited test outputs of the model (they replace the site images, so the 'proof from the "
              "product's own site' rule is met by them), and 'denedik / yazdırdık / sorduk' about these tests "
              "is true. Judge every result claim against tool_data_source.kavar_test, the rest against "
              "tool_data_source.article." if tool.get("kavar_test") else ""))
    return _ask(folder, msg)
