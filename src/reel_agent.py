"""KAVAR's own fixing agent for a rejected Reel draft (D-45, the user 2026-10-23: "dar bir kod kalıbının
içine sıkışıp ... kodun dışına çıkamayan birşey istemiyorum"; "benim kendi agent veya bot").

The old fixer (src/reel_fixer.py) gave one answer from a fixed form: new text and picture numbers. The
agent works like a person at the edit desk instead:
  - it reads what went wrong (the editor's problems, the rejected frames) and the knowledge base
    (knowledge/playbook.md: every problem we have seen, its cause and the fix that worked; and the
    editor's lessons),
  - names the cause, and changes whatever removes it: the words (script.json), the pictures, still or
    moving shots, the layout (CSS for this one Reel) (plan.json),
  - renders the draft on the silent voice and LOOKS at the result (src/agent_tools.py render: frames
    every 1.5 s + measurements), and tries again until it is right or it sees the topic can't be fixed.
The brain is a model behind `claude -p` (swappable: only `_run_brain` knows it); the knowledge, the
measurements, the tools and the loop are ours. Hard rules stay in code: no prices (the render refuses
them), never the real voice here, and the editor still decides (daily.py reviews what comes back).

    python src/reel_agent.py <reel folder>     # heavy (render): cloud only; exit 0 fixed, 3 not fixed
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
TEMP_DIR = ROOT / "output" / "temp"
WORK = TEMP_DIR / "agent"
AGENT_LOG = ROOT / "state" / "agent_log.jsonl"  # what the agent did, read by Claude every morning (learning loop)
UNFIXED = 3
# D-47 (user 10-23: "haftalık token yetersiz kalır ... yayın saatinde yayınlamak olan yetişmez"): one short session
SESSION_TIMEOUT = 12 * 60
MAX_TURNS = 30
WORK_REL = "output/temp/agent"
# what the brain may do: read anything, write only its workspace, run only our render tool
ALLOWED_TOOLS = ["Read", "Glob", "Grep", f"Edit({WORK_REL}/**)", f"Write({WORK_REL}/**)",
                 "Bash(python src/agent_tools.py render)", "Bash(python3 src/agent_tools.py render)"]

SYSTEM = f"""You are KAVAR's Reel fixing agent. KAVAR (@thekavar.ai) is a Turkish Instagram page about AI. \
The editor rejected a silent draft Reel. Your job is to make it right, the way a skilled human editor would: \
understand what is wrong and why, change whatever fixes the cause, look at the result, and repeat. You are not \
limited to one kind of change.

Your workspace is {WORK_REL}/ (paths below are inside it):
- playbook.md: our knowledge base, problem -> cause -> right fix -> check. READ IT FIRST. editor_lessons.md too.
- verdict.json: the editor's problems. rejected_frames.jpg: the rejected draft's frames.
- tool.json: the source facts (the only truth for claims). script.json: the Reel's words (EDITABLE).
- candidates.jpg + candidates.json: every picture we have, numbered from 0.
- plan.json (EDITABLE): {{"proof": n, "shots": [n, n], "still": bool, "css": ""}}. proof = the picture under \
the hook (it must prove the hook), shots = the two later full-screen pictures; -1 keeps the current one. \
still = true stops the shot zoom. css = extra CSS for this Reel's 1080x1920 template (ids: #hook, #hook-title, \
#hook-proof, #hook-proof-img, #hook-stamp, #card1-box..#card3-box, #card1-title, #card1-detail, #shot1-cam, \
#shot1-img, #shot1-tag, #shot2-*, #captions, #why-text, #outro-cta, #outro-domain). Keep text out of the top \
270 px and the bottom 35 %; nothing may run off the frame.
- report.json, frames.jpg, draft.mp4: written by the render.

Loop:
1. Read playbook.md, verdict.json, tool.json, script.json; look at rejected_frames.jpg and candidates.jpg.
2. For each problem, name its cause in one sentence (look at the frames, don't guess).
3. Change what removes the cause: rewrite words (keep every field of script.json and its shape; the \
voiceover is voiceover_segments hook, point1, point2, point3, why, cta joined in order, 34-42 words; key_points \
follow point1-3; hook 3-6 words, at most 32 characters), pick other pictures, make shots still, adjust the \
layout with css. A smaller true promise that a picture shows beats a big unproven one.
4. Run exactly: python src/agent_tools.py render   (it refuses prices / broken scripts and says why). Then \
open frames.jpg and look at every frame as a strict editor: cut or overlapping text, a proof that doesn't \
prove the hook, empty boxes, unreadable pictures, claims stronger than tool.json. report.json has the \
measurements (cut_at_seconds must be empty, duration 14-26 s).
5. Repeat 3-4 until clean (at most 3 renders: get it right on the first one if you can).
6. Write result.json: {{"fixed": true|false, "reason": "what was wrong and what you changed", "lesson": \
"one rule for the playbook that would have prevented this, or empty"}}. fixed=true only when your LAST render \
is clean and script.json / plan.json are unchanged since it. fixed=false when the topic itself can't be made \
honest and proven (no picture shows the product working, no AI in it, the source too thin): say why.

Never: prices, currencies, free / paid, trials or discounts in any word or picture; other creators' content; \
claims the source doesn't make; English-only text on screen where Turkish is expected. Write all Reel text in \
natural Turkish (correct İ / ı)."""


def _setup(folder: Path) -> dict:
    """The workspace: the rejected draft's text, verdict, frames, pictures and the knowledge base."""
    from reel_fixer import candidates, sheet
    from voice_final import CAPTURE_PATH

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    capture = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    pictures = candidates(capture)  # copies into output/temp/fix; keep them where the plan can point
    # the agent's picture choices are written into its own folder: the rejected draft's files stay as they were
    if capture.get("proof_path") and Path(capture["proof_path"]).exists():
        (WORK / "pics").mkdir()
        capture["proof_path"] = str(shutil.copy(capture["proof_path"], WORK / "pics" / "proof.png"))
    (WORK / "candidates.json").write_text(json.dumps([str(p) for p in pictures], indent=1), encoding="utf-8")
    if pictures:
        shutil.copy(sheet(pictures), WORK / "candidates.jpg")
    (WORK / "capture_base.json").write_text(json.dumps(capture, indent=2, ensure_ascii=False, default=str),
                                            encoding="utf-8")
    (WORK / "plan.json").write_text(json.dumps({"proof": -1, "shots": [-1, -1], "still": bool(capture.get("still")),
                                                "css": str(capture.get("css") or "")}, indent=1), encoding="utf-8")
    shutil.copy(TEMP_DIR / "script.json", WORK / "script.json")
    shutil.copy(TEMP_DIR / "tool.json", WORK / "tool.json")
    shutil.copy(folder / "_verdict.json", WORK / "verdict.json")
    if (folder / "_review_sheet.jpg").exists():
        shutil.copy(folder / "_review_sheet.jpg", WORK / "rejected_frames.jpg")
    for src, name in ((ROOT / "knowledge" / "playbook.md", "playbook.md"),
                      (ROOT / "rules" / "editor_lessons.md", "editor_lessons.md")):
        if src.exists():
            shutil.copy(src, WORK / name)
    return json.loads((WORK / "verdict.json").read_text(encoding="utf-8"))


def _run_brain(message: str) -> bool:
    """The model behind the agent: Claude Code headless, allowed only to read, edit its workspace and run
    our render tool. Returns whether the session ran."""
    from script_writer import _claude_cli

    exe = _claude_cli()
    if not exe:
        print("✖ no agent brain available (claude CLI missing)")
        return False
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run([exe, "-p", "--output-format", "json", "--system-prompt", SYSTEM,
                               "--allowedTools", ",".join(ALLOWED_TOOLS), "--max-turns", str(MAX_TURNS),
                               "--no-session-persistence"],
                              input=message, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=SESSION_TIMEOUT, cwd=ROOT, env=env)
    except subprocess.TimeoutExpired:
        print(f"✖ agent session timed out after {SESSION_TIMEOUT}s")
        return True  # it may still have left a clean render and a result
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        out = {"raw": (proc.stdout or "")[-3000:], "stderr": (proc.stderr or "")[-2000:]}
    # what the agent said and what it was refused: kept with the Reel (10-23: 14 turns, no render, no word why)
    (WORK / "session.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    denied = out.get("permission_denials") or []
    print(f"   agent session: {out.get('subtype', '?')}, {out.get('num_turns', '?')} turns, "
          f"{len(denied)} refused tool calls")
    for d in denied[:5]:
        print(f"   agent refused: {json.dumps(d, ensure_ascii=False)[:200]}")
    if out.get("result"):
        print(f"   agent said: {str(out['result'])[-400:]}")
    return True


def accepted(work: Path = WORK) -> tuple[bool, str]:
    """The agent's claim checked against the files: a clean last render of exactly the final text and plan."""
    from agent_tools import digest

    try:
        result = json.loads((work / "result.json").read_text(encoding="utf-8"))
        report = json.loads((work / "report.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "no result / no render"
    if not result.get("fixed"):
        return False, str(result.get("reason") or "not fixable")[:400]
    if not report.get("ok"):
        return False, f"its last render was not clean: {report}"[:400]
    if report.get("script_digest") != digest(work / "script.json") or report.get("plan_digest") != digest(work / "plan.json"):
        return False, "script.json / plan.json changed after the last render"
    if not (work / "draft.mp4").exists():
        return False, "no draft"
    return True, str(result.get("reason") or "")[:400]


EVIDENCE = ("session.json", "result.json", "report.json", "plan.json", "frames.jpg", "candidates.jpg", "renders.txt")


def _keep_evidence(folder: Path) -> None:
    """The agent's work goes into the Reel's folder (and so into the day's archive) for the morning review."""
    keep = folder / "_agent"
    keep.mkdir(parents=True, exist_ok=True)
    for name in EVIDENCE:
        if (WORK / name).exists():
            shutil.copy(WORK / name, keep / name)


def main(folder: Path) -> int:
    from distribution import build_post
    from hyperframes_builder import FINAL_PATH
    from reel_qa import pacing_report
    from voice_final import CAPTURE_PATH

    verdict = _setup(folder)
    print(f"   agent: {len(json.loads((WORK / 'candidates.json').read_text()))} pictures, "
          f"{len(verdict.get('problems', []))} problems from the editor")
    message = ("The editor rejected this Reel draft. Make it publishable (or decide honestly that it can't be). "
               f"Start by reading {WORK_REL}/playbook.md and {WORK_REL}/verdict.json.")
    ran = _run_brain(message)
    ok, why = accepted() if ran else (False, "no session")
    _keep_evidence(folder)
    result = {}
    try:
        result = json.loads((WORK / "result.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    AGENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AGENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"date": date.today().isoformat(), "reel": folder.name, "fixed": ok, "why": why,
                             "problems": verdict.get("problems", [])[:4], "lesson": result.get("lesson", ""),
                             "renders": (WORK / "renders.txt").read_text() if (WORK / "renders.txt").exists() else "0"},
                            ensure_ascii=False) + "\n")
    if not ok:
        print(f"✖ agent: not fixed: {why}")
        return UNFIXED
    script = json.loads((WORK / "script.json").read_text(encoding="utf-8"))
    (TEMP_DIR / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy(WORK / "last_capture.json", CAPTURE_PATH)  # the voiced render rebuilds exactly this
    FINAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(WORK / "draft.mp4", FINAL_PATH)
    video = {"duration_sec": pacing_report(FINAL_PATH)["duration_sec"], "video_path": str(FINAL_PATH)}
    post = build_post(script, video)
    (FINAL_PATH.parent / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"   agent fix: {why}")
    if result.get("lesson"):
        print(f"   agent lesson: {str(result['lesson'])[:300]}")
    print(f"✅ agent fixed draft: {FINAL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
