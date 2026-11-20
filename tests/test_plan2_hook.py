"""Plan 2 / COMMITMENTS #11 (user-approved 11-12): 76 of 115 Reels opened with the same "result" pattern, and the
11-19 dry run 44533578511 still picked "result" three times out of three. New patterns, at most one "result"
candidate, and a judge that scores surprise first and sees the recent patterns."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import script_writer as sw  # noqa: E402


def test_new_hook_patterns_exist():
    for p in ("risk", "contrast", "number"):
        sw.HookCandidate(pattern=p, headline="x", spoken="y")


def test_the_writer_is_told_to_spread_patterns():
    assert "at least 4 DIFFERENT patterns, at most one of them \"result\"" in sw.SYSTEM_PROMPT


def test_the_judge_scores_surprise_first_and_sees_recent_patterns():
    assert "SURPRISE FIRST" in sw.JUDGE_SYSTEM
    src = Path(sw.__file__).read_text(encoding="utf-8")
    assert "Patterns of the last Reels" in src


def test_the_guide_reel_closing_rotates_too():
    src = (ROOT / "src" / ("gu" + "ide_reel.py")).read_text(encoding="utf-8")
    assert "cta_rule(_load_history())" in src
