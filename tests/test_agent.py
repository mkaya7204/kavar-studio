"""D-45: KAVAR's own fixing agent (src/reel_agent.py + src/agent_tools.py). The brain may change words, pictures
and layout freely; these tests guard what it may never do: show a price, spend the real voice, render without
end, write outside its workspace, or claim a fix its files don't prove."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def work(monkeypatch, tmp_path):
    import agent_tools
    import reel_agent

    w = tmp_path / "agent"
    w.mkdir()
    monkeypatch.setattr(agent_tools, "WORK", w)
    monkeypatch.setattr(reel_agent, "WORK", w)
    (w / "script.json").write_text('{"hook": "h"}', encoding="utf-8")
    (w / "plan.json").write_text('{"proof": -1, "shots": [-1, -1], "still": false, "css": ""}', encoding="utf-8")
    (w / "candidates.json").write_text("[]", encoding="utf-8")
    (w / "capture_base.json").write_text("{}", encoding="utf-8")
    return w


def test_a_price_never_reaches_a_render(monkeypatch, work):
    import agent_tools
    import reel_fixer

    monkeypatch.setattr(reel_fixer, "text_problems", lambda s: ["price words: 50 TL"])
    assert agent_tools.render() == 2
    assert not (work / "renders.txt").exists()  # refused before anything was built


def test_the_agent_never_spends_the_real_voice(monkeypatch, work):
    import os

    import agent_tools
    import reel_fixer
    import tts_engine

    monkeypatch.delenv(tts_engine.DRAFT_ENV, raising=False)
    monkeypatch.setattr(reel_fixer, "text_problems", lambda s: [])
    seen = {}

    def voice(text, **kw):
        seen["draft"] = os.environ.get(tts_engine.DRAFT_ENV)
        raise RuntimeError("stop here")

    monkeypatch.setattr(tts_engine, "reel_voice", voice)
    (work / "script.json").write_text('{"hook": "h", "voiceover": "v"}', encoding="utf-8")
    with pytest.raises(RuntimeError):
        agent_tools.render()
    assert seen["draft"] == "1"


def test_renders_are_limited(work):
    import agent_tools

    (work / "renders.txt").write_text(str(agent_tools.MAX_RENDERS))
    assert agent_tools.render() == 4


def test_a_fix_counts_only_when_the_files_prove_it(work):
    import agent_tools
    import reel_agent

    (work / "draft.mp4").write_bytes(b"v")
    report = {"ok": True, "script_digest": agent_tools.digest(work / "script.json"),
              "plan_digest": agent_tools.digest(work / "plan.json")}
    (work / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (work / "result.json").write_text('{"fixed": true, "reason": "picked the screen that shows the translation"}',
                                      encoding="utf-8")
    assert reel_agent.accepted(work)[0]
    (work / "script.json").write_text('{"hook": "changed after the render"}', encoding="utf-8")
    assert not reel_agent.accepted(work)[0]  # the last render isn't what would go out
    (work / "report.json").write_text(json.dumps({**report, "ok": False}), encoding="utf-8")
    assert not reel_agent.accepted(work)[0]
    (work / "result.json").write_text('{"fixed": false, "reason": "no picture shows the product"}', encoding="utf-8")
    ok, why = reel_agent.accepted(work)
    assert not ok and "no picture" in why


def test_the_brain_writes_only_its_workspace_and_runs_only_the_render():
    import reel_agent

    writes = [t for t in reel_agent.ALLOWED_TOOLS if t.startswith(("Edit", "Write"))]
    assert writes == ["Edit(output/temp/agent/**)", "Write(output/temp/agent/**)"]
    runs = [t for t in reel_agent.ALLOWED_TOOLS if t.startswith("Bash")]
    assert runs == ["Bash(python src/agent_tools.py render)", "Bash(python3 src/agent_tools.py render)"]
    assert set(reel_agent.ALLOWED_TOOLS) - set(writes) - set(runs) == {"Read", "Glob", "Grep"}  # looking only
    assert "playbook.md" in reel_agent.SYSTEM and "prices" in reel_agent.SYSTEM


def test_the_agents_work_is_kept_with_the_reel(work, tmp_path):
    """10-23 first cloud run: 14 turns, no render, and nothing showed why. Its session and files now stay."""
    import reel_agent

    (work / "session.json").write_text('{"permission_denials": [{"tool_name": "Bash"}]}', encoding="utf-8")
    (work / "report.json").write_text("{}", encoding="utf-8")
    reel = tmp_path / "reel"
    reel_agent._keep_evidence(reel)
    assert (reel / "_agent" / "session.json").exists() and (reel / "_agent" / "plan.json").exists()


def test_the_agents_css_is_styles_only():
    from hyperframes_builder import with_agent_css

    page = with_agent_css("<html><head></head><body></body></html>",
                          "#hook-proof { top: 900px }</style><script>alert(1)</script>")
    assert '<style id="agent-css">' in page and "#hook-proof { top: 900px }" in page
    assert "<script" not in page and page.count("</style>") == 1


def test_daily_sends_a_rejected_draft_to_the_agent():
    import inspect

    import daily

    assert '"src/reel_agent.py"' in inspect.getsource(daily._fix_draft)
    assert daily.REEL_FIX_ROUNDS == 1
