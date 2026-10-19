"""The product's own screens for a tool Reel's proof (user approved 2026-10-19, D-36).

10-19: Krea 3, Inbox Zero and Popcraft were rejected 3 x 3 times because the proof box only ever
showed the top of the home page: slogans, prompt cards and logo walls. The product's interface is
usually further down the page, on its feature pages or in its GitHub README. This module turns what
media_capturer saw on the page (capture["page_media"]) into image files:

  1. big images anywhere on the home page (screenshots of the app, demo outputs)
  2. the og:image of a few of the site's own feature pages (/bulk-email-unsubscriber ...)
  3. the screenshots in the product's GitHub README, when the site links its repo

They are only candidates: best_proof_crop and the Reel fixer still let Claude pick, with the same
bans (prices, logos, badges, cut text, other products). Any failure means fewer candidates, never
a crash.
"""

import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image, ImageStat

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"}
TIMEOUT = 10
MAX_BYTES = 8_000_000
MAX_IMAGES = 6
MAX_FEATURE_PAGES = 5
MIN_SIZE = (600, 300)
# pages that are never a feature: their og:image is a price table, a blog cover or a logo card
SKIP_PATHS = re.compile(r"pric|plan|login|sign|regist|account|blog|news|about|career|job|privacy|terms|legal|"
                        r"contact|affiliate|partner|docs?\b|changelog|status|press|case-stud|customer|enterprise|"
                        r"cookie|security|download|support|help|faq|alternative|vs-|compare|team|invest", re.I)
SKIP_IMAGES = re.compile(r"\.(svg|gif|ico)(\?|$)|shields\.io|badge|logo|avatar|favicon|sponsor|star-history|"
                         r"contrib\.rocks|producthunt|trendshift|/svg\?", re.I)

# media_capturer runs this on the home page once it is fully scrolled
PAGE_MEDIA_JS = r"""() => {
  const imgs = [...document.images]
    .map(i => ({src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight}))
    .filter(i => i.src && i.src.startsWith('http') && i.w >= 600 && i.h >= 300);
  const host = location.hostname.replace(/^www\./, '');
  const links = [...document.querySelectorAll('a[href]')].map(a => a.href);
  const github = links.find(h => /^https:\/\/github\.com\/[^\/]+\/[^\/#?]+\/?$/.test(h)) || null;
  const pages = [...new Set(links.filter(h => {
      try { const u = new URL(h); return u.hostname.replace(/^www\./, '') === host && u.pathname.length > 1; }
      catch (e) { return false; }
    }).map(h => h.split('#')[0].split('?')[0]))];
  return {imgs, github, pages};
}"""


def _key(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.netloc}{parts.path}".lower()


def feature_pages(pages: list[str]) -> list[str]:
    """The site's own pages that can show a feature, in page order."""
    return [p for p in pages if not SKIP_PATHS.search(urlsplit(p).path)][:MAX_FEATURE_PAGES]


def og_image(page_url: str) -> str | None:
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException:
        return None
    for attr in ("og:image", "twitter:image"):
        tag = re.search(rf'<meta[^>]+(?:property|name)=["\']{attr}["\'][^>]*>', r.text, re.I)
        if tag and (m := re.search(r'content=["\']([^"\']+)["\']', tag.group(0))):
            return urljoin(page_url, m.group(1).strip())
    return None


def readme_images(repo_url: str) -> list[str]:
    """Image URLs in the repo's README (badges and logos dropped later)."""
    m = re.match(r"https://github\.com/([^/]+)/([^/#?]+)", repo_url)
    if not m:
        return []
    base = f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2).removesuffix('.git')}/HEAD/"
    try:
        r = requests.get(base + "README.md", headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException:
        return []
    found = re.findall(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)", r.text) + re.findall(r"<img[^>]+src=[\"']([^\"']+)", r.text)
    return [urljoin(base, u) for u in found]


def repo_behind(pages: list[str]) -> str | None:
    """The GitHub repo a site links through its own redirect (Inbox Zero: getinboxzero.com/github)."""
    for page in pages:
        if "github" not in urlsplit(page).path.lower():
            continue
        try:
            r = requests.head(page, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        except requests.RequestException:
            continue
        if re.match(r"https://github\.com/[^/]+/[^/#?]+/?$", r.url):
            return r.url
    return None


def usable(img: Image.Image) -> bool:
    """Big enough, not a banner strip or a tall phone scroll, not one flat colour."""
    w, h = img.size
    if w < MIN_SIZE[0] or h < MIN_SIZE[1] or not 0.45 <= w / h <= 3.2:
        return False
    return ImageStat.Stat(img.convert("L").resize((128, 128))).stddev[0] > 2  # dark UIs score low; flat = 0


def download(url: str, out: Path) -> Path | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        r.raise_for_status()
        data = r.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(data) > MAX_BYTES:
            return None
        with Image.open(BytesIO(data)) as img:
            img = img.convert("RGB")
            if not usable(img):
                return None
            img.save(out)
        return out
    except (requests.RequestException, OSError, ValueError, Image.DecompressionBombError):
        return None


def collect(page_media: dict | None, out_dir: Path | str, limit: int = MAX_IMAGES) -> list[str]:
    """Files of the product's own screens, best sources first (page, feature pages, README)."""
    if not page_media:
        return []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("product_*.png"):
        old.unlink()  # never reuse the previous tool's screens
    urls = [i["src"] for i in sorted(page_media.get("imgs") or [], key=lambda i: -i["w"] * i["h"])]
    pages = page_media.get("pages") or []
    # README screenshots before the feature pages' og:images (those are often marketing cards)
    if repo := page_media.get("github") or repo_behind(pages):
        urls += readme_images(repo)
    urls += [u for u in (og_image(p) for p in feature_pages([p for p in pages if "github" not in p.lower()])) if u]
    files, seen = [], set()
    for url in urls:
        if len(files) >= limit:
            break
        if SKIP_IMAGES.search(url) or _key(url) in seen:
            continue
        seen.add(_key(url))
        if path := download(url, out_dir / f"product_{len(files)}.png"):
            with Image.open(path) as img:  # the same picture under two URLs (README + og:image, 10-19)
                print_ = img.convert("L").resize((16, 16)).tobytes()
            if print_ in seen:
                path.unlink()
                continue
            seen.add(print_)
            files.append(str(path))
    return files
