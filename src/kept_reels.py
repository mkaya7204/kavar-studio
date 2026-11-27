"""An empty Reel slot takes an approved Reel that never went out (user 2026-11-27: "Bunu öyle sözle falan değil
gerçek kodla davranışla yap").

11-27 and 11-28 the Reel slots stayed empty in production while approved, never-published Reels sat in older runs:
Claude found them by hand (Figma 11-25 -> 27 Nov 07:30, ElevenLabs and Astor 11-25 -> 28 Nov) and the dry run's Mika
needed a hand-started voice.yml. Now the production run does it itself, as its last Reel step:

  1. candidates: the release "kept-reels" (D-80: every approved Reel's silent kit, kept for good), made in the last
     KEEP_DAYS days, newest first; never one already taken (state/kept_used.json), never a tool already queued
     (state/recent_posts.json) or taken; a guide kit only for the 07:30 guide slot's concept, any kit for the others
  2. take: the kit is downloaded, voiced once with George (src/voice_kept.py: the same measured checks as
     production) and copied into today's folder (so the day's archive carries it), without its _voice kit (so it is
     never kept and taken twice)
  3. a test run (KAVAR_DRY) never spends George (D-46): it only logs what it would take.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = "kept-reels"
KEEP_DAYS = 4  # a tool Reel is still current for a few days; older ones say things that may have changed
USED = ROOT / "state" / "kept_used.json"
RECENT = ROOT / "state" / "recent_posts.json"
NAME = re.compile(r"^keep-(\d{4}-\d{2}-\d{2})_(.+)\.tgz$")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_used() -> dict:
    try:
        return json.loads(USED.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"reels": [], "tools": []}


def mark_taken(name: str, tool: str) -> None:
    used = load_used()
    used.setdefault("reels", []).append(name)
    used.setdefault("tools", []).append(slug(tool))
    USED.parent.mkdir(parents=True, exist_ok=True)
    USED.write_text(json.dumps(used, indent=1, ensure_ascii=False), encoding="utf-8")


def posted_tools() -> set[str]:
    """Slugs of the Reels already queued for a day (they were scheduled), plus the ones taken from the kept kits."""
    try:
        rows = json.loads(RECENT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        rows = []
    return {slug(r.get("title", "")) for r in rows if r.get("kind") == "reel"} | set(load_used().get("tools", []))


def _assets() -> list[str]:
    try:
        out = subprocess.run(["gh", "release", "view", TAG, "--json", "assets", "--jq", ".assets[].name"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return out.stdout.split() if out.returncode == 0 else []


def candidates(assets: list[str], today: date | None = None) -> list[dict]:
    """The kept kits that may fill a slot, newest first: [{asset, name, made, tool_slug}]."""
    today = today or date.today()
    used = set(load_used().get("reels", []))
    posted = posted_tools()
    out = []
    for asset in assets:
        m = NAME.match(asset)
        if not m:
            continue
        made, rest = m.group(1), m.group(2)
        name = f"{made}_{rest}"
        tool = re.sub(r"-\d+$", "", rest)  # "google-workspace-2" is the second Reel of google-workspace
        age = (today - datetime.strptime(made, "%Y-%m-%d").date()).days
        if not 0 <= age <= KEEP_DAYS or name in used or tool in posted:
            continue
        out.append({"asset": asset, "name": name, "made": made, "tool_slug": tool})
    return sorted(out, key=lambda c: c["made"], reverse=True)


def is_guide(kit: Path) -> bool:
    """A guide Reel's kit (D-31): its tool data says so."""
    try:
        tool = json.loads((kit / "_voice" / "tool.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(tool.get("post_url")) or "GUIDE Reel" in str(tool.get("kind", ""))


def download(c: dict) -> Path | None:
    """The kit unpacked at its own path (output/reels/<name>), where its _voice paths point."""
    tmp = Path(tempfile.mkdtemp(prefix="kept-"))
    try:
        subprocess.run(["gh", "release", "download", TAG, "-p", c["asset"], "-D", str(tmp)], check=True,
                       capture_output=True, timeout=300)
        with tarfile.open(tmp / c["asset"]) as tar:
            members = [m for m in tar.getmembers() if m.name.startswith(f"output/reels/{c['name']}/")
                       and ".." not in Path(m.name).parts and (m.isfile() or m.isdir())]
            tar.extractall(ROOT, members=members)
    except (OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print(f"[kept] {c['name']}: download failed: {type(exc).__name__}")
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    kit = ROOT / "output" / "reels" / c["name"]
    return kit if (kit / "_voice" / "capture.json").exists() else None


def voice(kit: Path) -> bool:
    """George, once, with production's measured checks (src/voice_kept.py)."""
    proc = subprocess.run([sys.executable, str(ROOT / "src" / "voice_kept.py"), str(kit)], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    for line in proc.stdout.splitlines()[-4:]:
        print(f"[kept]    {line}")
    return proc.returncode == 0 and (kit / "final_video.mp4").exists()


def into_today(kit: Path, new_folder: Path) -> Path:
    """The voiced Reel copied into today's folder (packed with the day), without its _voice kit."""
    shutil.copytree(kit, new_folder, ignore=shutil.ignore_patterns("_voice"))
    return new_folder
