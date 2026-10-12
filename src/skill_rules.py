"""Read the RULES section of a project skill (.claude/skills/<name>/SKILL.md).

The Reel prompts (script writer, hook judge, editor review) take their rules from the skills, so
the skill file is the single place to change how Reels are written and reviewed.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"


def skill_rules(name: str) -> str:
    """Text between <!-- RULES:START --> and <!-- RULES:END --> ("" if the skill is missing)."""
    try:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"<!-- RULES:START -->(.*?)<!-- RULES:END -->", text, re.S)
    return m.group(1).strip() if m else ""
