"""D-89 (user 2026-11-23: "bunu sistemine de öğretip o da öğrensin, aynı şeylerle karşılaştığında o da yapabilsin"):
the system learns from its own fixes.

Every fixing-agent session writes one "lesson" line to state/agent_log.jsonl (D-45). Until 11-23 Claude was meant to
carry them into the rules by hand every morning; from 11-08 to 11-23 none were carried (53 lessons written, the
writers never saw them). Now, at the end of every production run, one Claude call reads the new agent lessons
against the lessons the writers already have and writes a rule only for a cause seen in at least two Reels that no
lesson covers yet. The rule goes to state/learned_lessons.md (committed with the run's state), which
skill_rules.editor_lessons() feeds to the writers, the editor, the fixer and the agent next to rules/editor_lessons.md.
Claude reports the new ones at every "yükle" (`python daily.py learned`).

    python src/learning.py            # distil now (one Claude call, no tools; light)
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
AGENT_LOG = ROOT / "state" / "agent_log.jsonl"
LEARNED = ROOT / "state" / "learned_lessons.md"
DONE = ROOT / "state" / "learned.json"  # how many agent_log lines were already read
MIN_REELS = 2  # a cause seen once is a story; seen in two Reels it is a rule
MAX_NEW = 3  # per run
CONTEXT = 40  # earlier agent sessions shown with the new ones, so a new case can pair with an old one
TIMEOUT = 240
HEADER = ("# Learned lessons (written by the system, D-89)\n\n"
          "Rules the system wrote itself from its fixing agent's repeated fixes (src/learning.py). The writers, the\n"
          "editor, the fixer and the agent read them with rules/editor_lessons.md. Claude reports new ones at every\n"
          "\"yükle\"; a wrong one is marked withdrawn there with the reason, never silently deleted.\n")
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["lessons"],
    "properties": {"lessons": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["title", "what", "rule", "seen_in"],
        "properties": {"title": {"type": "string"}, "what": {"type": "string"}, "rule": {"type": "string"},
                       "seen_in": {"type": "array", "items": {"type": "string"}}}}}},
}
PROMPT = """You keep the rules of KAVAR, an automatic Instagram page that makes Turkish AI Reels and carousels. When \
the editor rejects a Reel, a fixing agent repairs it and writes down what it learned. Your job: turn REPEATED \
fixes into rules the writers follow BEFORE writing, so the same mistake is not made again.

Rules the writers already have:
<existing>
{existing}
</existing>

Fixing-agent sessions (reel = folder name; NEW = not read before):
<sessions>
{sessions}
</sessions>

Write a new rule only when ALL hold:
- the same cause appears in at least {min_reels} different reels in the sessions, and at least one of them is NEW;
- no existing rule already says it (a rule that exists but keeps being broken is NOT new: skip it);
- it is something a writer, the editor or the picture chooser can do before or while writing (not a code bug).
Never write a rule that touches the locked decisions: no prices ever, George voice only, only the editor's \
"publish" goes out, only our own or the companies' own pictures, the outro and the crow sign-off stay. Never invent: \
use only what the sessions say. At most {max_new} rules; an empty list is the usual, right answer.
Each rule: title (under 70 characters, English), what (one sentence: what happened, naming the reels), rule (one or \
two sentences the writers must follow, English), seen_in (the reel folder names, exactly as given)."""


def _sessions() -> list[dict]:
    try:
        lines = AGENT_LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({})  # keep the line count right
    return out


def _done() -> int:
    try:
        return int(json.loads(DONE.read_text(encoding="utf-8")).get("agent_log_lines", 0))
    except (OSError, ValueError, AttributeError):
        return 0


def pending() -> list[dict]:
    """Agent sessions with a lesson that were not read yet."""
    return [s for s in _sessions()[_done():] if s.get("lesson")]


def valid(lessons: list[dict], known: set[str], new: set[str], existing: str) -> list[dict]:
    """Keep what the rules above say, checked in code: two real reels (one new), no prices, short, not a repeat."""
    from script_writer import price_mentions

    out = []
    for les in lessons:
        title, what, rule = (str(les.get(k, "")).strip() for k in ("title", "what", "rule"))
        reels = sorted({r for r in les.get("seen_in", []) if r in known})
        if len(reels) < MIN_REELS or not set(reels) & new:
            continue
        if not title or not rule or len(title) > 90 or len(rule) > 600 or len(what) > 600:
            continue
        if price_mentions(" ".join((title, what, rule))):
            continue  # §1.1, also in a rule's wording
        if title.lower() in existing.lower():
            continue
        out.append({"title": title, "what": what, "rule": rule, "seen_in": reels})
    return out[:MAX_NEW]


def write(lessons: list[dict], today: date) -> None:
    text = LEARNED.read_text(encoding="utf-8") if LEARNED.exists() else HEADER
    for les in lessons:
        text += (f"\n## {today.isoformat()} - {les['title']} (learned by the system)\n"
                 f"- **What happened:** {les['what']} (seen in: {', '.join(les['seen_in'])})\n"
                 f"- **Rule:** {les['rule']}\n")
    LEARNED.write_text(text, encoding="utf-8")


def _ask(prompt: str) -> list[dict] | None:
    from claude_usage import record as record_usage
    from script_writer import _claude_cli

    exe = _claude_cli()
    if not exe:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run([exe, "-p", "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
                               "--tools", "", "--no-session-persistence"],
                              input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT, env=env)
        record_usage("learning", proc.stdout)
        return (json.loads(proc.stdout).get("structured_output") or {}).get("lessons") or []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def distil(today: date | None = None) -> list[str]:
    """Read the new agent lessons, write the repeated ones as rules. Returns the new rules' titles."""
    from skill_rules import editor_lessons

    today = today or date.today()
    sessions = _sessions()
    start = _done()
    new = [s for s in sessions[start:] if s.get("lesson")]
    if not new:
        return []
    shown = [s for s in sessions[:start] if s.get("lesson")][-CONTEXT:] + new
    known = {s.get("reel", "") for s in shown} - {""}
    new_reels = {s.get("reel", "") for s in new} - {""}
    lines = [f"- {'NEW ' if s in new else ''}{s.get('reel')} ({'fixed' if s.get('fixed') else 'not fixed'}): "
             f"{s['lesson'][:400]}" for s in shown]
    existing = editor_lessons()
    answer = _ask(PROMPT.format(existing=existing, sessions="\n".join(lines), min_reels=MIN_REELS, max_new=MAX_NEW))
    if answer is None:
        return []  # no answer (usage limit, no CLI): read them again next run
    kept = valid(answer, known, new_reels, existing)
    if kept:
        write(kept, today)
    DONE.write_text(json.dumps({"agent_log_lines": len(sessions), "date": today.isoformat()}), encoding="utf-8")
    return [k["title"] for k in kept]


def recent(days: int = 2, today: date | None = None) -> list[str]:
    """The learned rules written in the last `days` days ("## <date> - <title>" lines), for the "yükle" report."""
    today = today or date.today()
    try:
        text = LEARNED.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        if line.startswith("## ") and " - " in line:
            try:
                when = date.fromisoformat(line[3:13])
            except ValueError:
                continue
            if (today - when).days < days:
                out.append(line[3:])
    return out


if __name__ == "__main__":
    for t in distil():
        print("learned:", t)
