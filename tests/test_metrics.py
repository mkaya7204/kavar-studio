"""The feedback loop (audit 2026-10-16): every published post's numbers, by format."""

import pytest

import post_metrics


def test_rows_merge_and_summarise(monkeypatch, tmp_path):
    monkeypatch.setattr(post_metrics, "PATH", tmp_path / "posts.json")
    post_metrics.add([{"published": "2026-10-15 21:22", "kind": "reel", "reach": 130, "avg_watch_sec": 4}])
    post_metrics.add([{"published": "2026-10-15 21:22", "kind": "reel", "reach": 150, "follows": 1},
                      {"published": "2026-10-15 18:01", "kind": "carousel", "reach": 24}])
    s = post_metrics.summary()
    assert s["reel"] == {"posts": 1, "reach": 150, "avg_watch_sec": 4, "follows": 1}
    assert s["carousel"]["reach"] == 24


@pytest.mark.parametrize("row", [{"published": "x", "kind": "video"}, {"kind": "reel"},
                                 {"published": "x", "kind": "reel", "reach": "130"}])
def test_bad_rows_are_refused(monkeypatch, tmp_path, row):
    monkeypatch.setattr(post_metrics, "PATH", tmp_path / "posts.json")
    with pytest.raises(ValueError):
        post_metrics.add([row])
