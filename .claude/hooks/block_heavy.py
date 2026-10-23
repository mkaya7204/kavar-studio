"""PreToolUse hook: heavy work and waiting never run on this 4 GB PC; they belong in the cloud
(GitHub Actions: produce.yml, rerender.yml). The user asked for this to be enforced, not promised
(2026-10-15). Exit code 2 blocks the command and shows the reason to Claude."""
import json
import os
import re
import sys

# The cloud is where this work belongs: the fixing agent's `claude -p` session in GitHub Actions loads the same
# project hooks, and this guard refused its render (10-23, D-45: "agent refused ... agent_tools.py render").
if os.getenv("GITHUB_ACTIONS") == "true":
    sys.exit(0)

BLOCKED = [
    (r"\bff(mpeg|probe)\b", "video processing (ffmpeg)"),
    (r"\bmain\.py\b", "video rendering (main.py)"),
    (r"\btrial_reel\.py\b", "video rendering (trial_reel.py)"),
    (r"\btr_reel\.py\b", "video rendering (tr_reel.py)"),
    (r"\bguide_reel\.py\b", "video rendering (guide_reel.py)"),
    (r"\bvoice_final\.py\b", "voiced Reel render (voice_final.py)"),
    (r"\breel_fixer\.py\b", "fixed Reel render (reel_fixer.py)"),
    (r"\breel_agent\.py\b", "fixing agent with Reel renders (reel_agent.py)"),
    (r"\bagent_tools\.py\W+render\b", "agent draft render (agent_tools.py render)"),
    (r"\bcarousel\.py\b", "carousel capture and render (carousel.py)"),
    (r"daily\.py\W+produce\b", "production (daily.py produce)"),
    (r"hyperframes\S*\s+render\b", "HyperFrames render"),
    (r"\brun\s+watch\b", "waiting on a cloud run (gh run watch)"),
    (r"\bStart-Sleep\b|(^|[;&|\s])sleep\s+\d", "waiting / sleep loop"),
    (r"while\s*\(\s*\$true\s*\)|while\s+true\b|\buntil\b.*\bdo\b", "polling loop"),
]

command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
for pattern, what in BLOCKED:
    if re.search(pattern, command, re.IGNORECASE):
        print(f"BLOCKED on this PC: {what}. Heavy work and waiting run in the cloud: start it with "
              f"`gh workflow run produce.yml` or `rerender.yml`, check once with `gh run view`, then "
              f"download only the result. (rule: memory/cloud-first-rule.md)", file=sys.stderr)
        sys.exit(2)
