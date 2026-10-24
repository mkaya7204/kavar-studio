"""D-49 (10-24): a produced day must reach the PC. Run 40057675759 made 3 ready posts (one voiced Reel) and lost
them all: the artifact storage quota was full, both uploads failed, and Save state still marked the day produced.
The same run's fixing agent had every Bash call refused by the PC hook, which calls a Windows path."""

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _steps(name: str) -> list[dict]:
    flow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return next(iter(flow["jobs"].values()))["steps"]


def _index(steps: list[dict], text: str) -> int:
    return next(i for i, s in enumerate(steps) if text in (s.get("run", "") + s.get("uses", "") + s.get("name", "")))


def test_every_workflow_with_claude_drops_the_pc_hook_before_running_anything():
    """The hook config calls C:/Users/... ; on Linux it fails and `onFailure: block` refuses every Bash call."""
    flows = [p.name for p in WORKFLOWS.glob("*.yml") if "@anthropic-ai/claude-code" in p.read_text(encoding="utf-8")]
    assert "produce.yml" in flows and len(flows) >= 4
    for name in flows:
        steps = _steps(name)
        drop = _index(steps, "rm -f .claude/settings.json")
        # the first step that runs project code (the guard's `python3 -c` reads a json file only)
        first_python = min(i for i, s in enumerate(steps) if re.search(r"python3? (-m pytest|\S+\.py)", s.get("run", "")))
        assert drop < first_python, name


def test_the_pc_keeps_its_hook():
    """The cloud removes the hook on the runner only; the repo's file (the PC's guard) stays."""
    settings = (ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "block_heavy.py" in settings and '"onFailure": "block"' in settings


def test_old_archives_are_freed_before_production_uploads():
    flow = yaml.safe_load((WORKFLOWS / "produce.yml").read_text(encoding="utf-8"))
    assert flow["permissions"]["actions"] == "write"
    assert "GH_TOKEN" in flow["jobs"]["produce"]["env"]
    steps = _steps("produce.yml")
    assert _index(steps, "free_artifacts.sh") < _index(steps, "actions/upload-artifact")
    script = (ROOT / ".github" / "free_artifacts.sh").read_text(encoding="utf-8")
    assert "DELETE" in script and "exit 0" in script  # never fails the run


def test_a_failed_upload_goes_to_a_release_and_only_a_delivered_day_counts_as_produced():
    steps = _steps("produce.yml")
    uploads = [s for s in steps if "upload-artifact" in s.get("uses", "")]
    assert len(uploads) == 2
    for up in uploads:
        assert up.get("continue-on-error") is True and up["with"]["if-no-files-found"] == "error"
        release = next(s for s in steps if f"steps.{up['id']}.outcome == 'failure'" in str(s.get("if", "")))
        assert "deliver.sh" in release["run"]
    save = steps[_index(steps, "git add state")]
    assert "steps.up_day.outcome == 'success'" in save["if"] and "steps.rel_day.outcome == 'success'" in save["if"]
    # the runner dropped the PC hook: put back before the rebase, or "You have unstaged changes" loses the state
    assert save["run"].index("git checkout -- .claude/settings.json") < save["run"].index("git pull --rebase")


def test_publishing_workflows_deliver_by_release_when_the_artifact_upload_fails():
    for name in ("produce.yml", "voice.yml", "shrink.yml", "rerender.yml"):
        flow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
        assert flow["permissions"]["contents"] == "write", name
        steps = _steps(name)
        for up in (s for s in steps if "upload-artifact" in s.get("uses", "")):
            assert up.get("continue-on-error") is True, name
            assert any(f"steps.{up['id']}.outcome == 'failure'" in str(s.get("if", "")) and "deliver.sh" in s["run"]
                       for s in steps), name
    check = steps[_index(steps, "Delivery check")]
    assert "exit 1" in check["run"]


def test_fetch_reads_the_release_when_the_artifact_is_missing(monkeypatch, tmp_path):
    import tarfile

    import daily

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[1:3] == ["release", "download"]:
            out = Path(cmd[cmd.index("--dir") + 1])
            out.mkdir(parents=True, exist_ok=True)
            with tarfile.open(out / "kavar-2026-10-24.tgz", "w:gz"):
                pass
        return subprocess.CompletedProcess(cmd, 0, stdout="" if kw.get("text") else b"", stderr="")

    monkeypatch.setattr(daily, "_gh", lambda: "gh")
    monkeypatch.setattr(daily.subprocess, "run", fake_run)
    archive, error = daily._download_archive(40057675759, "kavar-output", tmp_path / "dl")
    assert archive and archive.name == "kavar-2026-10-24.tgz", error
    release = next(c for c in calls if c[1:3] == ["release", "download"])
    assert "out-40057675759" in release and "kavar-*.tgz" in release
    assert daily.RELEASE_FILES["kavar-morning"] == "morning-*.tgz"


def test_deliver_names_the_release_the_way_fetch_reads_it():
    import daily

    script = (ROOT / ".github" / "deliver.sh").read_text(encoding="utf-8")
    assert 'TAG="out-$GITHUB_RUN_ID"' in script and daily.RELEASE_TAG == "out-{run_id}"
    assert "--clobber" in script


def test_release_tags_do_not_start_the_checks():
    flow = yaml.safe_load((WORKFLOWS / "checks.yml").read_text(encoding="utf-8"))
    assert flow[True]["push"]["branches"] == ["**"]  # yaml reads `on:` as True
