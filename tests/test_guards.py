"""§0 cloud-first hook, §1.3 editor lessons, and the workflows' safety steps."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "block_heavy.py"


def _hook(command: str) -> int:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(HOOK)], input=payload, text=True, capture_output=True).returncode


@pytest.mark.parametrize("cmd", ["ffmpeg -i a.mp4 b.mp4", "ffprobe x", "python main.py", "python daily.py produce",
                                 "python src/trial_reel.py output/carousel/x", "python carousel.py --news",
                                 "npx hyperframes@0.8.145 render .", "gh run watch 1", "Start-Sleep 5", "sleep 10",
                                 "while true; do x; done", "while ($true) { x }"])
def test_heavy_or_waiting_commands_are_blocked_on_the_pc(cmd):
    assert _hook(cmd) == 2


@pytest.mark.parametrize("cmd", ["pytest -q", "python daily.py status", "gh run view 1", "git status"])
def test_light_commands_pass(cmd):
    assert _hook(cmd) == 0


def test_editor_lessons_reach_the_editor_and_the_writers():
    import editor_review
    import news_writer
    import script_writer
    from skill_rules import editor_lessons

    lessons = editor_lessons()
    assert "Our test image carried an invented price" in lessons
    for prompt in (editor_review.SYSTEM, news_writer.SYSTEM_PROMPT, script_writer.SYSTEM_PROMPT):
        assert lessons in prompt


def _wf(name):
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def test_production_has_three_tries_and_a_guard():
    wf = _wf("produce.yml")
    assert len(wf[True]["schedule"]) == 3  # yaml reads "on" as True
    steps = wf["jobs"]["produce"]["steps"]
    assert "'main'" in steps[0]["with"]["ref"] and "schedule" in steps[0]["with"]["ref"]
    assert steps[1]["id"] == "guard"
    produce = next(s for s in steps if s.get("name", "").startswith("Produce"))
    assert "steps.guard.outputs.skip" in produce["if"]


def test_cron_job_org_start_is_guarded():
    """D-25: cron-job.org dispatches with auto=yes; that run must skip a produced day, not force one."""
    wf = _wf("produce.yml")
    assert wf[True]["workflow_dispatch"]["inputs"]["auto"]["default"] == "no"
    guard = wf["jobs"]["produce"]["steps"][1]["run"]
    assert 'github.event.inputs.auto }}" = "yes"' in guard
    assert "inputs.auto != 'yes'" in wf["jobs"]["produce"]["env"]["KAVAR_FORCE"]


@pytest.mark.parametrize("name", ["produce.yml", "news-test.yml"])
def test_claude_cli_is_verified_after_install(name):
    text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    assert "for i in 1 2 3" in text and "claude --version && break" in text


def test_production_gets_the_secrets():
    env = _wf("produce.yml")["jobs"]["produce"]["env"]
    for key in ("CLAUDE_CODE_OAUTH_TOKEN", "ELEVENLABS_API_KEY", "OPENROUTER_API_KEY", "HF_TOKEN"):
        assert env[key] == "${{ secrets.%s }}" % key


def test_project_rules_file_lists_the_locked_decisions():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for needle in ("No prices, ever", "Editor gate", "Rejected content", "Biz denedik", "George", "TAKİP ET"):
        assert needle in text, needle
