"""The fixing agent's hands and eyes (D-45, src/reel_agent.py). The agent edits two files in its workspace
(output/temp/agent): script.json (the Reel's words) and plan.json (which pictures, still or moving, extra
CSS for the layout), then runs

    python src/agent_tools.py render      # heavy (render): cloud only

which builds the draft on the SILENT voice (George is never spent here, D-30), measures it and writes
frames.jpg (what the viewer sees, every ~1.5 s) and report.json. The hard rules are checked here, in code,
whatever the agent wrote: no prices or broken script rules (the render is refused), at most MAX_RENDERS.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
WORK = ROOT / "output" / "temp" / "agent"
MAX_RENDERS = 4
REEL_SECONDS = (14.0, 26.0)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def plan_capture(base: dict, plan: dict, pictures: list[Path]) -> dict:
    """The capture the builder renders: the chosen pictures (whole, never cropped), still, css."""
    from reel_fixer import apply_pictures

    capture = apply_pictures(dict(base), pictures, int(plan.get("proof", -1)), [int(i) for i in plan.get("shots", [-1, -1])][:2])
    capture["still"] = bool(plan.get("still"))
    capture["css"] = str(plan.get("css") or "")[:4000]
    return capture


def render() -> int:
    from editor_review import contact_sheet, video_frames
    from hyperframes_builder import build_video_hyperframes
    from reel_fixer import text_problems
    from reel_qa import cut_frames, first_frame_report, pacing_report
    from script_writer import _load_language
    from tts_engine import DRAFT_ENV, reel_voice, voice_for

    os.environ[DRAFT_ENV] = "1"  # the agent never spends the real voice
    count = WORK / "renders.txt"
    done = int(count.read_text() or 0) if count.exists() else 0
    if done >= MAX_RENDERS:
        print(json.dumps({"ok": False, "error": f"render limit reached ({MAX_RENDERS}); write result.json now"}))
        return 4
    script = json.loads((WORK / "script.json").read_text(encoding="utf-8"))
    if problems := text_problems(script):
        print(json.dumps({"ok": False, "script_problems": problems}, ensure_ascii=False))
        return 2
    plan = json.loads((WORK / "plan.json").read_text(encoding="utf-8"))
    pictures = [Path(p) for p in json.loads((WORK / "candidates.json").read_text(encoding="utf-8"))]
    base = json.loads((WORK / "capture_base.json").read_text(encoding="utf-8"))
    capture = plan_capture(base, plan, pictures)
    count.write_text(str(done + 1))
    voice = reel_voice(script["voiceover"], voice=voice_for(_load_language()))
    draft = WORK / "draft.mp4"
    build_video_hyperframes(script, capture, voice["audio_path"], draft)
    cut = cut_frames(draft, WORK)
    first = first_frame_report(draft, WORK)
    pace = pacing_report(draft)
    dur = pace["duration_sec"]
    times = [round(t * 1.5, 1) for t in range(int(dur / 1.5) + 1)]
    contact_sheet(video_frames(draft, WORK, times), WORK / "frames.jpg", cols=8, w=240)
    (WORK / "last_capture.json").write_text(json.dumps(capture, indent=2, ensure_ascii=False, default=str),
                                            encoding="utf-8")
    report = {"ok": not cut and first["ok"] and REEL_SECONDS[0] <= dur <= REEL_SECONDS[1],
              "render": done + 1, "renders_left": MAX_RENDERS - done - 1,
              "cut_at_seconds": cut[:10], "first_frame_ok": first["ok"], "duration_sec": dur,
              "longest_static_sec": pace["longest_static_sec"],
              "frames": f"frames.jpg (every 1.5 s from 0: {'/'.join(f'{t:g}' for t in times)})",
              "script_digest": digest(WORK / "script.json"), "plan_digest": digest(WORK / "plan.json")}
    (WORK / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["render"]:
        sys.exit(render())
    print("usage: python src/agent_tools.py render")
    sys.exit(1)
