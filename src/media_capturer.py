"""Capture vertical (9:16) visuals of a SaaS website with Playwright.

The site is opened as a phone (mobile layout) whose CSS viewport, scaled by
the device pixel ratio, matches config.json's video size exactly, e.g.
360x640 @3x = 1080x1920. Produces:
  - screenshot.png   clean above-the-fold shot (cookie banners, popups, ads hidden)
  - fullpage.png     the top few screens of the page, for scrolling
  - scroll.mp4       smooth eased scroll down `fullpage.png`, rendered by FFmpeg
"""

import json
import re
import subprocess
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageStat
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from product_images import PAGE_MEDIA_JS

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output" / "temp"

DEVICE_SCALE = 3  # 1080x1920 px = 360x640 CSS px, a typical phone layout
MAX_SCROLL_SCREENS = 4  # how far down the page the scroll video goes
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.8010.12 Mobile Safari/537.36"
)

# Cookie / consent "accept" buttons, matched by accessible name.
ACCEPT_BUTTON = re.compile(
    r"^\s*(accept( all)?( cookies)?|allow( all)?( cookies)?|i agree|agree|got it|ok(ay)?|"
    r"i understand|consent|alle akzeptieren|kabul et|tümünü kabul et)\s*$",
    re.I,
)

# Known consent / chat / ad widgets, hidden unconditionally.
HIDE_CSS = """
#onetrust-consent-sdk, #onetrust-banner-sdk, .onetrust-pc-dark-filter,
#CybotCookiebotDialog, #CybotCookiebotDialogBodyUnderlay, .cc-window, .cc-banner,
#usercentrics-root, #truste-consent-track, .osano-cm-window, #cookiescript_injected,
#hubspot-messages-iframe-container, #intercom-container, .intercom-lightweight-app,
#drift-widget-container, .drift-frame-controller, #crisp-chatbox, #launcher,
iframe[src*="doubleclick"], iframe[id^="google_ads"], ins.adsbygoogle,
[data-testid="cookie-banner"], [aria-label*="cookie" i][role="dialog"]
{ display: none !important; }
html, body { overflow: auto !important; }
"""

# Generic cleanup for anything the list misses: fixed/sticky elements that look
# like consent/promo/chat widgets by name, or overlays covering a large part
# of the screen (newsletter modals). Small fixed bars such as a site's own
# navigation header are left alone.
HIDE_OVERLAYS_JS = """
() => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const keyword = /cookie|consent|gdpr|privacy-banner|newsletter|popup|modal|subscribe|chat-widget|promo-bar|announcement|interstitial|advert|dfp|gpt-ad|ad-slot|sponsor/i;
  const adFrame = 'iframe[src*="doubleclick"], iframe[src*="googlesyndication"], iframe[id^="google_ads"], iframe[src*="adnxs"], iframe[src*="amazon-adsystem"]';
  let hidden = 0;
  for (const el of document.querySelectorAll('body *')) {
    const style = getComputedStyle(el);
    if (style.position !== 'fixed' && style.position !== 'sticky') continue;
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    const area = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0)) *
                 Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
    const named = keyword.test((el.id || '') + ' ' + (el.className?.baseVal ?? el.className ?? '') +
                               ' ' + (el.getAttribute('aria-label') || ''));
    const isNav = el.tagName === 'HEADER' || el.tagName === 'NAV' || el.querySelector('nav');
    const hasAd = el.querySelector(adFrame) !== null;
    if (named || hasAd || (!isNav && area > vw * vh * 0.3)) {
      el.style.setProperty('display', 'none', 'important');
      hidden++;
    }
  }
  return hidden;
}
"""


# Header logo: an <img>/<svg> near the top whose name, alt or link marks it as the logo.
FIND_LOGO_JS = """
() => {
  const vh = window.innerHeight;
  const ok = el => {
    const r = el.getBoundingClientRect();
    return r.top < vh * 0.25 && r.width >= 24 && r.height >= 16 && r.width <= 600 && r.height <= 300
      && getComputedStyle(el).visibility !== 'hidden';
  };
  const named = el => /logo|brand/i.test([el.id, el.className?.baseVal ?? el.className,
      el.getAttribute('alt'), el.getAttribute('aria-label'), el.getAttribute('src'),
      el.closest('a')?.getAttribute('aria-label'), el.parentElement?.className?.baseVal ?? el.parentElement?.className].join(' '));
  const homeLink = el => { const a = el.closest('a'); return a && /^(\\/|\\.\\/|#|https?:\\/\\/[^/]+\\/?)$/.test(a.getAttribute('href') || ''); };
  const cands = [...document.querySelectorAll('header img, header svg, nav img, nav svg, a img, a svg, img, svg')]
    .filter(el => ok(el) && (named(el) || homeLink(el)));
  if (!cands.length) return null;
  cands.sort((a, b) => (named(b) - named(a)) || (a.getBoundingClientRect().top - b.getBoundingClientRect().top));
  cands[0].setAttribute('data-capture-logo', '1');
  return true;
}
"""


class CaptureError(Exception):
    """The site could not be loaded or captured."""


def precheck(url: str, timeout: float = 15.0) -> None:
    """Fail fast (seconds, no browser) when the site doesn't answer at all.

    Only connection failures, timeouts and 5xx count; a 403 from bot protection
    is fine, since the real browser may still get through.
    """
    try:
        resp = requests.get(url, headers={"User-Agent": MOBILE_UA}, timeout=(10, timeout), stream=True)
        resp.close()
    except requests.RequestException as exc:
        raise CaptureError(f"{url} is not reachable ({type(exc).__name__})") from exc
    if resp.status_code >= 500:
        raise CaptureError(f"{url} returned HTTP {resp.status_code}")


def _is_blank(path: Path) -> bool:
    """True if a screenshot is (nearly) a single flat colour, e.g. an empty or broken page."""
    with Image.open(path) as img:
        return max(ImageStat.Stat(img.convert("L").resize((108, 192))).stddev) < 6


# Site icons, best first: apple-touch-icon (usually 180px), then the largest declared icon.
ICON_URLS_JS = """
() => [...document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"], link[rel="apple-touch-icon-precomposed"], link[rel="shortcut icon"]')]
  .map(l => ({href: l.href, apple: l.rel.includes('apple'), size: parseInt((l.sizes && l.sizes.value || '0').split('x')[0]) || 0}))
  .sort((a, b) => (b.apple - a.apple) || (b.size - a.size))
  .map(i => i.href)
"""


def _capture_icon(page: Page, out: Path) -> Path | None:
    """Fallback logo: download the site's app icon / favicon if it's large enough."""
    try:
        hrefs = page.evaluate(ICON_URLS_JS)
    except PlaywrightError:
        return None
    for href in hrefs[:4]:
        if href.lower().endswith(".svg"):
            continue  # Pillow can't rasterise SVG
        try:
            resp = page.request.get(href, timeout=10_000)
            if not resp.ok:
                continue
            with Image.open(BytesIO(resp.body())) as icon:
                icon.load()
                if icon.format == "ICO":
                    icon.size = max(icon.ico.sizes())
                icon = icon.convert("RGBA")
                if min(icon.size) < 64:
                    continue
                icon.save(out)
                return out
        except (PlaywrightError, OSError, ValueError):
            continue
    return None


def _capture_logo(page: Page, out: Path) -> Path | None:
    """Header logo element if one can be identified, else the site's app icon."""
    try:
        if page.evaluate(FIND_LOGO_JS):
            page.locator("[data-capture-logo]").first.screenshot(path=out, omit_background=True, timeout=5000)
            return out
    except PlaywrightError:
        pass
    return _capture_icon(page, out)


def load_video_size() -> tuple[int, int, int]:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    return cfg["video_width"], cfg["video_height"], cfg.get("fps", 30)


def _accept_cookies(page: Page) -> bool:
    """Click a consent 'accept' button in the page or any iframe, if present."""
    for frame in page.frames:
        try:
            button = frame.get_by_role("button", name=ACCEPT_BUTTON).first
            if button.is_visible(timeout=500):
                button.click(timeout=2000)
                page.wait_for_timeout(600)
                return True
        except PlaywrightError:
            continue
    return False


def _clean_page(page: Page) -> dict:
    clicked = _accept_cookies(page)
    page.keyboard.press("Escape")  # closes many JS modals
    page.add_style_tag(content=HIDE_CSS)
    hidden = page.evaluate(HIDE_OVERLAYS_JS)
    return {"cookie_accept_clicked": clicked, "overlays_hidden": hidden}


def _trigger_lazy_load(page: Page, max_css_height: int) -> None:
    """Scroll down in steps so lazy images load, then return to the top."""
    vh = page.viewport_size["height"]
    for y in range(0, max_css_height, vh // 2):
        page.mouse.wheel(0, vh // 2)
        page.wait_for_timeout(150)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)


def render_scroll_video(image: Path, out: Path, width: int, height: int,
                        fps: int, seconds: float) -> Path:
    """Eased top-to-bottom pan over a tall image (crisp, constant frame rate)."""
    # y goes 0 -> (image height - frame height) with ease-in-out (cosine).
    pan = f"crop={width}:{height}:0:'(ih-oh)*(1-cos(PI*min(t/{seconds},1)))/2'"
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(fps), "-i", str(image),
        "-vf", f"{pan},format=yuv420p", "-t", str(seconds), "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-movflags", "+faststart", str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
    except FileNotFoundError as exc:
        raise CaptureError("ffmpeg not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise CaptureError(f"ffmpeg failed: {exc.stderr.strip()[-500:]}") from exc
    return out


SCREENSHOT_TIMEOUT_MS = 90_000


def capture_site(
    url: str,
    out_dir: Path | str = OUTPUT_DIR,
    scroll_seconds: float | None = 8.0,
    timeout_ms: int = 30_000,
) -> dict:
    """Open `url` as a phone and save screenshot / full page / scroll video.

    Set scroll_seconds=None to skip the scroll video.
    """
    width, height, fps = load_video_size()
    css_w, css_h = width // DEVICE_SCALE, height // DEVICE_SCALE
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot = out_dir / "screenshot.png"
    fullpage = out_dir / "fullpage.png"
    logo = out_dir / "logo.png"
    logo.unlink(missing_ok=True)  # never reuse a previous tool's logo
    precheck(url)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": css_w, "height": css_h},
                device_scale_factor=DEVICE_SCALE,
                is_mobile=True,
                has_touch=True,
                user_agent=MOBILE_UA,
                locale="en-US",
                bypass_csp=True,  # strict CSPs (style-src 'self') would block our cleanup CSS/JS
            )
            page = context.new_page()
            # Only the server's first response is required; load times vary a lot
            # (notion.com: 3-15s+), so later load stages are best-effort.
            try:
                response = page.goto(url, wait_until="commit", timeout=timeout_ms)
            except PlaywrightTimeout as exc:
                raise CaptureError(f"timed out connecting to {url}") from exc
            except PlaywrightError as exc:
                raise CaptureError(f"could not load {url}: {exc.message.splitlines()[0]}") from exc
            if response is not None and response.status >= 400:
                raise CaptureError(f"{url} returned HTTP {response.status}")
            for state, wait_ms in (("load", timeout_ms), ("networkidle", 10_000)):
                try:
                    page.wait_for_load_state(state, timeout=wait_ms)
                except PlaywrightTimeout:
                    print(f"[capture] '{state}' not reached within {wait_ms / 1000:.0f}s; continuing")

            page.wait_for_timeout(1500)  # let late consent banners appear
            cleanup = _clean_page(page)

            max_css_height = css_h * MAX_SCROLL_SCREENS
            _trigger_lazy_load(page, max_css_height)

            # Ads and promo popups can appear late (on timers or on scroll), so
            # sweep again right before each capture.
            cleanup["overlays_hidden"] += page.evaluate(HIDE_OVERLAYS_JS)
            # Heavy pages on a 4 GB machine can take well over Playwright's default 30s to paint.
            page.screenshot(path=screenshot, animations="disabled", timeout=SCREENSHOT_TIMEOUT_MS)
            if _is_blank(screenshot):
                raise CaptureError(f"{url} rendered a blank page")
            logo_path = _capture_logo(page, logo)
            page_height = page.evaluate("document.documentElement.scrollHeight")
            cleanup["overlays_hidden"] += page.evaluate(HIDE_OVERLAYS_JS)
            page.screenshot(
                path=fullpage,
                full_page=True,
                animations="disabled",
                timeout=SCREENSHOT_TIMEOUT_MS,
                clip={"x": 0, "y": 0, "width": css_w, "height": min(page_height, max_css_height)},
            )
            # D-36: the product's own screens are usually below the first screens; collect them after the
            # captures (the deeper scroll must not change what was shot)
            page_media = None
            try:
                _trigger_lazy_load(page, css_h * 15)
                page_media = page.evaluate(PAGE_MEDIA_JS)
            except PlaywrightError as exc:
                print(f"[capture] page images not read: {exc.message.splitlines()[0]}")
            title, final_url = page.title(), page.url
        except PlaywrightError as exc:  # any other browser failure: skip this tool, don't crash the run
            raise CaptureError(f"capture of {url} failed: {exc.message.splitlines()[0]}") from exc
        finally:
            browser.close()

    result = {
        "url": url,
        "final_url": final_url,
        "title": title,
        "screenshot_path": str(screenshot),
        "fullpage_path": str(fullpage),
        "logo_path": str(logo_path) if logo_path else None,
        "scroll_video_path": None,
        "page_media": page_media,
        **cleanup,
    }
    if scroll_seconds and min(page_height, max_css_height) > css_h:
        result["scroll_video_path"] = str(
            render_scroll_video(fullpage, out_dir / "scroll.mp4", width, height, fps, scroll_seconds)
        )
    return result


if __name__ == "__main__":
    import sys

    from PIL import Image

    width, height, _ = load_video_size()
    urls = sys.argv[1:] or ["https://www.notion.com", "https://github.com"]
    for i, url in enumerate(urls):
        # The first site writes the canonical output/temp files; others go to subfolders.
        out = OUTPUT_DIR if i == 0 else OUTPUT_DIR / f"capture_test_{i}"
        result = capture_site(url, out_dir=out)
        with Image.open(result["screenshot_path"]) as img:
            assert img.size == (width, height), f"screenshot is {img.size}, expected {(width, height)}"
        with Image.open(result["fullpage_path"]) as img:
            full_size = img.size
        assert full_size[0] == width, f"full page width {full_size[0]} != {width}"
        if result["scroll_video_path"]:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=width,height,r_frame_rate:format=duration", "-of", "json",
                 result["scroll_video_path"]],
                capture_output=True, text=True, check=True,
            )
            info = json.loads(probe.stdout)
            stream = info["streams"][0]
            assert (stream["width"], stream["height"]) == (width, height), stream
            result["scroll_video"] = f"{stream['width']}x{stream['height']} @ {stream['r_frame_rate']} fps, " \
                                     f"{float(info['format']['duration']):.1f}s"
        result["fullpage_size"] = f"{full_size[0]}x{full_size[1]}"
        print(f"=== {url} ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    # Error handling: an unreachable site must raise CaptureError, not crash.
    try:
        capture_site("https://this-domain-does-not-exist-xyz123.com", out_dir=OUTPUT_DIR / "capture_err",
                     scroll_seconds=None, timeout_ms=10_000)
    except CaptureError as exc:
        print(f"OK (unreachable) -> CaptureError: {exc}")
    else:
        raise AssertionError("unreachable site did not raise")
    print("All media_capturer checks passed.")
