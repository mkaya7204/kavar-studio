"""Render the final 9:16 video with HyperFrames (HTML composition -> MP4).

The composition template lives in templates/hyperframes_news/ (index.html). Per video,
it is copied to output/temp/hyperframes/, the captured media are dropped into its
assets/ folder under fixed names, and the script's text goes in as composition
variables (--variables-file). Flow (reel-cover-designer / reel-retention-editor skills):
  hook    the headline over the product screen, fully visible on frame 0 (it is also the cover)
  cards   the 3 key points as animated cards, with the site's screenshot (zoom) and
          full page (pan) in between
  why     why it matters
  outro   ~2 s: the closing send/save line, the source and the page's wordmark
When the script has voiceover_segments and the TTS word timings exist, plan_timeline() moves
every scene boundary to where its part is spoken and sizes the Reel to its voice (about
17-25 s, never padded to 30 s), word-synced captions follow the voice, and soundtrack.py mixes
the re-timed voice with a music bed and transition SFX. Without timings the fixed 30 s
DEFAULT_PLAN is used. After the render, cover.jpg / cover_grid.jpg are saved next to the video.
Output: H.264 / AAC MP4 at config.json size and fps.
"""

import html
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from reel_qa import first_frame_report, make_cover, pacing_report
from soundtrack import SoundtrackError, build_soundtrack

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates" / "hyperframes_news"
TEMP_DIR = ROOT / "output" / "temp"
BUILD_DIR = TEMP_DIR / "hyperframes"
FINAL_PATH = ROOT / "output" / "final" / "final_video.mp4"

HYPERFRAMES = "hyperframes@0.8.145"  # pinned so renders stay reproducible
FONT_FILES = [Path("C:/Windows/Fonts/seguibl.ttf"), Path("C:/Windows/Fonts/seguisb.ttf")]
RENDER_TIMEOUT = 1800  # seconds
RENDER_WORKERS = 1  # each worker is a ~256 MB Chrome; "auto" ran this 4 GB machine out of memory
TOTAL = 30.0  # seconds; the longest Reel, and the length of the fixed fallback plan
MIN_TOTAL = 12.0

# Scene order; point1/point2 scenes also hold a site shot after their card.
SCENES = ["hook", "card1", "shot1", "card2", "shot2", "card3", "why", "outro"]
DEFAULT_PLAN = {"hook": [0, 3], "card1": [3, 4], "shot1": [7, 2.5], "card2": [9.5, 4],
                "shot2": [13.5, 2.5], "card3": [16, 4], "why": [20, 7], "outro": [27, 3]}
SEGMENT_MIN = [1.8, 3.6, 3.6, 2.4, 2.6]  # hook, point1, point2, point3, why (seconds on screen)
OUTRO_MIN = 2.0  # the closing card: long enough to read the send line, short enough not to lose viewers
VOICE_TAIL = 0.5  # silence kept after the last word
LEAD = 0.25  # a scene appears this long before its part is spoken
EXTRA_PAUSE = 0.12  # breathing room added per scene cut (no padding towards a fixed length)
CAPTION_MAX_WORDS = 3
CAPTION_MAX_CHARS = 16

# On-screen labels per config.json "language".
LABELS = {
    "tr": {"why_label": "NEDEN ÖNEMLİ?", "source_label": "KAYNAK", "follow_label": "TAKİP ET",
           "follow_sub": "Her gün yeni teknoloji haberleri için", "kicker": ""},
    "en": {"why_label": "WHY IT MATTERS", "source_label": "SOURCE", "follow_label": "FOLLOW",
           "follow_sub": "New tech stories every day", "kicker": ""},
}


class BuildError(Exception):
    """The video could not be rendered."""


def _load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _load_brand() -> dict:
    """The page's brand (brand.json, shared with the carousel pipeline)."""
    return json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))


def _npx() -> str:
    exe = shutil.which("npx") or shutil.which("npx.cmd")
    if not exe:
        raise BuildError("npx not found on PATH (install Node.js to render with HyperFrames)")
    return exe


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _domain(url: str) -> str:
    return (urlsplit(url).hostname or url).removeprefix("www.")


def _norm(text: str) -> str:
    return re.sub(r"[\W_]", "", text.casefold())


def _segments_from_sentences(voiceover: str) -> list[str] | None:
    """Old scripts: hook = first sentence, cta = last, why = second last, points share the middle."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", voiceover.strip()) if s]
    if len(sentences) < 6:
        return None
    middle = sentences[1:-2]
    parts: list[list[str]] = [[], [], []]
    total, acc = sum(len(s.split()) for s in middle), 0
    for i, sentence in enumerate(middle):
        # Next point once this one has its share of words, keeping one sentence for each later point.
        cur = _point_index(acc, total, i, len(middle))
        parts[cur].append(sentence)
        acc += len(sentence.split())
    if not all(parts):
        return None
    return [sentences[0], *(" ".join(p) for p in parts), sentences[-2], sentences[-1]]


def _point_index(words_before: int, total: int, i: int, count: int) -> int:
    by_words = min(2, int(3 * words_before / max(1, total)))
    return max(by_words, 3 - (count - i)) if count >= 3 else by_words


def _assign_words(segments: list[str], words: list[dict]) -> list[int] | None:
    """Segment index for each TTS word, by aligning normalised letters (punctuation-proof)."""
    bounds, acc = [], 0
    for seg in segments:
        acc += len(_norm(seg))
        bounds.append(acc)
    owner, pos, k = [], 0, 0
    for w in words:
        n = len(_norm(w["word"]))
        mid = pos + n / 2
        while k < len(bounds) - 1 and mid > bounds[k]:
            k += 1
        owner.append(k)
        pos += n
    if abs(pos - acc) > max(3, acc * 0.08) or set(owner) != set(range(len(segments))):
        return None  # TTS text drifted from the script; fall back to the fixed slots
    return owner


def plan_timeline(segments: list[str] | None, words: list[dict], max_total: float = TOTAL) -> dict | None:
    """Scene slots aligned to the voice, the pauses to insert into it, and the Reel's length.

    Returns {"plan": {scene: [start, duration]}, "total": seconds, "cuts": [...], "pauses": [...],
    "owner": [...]} or None when the voiceover can't be split (the fixed DEFAULT_PLAN is used then).
    The Reel is as long as its voice plus short pauses and a ~2 s closing card, never padded.
    """
    if not segments or len(segments) != 6 or not words:
        return None
    owner = _assign_words(segments, words)
    if owner is None:
        return None
    starts = [next(w["start"] for w, o in zip(words, owner) if o == i) for i in range(6)]
    ends = [max(w["end"] for w, o in zip(words, owner) if o == i) for i in range(6)]
    voice_end = ends[-1]
    cuts = [(ends[i] + starts[i + 1]) / 2 for i in range(5)]
    bounds0 = [max(cuts[i], starts[i + 1] - LEAD) for i in range(5)]  # scene i ends here
    natural = [bounds0[0]] + [bounds0[i] - bounds0[i - 1] for i in range(1, 5)]

    pauses = [max(0.0, m - d) + EXTRA_PAUSE for m, d in zip(SEGMENT_MIN, natural)]
    budget = max(0.0, max_total - VOICE_TAIL - voice_end)
    if sum(pauses) > budget:  # a long voice: squeeze the pauses to stay within max_total
        pauses = [p * budget / sum(pauses) for p in pauses]

    shift = [sum(pauses[: i + 1]) for i in range(5)]
    b = [bounds0[i] + shift[i] for i in range(5)]
    total = max(voice_end + sum(pauses) + VOICE_TAIL, b[4] + OUTRO_MIN, MIN_TOTAL)
    total = min(max_total, math.ceil(total * 10) / 10)
    slots = [(0.0, b[0])] + [(b[i - 1], b[i] - b[i - 1]) for i in range(1, 5)] + [(b[4], total - b[4])]

    plan = {"hook": [0.0, slots[0][1]], "card3": list(slots[3]), "why": list(slots[4]), "outro": list(slots[5])}
    for n, (start, dur) in ((1, slots[1]), (2, slots[2])):
        shot = min(2.4, max(1.4, dur * 0.4))
        plan[f"card{n}"] = [start, dur - shot]
        plan[f"shot{n}"] = [start + dur - shot, shot]
    plan = {k: [round(plan[k][0], 3), round(plan[k][1], 3)] for k in SCENES}
    return {"plan": plan, "total": total, "cuts": cuts, "pauses": pauses, "owner": owner}


def caption_groups(words: list[dict], owner: list[int], pauses: list[float], skip_segments=(0, 5)) -> list[dict]:
    """Re-timed words grouped into short caption lines: {"s", "e", "w": [[text, start], ...]}.

    The hook (0) and the closing line (5) get no captions: the headline / closing card already
    show those words on screen (triple hook)."""
    groups, cur = [], []
    for w, o in zip(words, owner):
        if o in skip_segments:
            continue
        offset = sum(pauses[:o])
        word = (w["word"], w["start"] + offset, w["end"] + offset, o)
        if cur:
            prev = cur[-1]
            chars = sum(len(c[0]) + 1 for c in cur) + len(word[0])
            if (len(cur) >= CAPTION_MAX_WORDS or chars > CAPTION_MAX_CHARS or o != prev[3]
                    or word[1] - prev[2] > 0.45):
                groups.append(cur)
                cur = []
        cur.append(word)
    if cur:
        groups.append(cur)
    out = []
    for gi, g in enumerate(groups):
        nxt = groups[gi + 1][0][1] if gi + 1 < len(groups) else g[-1][2] + 0.5
        out.append({"s": round(g[0][1] - 0.05, 3), "e": round(min(nxt - 0.05, g[-1][2] + 0.45), 3),
                    "w": [[t, round(s, 3)] for t, s, _, _ in g]})
    return out


def sfx_events(plan: dict) -> list[tuple[float, str]]:
    events = [(0.0, "impact")]
    for name in SCENES[1:]:
        events.append((max(0.0, plan[name][0] - 0.22), "whoosh"))
    for name in ("card1", "card2", "card3"):
        events.append((plan[name][0] + 0.22, "pop"))
    events += [(plan["why"][0] + 0.08, "pop"), (plan["outro"][0] + 0.05, "impact"),
               (plan["outro"][0] + 0.62, "ding")]
    return events


def _apply_plan_to_html(index: Path, plan: dict, total: float = TOTAL) -> None:
    """Write each scene's slot into its data-start / data-duration (the runtime reads these), and
    the Reel's length into the composition and its full-length layers."""
    html = index.read_text(encoding="utf-8")
    for layer in ("root", "bg", "chrome"):
        pattern = re.compile(rf'(<div\s+id="{layer}"[^>]*?data-duration=")[^"]*(")', re.S)
        html, count = pattern.subn(rf"\g<1>{total:g}\g<2>", html, count=1)
        if count != 1:
            raise BuildError(f"<div id=\"{layer}\"> with data-duration not found in the template")
    for name, (start, dur) in plan.items():
        pattern = re.compile(rf'(<section id="{name}"[^>]*?data-start=")[^"]*("[^>]*?data-duration=")[^"]*(")')
        html, count = pattern.subn(rf"\g<1>{start:g}\g<2>{dur:g}\g<3>", html, count=1)
        if count != 1:
            raise BuildError(f"scene <section id=\"{name}\"> not found in the template")
    index.write_text(html, encoding="utf-8")


def _bake_variable_defaults(index: Path, values: dict) -> None:
    """Make this video's values the composition defaults, so check / snapshot / preview (which
    take no --variables-file) show exactly what the render will."""
    html_text = index.read_text(encoding="utf-8")
    m = re.search(r"data-composition-variables='(.*?)'\s*>", html_text, re.S)
    if not m:
        raise BuildError("data-composition-variables not found in the template")
    decls = json.loads(html.unescape(m.group(1)))
    for decl in decls:
        if decl["id"] in values:
            decl["default"] = values[decl["id"]]
    attr = json.dumps(decls, ensure_ascii=True, indent=1).replace("'", "&#39;")
    index.write_text(html_text[:m.start(1)] + attr + html_text[m.end(1):], encoding="utf-8")


PROOF_SIZE = (920, 660)  # the hook's proof box (templates/hyperframes_news #hook-proof); D-17: result-first


PROOF_CANDIDATES = 8


def _proof_windows(img: Image.Image, screens: int = 4) -> list[int]:
    """Tops of non-overlapping proof-shaped windows over the page's first screens, skipping the
    top strip (often a cookie / announcement bar) and near-empty areas."""
    from PIL import ImageFilter, ImageStat

    w = img.width
    win_h = round(w * PROOF_SIZE[1] / PROOF_SIZE[0])
    end = min(img.height, round(w * 16 / 9 * screens)) - win_h
    edges = img.resize((w // 4, img.height // 4)).convert("L").filter(ImageFilter.FIND_EDGES)
    scored = []
    skip = round(w * 0.2)  # the site's nav bar (its logo + name reads like an ad) and announcement strips
    for top in range(skip, max(skip, end) + 1, win_h // 2):
        detail = ImageStat.Stat(edges.crop((0, top // 4, w // 4, (top + win_h) // 4))).mean[0]
        if detail > 4:  # not a blank band
            scored.append((detail, top))
    picked: list[int] = []
    for _, top in sorted(scored, reverse=True):
        if all(abs(top - p) >= win_h for p in picked):
            picked.append(top)
        if len(picked) == PROOF_CANDIDATES:
            break
    return sorted(picked) or [0]


def _ask_proof_choice(sheet: Path, hint: str, count: int) -> list[int] | None:
    """Claude (Read tool only) looks at the numbered candidates and ranks the allowed ones, best
    proof first (empty list = none allowed)."""
    exe = shutil.which("claude")
    if not exe:
        return None
    schema = {"type": "object", "additionalProperties": False, "required": ["allowed"],
              "properties": {"allowed": {"type": "array", "maxItems": count,
                                         "items": {"type": "integer", "minimum": 0, "maximum": count - 1}}}}
    prompt = (f"Open {sheet.name} with the Read tool. It shows {count} numbered crops (0-{count - 1}) of a "
              f"product's website and images from its own pages (screenshots of the app, its outputs). "
              f"A Reel opens with this promise on screen: \"{hint}\". Pick the crop that "
              f"best PROVES it at a glance: the product's real interface, output or a clear workflow diagram. "
              f"A crop is NOT allowed if it shows a big number or statistic (e.g. '500K+', '90%+ of invoices'; "
              f"the Reel can't back it up), text cut off at the crop's edge, "
              f"any price or currency (even small prices on demo products, "
              f"$, €, ₺, 'free', 'pricing', plans), the product's own logo or name bar, a badge (e.g. "
              f"'Featured on Product Hunt'), a cookie or announcement bar, a big call-to-action button "
              f"('Sign up', 'Create', 'Try', 'Get started'), a slogan or marketing headline on its own, a "
              f"menu of feature cards or a template/prompt card (10-19: the editor rejected all of these as "
              f"proof), a wall of customer logos, or another product. Prefer the product's "
              f"output or interface in use over empty forms; avoid plain paragraphs of text. Answer with "
              f"every allowed crop's number, best proof first (the next ones are shown later in the Reel), "
              f"or an empty list if none is allowed.")
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run([exe, "-p", "--output-format", "json", "--json-schema", json.dumps(schema),
                               "--tools", "Read", "--allowedTools", "Read", "--no-session-persistence"],
                              input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=300,
                              cwd=sheet.parent, env=env)
        allowed = (json.loads(proc.stdout).get("structured_output") or {}).get("allowed")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None
    if not isinstance(allowed, list):
        return None
    return list(dict.fromkeys(i for i in allowed if isinstance(i, int) and 0 <= i < count))


SHOT_NAMES = ("shot1.png", "shot2.png")  # written next to proof.png; replace the raw site captures


def _shot_frame(crop: Image.Image, out: Path) -> None:
    """A 1080x1920 frame for a site shot: the approved crop on a blurred, darkened copy of itself.
    Raw viewport captures showed nav bars, logos, sign-up buttons and 'no credit card' lines."""
    from PIL import ImageDraw, ImageFilter, ImageOps

    bg = ImageOps.fit(crop, (1080, 1920), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", bg.size, "black"), 0.55)
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *crop.size), radius=32, fill=255)
    bg.paste(crop, ((1080 - crop.width) // 2, (1920 - crop.height) // 2 - 120), mask)
    bg.save(out)


def _fit_whole(path: str | Path) -> Image.Image:
    """A product screen in the proof box, whole (never cut): letterboxed on the template's dark blue."""
    from PIL import ImageOps

    with Image.open(path) as img:
        return ImageOps.pad(img.convert("RGB"), PROOF_SIZE, Image.LANCZOS, color=(10, 16, 32))


def best_proof_crop(page: Path, out: Path, hint: str = "", extra: list[str] | tuple = ()) -> Path | None:
    """The hook's proof image (the box under the headline on frame 0 / the cover): Claude picks,
    from up to 8 crops of the page plus the product's own screens (`extra`, D-36: images further down
    the page, feature pages, GitHub README), the one that best proves the hook without prices, logos
    or badges. Returns None when nothing is allowed (the hook then shows the headline alone); without
    Claude the first detailed crop is used. The next allowed pictures become the two site shots
    (SHOT_NAMES next to `out`)."""
    from PIL import ImageDraw

    with Image.open(page) as img:
        img = img.convert("RGB")
        w = img.width
        win_h = round(w * PROOF_SIZE[1] / PROOF_SIZE[0])
        tops = _proof_windows(img)
        crops = [img.crop((0, t, w, min(img.height, t + win_h))).resize(PROOF_SIZE, Image.LANCZOS) for t in tops]
    for path in extra:
        try:
            crops.append(_fit_whole(path))
        except OSError:
            continue
    ranked = [0]
    if len(crops) > 1:
        tile = (460, 235)
        sheet = Image.new("RGB", (tile[0] * 2, (tile[1] + 10) * ((len(crops) + 1) // 2)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, c in enumerate(crops):
            x, y = (i % 2) * tile[0], (i // 2) * (tile[1] + 10)
            sheet.paste(c.resize(tile), (x, y))
            draw.rectangle((x, y, x + 54, y + 44), fill="red")
            draw.text((x + 18, y + 10), str(i), fill="white")
        sheet_path = out.with_name("_proof_candidates.jpg")
        sheet.save(sheet_path, quality=85)
        picked = _ask_proof_choice(sheet_path, hint, len(crops))
        if picked == []:
            return None  # every crop shows a price / logo / badge: headline only
        ranked = picked or [0]
        # fallback (no Claude): the window list is in page order; the first detailed one is usually the hero
    crops[ranked[0]].save(out)
    # shots: the next allowed crops; with fewer, repeat the last one rather than show a raw capture
    for i, name in enumerate(SHOT_NAMES, 1):
        _shot_frame(crops[ranked[min(i, len(ranked) - 1)]], out.with_name(name))
    return out


def prepare_project(script: dict, capture: dict | None = None, audio_path: Path | str | None = None,
                    build_dir: Path = BUILD_DIR) -> dict:
    """Copy the template + this video's media into `build_dir`; return the variable values."""
    capture = capture or {}
    screenshot = Path(capture.get("screenshot_path") or TEMP_DIR / "screenshot.png")
    fullpage = Path(capture.get("fullpage_path") or TEMP_DIR / "fullpage.png")
    logo = capture.get("logo_path")
    audio = Path(audio_path or TEMP_DIR / "voiceover.mp3")
    for p in (screenshot, audio):
        if not p.exists():
            raise BuildError(f"missing input: {p}")
    if not fullpage.exists():
        fullpage = screenshot

    # Empty the build dir rather than delete it: Windows refuses to remove a folder that a
    # shell or Explorer window has open.
    build_dir.mkdir(parents=True, exist_ok=True)
    for child in build_dir.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    shutil.copytree(TEMPLATE_DIR, build_dir, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("snapshots", "renders", ".thumbnails"))
    assets = build_dir / "assets"
    for font in FONT_FILES:
        if font.exists():
            shutil.copy2(font, assets / "fonts" / font.name)
    shutil.copy2(screenshot, assets / "screenshot.png")
    width = _load_config()["video_width"]
    with Image.open(fullpage) as img:  # the pan assumes a frame-wide image
        if img.width != width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        img.convert("RGB").save(assets / "fullpage.png")
        fullpage_height = img.height
    picked = capture.get("proof_path")  # main.py picks it right after the capture
    if picked and Path(picked).exists():
        shutil.copy2(picked, assets / "proof.png")
        has_proof = True
    else:
        picked = best_proof_crop(assets / "fullpage.png", assets / "proof.png", script.get("hook", ""))
        has_proof = picked is not None
    if not has_proof:  # keep the asset path valid for the renderer; the template hides the box
        shutil.copy2(assets / "screenshot.png", assets / "proof.png")
    shots = [Path(picked).with_name(n) for n in SHOT_NAMES] if picked else []
    if shots and all(s.exists() for s in shots):  # approved crops replace the raw captures in shot1 / shot2
        shutil.copy2(shots[0], assets / "screenshot.png")
        shutil.copy2(shots[1], assets / "fullpage.png")
        fullpage_height = 1920  # no page to pan through: shot2 only zooms
    brand = _load_brand()
    for key, name in (("logo", "brand_icon"), ("wordmark", "brand_wordmark")):
        src = ROOT / brand[key] if brand.get(key) else None
        if not (src and src.exists()):
            raise BuildError(f"brand.json {key} file is missing: {src}")
        shutil.copy2(src, assets / f"{name}{src.suffix.lower()}")
    has_logo = bool(logo and Path(logo).exists())
    if has_logo:
        with Image.open(logo) as img:
            img.convert("RGBA").save(assets / "logo.png")

    # Voice-aligned timeline (falls back to the fixed slots), captions and the mixed soundtrack.
    words_path = audio.with_name(audio.stem + "_words.json")
    words = json.loads(words_path.read_text(encoding="utf-8")) if words_path.exists() else []
    seg = script.get("voiceover_segments")
    segments = [seg[k] for k in ("hook", "point1", "point2", "point3", "why", "cta")] if seg \
        else _segments_from_sentences(script.get("voiceover", ""))
    timing = plan_timeline(segments, words)
    plan = timing["plan"] if timing else DEFAULT_PLAN
    total = timing["total"] if timing else TOTAL
    captions = caption_groups(words, timing["owner"], timing["pauses"]) if timing else []
    _apply_plan_to_html(build_dir / "index.html", plan, total)
    try:
        sound = build_soundtrack(audio, assets / "soundtrack.mp3", total,
                                 timing["cuts"] if timing else None, timing["pauses"] if timing else None,
                                 sfx_events(plan))
    except SoundtrackError as exc:
        raise BuildError(str(exc)) from exc

    language = _load_config().get("language", "en")
    labels = LABELS.get(language, LABELS["en"])
    points = script["key_points"]
    values = {
        **labels,
        "follow_sub": brand.get("follow_line") or labels["follow_sub"],
        "brand_handle": brand.get("handle", ""),
        "headline": script["hook"],
        "why": script["why_it_matters"],
        "tool_name": script["tool_name"],
        "domain": capture.get("domain_label") or _domain(script["website_url"]),  # "Biz denedik": ours
        "has_logo": has_logo,
        "fullpage_height": fullpage_height,
        "plan": json.dumps(plan),
        "captions": json.dumps(captions),
        "total": total,
        "has_proof": has_proof,
        "cta_text": (seg or {}).get("cta") or labels["follow_label"],
    }
    for i, point in enumerate(points[:3], 1):
        values[f"p{i}_title"] = point["title"]
        values[f"p{i}_detail"] = point.get("detail", "")
    # ASCII-escaped JSON: Turkish letters survive whatever encoding the reader assumes.
    (build_dir / "variables.json").write_text(json.dumps(values, ensure_ascii=True, indent=2), encoding="utf-8")
    _bake_variable_defaults(build_dir / "index.html", values)
    values["_synced"] = timing is not None
    values["_total"] = total
    values["_music"] = sound["music"]
    return values


def _run(args: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([_npx(), "--yes", HYPERFRAMES, *args], cwd=cwd, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise BuildError(f"hyperframes {args[0]} timed out after {timeout}s") from exc


def build_video_hyperframes(
    script: dict,
    capture: dict | None = None,
    audio_path: Path | str | None = None,
    out_path: Path | str = FINAL_PATH,
    quality: str = "delivery",
) -> dict:
    """Render the HyperFrames composition for one script; same result shape as video_builder.build_video."""
    t0 = time.perf_counter()
    values = prepare_project(script, capture, audio_path)
    fps = _load_config().get("fps", 30)
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Render next to the build, then replace: a failed render never deletes the previous video.
    tmp_out = BUILD_DIR / "renders" / out_path.name

    proc = _run(["render", ".", "--output", str(tmp_out), "--quality", quality, "--fps", str(fps),
                 "--workers", str(RENDER_WORKERS), "--variables-file", "variables.json", "--strict-variables"], BUILD_DIR, RENDER_TIMEOUT)
    log = (proc.stdout or "") + (proc.stderr or "")
    (BUILD_DIR / "render.log").write_text(log, encoding="utf-8")
    if proc.returncode != 0 or not tmp_out.exists() or tmp_out.stat().st_size == 0:
        hint = " (0xC0000142: Windows could not start the process, usually low memory)" \
            if proc.returncode == 3221225794 else ""
        raise BuildError(f"hyperframes render failed (exit {proc.returncode}){hint}: {log.strip()[-800:]}")
    shutil.move(tmp_out, out_path)
    cover = make_cover(out_path)  # cover.jpg = the first frame the viewer sees; cover_grid.jpg = grid crop
    qa = {"first_frame": first_frame_report(out_path), "pacing": pacing_report(out_path)}
    (out_path.parent / "reel_qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")

    return {
        "video_path": str(out_path),
        "duration_sec": round(_probe_duration(out_path), 2),
        "size_mb": round(out_path.stat().st_size / 1_048_576, 2),
        "render_seconds": round(time.perf_counter() - t0, 1),
        "scenes": "HyperFrames: hook + 3 cards + 2 site shots + why + outro"
                  + (" (with logo)" if values["has_logo"] else " (no logo)")
                  + (", voice-synced + captions" if values["_synced"] else ", fixed slots")
                  + f", music: {values['_music']}",
        "project_dir": str(BUILD_DIR),
        "cover_path": cover["cover"],
        "qa": qa,
    }


if __name__ == "__main__":
    # Reuses the latest pipeline outputs in output/temp (script.json, voiceover, captures).
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from script_writer import VideoScript

    script = VideoScript.model_validate_json((TEMP_DIR / "script.json").read_text(encoding="utf-8"))
    script = script.model_dump(mode="json")
    logo = TEMP_DIR / "logo.png"
    result = build_video_hyperframes(script, {"logo_path": str(logo) if logo.exists() else None},
                                     quality=(sys.argv[1] if len(sys.argv) > 1 else "delivery"))
    print(json.dumps(result, indent=2, ensure_ascii=False))

    cfg = _load_config()
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate", "-of", "json", result["video_path"]],
        capture_output=True, text=True, check=True,
    ).stdout)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (cfg["video_width"], cfg["video_height"]), video
    assert any(s["codec_type"] == "audio" for s in probe["streams"]), "no audio stream"
    assert MIN_TOTAL - 0.5 <= result["duration_sec"] <= TOTAL + 0.5, result
    assert result["qa"]["first_frame"]["ok"], result["qa"]
    print("All hyperframes_builder checks passed.")
