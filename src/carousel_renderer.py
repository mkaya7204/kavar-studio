"""Render a carousel script to Instagram-ready JPEGs with Playwright.

templates/carousel/index.html is copied into a build folder next to the site
captures and a data.js holding the script; one Chromium page renders the whole
strip, the template fits the type and measures every frame (overflow, minimum
size, safe zone, collisions, contrast), then each frame is screenshotted.

Output per frame: JPEG quality 90, 4:4:4 chroma, sRGB ICC profile embedded, and
the page's copyright in EXIF (Instagram strips EXIF on upload, but the files you
keep carry it, as proof of origin next to their timestamps).
"""

import json
import shutil
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageCms
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates" / "carousel"
FONTS_DIR = ROOT / "templates" / "hyperframes_news" / "assets" / "fonts"
BRAND_PATH = ROOT / "brand.json"
SIZES = {"carousel": (1080, 1350), "story": (1080, 1920)}
JPEG_QUALITY = 90
READY_TIMEOUT_MS = 60_000
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
_ASCII = str.maketrans({**dict(zip("çğıöşüÇĞİÖŞÜâîûÂÎÛ", "cgiosuCGIOSUaiuAIU")), "©": "(c)", "—": "-"})


class RenderError(RuntimeError):
    pass


def load_brand() -> dict:
    brand = json.loads(BRAND_PATH.read_text(encoding="utf-8"))
    brand.setdefault("handle", "@" + brand.get("name", "marka").lower())
    return brand


def _domain(url: str) -> str:
    from urllib.parse import urlsplit

    return (urlsplit(url).hostname or url).removeprefix("www.")


CARD_HEIGHT = {"carousel": 520, "story": 600}  # .pagecard heights in the template, 920px wide


def _page_offsets(fullpage: Image.Image) -> dict:
    """For page sections 1-3, the crop top (source px) with the most visual detail.

    A section is roughly one phone screen down the page; around it, windows of the
    card's height are scored by edge density, so a card shows a busy part of the
    site (headline, UI, product shot) instead of white space or a cut-off line.
    """
    from PIL import ImageFilter, ImageStat

    small = fullpage.convert("L").resize((270, round(fullpage.height / 4)))
    edges = small.filter(ImageFilter.FIND_EDGES)
    out = {}
    for mode, card_h in CARD_HEIGHT.items():
        win = round(card_h * 1080 / 920 / 4)  # window height in the 1/4-scale image
        out[mode] = {}
        for section in (1, 2, 3):
            centre = round(section * 1920 * 0.9 / 4)
            best, best_score = 0, -1.0
            for top in range(max(0, centre - 180), max(1, min(centre + 180, small.height - win)), 10):
                box = (0, top, small.width, top + win)
                score = ImageStat.Stat(edges.crop(box)).mean[0] + 0.3 * ImageStat.Stat(small.crop(box)).stddev[0]
                # a crop that opens on a busy row cuts something in half: penalise its top edge
                score -= 1.5 * ImageStat.Stat(edges.crop((0, top, small.width, top + 4))).mean[0]
                if score > best_score:
                    best, best_score = top, score
            # Start the crop in a quiet row (a gap between blocks) just above, so the
            # card doesn't open on a headline sliced in half.
            for up in range(0, 70):
                row = best - up
                if row <= 0 or ImageStat.Stat(edges.crop((0, row, small.width, row + 1))).mean[0] < 2.5:
                    best = max(0, row - 4)
                    break
            out[mode][section] = best * 4
    return out


TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
             "Kasım", "Aralık"]


def _date_label(iso: str) -> str:
    """'2026-10-10T14:41:16+00:00' -> '10 Ekim 2026' ('' if unknown)."""
    try:
        y, m, d = (int(x) for x in iso[:10].split("-"))
        return f"{d} {TR_MONTHS[m - 1]} {y}"
    except (ValueError, IndexError):
        return ""


def _fit_width(img: Image.Image, width: int = 1080) -> Image.Image:
    """RGB copy at most `width` wide: large images make the template's page load crawl."""
    img = img.convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    return img


def _news_assets(assets: Path, article: dict) -> dict:
    """Cover, article header and figures for news mode; returns the template's news data."""
    figures = []
    for f in article["figures"]:
        with Image.open(f["path"]) as img:
            _fit_width(img).save(assets / f"fig_{f['n']}.jpg", quality=92)
        figures.append({"src": f"assets/fig_{f['n']}.jpg"})
    with Image.open(article["page_path"]) as img:
        img.convert("RGB").resize((1080, round(img.height * 1080 / img.width)), Image.LANCZOS).save(
            assets / "page.jpg", quality=92)
    with Image.open(article["cover_path"]) as img:
        cover_ratio = img.width / img.height
    return {"publisher": article["publisher"], "date_label": _date_label(article.get("published", "")),
            "figures": figures, "cover_ratio": round(cover_ratio, 3)}


def _prepare(build: Path, script: dict, capture: dict, brand: dict) -> None:
    if build.exists():
        shutil.rmtree(build)
    assets = build / "assets"
    shutil.copytree(TEMPLATE_DIR, build)
    shutil.copytree(FONTS_DIR, assets / "fonts", dirs_exist_ok=True)
    news = None
    if script.get("kind") == "news":  # capture is an article from article_capture
        news = _news_assets(assets, capture)
        with Image.open(capture["cover_path"]) as img:
            _fit_width(img).save(assets / "cover.jpg", quality=92)
        # shared story layouts: "screenshot" shows the cover, "page" the article's header
        capture = {"screenshot_path": capture["cover_path"], "fullpage_path": capture["page_path"]}
    # JPEG, and the long page scaled to the 920px card width: large PNGs took ~20s to decode.
    with Image.open(capture["screenshot_path"]) as img:
        img.convert("RGB").save(assets / "screenshot.jpg", quality=92)
    with Image.open(capture["fullpage_path"]) as img:
        if img.width != 1080:  # the template measures the page in 1080-wide source pixels
            img = img.convert("RGB").resize((1080, round(img.height * 1080 / img.width)), Image.LANCZOS)
        fullpage_height = img.height
        page_offsets = _page_offsets(img)
        img.convert("RGB").resize((920, round(img.height * 920 / img.width)), Image.LANCZOS).save(
            assets / "fullpage.jpg", quality=92)
    logo = capture.get("logo_path")
    has_tool_logo = bool(logo and Path(logo).exists())
    if has_tool_logo:
        shutil.copy(logo, assets / "logo.png")
    brand = dict(brand)
    # brand files (SVG or PNG) are copied as-is; the template gets their published names
    for key in ("logo", "wordmark"):
        src = ROOT / brand[key] if brand.get(key) else None
        if src and src.exists():
            shutil.copy(src, assets / f"brand_{key}{src.suffix.lower()}")
            brand[key] = f"assets/brand_{key}{src.suffix.lower()}"
        else:
            brand[key] = None
    data = {
        "slides": script["slides"],
        "story": script["story"],
        "tool_name": script["tool_name"],
        "domain": _domain(script["website_url"]),
        "has_tool_logo": has_tool_logo,
        "fullpage_height": fullpage_height,
        "page_offsets": page_offsets,
        "brand": brand,
        "kind": script.get("kind", "tool"),
        "news": news,
    }
    (assets / "data.js").write_text("window.DATA = " + json.dumps(data, ensure_ascii=False) + ";",
                                    encoding="utf-8")


def _save_jpeg(png: bytes, path: Path, brand: dict, description: str) -> None:
    with Image.open(BytesIO(png)) as img:
        rgb = img.convert("RGB")
    def ascii_(s: str) -> str:  # EXIF text fields are ASCII
        return s.translate(_ASCII).encode("ascii", "ignore").decode()

    exif = Image.Exif()
    exif[0x013B] = ascii_(brand.get("name", ""))  # Artist
    exif[0x8298] = ascii_(brand.get("copyright", ""))  # Copyright
    exif[0x010E] = ascii_(description)  # ImageDescription
    rgb.save(path, "JPEG", quality=JPEG_QUALITY, subsampling=0, icc_profile=SRGB, exif=exif,
             optimize=True)


VIDEO_SLOT_JS = """(i) => {
  const s = document.querySelectorAll('.slide')[i];
  const v = s && s.querySelector('[data-video-slot]');
  if (!v) return null;
  const r = v.getBoundingClientRect();
  const b = 3;  // inside the card's border
  // the card's tags (VIDEO, @handle) are stamped back over the clip: the watermark stays on video too
  const tags = [...v.querySelectorAll('.tag')].map((t) => {
    const q = t.getBoundingClientRect();
    return {x: Math.floor(q.left), y: Math.floor(q.top), w: Math.ceil(q.width) & ~1, h: Math.ceil(q.height) & ~1};
  });
  return {n: Number(v.dataset.videoSlot), x: Math.round(r.left + b), y: Math.round(r.top + b),
          w: Math.round(r.width - 2 * b) & ~1, h: Math.round(r.height - 2 * b) & ~1, tags};
}"""
VIDEO_MAX_SECONDS = 15


def _video_slide(frame_jpg: Path, video: str, slot: dict, out: Path) -> Path:
    """The article's video playing inside the slide's card: an MP4 carousel item (H.264, 30 fps).

    The rendered slide is the background; the clip is scaled to cover the card and cut to
    VIDEO_MAX_SECONDS. Its own sound is kept when it has any.
    """
    import subprocess

    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "default=nw=1:nk=1", video], capture_output=True, text=True,
                                   timeout=60).stdout.strip() or 0)
    except (ValueError, subprocess.TimeoutExpired):
        dur = 0
    if dur <= 0.5:
        raise RenderError(f"video {Path(video).name} is unreadable; the slide stays an image")
    t = min(dur, VIDEO_MAX_SECONDS)
    w, h, x, y = slot["w"], slot["h"], slot["x"], slot["y"]
    tags = slot.get("tags") or []
    graph = (f"[0:v]split={len(tags) + 1}" + "".join(f"[f{k}]" for k in range(len(tags) + 1)) + ";"
             f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30[clip];"
             f"[f0][clip]overlay={x}:{y}:shortest=1[v0];")
    for k, tg in enumerate(tags, 1):
        graph += (f"[f{k}]crop={tg['w']}:{tg['h']}:{tg['x']}:{tg['y']}[t{k}];"
                  f"[v{k - 1}][t{k}]overlay={tg['x']}:{tg['y']}[v{k}];")
    graph += f"[v{len(tags)}]format=yuv420p[out]"
    cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", str(frame_jpg),
           "-t", f"{t:.2f}", "-i", video, "-filter_complex", graph, "-map", "[out]", "-map", "1:a?",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "128k",
           "-t", f"{t:.2f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not out.exists():
        raise RenderError(f"video slide failed: {proc.stderr.strip()[:200]}")
    frame_jpg.unlink()
    return out


def render(script: dict, capture: dict, out_dir: Path, brand: dict | None = None) -> dict:
    """Render carousel + story frames into out_dir/carousel and out_dir/story.

    Returns {'carousel': [paths], 'story': [paths], 'qa': [problems], 'seconds': float}.
    A frame with problems is still written, so it can be looked at.
    """
    t0 = time.perf_counter()
    brand = brand or load_brand()
    out_dir = Path(out_dir).resolve()
    build = out_dir / "_build"
    _prepare(build, script, capture, brand)
    result = {"carousel": [], "story": [], "qa": []}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for mode, frames in (("carousel", script["slides"]), ("story", script["story"])):
                w, h = SIZES[mode]
                page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                page.goto((build / "index.html").as_uri() + "?mode=" + mode, wait_until="commit")
                try:
                    page.wait_for_function("window.__ready === true", timeout=READY_TIMEOUT_MS)
                except Exception as exc:
                    raise RenderError(f"{mode} template never became ready: {exc}") from exc
                for q in page.evaluate("window.__qa"):
                    result["qa"].append({"mode": mode, **q})
                folder = out_dir / mode
                if folder.exists():
                    shutil.rmtree(folder)
                folder.mkdir(parents=True)
                for i, frame in enumerate(frames):
                    page.evaluate(f"window.__show({i})")
                    png = page.screenshot(type="png", animations="disabled")
                    path = folder / f"{i + 1:02d}.jpg"
                    _save_jpeg(png, path, brand, frame.get("alt_text") or frame.get("title", ""))
                    slot = page.evaluate(VIDEO_SLOT_JS, i)
                    if slot and (videos := capture.get("videos")) and slot["n"] <= len(videos):
                        try:
                            path = _video_slide(path, videos[slot["n"] - 1], slot, folder / f"{i + 1:02d}.mp4")
                        except RenderError as exc:
                            result["qa"].append({"mode": mode, "frame": i, "kind": "video", "msg": str(exc)})
                    result[mode].append(str(path))
                page.close()
        finally:
            browser.close()
    result["seconds"] = round(time.perf_counter() - t0, 1)
    return result
