"""Invariant tests: the user's locked decisions (CLAUDE.md §1) as code.

Offline: no network, no Claude, no renders. A failing test means a locked decision broke;
fix the code, not the test, unless the user changed the decision.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
os.environ["SCRIPT_WRITER_NO_CLI"] = "1"  # never reach Claude from a test
os.environ.pop("ANTHROPIC_API_KEY", None)

import json  # noqa: E402

import pytest  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _ledger_in_tmp(monkeypatch, tmp_path):
    """D-39: tests never write the real failure ledger (state/failures.json, state/self_correct.json)."""
    import failures

    monkeypatch.setattr(failures, "LEDGER", tmp_path / "_ledger" / "failures.json")
    monkeypatch.setattr(failures, "ACTIONS", tmp_path / "_ledger" / "self_correct.json")
    import claude_usage  # D-48: nor the real usage log

    monkeypatch.setattr(claude_usage, "LOG", tmp_path / "_ledger" / "claude_usage.jsonl")
    # D-74/D-75/D-76: no news channel or Show HN request, and no write to the real record of recent posts
    import discovery
    import fetcher
    import recent_posts

    monkeypatch.setattr(discovery, "channels", lambda: [])
    monkeypatch.setattr(fetcher, "HN_TOOLS", 0)
    monkeypatch.setattr(recent_posts, "PATH", tmp_path / "_ledger" / "recent_posts.json")
    monkeypatch.setattr(recent_posts, "QUEUE_DIR", tmp_path / "_ledger" / "queue")


@pytest.fixture
def news_script() -> dict:
    """A real news carousel that passed the editor (FLUX.3 "Biz denedik", 2026-10-16)."""
    return json.loads((FIXTURES / "news_carousel.json").read_text(encoding="utf-8"))


@pytest.fixture
def trial_article() -> dict:
    """Its article.json: two of our test outputs, the second one is the cover."""
    return json.loads((FIXTURES / "trial_article.json").read_text(encoding="utf-8"))
