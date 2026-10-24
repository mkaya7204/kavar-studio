"""KAVAR's daily autopilot: produce in the morning, publish at fixed times.

    python daily.py produce        # 06:30: 2 news carousels + 1 Reel, each reviewed by the editor
    python daily.py publish 1      # 12:30 / 18:00 / 20:30: publish queue item 1 / 2 / 3
    python daily.py status         # what is queued / published today
    python daily.py fetch          # download today's cloud production (GitHub Actions) to this PC
    python daily.py check          # Instagram login, quota and tunnel smoke test (publishes nothing)
    python daily.py reserve [keep HH:MM | used N]   # approved posts kept for empty slots (D-37)

Windows Task Scheduler runs these (setup_tasks.ps1). Only content the editor review
(src/editor_review.py) passes is queued; a carousel the editor wants fixed is rewritten,
re-rendered and reviewed once more. Story frames that need a poll / link sticker are not
published (the API can't add stickers). Everything is logged to output/logs/<date>.log.
"""

import io
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
from news_writer import NewsScript, revise_for_editor  # noqa: E402
from reel_metrics import log_reel  # noqa: E402
from reel_metrics import update as update_metrics  # noqa: E402
from reel_qa import cut_frames, first_frame_report, make_cover, pacing_report  # noqa: E402
import claude_usage  # noqa: E402
import failures  # noqa: E402
import reserve  # noqa: E402
from tts_engine import DRAFT_ENV  # noqa: E402

SCHEDULE_PATH = ROOT / "schedule.json"
QUEUE_DIR = ROOT / "output" / "queue"
LOG_DIR = ROOT / "output" / "logs"
REELS_DIR = ROOT / "output" / "reels"
SURPLUS_DIR = ROOT / "output" / "reserve"
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


def _apply_fixes(folder: Path, verdict: dict) -> bool:
    """D-40: the writer carries out the editor's "fix" inside every rule (slides, story, caption; wrong
    pictures dropped). Only if the writer can't, the editor's own slide text is pasted in, as before."""
    path = folder / "carousel.json"
    script = json.loads(path.read_text(encoding="utf-8"))
    try:
        article = json.loads((folder / "article" / "article.json").read_text(encoding="utf-8"))
        revised = revise_for_editor(script, verdict, article)
    except Exception as exc:  # noqa: BLE001  the old way below still runs
        log(f"   writer could not apply the editor's fixes: {type(exc).__name__}: {str(exc)[:200]}")
        revised = None
    if revised is not None:
        log(f"   the writer rewrote it for the editor (pictures dropped on slides {verdict.get('bad_visual_slides', [])})")
        script = revised
    else:
        for f in verdict.get("fixes", []):
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
        if verdict["verdict"] != "fix":
            break
        if not _apply_fixes(folder, verdict):
            return False, verdict["problems"]
        verdict = review_carousel(folder)
        log(f"   editor (after fixes {round_}): {verdict['verdict']} {verdict['problems'][:4]}")
    return verdict["verdict"] == "publish", verdict["problems"]


FIX_ROUNDS = 2  # 2026-10-15: two carousels died on small second-round fixes (one word, one date)


def produce_news_items(count: int) -> list[dict]:
    items, chosen_titles, chosen_companies, tries = [], [], set(), 0
    blocked = set(failures.blocked_hosts())  # D-39: hosts that kept failing are skipped for 7 days
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
            failures.record("news", "news", item["title"], f"{type(exc).__name__}: {exc}", item["url"],
                            rendered=False)
            continue
        if ok:
            failures.ok("news", "news", item["title"], item["url"])
            tested = "trial_note" in json.loads((folder / "article" / "article.json").read_text(encoding="utf-8"))
            items.append({"kind": "carousel", "folder": _rel(folder), "title": item["title"], "tested": tested,
                          "category": (item.get("rank") or {}).get("category", "")})
            chosen_titles.append(item["title"])
            chosen_companies.add(company)
        else:
            log(f"   rejected, not queued: {folder.name}")
            failures.record("news", "news", item["title"], "; ".join(problems), item["url"])
    # a carousel with our own test takes the day's first carousel slot
    return sorted(items, key=lambda i: not i["tested"])


REEL_TIMEOUT = 1800  # seconds per Reel run; the job has 120 min for everything
REEL_ATTEMPTS = 3  # rendered Reels per day; 1 in 7 passed the editor on 2026-10-13/14, so retry with the next tool
GUIDE_ATTEMPTS = 2  # 07:30 guide Reel drafts per morning (silent drafts cost no voice, D-30); the rest waits for it
# D-33 fixed a rejected silent draft twice (src/reel_fixer.py); D-38 (user 2026-10-22) switched it off: its fixes
# cropped the proof picture (cut text in 12 of 14 fix rounds, 10-19..10-21). D-42 (user 10-23: "düzeltilerek uygun
# hale getirilecek varsa yapmayıp boş denilmesinden bıktım") turns it on again: the crops are gone (whole pictures,
# windows end in a gap, shots never reach the frame's edge) and every fixed draft is measured for cuts first.
# D-45: the fixer is now our agent (src/reel_agent.py), which renders and looks up to 3 times inside one round;
# one round per draft keeps the morning inside the job's time.
REEL_FIX_ROUNDS = 1
# D-47 (user 10-23: "haftalık token yetersiz kalır ... yayın saatinde yayınlamak olan yetişmez"): the agent runs at
# most this many times per production run (each session is up to 12 min of Claude), on the first rejections
AGENT_SESSIONS_PER_RUN = 2
_agent_sessions = 0
GUIDE_EXTRA = 2  # D-42: guide Reel drafts the rest stage may make for a Reel slot that is still empty
REEL_SECONDS = (14.0, 26.0)  # the editor's length rule (reel-retention-editor), checked again on the voiced Reel


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
        try:
            item, rendered = _reel_attempt()
        except Exception as exc:  # noqa: BLE001  D-49: one broken attempt never ends the day's tool Reels
            log(f"   reel attempt failed: {type(exc).__name__}: {str(exc)[:300]}")
            continue
        if item or not rendered:  # queued, or the pipeline found nothing to film
            return item
    return None


def produce_trial_reel(news: list[dict]) -> dict | None:
    """"Biz denedik" Reel (agreed 2026-10-16) from the day's tested carousel; None if there is none
    or the editor rejects it (the tool Reel is made instead)."""
    tested = next((n for n in news if n.get("tested")), None)
    if not tested:
        return None
    if failures.paused("trial"):  # D-39
        log("reel: Biz denedik Reels are paused by the failure ledger (state/self_correct.json)")
        return None
    log(f"reel: Biz denedik Reel from {tested['folder']}")
    try:
        item, _ = _reel_attempt([sys.executable, "src/trial_reel.py", str(ROOT / tested["folder"])])
    except Exception as exc:  # the tool Reel is still made
        log(f"   Biz denedik Reel failed: {type(exc).__name__}: {str(exc)[:300]}")
        return None
    return item


def _voice_approved_reel(out: Path) -> bool:
    """D-30 (the user, 2026-10-18): the editor approved the silent draft, so George speaks now, once.
    The voiced Reel replaces the draft in `out` and must pass the measured first-frame and length checks."""
    try:
        proc = subprocess.run([sys.executable, "src/voice_final.py"], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=REEL_TIMEOUT)
    except subprocess.TimeoutExpired:
        log(f"   voiced render timed out after {REEL_TIMEOUT}s")
        return False
    for line in proc.stdout.splitlines()[-4:]:
        log("   " + line)
    if proc.returncode != 0:
        log("   no voice for the approved Reel (both ElevenLabs accounts refused?): Reel not made")
        return False
    final = ROOT / "output" / "final"
    for name in ("final_video.mp4", "post.json", "reel_qa.json"):
        if (final / name).exists():
            shutil.copy(final / name, out / name)
    make_cover(out / "final_video.mp4", out)
    first, dur = first_frame_report(out / "final_video.mp4", out), pacing_report(out / "final_video.mp4")["duration_sec"]
    if not first["ok"] or not REEL_SECONDS[0] <= dur <= REEL_SECONDS[1]:
        log(f"   voiced Reel failed the measured checks: first frame ok={first['ok']}, {dur:.1f}s")
        return False
    if cut := cut_frames(out / "final_video.mp4", out):
        # D-49 (10-24 gerty: approved, voiced, then dropped for a cut at 11.25 s): rebuilt still on the same
        # George audio (voice_final keeps it), never voiced again
        log(f"   voiced Reel: a picture runs off the frame at {cut[:6]} s; rebuilding it still on the same voice")
        if cut := _voiced_still_rebuild(out):
            log(f"   voiced Reel still cut at {cut[:6]} s after the still rebuild; not queued")
            return False
    log(f"   voiced with George: {dur:.1f}s")
    return True


def _voiced_still_rebuild(out: Path) -> list[float]:
    """The approved Reel again without the shot zoom, on the George audio already made (REUSE_VOICE_ENV);
    returns the seconds still cut ([] = clean, files in `out` replaced)."""
    from voice_final import REUSE_VOICE_ENV

    capture_path = ROOT / "output" / "temp" / "capture.json"
    try:
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [-1.0]
    if capture.get("still"):
        return cut_frames(out / "final_video.mp4", out)
    capture_path.write_text(json.dumps({**capture, "still": True}, indent=2, ensure_ascii=False), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != DRAFT_ENV}
    try:
        proc = subprocess.run([sys.executable, "src/voice_final.py"], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=REEL_TIMEOUT,
                              env={**env, REUSE_VOICE_ENV: "1"})
    except subprocess.TimeoutExpired:
        return [-1.0]
    if proc.returncode != 0:
        log("   voiced still rebuild failed: " + (proc.stderr or proc.stdout or "").strip()[-300:])
        return [-1.0]
    final = ROOT / "output" / "final"
    for name in ("final_video.mp4", "post.json", "reel_qa.json"):
        if (final / name).exists():
            shutil.copy(final / name, out / name)
    make_cover(out / "final_video.mp4", out)
    return cut_frames(out / "final_video.mp4", out)


DRY_ENV = "KAVAR_DRY"  # produce.yml dry=yes (D-46)
VOICE_KIT = "_voice"  # inside a Reel's folder: what voice.yml needs to voice it later


def _keep_for_voice(out: Path) -> None:
    """D-46 (the user, 10-23: "deneme veya işte reel ararken yada reel de düzenleme ekleme yapılırken seslendirme
    kullanılmayacak"): an approved Reel of a test run stays silent. Its words, facts and the exact pictures are
    kept in <reel>/_voice, so voice.yml can voice the same Reel once, if it is chosen to go out."""
    temp = ROOT / "output" / "temp"
    kit = out / VOICE_KIT
    shutil.rmtree(kit, ignore_errors=True)
    kit.mkdir(parents=True)
    for name in ("script.json", "tool.json"):
        if (temp / name).exists():
            shutil.copy(temp / name, kit / name)
    try:
        capture = json.loads((temp / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        capture = {}
    for key in ("proof_path", "screenshot_path", "fullpage_path", "logo_path"):
        src = Path(capture[key]) if capture.get(key) else None
        if src and src.exists():
            dst = kit / f"{key}{src.suffix}"
            shutil.copy(src, dst)
            capture[key] = _rel(dst)
    capture.pop("pictures", None)  # the fixer's choices are made; the voiced Reel shows exactly these
    (kit / "capture.json").write_text(json.dumps(capture, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _still_if_cut(out: Path) -> list[float]:
    """D-42: the draft is measured before the editor sees it. A picture running off the frame (the cut text
    the editor rejected on 10-19, 10-21, 10-22 and 10-23) rebuilds the same Reel without the shot zoom, on
    the silent voice; returns the seconds still cut ([] = clean)."""
    cut = cut_frames(out / "final_video.mp4", out)
    if not cut:
        return []
    log(f"   measured: a picture runs off the frame at {cut[:6]} s; rebuilding it without the zoom")
    capture_path = ROOT / "output" / "temp" / "capture.json"
    try:
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cut
    if capture.get("still"):
        return cut
    capture_path.write_text(json.dumps({**capture, "still": True}, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        proc = subprocess.run([sys.executable, "src/voice_final.py"], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=REEL_TIMEOUT,
                              env={**os.environ, DRAFT_ENV: "1"})
    except subprocess.TimeoutExpired:
        log("   still rebuild timed out")
        return cut
    if proc.returncode != 0:
        log("   still rebuild failed: " + (proc.stderr or proc.stdout or "").strip()[-300:])
        return cut
    _copy_draft(out, json.loads((ROOT / "output" / "temp" / "script.json").read_text(encoding="utf-8")))
    cut = cut_frames(out / "final_video.mp4", out)
    log(f"   after the still rebuild: {f'still cut at {cut[:6]} s' if cut else 'no picture runs off the frame'}")
    return cut


def _review(out: Path, script: dict, tool: dict) -> dict:
    """The measured cut check first (a cut the rebuild can't remove is a reject the fixer works on), then the
    editor."""
    if cut := _still_if_cut(out):
        return {"verdict": "reject", "problems": [f"görsel kenardan kesik (ölçüldü: {cut[:6]} s); kesik yazı kabul "
                                                  f"edilmez, görseli bütün gösteren başka bir görsel seç"], "fixes": []}
    return review_reel(out / "final_video.mp4", script, tool)


def _copy_draft(out: Path, script: dict) -> None:
    """The rendered draft (output/final) and its script into the Reel's folder."""
    final = ROOT / "output" / "final"
    out.mkdir(parents=True, exist_ok=True)
    for name in ("final_video.mp4", "post.json", "cover.jpg", "cover_grid.jpg", "reel_qa.json"):
        if (final / name).exists():
            shutil.copy(final / name, out / name)
    (out / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")


def _fix_draft(out: Path, verdict: dict, fix_round: int) -> dict | None:
    """D-33 (the user, 2026-10-18: "editör red derse sen devreye giriyorsun, düzeltilecek bir yanı varsa
    düzelt"). D-45: our fixing agent (src/reel_agent.py) works on the rejected silent draft: it finds the
    cause, changes words, pictures or layout, renders on the draft voice and looks at the result until it is
    clean. Returns the fixed script, or None when the topic itself can't be fixed."""
    (out / "_verdict.json").write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"   fixing the rejected draft with the agent (round {fix_round}/{REEL_FIX_ROUNDS})")
    try:
        proc = subprocess.run([sys.executable, "src/reel_agent.py", str(out)], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=REEL_TIMEOUT,
                              env={**os.environ, DRAFT_ENV: "1"})
    except subprocess.TimeoutExpired:
        log(f"   fix timed out after {REEL_TIMEOUT}s")
        return None
    for line in [l for l in proc.stdout.splitlines() if l.strip()][-12:]:  # the agent's refusals and words too
        log("   " + line)
    if proc.returncode != 0:
        if proc.returncode != 3:
            log("   fix failed: " + proc.stderr.strip()[-300:])
        return None
    script = json.loads((ROOT / "output" / "temp" / "script.json").read_text(encoding="utf-8"))
    _copy_draft(out, script)
    return script


def _reel_attempt(cmd: list[str] | None = None) -> tuple[dict | None, bool]:
    """One main.py run + editor review. Returns (queue item or None, whether a Reel was rendered).
    A rejected tool is in the script history, so the next run moves on to another tool.
    The run uses the silent draft voice (D-30); only an approved Reel is voiced. Every outcome goes to the
    failure ledger (D-39)."""
    kind = "trial" if cmd and any("trial_reel" in c for c in cmd) \
        else "guide" if cmd and any("guide_reel" in c for c in cmd) else "tool"
    try:
        proc = subprocess.run(cmd or [sys.executable, "main.py", "--live-only"], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=REEL_TIMEOUT,
                              env={**os.environ, DRAFT_ENV: "1"})
    except subprocess.TimeoutExpired:
        log(f"   video pipeline timed out after {REEL_TIMEOUT}s")
        return None, False
    lines = proc.stdout.splitlines()
    picked = [l for l in lines if "fetcher" in l or "Candidate" in l or "✖" in l or "▶" in l or "   rank " in l]
    for line in picked[:16] + lines[-8:]:
        log("   " + line)
    if proc.returncode != 0:
        log("   video pipeline failed")
        failures.record("reel", kind, "-", " ".join(l for l in lines if "✖" in l or "[" in l)[-600:], rendered=False)
        return None, False
    temp = ROOT / "output" / "temp"
    script = json.loads((temp / "script.json").read_text(encoding="utf-8"))
    tool = json.loads((temp / "tool.json").read_text(encoding="utf-8"))
    out = REELS_DIR / f"{date.today().isoformat()}_{re.sub(r'[^a-z0-9]+', '-', script['tool_name'].lower()).strip('-')}"
    _copy_draft(out, script)
    log(f"   hook [{script.get('hook_pattern', '?')}]: \"{script['hook']}\""
        + (f" (judge: {script['hook_judge']['reason']})" if script.get("hook_judge") else ""))
    verdict = _review(out, script, tool)
    log(f"   editor: {verdict['verdict']} {verdict['problems'][:4]}")
    global _agent_sessions
    for fix_round in range(1, REEL_FIX_ROUNDS + 1):  # D-33: a rejected draft is fixed before another is tried
        if verdict["verdict"] == "publish" or not _time_for_a_reel():
            break
        if _agent_sessions >= AGENT_SESSIONS_PER_RUN:
            log(f"   no agent session left in this run ({AGENT_SESSIONS_PER_RUN}, D-47): the next candidate is tried")
            break
        _agent_sessions += 1
        fixed = _fix_draft(out, verdict, fix_round)
        if fixed is None:
            break
        script = fixed
        verdict = _review(out, script, tool)
        log(f"   editor (after fix {fix_round}): {verdict['verdict']} {verdict['problems'][:4]}")
    if verdict["verdict"] == "publish" and os.getenv(DRY_ENV):
        _keep_for_voice(out)
        log("   approved in a test run: kept silent for voice.yml (George only for a Reel going out, D-46)")
        failures.ok("reel", kind, script["tool_name"], script.get("website_url", ""))
        return {"kind": "reel", "folder": _rel(out), "title": script["tool_name"], "needs_voice": True}, True
    if verdict["verdict"] == "publish" and not _voice_approved_reel(out):
        # D-49: logged before its status is set (10-24 gerty: update_metrics raised KeyError on an unlogged
        # Reel, which ended every tool Reel of the day)
        log_reel(out.name, script, 0.0, kind=kind)
        update_metrics(out.name, status="approved draft, but the voiced Reel failed")
        failures.record("reel", kind, script["tool_name"], "no voice / voiced Reel failed", rendered=False)
        return None, False  # no voice left (or a broken render): another attempt would fail the same way
    duration = json.loads((out / "reel_qa.json").read_text(encoding="utf-8"))["pacing"]["duration_sec"] \
        if (out / "reel_qa.json").exists() else 0.0
    log_reel(out.name, script, duration, kind=kind)
    if verdict["verdict"] != "publish":
        update_metrics(out.name, status=f"rejected: {'; '.join(verdict['problems'][:3])}")
        log("   reel not queued")
        failures.record("reel", kind, script["tool_name"], "; ".join(verdict["problems"]),
                        script.get("website_url", ""), rendered="no verdict" not in " ".join(verdict["problems"]))
        return None, True
    failures.ok("reel", kind, script["tool_name"], script.get("website_url", ""))
    return {"kind": "reel", "folder": _rel(out), "title": script["tool_name"]}, True


STAGES = ("morning", "rest")  # D-29/D-31: the 07:30 guide Reel first, the rest after it is scheduled


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


def produce_guide_reel() -> dict | None:
    """The guide Reel (D-31); None if no company post fit the concept, or the editor said no."""
    if failures.paused("guide"):  # D-39
        log("reel: guide Reels are paused by the failure ledger (state/self_correct.json)")
        return None
    for attempt in range(1, GUIDE_ATTEMPTS + 1):  # a rejected post is marked used, so the next try takes another
        log(f"reel: 07:30 Rehber Reel (attempt {attempt}/{GUIDE_ATTEMPTS})")
        try:
            item, rendered = _reel_attempt([sys.executable, "src/guide_reel.py"])
        except Exception as exc:  # noqa: BLE001  the rest of the day still runs
            log(f"   Rehber Reel failed: {type(exc).__name__}: {str(exc)[:300]}")
            return None
        if item or not rendered:
            return {**item, "concept": "guide"} if item else None
    return None


def produce(only: str = "") -> bool:
    """only: "" (both stages), "next" (the first stage not done today: cron-job.org 06:17 and 08:00),
    "morning" / "rest" (one stage), or "reel" / "news" for test runs (part of "rest").
    Returns whether the rest of the day (the non-morning slots) was made in this run."""
    log(f"=== produce {only} ===".replace("  ", " "))
    forced = bool(os.getenv("KAVAR_FORCE"))
    if only == "next":
        todo = [s for s in STAGES if s not in stages_done()]
        if not todo:
            log("today's production already ran (state/last_produce.json); skipping")
            return False
        only = todo[0]
        log(f"next stage: {only}")
    elif not only and not forced:  # scheduled backups: only the stages not done yet
        done = stages_done()
        if len(done) == len(STAGES):
            log("today's production already ran (state/last_produce.json); skipping")
            return False
        if "morning" in done:
            only = "rest"
    elif only in STAGES and not forced and only in stages_done():
        # D-40: produce.yml runs the stages as two steps (the morning Reel is uploaded on its own); a backup
        # run must not make a stage again that an earlier run already made
        log(f"the {only} stage already ran today; skipping")
        return False
    cfg = schedule()
    slots = cfg["slots"]
    for line in failures.react():  # D-39: the last 7 days' failures change today's run by fixed rules
        log("self-correct: " + line)
    if only in ("", "morning"):
        wants_guide = cfg.get("guide_reel") or any(s.get("concept") == "guide" for s in slots)
        morning = produce_guide_reel() if wants_guide else None
        save_queue(_build_queue(slots, [], [], morning))
        log(f"guide Reel: {morning['title'] if morning else '-'} [{'ready' if morning else 'none'}]")
        _mark_done("morning")  # tried: the rest of the day starts even without a morning Reel
        if only == "morning":
            return False
    _produce_rest(slots, only)
    return True


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
    # the morning stage's guide Reel stays in its slot when the rest is made in the same run
    morning = next((q for q in load_queue() if q.get("concept") == "guide" and q["status"] == "ready"), None)
    save_queue(_build_queue(slots, list(news), [], morning))  # approved carousels survive a Reel crash or timeout
    reels: list[dict] = []  # best first: the "Biz denedik" Reel, then tool Reels
    wanted = sum(s["kind"] == "reel" and s.get("concept") != "guide" for s in slots)
    if wanted and only != "news":
        if trial := produce_trial_reel(news):
            reels.append(trial)
        while len(reels) < wanted and schedule().get("tool_reels", True) and not failures.paused("tool"):
            try:
                tool_reel = produce_reel()
            except Exception as exc:
                log(f"reel production failed: {type(exc).__name__}: {str(exc)[:300]}")
                break
            if tool_reel is None:
                break
            reels.append(tool_reel)
            save_queue(_build_queue(slots, list(news), reels, morning))
    if only != "news":
        morning = _fill_empty_reel_slots(slots, news, reels, morning)
    queue = _build_queue(slots, list(news), reels, morning)
    save_queue(queue)
    queued = {q.get("folder") for q in queue}
    _save_surplus([i for i in news + reels + ([morning] if morning else []) if i.get("folder") not in queued])
    for q in queue:
        log(f"queued {q['time']}: {q['kind']} {q.get('title', '-')} [{q['status']}]")
    # the rest counts as done only when something is ready: a crashed or empty run leaves room for
    # the later runs (08:00 cron-job.org, produce.yml backups) to try again
    if only in ("", "rest") and any(q["status"] == "ready" for q in queue):
        _mark_done("rest")


def _fill_empty_reel_slots(slots: list[dict], news: list[dict], reels: list[dict], morning: dict | None) -> dict | None:
    """D-42 (user 10-23: "reel boş deyip ... boş denilmesinden bıktım"): a Reel slot the trial and tool Reels
    left empty is not given up. The guide Reel (its own concept, the next unused company post each time) is
    made for it: first for an empty 07:30 guide slot (it goes out later that morning), then for the other
    Reel slots. `reels` grows in place; returns the guide slot's Reel."""
    cfg = schedule()
    has_guide_slot = any(s.get("concept") == "guide" for s in slots)
    if not (cfg.get("guide_reel") or has_guide_slot):
        return morning
    open_slots = sum(s["kind"] == "reel" and s.get("concept") != "guide" for s in slots) - len(reels) \
        - (1 if morning and not has_guide_slot else 0)
    tries = GUIDE_EXTRA
    if has_guide_slot and morning is None and tries and _time_for_a_reel():
        log("reel: the 07:30 guide slot is empty; making a guide Reel for it now")
        tries -= 1
        if extra := produce_guide_reel():
            morning = extra
            save_queue(_build_queue(slots, list(news), reels, morning))
    while open_slots > 0 and tries and _time_for_a_reel():
        log(f"reel: {open_slots} Reel slot(s) still empty; trying a guide Reel for it")
        tries -= 1
        extra = produce_guide_reel()
        if extra is None:
            continue
        if morning is None and not has_guide_slot:
            morning = extra  # D-38 day: the guide Reel is the last choice for a Reel slot
        else:
            reels.append(extra)
        open_slots -= 1
        save_queue(_build_queue(slots, list(news), reels, morning))
    return morning


def empty_day() -> bool:
    """Nothing in today's queue is ready (D-38: 10-22 made 0/5 and the run still showed success)."""
    return not any(q["status"] in ("ready", "published") for q in load_queue())


def _save_surplus(items: list[dict]) -> None:
    """D-37: approved posts that found no slot today are named for the reserve; `fetch` keeps their files."""
    if not items:
        return
    SURPLUS_DIR.mkdir(parents=True, exist_ok=True)
    (SURPLUS_DIR / f"{date.today().isoformat()}.json").write_text(
        json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    for i in items:
        log(f"reserve: {i['kind']} {i.get('title', '-')} (approved, no slot today)")


def _build_queue(slots: list[dict], news: list[dict], reels: list[dict], morning: dict | None = None) -> list[dict]:
    """Carousels fill their slots in order. Reels (best first) fill the reel slots from the LAST one
    back: the best Reel ("Biz denedik") goes out in the evening, a second one at noon (user, 2026-10-16).
    A slot with concept "guide" (D-31) takes only the guide Reel, and the guide Reel only that slot. Without
    such a slot (D-38) the guide Reel is the last choice for the Reel slots, after "Biz denedik" and tool Reels."""
    reel_slots = [i for i, s in enumerate(slots) if s["kind"] == "reel" and s.get("concept") != "guide"]
    has_guide_slot = any(s.get("concept") == "guide" for s in slots)
    by_slot = dict(zip(reversed(reel_slots), reels + ([morning] if morning and not has_guide_slot else [])))
    by_slot.update({i: morning for i, s in enumerate(slots) if s.get("concept") == "guide" and morning})
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


def _import_surplus() -> None:
    """Copy today's surplus (output/reserve/<date>.json) into the reserve, files and all (D-37)."""
    path = SURPLUS_DIR / f"{date.today().isoformat()}.json"
    if not path.exists():
        return
    for item in json.loads(path.read_text(encoding="utf-8")):
        if entry := reserve.add(item, date.today().isoformat()):
            log(f"reserve: kept {entry['kind']} {entry['title']}")


def reserve_cli(args: list[str]) -> None:
    if args[:1] == ["keep"]:  # a ready item of today's queue that was not posted
        item = next((q for q in load_queue() if q["time"] == args[1] and q["status"] == "ready"), None)
        if not item:
            raise SystemExit(f"no ready item at {args[1]} today")
        entry = reserve.add(item, date.today().isoformat())
        print(f"kept: {entry['title']}" if entry else "already kept, or its files are gone")
    elif args[:1] == ["used"]:
        print(f"dropped: {reserve.used(int(args[1]))['title']}")
    items = reserve.load()
    if not items:
        print("The reserve is empty.")
    for i, r in enumerate(items, 1):
        print(f"{i}. {r['made']} {r['kind']:8} {r['concept']:6} {'current' if reserve.current(r) else 'OLD    '} "
              f"{r['title']} -> {r['folder']}")


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
    # a finished run's whole day first; else (D-40) the morning guide Reel, uploaded on its own while the
    # rest of the day is still being made
    tries = [(r, "kavar-output") for r in today if r["status"] == "completed"] + [(r, "kavar-morning") for r in today]
    for run, name in tries:
        archive, error = _download_archive(run["databaseId"], name, tmp)
        listing = subprocess.run(["tar", "-tzf", str(archive)], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout if archive else ""
        if want not in listing.split():
            log(f"cloud run {run['databaseId']} ({run['conclusion'] or run['status']}) has no {name} for today; "
                f"skipping it" + ("" if archive else f": {error[:200]}"))
            continue
        log(f"cloud run {run['databaseId']}: {run['conclusion'] or run['status']} ({name})")
        _unpack_keeping_today(archive)
        _import_surplus()
        shutil.rmtree(tmp, ignore_errors=True)
        if name == "kavar-morning" and run["status"] != "completed":
            log("only the morning guide Reel so far; the rest of the day is still being made: fetch again later")
        log("downloaded; queue:")
        status()
        return
    shutil.rmtree(tmp, ignore_errors=True)
    log("no cloud run with today's queue yet")


# D-49: where .github/deliver.sh puts an archive whose artifact upload failed (storage quota, 10-24)
RELEASE_TAG = "out-{run_id}"
RELEASE_FILES = {"kavar-output": "kavar-*.tgz", "kavar-morning": "morning-*.tgz"}


def _download_archive(run_id: int, name: str, tmp: Path) -> tuple[Path | None, str]:
    """The .tgz of one artifact of a run. `gh run download` first; for a run still going (D-40: the
    morning artifact) the artifacts API, which lists an artifact as soon as its upload step is done."""
    import zipfile

    shutil.rmtree(tmp, ignore_errors=True)
    proc = subprocess.run([_gh(), "run", "download", str(run_id), "-n", name, "--dir", str(tmp)], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")
    if archives := list(tmp.rglob("*.tgz")):
        return archives[0], ""
    ids = subprocess.run([_gh(), "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/artifacts", "--jq",
                          f'.artifacts[] | select(.name == "{name}" and (.expired | not)) | .id'], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8").stdout.split()
    if not ids:
        # D-49: an archive whose artifact upload failed is a release of the run (.github/deliver.sh)
        subprocess.run([_gh(), "release", "download", RELEASE_TAG.format(run_id=run_id), "-p",
                        RELEASE_FILES[name], "--dir", str(tmp)], cwd=ROOT, capture_output=True)
        if archives := list(tmp.rglob("*.tgz")):
            return archives[0], ""
        return None, proc.stderr.strip()
    data = subprocess.run([_gh(), "api", f"repos/{{owner}}/{{repo}}/actions/artifacts/{ids[0]}/zip"], cwd=ROOT,
                          capture_output=True).stdout
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(tmp)
    except zipfile.BadZipFile:
        return None, "the artifact download was not a zip"
    archives = list(tmp.rglob("*.tgz"))
    return (archives[0], "") if archives else (None, "no .tgz in the artifact")


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
        rest_ran = produce(sys.argv[2] if len(sys.argv) > 2 else "")
        for row in claude_usage.summary(days=1):  # D-48: what this morning cost of the Claude limit, per step
            log(f"claude usage today: {row['stage']}: {row['calls']} calls, {row['minutes']} min, "
                f"{row['tokens']} tokens, ~${row['cost_usd']}")
        if rest_ran and empty_day():  # D-38: an empty day shows red in GitHub, never "success"
            log("nothing is ready today: exit 1")
            sys.exit(1)
    elif cmd == "publish":
        publish(int(sys.argv[2]))
    elif cmd == "fetch":
        fetch()
    elif cmd == "check":
        check()
    elif cmd == "reserve":
        reserve_cli(sys.argv[2:])
    elif cmd == "failures":  # D-39: the last 7 days per kind (approved / failed / categories) and active rules
        print(json.dumps({"last_7_days": failures.summary(), "paused": [k for k in ("guide", "trial", "tool")
                          if failures.paused(k)], "blocked_hosts": sorted(failures.blocked_hosts())},
                         indent=1, ensure_ascii=False))
    elif cmd == "usage":  # D-48: Claude usage per step, last 7 days (state/claude_usage.jsonl)
        for row in claude_usage.summary():
            print(f"{row['stage']:28} {row['calls']:4} calls {row['minutes']:7} min {row['tokens']:10} tokens "
                  f"~${row['cost_usd']}")
    else:
        status()
