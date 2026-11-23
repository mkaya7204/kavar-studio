"""Read the RULES section of a project skill (.claude/skills/<name>/SKILL.md).

The Reel prompts (script writer, hook judge, editor review) take their rules from the skills, so
the skill file is the single place to change how Reels are written and reviewed.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"


LESSONS = ROOT / "rules" / "editor_lessons.md"
LEARNED = ROOT / "state" / "learned_lessons.md"  # D-89: rules the system wrote from its own repeated fixes
# all lessons must reach the prompts; at 8000 the oldest (the price lesson) fell out on 10-17; 11-23 five lessons from
# 53 agent fixes + the system's own (D-89) -> 30000
LESSONS_MAX_CHARS = 30000


def editor_lessons() -> str:
    """Lessons from content Claude fixed by hand after the editor rejected it (agreed workflow,
    rules/editor_lessons.md), then the ones the system learned itself (D-89, state/learned_lessons.md).
    The editor and the writers read them, so a mistake fixed once is not made, or wrongly rejected,
    again. "" if there are none."""
    entries = []
    for path in (LESSONS, LEARNED):
        try:
            entries += path.read_text(encoding="utf-8").split("\n## ")[1:]  # one "## <date> ..." section per lesson
        except OSError:
            continue
    out = ""
    for e in reversed(entries):  # newest first, until the budget is spent
        if len(out) + len(e) > LESSONS_MAX_CHARS:
            break
        out = f"## {e.strip()}\n\n" + out
    return ("Lessons from earlier posts (each was a real mistake or a wrong rejection, fixed by hand; "
            "apply them):\n\n" + out.strip()) if out else ""


def skill_rules(name: str) -> str:
    """Text between <!-- RULES:START --> and <!-- RULES:END --> ("" if the skill is missing)."""
    try:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"<!-- RULES:START -->(.*?)<!-- RULES:END -->", text, re.S)
    return m.group(1).strip() if m else ""
