"""Capture a news article for news mode: text, cover image, figures and videos.

Opens the article in a desktop browser, hides cookie banners / popups (shared
with media_capturer), then saves into out_dir:
  - cover.jpg      the article's own cover (og:image), credited on the slide
  - page.png       the top of the article as published (headline area), a "source card"
  - fig_N.png      screenshots of the article's large images / charts (max 6)
  - video_N.mp4    the article's own embedded video files, when it has any (max 2)
and returns the article text for the writer, which may only use figures that
appear in that text. YouTube / social embeds are never downloaded.
"""

import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from media_capturer import HIDE_OVERLAYS_JS, SCREENSHOT_TIMEOUT_MS, CaptureError, _clean_page

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"}
MAX_FIGURES = 6
MAX_VIDEOS = 2
MAX_VIDEO_MB = 80
MAX_TEXT = 14_000

EXTRACT_JS = r"""
() => {
  const meta = (k) => (document.querySelector(`meta[property="${k}"], meta[name="${k}"]`) || {}).content || "";
  // main text: the <article> (or <main>) with the most paragraph text
  const roots = [...document.querySelectorAll("article, main, [role=main]")];
  let root = roots.sort((a, b) => b.innerText.length - a.innerText.length)[0] || document.body;
  const blocks = [...root.querySelectorAll("h1, h2, h3, p, li, blockquote, figcaption")]
    .filter((e) => e.offsetParent !== null)
    .map((e) => (/^H/.test(e.tagName) ? "## " : "") + e.innerText.trim())
    .filter((t) => t.length > 1);
  const text = [...new Set(blocks)].join("\n");
  // figures: big images inside the article
  const figs = [...root.querySelectorAll("img, picture img")]
    .filter((im) => im.naturalWidth >= 600 && im.getBoundingClientRect().width >= 400)
    .map((im, i) => {
      im.setAttribute("data-cap-fig", String(i));
      const fc = im.closest("figure")?.querySelector("figcaption");
      return { i, alt: (im.alt || "").slice(0, 200), caption: fc ? fc.innerText.slice(0, 200) : "" };
    });
  const vids = [...root.querySelectorAll("video")]
    .map((v) => v.currentSrc || v.src || v.querySelector("source")?.src || "")
    .filter((s) => s && !s.startsWith("blob:"));
  return {
    title: meta("og:title") || document.title,
    site: meta("og:site_name") || location.hostname.replace(/^www\./, ""),
    published: meta("article:published_time") || (document.querySelector("time[datetime]") || {}).dateTime || "",
    cover: meta("og:image") || meta("twitter:image"),
    og_video: meta("og:video:secure_url") || meta("og:video") || "",
    text, figs, vids,
  };
}
"""


def _download(url: str, out: Path, max_mb: float) -> Path | None:
    try:
        with requests.get(url, headers=HEADERS, timeout=30, stream=True) as r:
            r.raise_for_status()
            size = 0
            with open(out, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    size += len(chunk)
                    if size > max_mb * 1e6:
                        raise ValueError("too large")
                    f.write(chunk)
        return out
    except (requests.RequestException, ValueError, OSError) as exc:
        print(f"[article] download skipped ({type(exc).__name__}): {url[:90]}")
        out.unlink(missing_ok=True)
        return None


def capture_article(url: str, out_dir: Path | str, timeout_ms: int = 45_000) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):
        if old.is_file():
            old.unlink()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=2,
                                    user_agent=HEADERS["User-Agent"], locale="en-US")
            try:  # only the first response is required; news pages keep loading ads for ages
                resp = page.goto(url, wait_until="commit", timeout=timeout_ms)
            except PlaywrightTimeout as exc:
                raise CaptureError(f"timed out connecting to {url}") from exc
            if resp is not None and resp.status >= 400:
                raise CaptureError(f"{url} returned HTTP {resp.status}")
            for state, wait_ms in (("domcontentloaded", timeout_ms), ("load", 20_000), ("networkidle", 8_000)):
                try:
                    page.wait_for_load_state(state, timeout=wait_ms)
                except PlaywrightTimeout:
                    print(f"[article] '{state}' not reached; continuing")
            page.wait_for_timeout(1500)
            _clean_page(page)
            page.evaluate(HIDE_OVERLAYS_JS)
            page.screenshot(path=out_dir / "page.png", animations="disabled", timeout=SCREENSHOT_TIMEOUT_MS)
            info = page.evaluate(EXTRACT_JS)
            # many blogs keep their videos as .mp4 links in the page data, not as <video> tags
            for src in re.findall(r"https?://[^\s\"'<>()]+?\.mp4", page.content()):
                if src not in info["vids"]:
                    info["vids"].append(src)
            figures = []
            for f in info["figs"]:
                if len(figures) >= MAX_FIGURES:
                    break
                path = out_dir / f"fig_{len(figures) + 1}.png"
                try:
                    el = page.locator(f'[data-cap-fig="{f["i"]}"]').first
                    el.scroll_into_view_if_needed(timeout=5000)
                    page.wait_for_timeout(400)
                    el.screenshot(path=path, animations="disabled", timeout=20_000)
                except PlaywrightError:
                    continue
                with Image.open(path) as im:
                    if im.width < 500 or im.height < 250:
                        path.unlink()
                        continue
                    size = im.size
                figures.append({"n": len(figures) + 1, "path": str(path), "size": size,
                                "alt": f["alt"], "caption": f["caption"]})
        except PlaywrightError as exc:
            raise CaptureError(f"capture of {url} failed: {exc.message.splitlines()[0]}") from exc
        finally:
            browser.close()

    cover = None
    if info["cover"]:
        cover = _download(urljoin(url, info["cover"]), out_dir / "cover_raw", 15)
        if cover:
            try:
                with Image.open(cover) as im:
                    im.convert("RGB").save(out_dir / "cover.jpg", quality=94)
                cover = out_dir / "cover.jpg"
            except OSError:
                cover = None
            (out_dir / "cover_raw").unlink(missing_ok=True)
    if cover is None and figures:  # no og:image: the article's first big image
        with Image.open(figures[0]["path"]) as im:
            im.convert("RGB").save(out_dir / "cover.jpg", quality=94)
        cover = out_dir / "cover.jpg"

    videos = []
    for src in [*info["vids"], info["og_video"]]:
        if len(videos) >= MAX_VIDEOS or not src:
            continue
        src = urljoin(url, src)
        if not re.search(r"\.(mp4|mov|webm)(\?|$)", src, re.I) or re.search(r"youtube|vimeo|tiktok|instagram|x\.com|twitter", src):
            continue
        if path := _download(src, out_dir / f"video_{len(videos) + 1}.mp4", MAX_VIDEO_MB):
            videos.append(str(path))

    host = urlsplit(url).hostname or ""
    return {
        "url": url,
        "title": info["title"],
        "publisher": info["site"] or host.removeprefix("www."),
        "domain": host.removeprefix("www."),
        "published": info["published"],
        "text": info["text"][:MAX_TEXT],
        "cover_path": str(cover) if cover else None,
        "page_path": str(out_dir / "page.png"),
        "figures": figures,
        "videos": videos,
    }


if __name__ == "__main__":
    import json
    import sys

    res = capture_article(sys.argv[1], Path(__file__).resolve().parent.parent / "output" / "temp" / "article")
    print(json.dumps({k: (v if k != "text" else v[:600] + "…") for k, v in res.items()}, indent=2, ensure_ascii=False))
