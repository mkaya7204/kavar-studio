"""D-89 (user 2026-11-23): what the fixing agent learns must reach the writers. From 11-08 to 11-23 the agent wrote 53
lessons into state/agent_log.jsonl and none reached a prompt."""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import learning  # noqa: E402
import skill_rules  # noqa: E402

# the real 11-23 sessions (state/agent_log.jsonl), shortened
TEASERKIT = {"date": "2026-11-23", "reel": "2026-11-23_teaserkit", "fixed": True,
             "lesson": "A play-button video still or a demo of another product is never proof; prefer the product's own UI card."}
SQUINT = {"date": "2026-11-23", "reel": "2026-11-23_squint", "fixed": True,
          "lesson": "A proof picture must not be a video still with a play button or a carousel with cut-off cards."}


def _setup(tmp_path, monkeypatch, sessions, done=0):
    log = tmp_path / "agent_log.jsonl"
    log.write_text("".join(json.dumps(s) + "\n" for s in sessions), encoding="utf-8")
    monkeypatch.setattr(learning, "AGENT_LOG", log)
    monkeypatch.setattr(learning, "LEARNED", tmp_path / "learned_lessons.md")
    monkeypatch.setattr(learning, "DONE", tmp_path / "learned.json")
    monkeypatch.setattr(skill_rules, "LEARNED", tmp_path / "learned_lessons.md")
    if done:
        (tmp_path / "learned.json").write_text(json.dumps({"agent_log_lines": done}), encoding="utf-8")


def test_a_cause_seen_in_two_reels_becomes_a_rule_the_writers_read(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [TEASERKIT, SQUINT])
    seen = {}

    def ask(prompt):
        seen["prompt"] = prompt
        return [{"title": "Play-button stills are never proof", "what": "teaserkit and squint used video stills.",
                 "rule": "Never use a video still with a play button as proof.",
                 "seen_in": ["2026-11-23_teaserkit", "2026-11-23_squint"]}]

    monkeypatch.setattr(learning, "_ask", ask)
    assert learning.distil(date(2026, 11, 24)) == ["Play-button stills are never proof"]
    assert "NEW 2026-11-23_squint" in seen["prompt"]
    assert "Never use a video still with a play button as proof." in skill_rules.editor_lessons()
    assert learning.recent(2, date(2026, 11, 24)) == ["2026-11-24 - Play-button stills are never proof (learned by the system)"]
    # read once: the next run does not ask again about the same sessions
    monkeypatch.setattr(learning, "_ask", lambda p: (_ for _ in ()).throw(AssertionError("asked again")))
    assert learning.distil(date(2026, 11, 25)) == []


def test_one_reel_invented_reels_and_prices_never_become_rules(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [TEASERKIT, SQUINT])
    monkeypatch.setattr(learning, "_ask", lambda p: [
        {"title": "Only one reel", "what": "x", "rule": "y", "seen_in": ["2026-11-23_squint"]},
        {"title": "Made-up reels", "what": "x", "rule": "y", "seen_in": ["2026-11-01_nothing", "2026-11-02_none"]},
        {"title": "Show the plan", "what": "x", "rule": "Say it costs $20 a month.",
         "seen_in": ["2026-11-23_teaserkit", "2026-11-23_squint"]},
    ])
    assert learning.distil(date(2026, 11, 24)) == []
    assert not (tmp_path / "learned_lessons.md").exists()


def test_no_answer_keeps_the_sessions_for_the_next_run(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [TEASERKIT, SQUINT])
    monkeypatch.setattr(learning, "_ask", lambda p: None)  # usage limit / no CLI
    assert learning.distil(date(2026, 11, 24)) == []
    assert len(learning.pending()) == 2


def test_the_hand_read_log_is_not_read_again_and_the_lessons_reach_every_prompt():
    done = json.loads((ROOT / "state" / "learned.json").read_text(encoding="utf-8"))["agent_log_lines"]
    assert done >= 56  # the 56 sessions to 11-23 were carried into rules/editor_lessons.md by hand
    lessons = skill_rules.editor_lessons()
    for title in ("Choose the picture first, then write the hook", "Pictures that are never proof",
                  "Read every number and word in a picture", "Say only what the source says",
                  "Drop a topic before writing", "Our test image carried an invented price"):
        assert title in lessons  # none fell out of the budget


def test_production_distils_and_yukle_reports_it():
    src = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert "learning.distil(" in src and 'cmd == "learned"' in src
    agent = (ROOT / "src" / "reel_agent.py").read_text(encoding="utf-8")
    assert "learned_lessons.md" in agent
