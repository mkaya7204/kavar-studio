"""Measured checks on a rendered Reel's first frame, and its cover image.

- first_frame_report(video): is frame 0 blank / a flat colour / too dark? (the kōdlo Reel opened
  on an empty teal blur, which was also its default cover)
- make_cover(video, out_dir): cover.jpg (1080x1920, the frame the viewer sees first) and
  cover_grid.jpg (the centre 3:4 crop the profile grid shows), to check at thumbnail size.
- pacing_report(video): how often the picture changes (ffmpeg scene score) and black frames.
"""

import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

COVER_AT = 0.3  # seconds; frame 0 is already composed, this skips the first-frame audio pop
BLANK_STD = 18  # luminance spread below this = a flat / blurred frame with no readable content
EDGE_MIN = 6.0  # mean edge strength below this = no text or detail


def grab_frame(video: Path | str, t: float, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                    "-q:v", "2", str(out)], check=True, timeout=120)
    return out


def frame_stats(img: Image.Image) -> dict:
    gray = img.convert("L").resize((270, 480))
    std = ImageStat.Stat(gray).stddev[0]
    edges = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
    return {"brightness": round(ImageStat.Stat(gray).mean[0], 1), "contrast": round(std, 1),
            "detail": round(edges, 1), "blank": std < BLANK_STD or edges < EDGE_MIN}


def first_frame_report(video: Path | str, scratch: Path | None = None) -> dict:
    """Stats of frame 0 and the cover frame; 'ok' is False when either looks empty."""
    video = Path(video)
    scratch = scratch or video.parent
    out = {}
    for name, t in (("frame0", 0.0), ("cover_frame", COVER_AT)):
        f = grab_frame(video, t, scratch / f"_qa_{name}.jpg")
        with Image.open(f) as img:
            out[name] = frame_stats(img)
        f.unlink(missing_ok=True)
    out["ok"] = not (out["frame0"]["blank"] or out["cover_frame"]["blank"])
    return out


def make_cover(video: Path | str, out_dir: Path | str | None = None) -> dict:
    """Write cover.jpg (full 9:16) and cover_grid.jpg (centre 1080x1440, what the grid shows)."""
    video = Path(video)
    out_dir = Path(out_dir or video.parent)
    cover = grab_frame(video, COVER_AT, out_dir / "cover.jpg")
    with Image.open(cover) as img:
        img = img.convert("RGB")
        img.save(cover, quality=92)  # sRGB JPEG, well under the API's 8 MB
        w, h = img.size
        crop_h = round(w * 4 / 3)
        top = (h - crop_h) // 2
        img.crop((0, top, w, top + crop_h)).save(out_dir / "cover_grid.jpg", quality=88)
        stats = frame_stats(img)
    return {"cover": str(cover), "grid": str(out_dir / "cover_grid.jpg"), **stats}


SCENE_THRESHOLD = 0.12  # ffmpeg scene score: our cuts and wipes score well above this


def pacing_report(video: Path | str) -> dict:
    """Seconds between visual changes, and black stretches, from one ffmpeg pass."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(video), "-an", "-vf",
         f"select='gt(scene,{SCENE_THRESHOLD})',showinfo,blackdetect=d=0.2:pix_th=0.06", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    log = proc.stderr
    changes = sorted({round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", log)})
    blacks = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)]
    dur = 0.0
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    points = [0.0, *changes, dur]
    gaps = [round(b - a, 2) for a, b in zip(points, points[1:])]
    return {"duration_sec": round(dur, 2), "visual_changes": len(changes),
            "longest_static_sec": max(gaps) if gaps else dur, "black_stretches": blacks}


# D-42: a picture cut by the frame. The template's background is dark and soft (blur, glow, grid), so sharp
# detail in the outer 24 px of a frame is a picture or its text running off the edge. Measured on the real
# rejected frames: clean 0.3-0.8, a card sliding in 1.07, cut pictures 1.7-3.2 ("in Google Mee" 10-22 11.6 s,
# 10-23 10.2-11.2 s).
EDGE_STRIP = 24
CUT_DETAIL = 1.4
CUT_FPS = 2  # frames measured per second; a cut must show in 2 in a row (a card slides past in ~0.5 s)


def edge_detail(img: Image.Image) -> tuple[float, float]:
    """Mean edge strength in the left and right strips of a 1080x1920 frame (rows 12-85 %, below the top UI)."""
    gray = img.convert("L")
    w, h = gray.size
    edges = gray.filter(ImageFilter.FIND_EDGES)
    top, bottom = round(h * 0.12), round(h * 0.85)
    left = ImageStat.Stat(edges.crop((2, top, EDGE_STRIP, bottom))).mean[0]  # 2 px: FIND_EDGES' own border
    right = ImageStat.Stat(edges.crop((w - EDGE_STRIP, top, w - 2, bottom))).mean[0]
    return round(left, 2), round(right, 2)


def cut_in(frames: list[Path], fps: float = CUT_FPS) -> list[float]:
    """Seconds where a picture runs off the frame's edge in two measured frames in a row ([] = clean)."""
    hot = []
    for f in frames:
        with Image.open(f) as img:
            hot.append(max(edge_detail(img)) >= CUT_DETAIL)
    return [round(i / fps, 1) for i in range(1, len(hot)) if hot[i] and hot[i - 1]]


def cut_frames(video: Path | str, scratch: Path | None = None) -> list[float]:
    """cut_in() over the whole video, CUT_FPS frames a second."""
    video = Path(video)
    work = (scratch or video.parent) / "_cut_check"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"fps={CUT_FPS}", "-q:v", "3",
                    str(work / "f_%04d.jpg")], check=True, timeout=600)
    found = cut_in(sorted(work.glob("f_*.jpg")))
    shutil.rmtree(work, ignore_errors=True)
    return found
