"""The reserve (D-37, user 2026-10-22): editor-approved posts that never reached Instagram.

An empty or rejected slot is filled from here first, before any token is spent on a fix or a new
run. Items are kept READY: the files Business Suite needs are copied into reserve/<name>/ on this
PC (output/ is replaced every morning), and state/reserve.json lists them (committed, so every
session sees the list). The cloud run only names its surplus in output/reserve/<date>.json;
`daily.py fetch` brings it in.

    python daily.py reserve                 # list, oldest first, with age and whether still current
    python daily.py reserve keep 18:00      # today's ready item at 18:00 was not posted: keep it
    python daily.py reserve used 1          # item 1 was posted: drop it (files deleted)
"""

import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "state" / "reserve.json"
STORE = ROOT / "reserve"
# what a post needs to be scheduled again; frames, builds and drafts are left behind
KEEP = {"reel": ("upload.mp4", "cover.jpg", "post.json", "script.json", "_verdict.json"),
        "carousel": ("carousel", "story", "caption.txt", "carousel.json", "qa.json")}
# company news ages in days; guide and tool Reels last longer (checked by hand before use)
MAX_AGE_DAYS = {"carousel": 4, "reel": 14}


def load() -> list[dict]:
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save(items: list[dict]) -> None:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add(item: dict, made: str) -> dict | None:
    """Copy an approved queue item's files into the store and list it; None if its files are gone
    or it is already there."""
    src = ROOT / item["folder"]
    kind = item["kind"]
    if not src.is_dir() or kind not in KEEP:
        return None
    dest = STORE / src.name
    items = load()
    if any(r["folder"] == _rel(dest) for r in items):
        return None
    dest.mkdir(parents=True, exist_ok=True)
    for name in KEEP[kind]:
        p = src / name
        if p.is_dir():
            shutil.copytree(p, dest / name, dirs_exist_ok=True)
        elif p.is_file():
            shutil.copy2(p, dest / name)
    entry = {"kind": kind, "concept": item.get("concept") or ("news" if kind == "carousel" else "tool"),
             "title": item.get("title", src.name), "folder": _rel(dest), "made": made, "editor": "publish"}
    save(items + [entry])
    return entry


def used(index: int) -> dict:
    """Drop item `index` (1-based, as listed) after it was posted; its files are deleted."""
    items = load()
    entry = items.pop(index - 1)
    shutil.rmtree(ROOT / entry["folder"], ignore_errors=True)
    save(items)
    return entry


def current(entry: dict, today: date | None = None) -> bool:
    age = ((today or date.today()) - date.fromisoformat(entry["made"])).days
    return age <= MAX_AGE_DAYS.get(entry["kind"], 4)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()
