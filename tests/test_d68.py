"""D-68 (2026-11-12, the user approved the audit's open points):
- the tool-site search asked Claude again for every Product Hunt product in every run (212 searches in 8 days,
  38 % of the cloud's Claude spend): a found site is remembered;
- voice.yml could not learn a new name (runs 42859526056, 43164086698 stopped on "no pronunciation for ...");
- a metrics row keeps its post's folder, so a Reel's numbers can be joined to its hook (state/metrics/reels.json)."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import fetcher  # noqa: E402
import post_metrics  # noqa: E402


def test_a_product_site_is_searched_once(monkeypatch, tmp_path):
    monkeypatch.setattr(fetcher, "SITES_PATH", tmp_path / "tool_sites.json")
    calls = []

    def search(name, tag_line):
        calls.append(name)
        return ("https://scroogefrog.com/", "Ad fraud protection") if name == "ScroogeFrog AI" else None

    monkeypatch.setattr(fetcher, "_find_site_with_claude", search)
    for _ in range(3):  # three runs of one day list the same products
        assert fetcher._find_site("ScroogeFrog AI", "x") == ("https://scroogefrog.com/", "Ad fraud protection")
        assert fetcher._find_site("Nobody Knows", "x") is None
    assert calls == ["ScroogeFrog AI", "Nobody Knows"]


def test_a_site_that_was_not_found_is_asked_again_after_three_days(monkeypatch, tmp_path):
    path = tmp_path / "tool_sites.json"
    old = (date.today() - timedelta(days=fetcher.SITE_MISS_DAYS)).isoformat()
    path.write_text(json.dumps({"nobodyknows": {"url": "", "description": None, "date": old}}), encoding="utf-8")
    monkeypatch.setattr(fetcher, "SITES_PATH", path)
    monkeypatch.setattr(fetcher, "_find_site_with_claude", lambda n, t: ("https://nobody.ai/", None))
    assert fetcher._find_site("Nobody Knows", "x") == ("https://nobody.ai/", None)


def test_voice_yml_can_learn_a_name():
    wf = (ROOT / ".github" / "workflows" / "voice.yml").read_text(encoding="utf-8")
    assert "CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in wf
    assert "npm install -g @anthropic-ai/claude-code@" in wf
    assert wf.index("rm -f .claude/settings.json") < wf.index("voice_kept.py")  # D-49: the PC's hook is not loaded
    assert wf.index("git checkout -- .claude/settings.json") < wf.index("git add state/used_tools.json")
    assert "state/pronunciations.json" in wf  # a learned name is kept


def test_a_metrics_row_keeps_its_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(post_metrics, "PATH", tmp_path / "posts.json")
    post_metrics.add([{"published": "2026-11-13 20:30", "kind": "reel", "title": "ScroogeFrog AI", "reach": 1,
                       "folder": "2026-11-12_scroogefrog-ai"}])
    post_metrics.add([{"published": "2026-11-13 20:30", "kind": "reel", "reach": 150}])
    row = post_metrics.load()[0]
    assert row["folder"] == "2026-11-12_scroogefrog-ai" and row["reach"] == 150
