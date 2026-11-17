"""D-71 (2026-11-12, the user): "C olsun onay veriyorum bunu da takip et, yeni hangi reel olduğunu bil, takip etmesi
kolay olsun, bakalım tutacak mı". 1 of the day's Reels is a KISA Reel: 10-12 s with ONE point, marked "kisa" from
the script to the queue, the reports and the metrics, so it can be compared after a week."""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import hyperframes_builder as hb  # noqa: E402
import script_writer as sw  # noqa: E402

TEMPLATE = ROOT / "templates" / "hyperframes_news"


def _script(short: bool) -> dict:
    point = {"title": "Toplantı notu kendiliğinden", "detail": "Görüşmeye bot girmeden not çıkarır."}
    seg = {"hook": "Toplantıya bot sokmadan not al.", "point1": "Adı Yogurt, bilgisayarında çalışan bir not uygulaması.",
           "point2": "" if short else "Konuşmayı yazıya döker.", "point3": "" if short else "Özet çıkarır.",
           "why": "" if short else "Not tutmakla uğraşmazsın.", "cta": "Ekibine gönder."}
    return {"hook": "Botsuz toplantı notu", "voiceover": "", "voiceover_segments": seg,
            "shots": [{"start_sec": 0, "end_sec": 5, "type": "screenshot", "direction": "x", "on_screen_text": ""},
                      {"start_sec": 5, "end_sec": 10, "type": "screenshot", "direction": "y", "on_screen_text": ""}],
            "key_points": [point] if short else [point] * 3, "why_it_matters": "" if short else "Zaman kazanırsın.",
            "caption": "Toplantı notunu bilgisayarında tutan uygulama. Kime gönderirsin?",
            "hashtags": ["#yapayzeka", "#aitools", "#yogurt"], "tool_name": "Yogurt",
            "website_url": "https://www.yogurt.so/", "source": "claude_code", **({"variant": "kisa"} if short else {})}


def test_a_kisa_script_has_one_point_and_a_normal_one_three(monkeypatch):
    monkeypatch.delenv(sw.SHORT_ENV, raising=False)
    assert sw.VideoScript.model_validate(_script(True)).variant == "kisa"
    assert sw.VideoScript.model_validate(_script(False)).variant == ""
    with pytest.raises(ValidationError):  # a normal Reel still needs 3 points
        sw.VideoScript.model_validate({**_script(False), "key_points": _script(True)["key_points"]})
    bad = _script(True)
    bad["voiceover_segments"]["point2"] = "İkinci bir nokta."
    with pytest.raises(ValidationError):  # one point means one point
        sw.VideoScript.model_validate(bad)


def test_the_short_env_makes_the_writer_ask_for_a_kisa_reel(monkeypatch):
    monkeypatch.setenv(sw.SHORT_ENV, "1")
    data = _script(True)
    data.pop("variant")
    assert sw.VideoScript.model_validate(data).variant == "kisa"
    tool = sw.Tool(tool_name="Yogurt", tag_line="Toplantı notu", website_url="https://www.yogurt.so/", description="Toplantı notu")
    msg = sw._user_message(tool, "tr")
    assert "KISA Reel" in msg and f"{sw.SHORT_WORDS[0]}-{sw.SHORT_WORDS[1]} words" in msg
    monkeypatch.delenv(sw.SHORT_ENV)
    assert "KISA Reel" not in sw._user_message(tool, "tr")


def _words(parts: list[str], per_word: float = 0.45) -> list[dict]:
    out, t = [], 0.0
    for part in parts:
        for w in part.split():
            out.append({"word": w, "start": round(t, 3), "end": round(t + per_word - 0.05, 3)})
            t += per_word
        t += 0.2
    return out


def test_the_kisa_plan_is_hook_card_shot_outro_and_lasts_10_to_12_s(tmp_path):
    seg = _script(True)["voiceover_segments"]
    segments = [seg[k] for k in ("hook", "point1", "point2", "point3", "why", "cta")]
    words = _words([seg["hook"], seg["point1"], seg["cta"]])  # 15 words, ~7 s of voice
    timing = hb.plan_short(segments, words)
    plan, total = hb.with_signoff(timing["plan"], timing["total"])
    assert 9.5 <= total <= sw.SHORT_SECONDS[1], total
    assert sw.SHORT_SECONDS[0] <= total
    seen = [n for n in hb.SCENES if plan[n][0] < plan["signoff"][0]]
    assert seen == ["hook", "card1", "shot1", "outro"]
    assert plan["outro"][1] >= hb.OUTRO_MIN
    assert all(t < plan["signoff"][0] + hb.SIGNOFF for t, _ in hb.sfx_events(plan))  # unused scenes stay silent
    shutil.copy(TEMPLATE / "index.html", tmp_path / "index.html")
    hb._apply_plan_to_html(tmp_path / "index.html", plan, total)  # every scene still has its slot
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<div\s+id="root"[^>]*data-duration="' + f"{total:g}", html)
    caps = hb.caption_groups(words, timing["owner"], timing["pauses"], (0, 2))
    assert caps and all(c["s"] < plan["outro"][0] for c in caps)  # captions only under point1


def test_a_normal_reel_keeps_its_plan_and_sounds():
    plan, _ = hb.with_signoff(dict(hb.DEFAULT_PLAN), hb.TOTAL)  # signoff starts where the outro ends
    kinds = [k for _, k in hb.sfx_events(plan)]
    assert kinds.count("whoosh") == len(hb.SCENES) - 1 and kinds.count("pop") == 4 + 1


def test_the_length_checks_know_the_kisa_reel():
    assert sw.reel_seconds("kisa") == sw.SHORT_SECONDS and sw.reel_seconds("") == (14.0, 27.6)
    daily = (ROOT / "daily.py").read_text(encoding="utf-8")
    assert "low, high = reel_seconds(_script_variant(out))" in daily
    assert "produce_reel(short=short)" in daily and "len(reels) == wanted - 1" in daily
    assert 'return {"variant": script["variant"]}' in daily
    for f in ("src/agent_tools.py", "src/voice_kept.py"):
        assert "reel_seconds(" in (ROOT / f).read_text(encoding="utf-8"), f
    assert json.loads((ROOT / "schedule.json").read_text(encoding="utf-8"))["short_reel"] is True
    editor = (ROOT / "src" / "editor_review.py").read_text(encoding="utf-8")
    assert "never reject it for being short" in editor
