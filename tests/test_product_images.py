"""D-36 (2026-10-19): a tool Reel's proof can be the product's own screens, not only the top of its home page."""
import inspect
from io import BytesIO
from types import SimpleNamespace

import requests
from PIL import Image, ImageDraw

import product_images


def _png(size, color="white", lines=True) -> bytes:
    img = Image.new("RGB", size, color)
    if lines:  # detail, like a real screenshot
        draw = ImageDraw.Draw(img)
        for y in range(0, size[1], 24):
            draw.line((0, y, size[0], y + 12), fill="black", width=3)
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


WEB = {
    "https://tool.ai/img/app-screen.png": _png((1200, 800)),
    "https://tool.ai/img/tiny.png": _png((300, 200)),
    "https://tool.ai/img/flat.png": _png((1200, 800), lines=False),
    "https://tool.ai/bulk-unsubscribe": '<meta property="og:image" content="/og/bulk.png">',
    "https://tool.ai/og/bulk.png": _png((1200, 630), "red"),
    "https://tool.ai/pricing": '<meta property="og:image" content="/og/pricing.png">',
    "https://raw.githubusercontent.com/me/tool/HEAD/README.md":
        "![build](https://img.shields.io/badge/build-ok.svg)\n![screen](docs/screen.png)",
    "https://raw.githubusercontent.com/me/tool/HEAD/docs/screen.png": _png((1400, 900), "blue"),
}


def _fake_get(url, **kw):
    if url not in WEB:
        raise requests.HTTPError(url)
    body = WEB[url]
    data = body if isinstance(body, bytes) else body.encode()
    return SimpleNamespace(raise_for_status=lambda: None, text=data.decode("latin-1"),
                           raw=SimpleNamespace(read=lambda n, decode_content=True: data[:n]))


MEDIA = {"imgs": [{"src": "https://tool.ai/img/tiny.png", "w": 300, "h": 200},
                  {"src": "https://tool.ai/img/flat.png", "w": 1200, "h": 800},
                  {"src": "https://tool.ai/img/app-screen.png", "w": 1200, "h": 800}],
         "pages": ["https://tool.ai/pricing", "https://tool.ai/bulk-unsubscribe"],
         "github": "https://github.com/me/tool"}


def test_the_products_own_screens_are_collected(monkeypatch, tmp_path):
    monkeypatch.setattr(product_images.requests, "get", _fake_get)
    files = product_images.collect(MEDIA, tmp_path)
    colors = []
    for f in files:
        with Image.open(f) as img:
            colors.append(img.convert("RGB").getpixel((5, 5)))
    # the app screen on the page, the feature page's picture, the README screenshot; no tiny / flat image,
    # no pricing page, no badge
    assert len(files) == 3
    assert colors[1] == (255, 0, 0) and colors[2] == (0, 0, 255)


def test_no_page_media_means_no_screens(tmp_path):
    assert product_images.collect(None, tmp_path) == []


def test_the_proof_pick_offers_the_product_screens(monkeypatch, tmp_path):
    import hyperframes_builder as hb

    page = Image.new("RGB", (1080, 3000), "white")
    draw = ImageDraw.Draw(page)
    for y in range(0, 3000, 40):
        draw.line((0, y, 1080, y + 20), fill="black", width=3)
    page.save(tmp_path / "fullpage.png")
    Image.new("RGB", (1200, 800), (0, 200, 0)).save(tmp_path / "product_0.png")
    seen = {}

    def pick(sheet, hint, count):
        seen["count"] = count
        return [count - 1]  # Claude picks the product screen (the last candidate)

    monkeypatch.setattr(hb, "_ask_proof_choice", pick)
    out = hb.best_proof_crop(tmp_path / "fullpage.png", tmp_path / "proof.png", "hint",
                             extra=[str(tmp_path / "product_0.png")])
    with Image.open(out) as img:
        assert img.size == hb.PROOF_SIZE
        assert img.getpixel((hb.PROOF_SIZE[0] // 2, hb.PROOF_SIZE[1] // 2)) == (0, 200, 0)  # whole, not cut
    assert seen["count"] >= 2


def test_slogans_and_card_menus_are_not_proof():
    src = inspect.getsource(__import__("hyperframes_builder")._ask_proof_choice)
    assert "slogan" in src and "template/prompt card" in src and "customer logos" in src


def test_the_fixer_sees_the_product_screens_first(monkeypatch, tmp_path):
    import reel_fixer

    page = Image.new("RGB", (540, 4000), "white")
    draw = ImageDraw.Draw(page)
    for y in range(0, 4000, 40):
        draw.line((0, y, 540, y + 20), fill="black", width=3)
    page.save(tmp_path / "fullpage.png")
    Image.new("RGB", (1200, 800), (0, 200, 0)).save(tmp_path / "product_0.png")
    monkeypatch.setattr(reel_fixer, "WORK", tmp_path / "fix")
    found = reel_fixer.candidates({"fullpage_path": str(tmp_path / "fullpage.png"),
                                   "product_images": [str(tmp_path / "product_0.png")]})
    assert len(found) <= reel_fixer.MAX_CANDIDATES
    with Image.open(found[0]) as img:
        assert img.getpixel((5, 5)) == (0, 200, 0)
