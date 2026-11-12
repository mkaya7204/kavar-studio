"""D-70 (2026-11-12): the user's decisions of 11-12 can't be dropped silently by a later session.
The user: "bütün bu oturumda aldığımız kararlar ... gerçekten yapılacak mı başka oturumda bunu hiç dikkat etmeden
... kendi kafasına göre yanlış yapmışsın". A promise leaves COMMITMENTS.md only as DONE (with evidence) or with
the user's OK recorded in DECISIONS.md; deleting a line turns these checks red on the next push."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMITMENTS = (ROOT / "COMMITMENTS.md").read_text(encoding="utf-8")

# the user's decisions of 11-12 that are not built yet; each must stay on the list until it is DONE
APPROVED_11_12 = {
    "C": "10-12 s single-point Reel",
    "D": "saveable guide carousel",
    "A": "A için evet",
    "crow sign-off": "crow's sign-off",
    "illustrator": "illustrator to draw the crow",
    "plan": "artifact/8nuzgbgVwnEzCJ1t1cTnMN",
}
STATUSES = ("DONE", "KODDA", "YAPILIYOR", "BAŞLAMADI", "KULLANICIDA", "CEVAP BEKLİYOR")


def test_the_decisions_of_11_12_stay_on_the_promise_list():
    for what, needle in APPROVED_11_12.items():
        assert needle in COMMITMENTS, f"{what} ({needle}) was dropped from COMMITMENTS.md"


def test_every_promise_has_a_known_status():
    rows = [r for r in COMMITMENTS.splitlines() if re.match(r"\| \d+ \|", r)]
    assert len(rows) >= 20
    for r in rows:
        assert any(f"| {s} |" in r for s in STATUSES), r


def test_every_session_starts_with_the_list_and_the_rule():
    # the SessionStart hook in .claude/settings.json needs the user's OK to switch on (a settings change);
    # until then the hook script must exist and print the list
    assert (ROOT / ".claude" / "hooks" / "show_commitments.py").exists()
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Every promise goes into `COMMITMENTS.md`" in claude
    decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    assert "## D-70" in decisions
