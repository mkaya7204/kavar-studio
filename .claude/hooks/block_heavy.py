"""PreToolUse hook: heavy work and waiting never run on this 4 GB PC; they belong in the cloud
(GitHub Actions: produce.yml, rerender.yml). The user asked for this to be enforced, not promised
(2026-10-15). Exit code 2 blocks the command and shows the reason to Claude."""
import json
import re
import sys

BLOCKED = [
    (r"\bff(mpeg|probe)\b", "video processing (ffmpeg)"),
    (r"\bmain\.py\b", "video rendering (main.py)"),
    (r"\btrial_reel\.py\b", "video rendering (trial_reel.py)"),
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
