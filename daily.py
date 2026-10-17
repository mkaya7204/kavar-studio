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
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from carousel import produce_news  # noqa: E402
from carousel_renderer import RenderError  # noqa: E402
from content_ranker import rank  # noqa: E402
from editor_review import review_carousel, review_reel  # noqa: E402
from media_capturer import CaptureError  # noqa: E402
from news_fetcher import fetch_news, mark_used  # noqa: E402
from model_trial import testable_first  # noqa: E402
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
    for round_ in range(1, FIX_ROUNDS + 1):
        if verdict["verdict"] != "fix" or not verdict["fixes"]:
            break
        if not _apply_fixes(folder, verdict["fixes"]):
            return False, verdict["problems"]
        verdict = review_carousel(folder)
        log(f"   editor (after fixes {round_}): {verdict['verdict']} {verdict['problems'][:4]}")
    return verdict["verdict"] == "publish", verdict["problems"]


FIX_ROUNDS = 2  # 2026-10-15: two carousels died on small second-round fixes (one word, one date)


def produce_news_items(count: int) -> list[dict]:
    items, chosen_titles, chosen_companies, blocked, tries = [], [], set(), set(), 0
    # "Biz denedik" (agreed 2026-10-15): new models we can run ourselves come first; then the stories
    # that reach more people (D-29, src/content_ranker.py)
    candidates = rank(testable_first(fetch_news(20)), "news_carousel")  # 20: more sources since D-29
    log(f"news: {len(candidates)} fresh candidates")
    for c in candidates:
        if r := c.get("rank"):
            log(f"   rank {r['score']:>2} {r['category']:<20} {'' if r['fits'] else 'off-concept '}"
                f"{'repeat ' if r['repeat'] else ''}{c['title'][:70]} ({r['reason'][:90]})")
    for item in candidates:
        if len(items) >= count or tries >= MAX_NEWS_TRIES:
            break
        r = item.get("rank") or {}
        if r and not item.get("testable") and (not r["fits"] or r["repeat"]):
            # 10-17 dry run: a gaming promotion (DLSS on GeForce NOW) reached 18:00 because off-concept
            # stories were only moved down; now they are never used
            log(f"   skip ({'repeat' if r['repeat'] else 'off-concept'}): {item['title']}")
            continue
        company = (r.get("company") or "").strip().lower()
        if company and company in chosen_companies:  # one story per company a day (3 of 4 were NVIDIA, 10-16)
            log(f"   skip (already a {company} story today): {item['title']}")
            continue
        host = urlsplit(item["url"]).hostname or ""
        if host in blocked:  # 10-17: openai.com answered 403 to the cloud three times, using half the tries
            log(f"   skip ({host} refuses this machine): {item['title']}")
            continue
        if any(_same_story(item["title"], t) for t in chosen_titles):
            log(f"   skip (same story): {item['title']}")
            continue
        log(f"news: {item['source']} - {item['title']}")
        tries += 1
        try:
            folder = produce_news(item)
            ok, problems = _reviewed_news(folder)
        except Exception as exc:  # one bad story never stops the day (any capture / write / render / review error)
            log(f"   failed: {type(exc).__name__}: {str(exc)[:300]}")
            if re.search(r"HTTP (401|403|429)\b", str(exc)):
                blocked.add(host)
                tries -= 1  # a refusal costs seconds, not a real try
            mark_used(item["url"])
            continue
        if ok:
            tested = "trial_note" in json.loads((folder / "article" / "article.json").read_text(encoding="utf-8"))
            items.append({"kind": "carousel", "folder": _rel(folder), "title": item["title"], "tested": tested,
                          "category": (item.get("rank") or {}).get("category", "")})
            chosen_titles.append(item["title"])
            chosen_companies.add(company)
        else:
            log(f"   rejected, not queued: {folder.name}")
    # a carousel with our own test takes the day's first carousel slot
    return sorted(items, key=lambda i: not i["tested"])


REEL_TIMEOUT = 1800  # seconds per Reel run; the job has 120 min for everything
REEL_ATTEMPTS = 3  # rendered Reels per day; 1 in 7 passed the editor on 2026-10-13/14, so retry with the next tool


JOB_BUDGET = 105 * 60  # produce.yml gives the job 120 min; stop starting Reel renders after this
_STARTED = time.monotonic()


def _time_for_a_reel() -> bool:
    return time.monotonic() - _STARTED + REEL_TIMEOUT <= JOB_BUDGET + 15 * 60


def produce_reel() -> dict | None:
    for attempt in range(1, REEL_ATTEMPTS + 1):
        if not _time_for_a_reel():
            log("reel: no time left in the job for another render")
            return None
        log(f"reel: running the video pipeline (attempt {attempt}/{REEL_ATTEMPTS})")
        item, rendered = _reel_attempt()
        if item or not rendered:  # queued, or the pipeline found nothing to film
            return item
    return None


def produce_trial_reel(news: list[dict]) -> dict | None:
    """"Biz denedik" Reel (agreed 2026-10-16) from the day's tested carousel; None if there is none
    or the editor rejects it (the tool Reel is made instead)."""
    tested = next((n for n in news if n.get("tested")), None)
    if not tested:
        return None
    log(f"reel: Biz denedik Reel from {tested['folder']}")
    try:
        item, _ = _reel_attempt([sys.executable, "src/trial_reel.py", str(ROOT / tested["folder"])])
    except Exception as exc:  # the tool Reel is still made
        log(f"   Biz denedik Reel failed: {type(exc).__name__}: {str(exc)[:300]}")
        return None
    return item


def _reel_attempt(cmd: list[str] | None = None) -> tuple[dict | None, bool]:
    """One main.py run + editor review. Returns (queue item or None, whether a Reel was rendered).
    A rejected tool is in the script history, so the next run moves on to another tool."""
    try:
        proc = subprocess.run(cmd or [sys.executable, "main.py", "--live-only"], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=REEL_TIMEOUT)
    except subprocess.TimeoutExpired:
        log(f"   video pipeline timed out after {REEL_TIMEOUT}s")
        return None, False
    lines = proc.stdout.splitlines()
    for line in [l for l in lines if "fetcher" in l or "Candidate" in l or "✖" in l][:8] + lines[-8:]:
        log("   " + line)
    if proc.returncode != 0:
        log("   video pipeline failed")
        return None, False
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
    log_reel(out.name, script, duration, kind="trial" if cmd and any("trial_reel" in c for c in cmd)
             else "tr" if cmd and any("tr_reel" in c for c in cmd) else "tool")
    if verdict["verdict"] != "publish":
        update_metrics(out.name, status=f"rejected: {'; '.join(verdict['problems'][:3])}")
        log("   reel not queued")
        return None, True
    return {"kind": "reel", "folder": _rel(out), "title": script["tool_name"]}, True


STAGES = ("morning", "rest")  # D-29: the 07:30 Turkey Reel first, the rest after it is scheduled


def _marker() -> Path:
    return ROOT / "state" / "last_produce.json"


def stages_done(day: date | None = None) -> list[str]:
    """Stages already produced today (an old marker without "stages" means the whole day)."""
    try:
        m = json.loads(_marker().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if m.get("date") != (day or date.today()).isoformat():
        return []
    return m.get("stages", list(STAGES))


def _mark_done(stage: str) -> None:
    _marker().parent.mkdir(parents=True, exist_ok=True)
    _marker().write_text(json.dumps({"date": date.today().isoformat(),
                                  "stages": sorted(set(stages_done()) | {stage}, key=STAGES.index)}), encoding="utf-8")


def produce_tr_reel() -> dict | None:
    """The 07:30 Turkey Reel (D-29); None if no story had the institution's own page, or the editor said no."""
    log("reel: 07:30 Türkiye Reel")
    try:
        item, _ = _reel_attempt([sys.executable, "src/tr_reel.py"])
    except Exception as exc:  # noqa: BLE001  the rest of the day still runs
        log(f"   Türkiye Reel failed: {type(exc).__name__}: {str(exc)[:300]}")
        return None
    return {**item, "concept": "tr"} if item else None


def produce(only: str = "") -> None:
    """only: "" (both stages), "next" (the first stage not done today: cron-job.org 06:17 and 08:00),
    "morning" / "rest" (one stage), or "reel" / "news" for test runs (part of "rest")."""
    log(f"=== produce {only} ===".replace("  ", " "))
    forced = bool(os.getenv("KAVAR_FORCE"))
    if only == "next":
        todo = [s for s in STAGES if s not in stages_done()]
        if not todo:
            log("today's production already ran (state/last_produce.json); skipping")
            return
        only = todo[0]
        log(f"next stage: {only}")
    elif not only and not forced:  # scheduled backups: only the stages not done yet
        done = stages_done()
        if len(done) == len(STAGES):
            log("today's production already ran (state/last_produce.json); skipping")
            return
        if "morning" in done:
            only = "rest"
    slots = schedule()["slots"]
    if only in ("", "morning"):
        morning = produce_tr_reel() if any(s.get("concept") == "tr" for s in slots) else None
        save_queue(_build_queue(slots, [], [], morning))
        log(f"queued 07:30: reel {morning['title'] if morning else '-'} [{'ready' if morning else 'empty'}]")
        _mark_done("morning")  # tried: the rest of the day starts even without a morning Reel
        if only == "morning":
            return
    _produce_rest(slots, only)


def _produce_rest(slots: list[dict], only: str) -> None:
    """11:45, 12:30, 18:00 and 20:30 (only: "" / "rest" = all, "reel" / "news" = part of it)."""
    try:
        from ig_publisher import refresh_token
        log(f"token refresh: {'ok' if refresh_token() else 'not needed / failed'}")
    except Exception as exc:
        log(f"token refresh skipped: {exc}")
    news = []
    if only != "reel":
        try:
            news = produce_news_items(sum(s["kind"] == "carousel" for s in slots))
        except Exception as exc:
            log(f"news production failed: {type(exc).__name__}: {str(exc)[:300]}")
    # the morning stage's Turkey Reel stays in its slot when the rest is made in the same run
    morning = next((q for q in load_queue() if q.get("concept") == "tr" and q["status"] == "ready"), None)
    save_queue(_build_queue(slots, list(news), [], morning))  # approved carousels survive a Reel crash or timeout
    reels: list[dict] = []  # best first: the "Biz denedik" Reel, then tool Reels
    wanted = sum(s["kind"] == "reel" and s.get("concept") != "tr" for s in slots)
    if wanted and only != "news":
        if trial := produce_trial_reel(news):
            reels.append(trial)
        while len(reels) < wanted:
            try:
                tool_reel = produce_reel()
            except Exception as exc:
                log(f"reel production failed: {type(exc).__name__}: {str(exc)[:300]}")
                break
            if tool_reel is None:
                break
            reels.append(tool_reel)
            save_queue(_build_queue(slots, list(news), reels, morning))
    queue = _build_queue(slots, list(news), reels, morning)
    save_queue(queue)
    for q in queue:
        log(f"queued {q['time']}: {q['kind']} {q.get('title', '-')} [{q['status']}]")
    # the rest counts as done only when something is ready: a crashed or empty run leaves room for
    # the later runs (08:00 cron-job.org, produce.yml backups) to try again
    if only in ("", "rest") and any(q["status"] == "ready" for q in queue):
        _mark_done("rest")


def _build_queue(slots: list[dict], news: list[dict], reels: list[dict], morning: dict | None = None) -> list[dict]:
    """Carousels fill their slots in order. Reels (best first) fill the reel slots from the LAST one
    back: the best Reel ("Biz denedik") goes out in the evening, a second one at noon (user, 2026-10-16).
    The 07:30 slot (concept "tr", D-29) takes only the Turkey Reel, and the Turkey Reel only that slot."""
    reel_slots = [i for i, s in enumerate(slots) if s["kind"] == "reel" and s.get("concept") != "tr"]
    by_slot = dict(zip(reversed(reel_slots), reels))
    by_slot.update({i: morning for i, s in enumerate(slots) if s.get("concept") == "tr" and morning})
    queue = []
    for i, s in enumerate(slots):
        item = news.pop(0) if s["kind"] == "carousel" and news else by_slot.get(i)
        if item:
            queue.append({**item, "time": s["time"], "status": "ready"})
        else:
            queue.append({"kind": s["kind"], "time": s["time"], "status": "empty"})
    return queue


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


def _merge_queue(old: list[dict], new: list[dict]) -> list[dict]:
    """Slot by slot: a later run's ready item wins; otherwise what was already there stays."""
    by_time = {q["time"]: q for q in old}
    return [q if q.get("status") == "ready" or q["time"] not in by_time else by_time[q["time"]] for q in new]


def _unpack_keeping_today(archive: Path) -> None:
    """Unpack a cloud archive without losing an earlier run of the same day (10-17: a Reel-only run
    replaced the morning's queue and log, so the carousels showed "empty" and their editor verdicts
    were gone). Today's queue is merged slot by slot; today's log gets the new run appended."""
    log_path = LOG_DIR / f"{date.today().isoformat()}.log"
    old_queue = load_queue()
    old_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    subprocess.run(["tar", "-xzf", str(archive), "-C", str(ROOT)], check=True)
    if old_queue:
        save_queue(_merge_queue(old_queue, load_queue()))
    new_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    if old_log and new_log and not new_log.startswith(old_log[:200]):
        log_path.write_text(old_log + new_log, encoding="utf-8")


def fetch() -> None:
    """Bring today's cloud production (GitHub Actions, .github/workflows/produce.yml) to this PC:
    pull the state commits, download the run's archive and unpack it into output/."""
    log("=== fetch (cloud production) ===")
    subprocess.run(["git", "pull", "--rebase", "--autostash", "-q"], cwd=ROOT, check=False)
    runs = json.loads(subprocess.run(
        [_gh(), "run", "list", "--workflow", "produce.yml", "--branch", "main", "--limit", "8",
         "--json", "databaseId,status,conclusion,createdAt"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    since = datetime.now(timezone.utc) - timedelta(hours=20)  # createdAt is UTC; 06:30 TRT = 03:30 UTC
    today = [r for r in runs if datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00")) >= since]
    if not today:
        log("no cloud run today yet")
        return
    # the newest finished run that actually made today's queue (2026-10-14: a late run that skipped
    # the day overwrote the good log); runs still going are reported, never waited on
    for r in today:
        if r["status"] != "completed":
            log(f"cloud run {r['databaseId']} is still {r['status']}")
    want = f"output/queue/{date.today().isoformat()}.json"
    tmp = ROOT / "output" / "_download"
    for run in [r for r in today if r["status"] == "completed"]:
        shutil.rmtree(tmp, ignore_errors=True)
        proc = subprocess.run([_gh(), "run", "download", str(run["databaseId"]), "-n", "kavar-output",
                               "--dir", str(tmp)], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8")
        archives = list(tmp.rglob("*.tgz"))
        listing = subprocess.run(["tar", "-tzf", str(archives[0])], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout if archives else ""
        if want not in listing.split():
            log(f"cloud run {run['databaseId']} ({run['conclusion']}) has no queue for today; skipping it"
                + ("" if archives else f": {proc.stderr.strip()[:200]}"))
            continue
        log(f"cloud run {run['databaseId']}: {run['conclusion']}")
        _unpack_keeping_today(archives[0])
        shutil.rmtree(tmp, ignore_errors=True)
        log("downloaded; queue:")
        status()
        return
    shutil.rmtree(tmp, ignore_errors=True)
    log("no finished cloud run with today's queue yet")


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
