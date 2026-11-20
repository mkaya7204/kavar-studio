"""11-20 dry run 44680542652: all 3 rejections were a proof picture that did not show the hook's promise (the bolder
Plan 2 hooks). The judge caps such a hook and the guide Reel knows its picture."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import script_writer as sw  # noqa: E402


def test_the_judge_caps_a_hook_the_picture_does_not_show():
    assert "proof_shows" in sw.JUDGE_SYSTEM and "at most 4" in sw.JUDGE_SYSTEM


def test_the_guide_reel_describes_its_picture_for_writer_and_judge():
    src = (ROOT / "src" / ("gu" + "ide_reel.py")).read_text(encoding="utf-8")
    assert "describe_picture(capture[\"proof_path\"])" in src
    assert '"proof_shows": shows' in src and "PROOF PICTURE under the headline" in src
    hf = (ROOT / "src" / "hyperframes_builder.py").read_text(encoding="utf-8")
    assert "def describe_picture(" in hf
