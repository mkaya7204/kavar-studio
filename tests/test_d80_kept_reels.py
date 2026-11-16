"""D-80 / COMMITMENTS #27 (user 11-15 "Evet"): approved Reels never vanish when a run's archive expires.

11-14: the reserve's Skillbox and ElevenLabs Reels could no longer be voiced because run 43158731682's archive
had expired (#20). Every produced Reel's silent kit now also goes to the release kept-reels, and voice.yml takes it
from there when the run's archive is gone."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"


def test_production_and_dry_runs_keep_every_reels_silent_kit_for_good():
    produce = (WF / "produce.yml").read_text(encoding="utf-8")
    assert "bash .github/keep_reels.sh" in produce
    step = produce[produce.index("Keep the Reels' silent parts for good"):]
    step = step[:step.index("- uses:")]
    assert "always()" in step and "continue-on-error: true" in step  # a failed copy never costs the day
    assert "dry" not in step  # dry runs too: their approved Reels are the reserve's source


def test_keep_script_copies_the_voice_kit_without_videos_to_a_release_that_never_expires():
    script = (ROOT / ".github" / "keep_reels.sh").read_text(encoding="utf-8")
    assert 'TAG="kept-reels"' in script
    assert "_voice/capture.json" in script
    assert "--exclude='*.mp4'" in script
    assert "gh release upload" in script and "--clobber" in script


def test_voice_run_falls_back_to_the_kept_copy_when_the_archive_expired():
    voice = (WF / "voice.yml").read_text(encoding="utf-8")
    assert "gh release download kept-reels" in voice
    assert voice.index("gh run download") < voice.index("gh release download kept-reels")
    assert 'test -f "output/reels/$R/_voice/capture.json"' in voice
