"""User 2026-11-27 ("Bunu öyle sözle falan değil gerçek kodla davranışla yap"): an empty Reel slot takes an approved,
never-posted Reel by itself (src/kept_reels.py). The cases are the real 11-27 ones: the dry run's approved Mika and
opendashboards (kept-reels), the posted openset-llm, an old Shipyard (11-22)."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import daily  # noqa: E402
import kept_reels  # noqa: E402

ASSETS = ["keep-2026-11-22_shipyard.tgz", "keep-2026-11-26_openset-llm.tgz", "keep-2026-11-27_mika.tgz",
          "keep-2026-11-27_opendashboards.tgz", "keep-2026-11-25_astor.tgz", "notes.txt"]


def _state(monkeypatch, tmp_path, used=None):
    monkeypatch.setattr(kept_reels, "USED", tmp_path / "kept_used.json")
    monkeypatch.setattr(kept_reels, "RECENT", tmp_path / "recent.json")
    (tmp_path / "recent.json").write_text(json.dumps([
        {"day": "2026-11-27", "time": "20:30", "kind": "reel", "title": "openset-llm"},
        {"day": "2026-11-28", "time": "18:00", "kind": "carousel", "title": "Mika"}]), encoding="utf-8")
    if used:
        (tmp_path / "kept_used.json").write_text(json.dumps(used), encoding="utf-8")


def test_only_recent_unposted_untaken_kits_newest_first(monkeypatch, tmp_path):
    _state(monkeypatch, tmp_path, {"reels": ["2026-11-25_astor"], "tools": []})
    names = [c["name"] for c in kept_reels.candidates(ASSETS, date(2026, 11, 28))]
    # shipyard too old, openset-llm already queued, astor already taken; a carousel titled Mika is no Reel
    assert names == ["2026-11-27_mika", "2026-11-27_opendashboards"]
    kept_reels.mark_taken("2026-11-27_mika", "mika")
    assert [c["name"] for c in kept_reels.candidates(ASSETS, date(2026, 11, 28))] == ["2026-11-27_opendashboards"]


def test_a_guide_kit_is_known_by_its_tool_data(tmp_path):
    kit = tmp_path / "2026-11-25_figma"
    (kit / "_voice").mkdir(parents=True)
    (kit / "_voice" / "tool.json").write_text(json.dumps({"tool_name": "Figma", "post_url": "https://figma.com/x"}))
    assert kept_reels.is_guide(kit)
    (kit / "_voice" / "tool.json").write_text(json.dumps({"tool_name": "Mika"}))
    assert not kept_reels.is_guide(kit)


def test_an_empty_slot_takes_a_kept_reel_and_a_test_run_never_voices(monkeypatch, tmp_path):
    slots = [{"time": "07:30", "kind": "reel", "concept": "guide"}, {"time": "11:45", "kind": "reel"},
             {"time": "12:30", "kind": "carousel"}, {"time": "18:00", "kind": "carousel", "concept": "guide"},
             {"time": "20:30", "kind": "reel"}]
    kits = {}
    for name, guide in (("2026-11-27_mika", False), ("2026-11-27_opendashboards", False)):
        kit = tmp_path / name
        (kit / "_voice").mkdir(parents=True)
        (kit / "_voice" / "tool.json").write_text(json.dumps({"tool_name": name.split("_")[1]}))
        kits[name] = kit
    monkeypatch.setattr(kept_reels, "_assets", lambda: ["x"])
    monkeypatch.setattr(kept_reels, "candidates", lambda assets: [
        {"asset": f"keep-{n}.tgz", "name": n, "made": "2026-11-27", "tool_slug": n.split("_")[1]} for n in kits])
    monkeypatch.setattr(kept_reels, "download", lambda c: kits[c["name"]])
    voiced = []
    monkeypatch.setattr(kept_reels, "voice", lambda kit: voiced.append(kit) or True)
    logs = []
    monkeypatch.setattr(daily, "log", lambda line: logs.append(line))
    monkeypatch.setenv(daily.DRY_ENV, "1")
    reels = [{"kind": "reel", "folder": "output/reels/2026-11-27_agweb", "title": "Agweb"}]  # 11:45 filled
    morning = daily._fill_from_kept(slots, reels, None)
    assert voiced == [] and morning is None  # D-46: no George in a test run; a tool Reel never takes 07:30
    assert any("kept Reel for the Reel slot: 2026-11-27_mika (test run: not voiced" in line for line in logs)
    assert daily._open_reel_slots(slots, reels, None) == (True, 1)
    src = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert "morning = _fill_from_kept(slots, reels, morning)" in src
