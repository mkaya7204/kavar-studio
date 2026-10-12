"""Still scenes for the video, drawn with Pillow (FFmpeg then animates them).

- section scenes: one screen of the site inside a browser-window mockup (title
  bar, traffic lights, URL pill, rounded corners, soft shadow) over a blurred,
  darkened copy of the same screen
- outro card: the site's logo (if captured), tool name and domain
"""

from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

FONT_DIR = Path("C:/Windows/Fonts")
FONT_BLACK = FONT_DIR / "seguibl.ttf"  # Segoe UI Black
FONT_REGULAR = FONT_DIR / "segoeui.ttf"
FONT_SEMIBOLD = FONT_DIR / "seguisb.ttf"

WINDOW_WIDTH = 0.80  # mockup width; leaves enough margin that Ken Burns never crops the window
BAR_HEIGHT = 78
RADIUS = 34


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default(size)


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or url).removeprefix("www.")


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _backdrop(img: Image.Image, w: int, h: int, brightness: float = 0.5) -> Image.Image:
    bg = _cover(img.convert("RGB"), w, h).filter(ImageFilter.GaussianBlur(36))
    return ImageEnhance.Brightness(bg).enhance(brightness)


def _shadow(size: tuple[int, int], box: tuple[int, int, int, int], radius: int) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius, fill=(0, 0, 0, 170))
    return layer.filter(ImageFilter.GaussianBlur(28))


def pick_sections(fullpage: Path | None, screenshot: Path, w: int, h: int, max_sections: int = 4) -> list[Image.Image]:
    """Cut the full page into screen-sized sections, skipping near-empty ones."""
    if fullpage is None or not Path(fullpage).exists():
        return [Image.open(screenshot).convert("RGB")]
    page = Image.open(fullpage).convert("RGB")
    if page.width != w:
        page = page.resize((w, round(page.height * w / page.width)), Image.LANCZOS)
    sections = []
    for top in range(0, page.height, h):
        if page.height - top < h * 0.6:  # a short leftover strip isn't worth a scene
            break
        crop = page.crop((0, top, w, top + h))
        if top + h > page.height:  # pad the last partial section with the page colour
            filled = Image.new("RGB", (w, h), crop.getpixel((w // 2, crop.height - 1 - (top + h - page.height))))
            filled.paste(crop.crop((0, 0, w, page.height - top)))
            crop = filled
        if max(ImageStat.Stat(crop.convert("L").resize((54, 96))).stddev) >= 8 or top == 0:
            sections.append(crop)
        if len(sections) == max_sections:
            break
    return sections


def browser_scene(section: Image.Image, url: str, w: int, h: int) -> Image.Image:
    """One site section inside a browser-window mockup over a blurred backdrop."""
    canvas = _backdrop(section, w, h).convert("RGBA")
    win_w = round(w * WINDOW_WIDTH)
    content_h = round(win_w * section.height / section.width)
    win_h = BAR_HEIGHT + content_h
    x0, y0 = (w - win_w) // 2, (h - win_h) // 2
    box = (x0, y0, x0 + win_w, y0 + win_h)

    canvas.alpha_composite(_shadow((w, h), (box[0], box[1] + 26, box[2], box[3] + 26), RADIUS))

    window = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(window)
    draw.rounded_rectangle((0, 0, win_w - 1, win_h - 1), RADIUS, fill=(30, 30, 34, 255))
    content = section.resize((win_w, content_h), Image.LANCZOS).convert("RGBA")
    window.paste(content, (0, BAR_HEIGHT))

    # Title bar: traffic lights + URL pill.
    cy = BAR_HEIGHT // 2
    for i, colour in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        cx = 36 + i * 30
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=colour)
    pill = (140, cy - 23, win_w - 36, cy + 23)
    draw.rounded_rectangle(pill, 23, fill=(52, 52, 58, 255))
    font = _font(FONT_SEMIBOLD, 26)
    text = domain_of(url)
    tw = draw.textlength(text, font=font)
    draw.text(((pill[0] + pill[2] - tw) / 2, cy), text, font=font, fill=(214, 214, 220), anchor="lm")

    # Round all four corners of the finished window.
    mask = Image.new("L", (win_w, win_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, win_w - 1, win_h - 1), RADIUS, fill=255)
    canvas.paste(window, (x0, y0), mask)
    return canvas.convert("RGB")


def _logo_is_light(logo: Image.Image) -> bool:
    alpha = logo.getchannel("A")
    if not alpha.getbbox():
        return False
    lum = ImageStat.Stat(logo.convert("L"), mask=alpha.point(lambda a: 255 if a > 128 else 0)).mean[0]
    return lum > 190


def outro_scene(background: Image.Image, logo_path: Path | None, tool_name: str, url: str, w: int, h: int) -> Image.Image:
    """Closing card: logo (if any), tool name, domain."""
    canvas = _backdrop(background, w, h, brightness=0.4).convert("RGBA")
    logo = None
    if logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert("RGBA")
        bbox = logo.getchannel("A").getbbox()
        logo = logo.crop(bbox) if bbox else None
    dark = bool(logo) and _logo_is_light(logo)
    card_fill = (18, 18, 22, 255) if dark else (255, 255, 255, 255)
    text_main = (255, 255, 255) if dark else (17, 17, 20)
    text_sub = (170, 170, 178) if dark else (110, 110, 118)

    card_w = round(w * 0.8)
    name_font = _font(FONT_BLACK, 84 if logo else 104)
    sub_font = _font(FONT_REGULAR, 40)
    logo_box = (round(card_w * 0.7), 220)
    if logo:
        logo.thumbnail(logo_box, Image.LANCZOS)
        if logo.width < logo_box[0] * 0.5 and logo.height < logo_box[1] * 0.5:  # tiny logos: upscale a bit
            factor = min(logo_box[0] * 0.5 / logo.width, logo_box[1] * 0.5 / logo.height)
            logo = logo.resize((round(logo.width * factor), round(logo.height * factor)), Image.LANCZOS)
    pad, gap = 70, 36
    probe = ImageDraw.Draw(canvas)
    name = tool_name if probe.textlength(tool_name, font=name_font) <= card_w - 2 * pad else tool_name[:22] + "…"
    card_h = pad * 2 + (logo.height + gap if logo else 0) + 100 + 56
    x0, y0 = (w - card_w) // 2, (h - card_h) // 2
    canvas.alpha_composite(_shadow((w, h), (x0, y0 + 24, x0 + card_w, y0 + card_h + 24), 44))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((x0, y0, x0 + card_w, y0 + card_h), 44, fill=card_fill)
    y = y0 + pad
    if logo:
        canvas.alpha_composite(logo, (x0 + (card_w - logo.width) // 2, y))
        y += logo.height + gap
    draw.text((w / 2, y + 50), name, font=name_font, fill=text_main, anchor="mm")
    draw.text((w / 2, y + 100 + 28), domain_of(url), font=sub_font, fill=text_sub, anchor="mm")
    return canvas.convert("RGB")
