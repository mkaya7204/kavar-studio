"""D-77 (user 2026-11-14): "Önemli olan ürünün ismi bir de haberi yapılacak şirketin veya firmanın logosu, gerisi
zaten haber içeriği ve video bilgine kalmış". When a tool's site shows no product screen, the Reel's picture is the
product's own brand picture: its share image (og:image / twitter:image, which carries the name and logo), else the
site's logo, else its home page. Only the product's own site, never another site's picture (§1.9)."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image

HEADERS = {"User-Agent": "Mozilla/5.0 (KAVAR brand picture)"}
MIN_WIDTH = 400
META = (r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\']')


def share_image_url(html: str, page: str) -> str | None:
    for pattern in META:
        if m := re.search(pattern, html, re.I):
            return urljoin(page, m.group(1).replace("&amp;", "&"))
    return None


def brand_picture(url: str, out_dir: Path | str, logo_path: str | None = None,
                  page_png: str | None = None) -> str | None:
    """The product's own picture with its name / logo, saved as <out_dir>/brand.png, or None."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "brand.png"
    parts = urlsplit(url)
    for page in dict.fromkeys((url, f"{parts.scheme}://{parts.hostname}/")):
        try:
            r = requests.get(page, headers=HEADERS, timeout=20)
            r.raise_for_status()
            if not (src := share_image_url(r.text, page)):
                continue
            img = requests.get(src, headers=HEADERS, timeout=20)
            img.raise_for_status()
            raw = out_dir / "brand_raw"
            raw.write_bytes(img.content)
            with Image.open(raw) as im:
                if im.width >= MIN_WIDTH:
                    im.convert("RGB").save(out)
                    return str(out)
        except (requests.RequestException, OSError):
            continue
    for path in (logo_path, page_png):  # the site's own logo, then its own home page
        if path and Path(path).exists():
            try:
                with Image.open(path) as im:
                    im.convert("RGB").save(out)
                    return str(out)
            except OSError:
                continue
    return None
