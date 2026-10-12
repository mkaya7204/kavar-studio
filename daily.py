"""KAVAR's daily autopilot: produce in the morning, publish at fixed times.

    python daily.py produce        # 06:30: 2 news carousels + 1 Reel, each reviewed by the editor
    python daily.py publish 1      # 12:30 / 18:00 / 20:30: publish queue item 1 / 2 / 3
    python daily.py status         # what is queued / published today
    python daily.py fetch          # download today's cloud production (GitHub Actions) to this PC
    python daily.py check          # Instagram login, quota and tunnel smoke test (publishes nothing)

Windows Task Scheduler runs these (setup_tasks.ps1). Only content the editor review
(src/editor_review.py) passes is queued; a carousel the editor wants fixed is rewritten,
re-rendered and reviewed once more. Story frames that need a poll / link sticker are not
published (the API can't add stickers). Everything is logged to output/logs/<date>.log.
"""

import json
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from carousel import produce_news  # noqa: E402
from carousel_renderer import RenderError  # noqa: E402
from editor_review import review_carousel, review_reel  # noqa: E402
from media_capturer import CaptureError  # noqa: E402
from news_fetcher import fetch_news, mark_used  # noqa: E402
from news_writer import NewsScript  # noqa: E402
from reel_metrics import log_reel  # noqa: E402
from reel_metrics import update as update_metrics  # noqa: E402

SCHEDULE_PATH = ROOT / "schedule.json"
QUEUE_DIR = ROOT / "output" / "queue"
LOG_DIR = ROOT / "output" / "logs"
REELS_DIR = ROOT / "output" / "reels"
MAX_NEWS_TRIES = 6


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG_DIR / f"{date.today().isoformat()}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def schedule() -> dict:
    return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))


def queue_path(day: date | None = None) -> Path:
    return QUEUE_DIR / f"{(day or date.today()).isoformat()}.json"


def load_queue() -> list[dict]:
    try:
        return json.loads(queue_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _rel(path: Path) -> str:
    """Queue paths are relative to the project, so a queue made in the cloud works on the PC."""
    return Path(path).resolve().relative_to(ROOT).as_posix()


def save_queue(items: list[dict]) -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    queue_path().write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- produce

def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


def _same_story(a: str, b: str) -> bool:
    """Two feeds covering one event (Verge + TechCrunch on Nadella) must not both run."""
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.4


def _apply_fixes(folder: Path, fixes: list[dict]) -> bool:
    path = folder / "carousel.json"
    script = json.loads(path.read_text(encoding="utf-8"))
    for f in fixes:
        i = f["slide"] - 1
        if 0 <= i < len(script["slides"]):
            script["slides"][i]["title"] = f["title"]
            script["slides"][i]["body"] = f["body"]
    try:
        NewsScript.model_validate(script)
    except Exception as exc:  # the fix itself broke a rule: don't publish
        log(f"   editor fixes break the rules: {str(exc)[:200]}")
        return False
    path.write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run([sys.executable, "carousel.py", "--rerender", str(folder)], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode == 0


def _reviewed_news(folder: Path) -> tuple[bool, list[str]]:
    verdict = review_carousel(folder)
    log(f"   editor: {verdict['verdict']} {verdict['problems'][:4]}")
    if verdict["verdict"] == "fix" and verdict["fixes"]:
        if not _apply_fixes(folder, verdict["fixes"]):
            return False, verdict["problems"]
        verdict = review_carousel(folder)
        log(f"   editor (after fixes): {verdict['verdict']} {verdict['problems'][:4]}")
    return verdict["verdict"] == "publish", verdict["problems"]


def produce_news_items(count: int) -> list[dict]:
    items, chosen_titles = [], []
    candidates = fetch_news(12)
    log(f"news: {len(candidates)} fresh candidates")
    for item in candidates[:MAX_NEWS_TRIES]:
        if len(items) >= count:
            break
        if any(_same_story(item["title"], t) for t in chosen_titles):
            log(f"   skip (same story): {item['title']}")
            continue
        log(f"news: {item['source']} - {item['title']}")
        try:
            folder = produce_news(item)
        except (CaptureError, RenderError) as exc:
            log(f"   failed: {exc}")
            mark_used(item["url"])
            continue
        ok, problems = _reviewed_news(folder)
        if ok:
            items.append({"kind": "carousel", "folder": _rel(folder), "title": item["title"]})
            chosen_titles.append(item["title"])
        else:
            log(f"   rejected, not queued: {folder.name}")
    return items


def produce_reel() -> dict | None:
    log("reel: running the video pipeline")
    proc = subprocess.run([sys.executable, "main.py", "--live-only"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=3600)
    lines = proc.stdout.splitlines()
    for line in [l for l in lines if "fetcher" in l or "Candidate" in l or "✖" in l][:8] + lines[-8:]:
        log("   " + line)
    if proc.returncode != 0:
        log("   video pipeline failed")
        return None
    temp, final = ROOT / "output" / "temp", ROOT / "output" / "final"
    script = json.loads((temp / "script.json").read_text(encoding="utf-8"))
    tool = json.loads((temp / "tool.json").read_text(encoding="utf-8"))
    out = REELS_DIR / f"{date.today().isoformat()}_{re.sub(r'[^a-z0-9]+', '-', script['tool_name'].lower()).strip('-')}"
    out.mkdir(parents=True, exist_ok=True)
    for name in ("final_video.mp4", "post.json", "cover.jpg", "cover_grid.jpg", "reel_qa.json"):
        if (final / name).exists():
            shutil.copy(final / name, out / name)
    (out / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"   hook [{script.get('hook_pattern', '?')}]: \"{script['hook']}\""
        + (f" (judge: {script['hook_judge']['reason']})" if script.get("hook_judge") else ""))
    verdict = review_reel(out / "final_video.mp4", script, tool)
    log(f"   editor: {verdict['verdict']} {verdict['problems'][:4]}")
    duration = json.loads((out / "reel_qa.json").read_text(encoding="utf-8"))["pacing"]["duration_sec"] \
        if (out / "reel_qa.json").exists() else 0.0
    log_reel(out.name, script, duration)
    if verdict["verdict"] != "publish":
        update_metrics(out.name, status=f"rejected: {'; '.join(verdict['problems'][:3])}")
        log("   reel not queued")
        return None
    return {"kind": "reel", "folder": _rel(out), "title": script["tool_name"]}


def produce(only: str = "") -> None:
    """only: "" (everything), "reel" or "news" - for test runs; the queue keeps the other slots empty."""
    log(f"=== produce {only} ===".replace("  ", " "))
    try:
        from ig_publisher import refresh_token
        log(f"token refresh: {'ok' if refresh_token() else 'not needed / failed'}")
    except Exception as exc:
        log(f"token refresh skipped: {exc}")
    slots = schedule()["slots"]
    news = produce_news_items(sum(s["kind"] == "carousel" for s in slots)) if only != "reel" else []
    reel = produce_reel() if any(s["kind"] == "reel" for s in slots) and only != "news" else None
    queue = []
    for s in slots:
        item = news.pop(0) if s["kind"] == "carousel" and news else (reel if s["kind"] == "reel" else None)
        if item:
            queue.append({**item, "time": s["time"], "status": "ready"})
        else:
            queue.append({"kind": s["kind"], "time": s["time"], "status": "empty"})
    save_queue(queue)
    for q in queue:
        log(f"queued {q['time']}: {q['kind']} {q.get('title', '-')} [{q['status']}]")


# ---------------------------------------------------------------- publish

def _carousel_payload(folder: Path) -> tuple[list[Path], str, list[str], list[Path]]:
    script = json.loads((folder / "carousel.json").read_text(encoding="utf-8"))
    files = sorted((folder / "carousel").glob("[0-9][0-9].*"))
    caption = script["caption"].strip() + "\n\n" + " ".join(script["hashtags"])
    alts = [s.get("alt_text", "") for s in script["slides"]]
    # story frames that need a sticker added by hand (poll, link) are skipped
    story = [p for p, f in zip(sorted((folder / "story").glob("*.jpg")), script["story"])
             if f["role"] in ("hook", "fact")]
    return files, caption, alts, story


def _reel_caption(folder: Path) -> str:
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    tags = " ".join(post["hashtags"][:5])
    return f"{post['caption'].strip()}\n\n{tags}"


def publish(index: int) -> None:
    from ig_publisher import permalink, publish_carousel, publish_reel, publish_story

    log(f"=== publish {index} ===")
    queue = load_queue()
    if not 1 <= index <= len(queue):
        log("nothing queued for this slot")
        return
    item = queue[index - 1]
    if item["status"] != "ready":
        log(f"slot {index} is {item['status']}; nothing to publish")
        return
    folder = ROOT / item["folder"]  # relative (absolute paths from older queues still work)
    try:
        if item["kind"] == "carousel":
            files, caption, alts, story = _carousel_payload(folder)
            media = publish_carousel(files, caption, alts)
            item["permalink"] = permalink(media)
            log(f"published carousel: {item['permalink']}")
            for frame in story:
                time.sleep(20)
                publish_story(frame)
                log(f"   story {frame.name} published")
        else:
            cover = folder / "cover.jpg"
            media = publish_reel(folder / "final_video.mp4", _reel_caption(folder),
                                 cover=cover if cover.exists() else None)
            item["permalink"] = permalink(media)
            log(f"published reel: {item['permalink']}")
            try:
                update_metrics(folder.name, status="published", permalink=item["permalink"])
            except KeyError:
                pass
        item["status"] = "published"
        item["published_at"] = datetime.now().isoformat(timespec="minutes")
    except Exception as exc:
        item["status"] = "failed"
        item["error"] = str(exc)[:300]
        log(f"publish failed: {exc}\n{traceback.format_exc()[-800:]}")
    save_queue(queue)


# ---------------------------------------------------------------- tools

def _gh() -> str:
    exe = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
    if not Path(exe).exists() and not shutil.which("gh"):
        raise SystemExit("GitHub CLI (gh) not found")
    return exe


def fetch() -> None:
    """Bring today's cloud production (GitHub Actions, .github/workflows/produce.yml) to this PC:
    pull the state commits, download the run's archive and unpack it into output/."""
    log("=== fetch (cloud production) ===")
    subprocess.run(["git", "pull", "--rebase", "--autostash", "-q"], cwd=ROOT, check=False)
    runs = json.loads(subprocess.run(
        [_gh(), "run", "list", "--workflow", "produce.yml", "--limit", "5",
         "--json", "databaseId,status,conclusion,createdAt"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    since = datetime.now(timezone.utc) - timedelta(hours=20)  # createdAt is UTC; 06:30 TRT = 03:30 UTC
    today = [r for r in runs if r["status"] != "completed"
             or datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00")) >= since]
    if not today:
        log("no cloud run today yet")
        return
    run = today[0]
    if run["status"] != "completed":
        log(f"cloud run {run['databaseId']} is still {run['status']}")
        return
    log(f"cloud run {run['databaseId']}: {run['conclusion']}")
    tmp = ROOT / "output" / "_download"
    shutil.rmtree(tmp, ignore_errors=True)
    proc = subprocess.run([_gh(), "run", "download", str(run["databaseId"]), "--dir", str(tmp)], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")
    archives = list(tmp.rglob("*.tgz"))
    if not archives:
        log(f"no archive in that run: {proc.stderr.strip()[:300]}")
        return
    subprocess.run(["tar", "-xzf", str(archives[0]), "-C", str(ROOT)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    log("downloaded; queue:")
    status()


def status() -> None:
    queue = load_queue()
    if not queue:
        print("Nothing queued today.")
    for i, q in enumerate(queue, 1):
        print(f"{i}. {q['time']} {q['kind']:8} {q['status']:9} {q.get('title', '-')} {q.get('permalink', '')}")


def check() -> None:
    from ig_publisher import account, publishing_quota
    from media_host import public_files

    info = account()
    print(f"Instagram: @{info.get('username')} ({info.get('account_type')}), {info.get('media_count')} posts")
    print(f"Quota: {publishing_quota()}")
    sample = next((ROOT / "brand" / "export").glob("*.png"))
    with public_files([sample]) as (url,):
        print(f"Tunnel OK: {url}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "produce":
        produce(sys.argv[2] if len(sys.argv) > 2 else "")
    elif cmd == "publish":
        publish(int(sys.argv[2]))
    elif cmd == "fetch":
        fetch()
    elif cmd == "check":
        check()
    else:
        status()
