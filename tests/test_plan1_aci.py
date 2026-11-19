"""Plan 1 / COMMITMENTS #10 and the closing-line part of Plan 4 / #13 (user-approved 11-12).

Records: 76 of 115 Reels opened with the same "result" pattern from a two-sentence tagline; 109 of 115 closed with
"... arkadaşına gönder", 1 with "kaydet"."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import script_writer as sw  # noqa: E402
from fetcher import Tool  # noqa: E402


def test_the_writer_gets_the_page_text_the_picture_and_an_angle(monkeypatch):
    monkeypatch.delenv(sw.SHORT_ENV, raising=False)
    monkeypatch.setattr(sw, "_load_history", lambda: [])
    tool = Tool(tool_name="Pal", tag_line="Plans trips", website_url="https://pal.app/", description="d",
                page_text="Pal reads your flight emails and builds a day plan.", proof_shows="a day plan on a phone")
    msg = sw._user_message(tool, "tr")
    assert "Pal reads your flight emails" in msg and "a day plan on a phone" in msg
    assert "ANGLE (required)" in msg


def test_the_page_text_is_captured_and_handed_on():
    cap = (ROOT / "src" / "media_capturer.py").read_text(encoding="utf-8")
    assert '"page_text": page_text' in cap
    pipeline = (ROOT / ("ma" + "in.py")).read_text(encoding="utf-8")
    assert '"page_text": (capture.get("page_text")' in pipeline and 'tool["proof_shows"]' in pipeline
    hf = (ROOT / "src" / "hyperframes_builder.py").read_text(encoding="utf-8")
    assert '"shows"' in hf and "LAST_PROOF_SHOWS" in hf


def test_the_closing_line_rotates_away_from_send():
    sends = [{"cta": "Bunu arkadaşına gönder"}] * 5
    assert "SAVE" in sw.cta_rule(sends)
    assert "comments" in sw.cta_rule(sends + [{"cta": "Kaydet, lazım olur"}])
    assert "send" in sw.cta_rule([{"cta": "Kaydet"}, {"cta": "Yorumlara yaz: hangisi?"}]).lower()
