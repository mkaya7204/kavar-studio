"""D-65 (user 2026-11-09: "testleri ve reelleri ses kredisini kullanmadan yapmaya çalış"): the network probe reads
each ElevenLabs key's credits (free) but never makes George speak unless voice=yes is asked for."""
from pathlib import Path

PROBE = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "probe.yml").read_text(encoding="utf-8")


def test_probe_spends_no_voice_by_default():
    assert 'default: "no"' in PROBE
    speak = PROBE.index('if [ "$SPEAK" = yes ]; then')
    tts = PROBE.index("/v1/text-to-speech/")
    end = PROBE.index("fi", tts)
    assert speak < tts < end  # the only text-to-speech call sits inside the voice=yes branch
    assert PROBE.count("/v1/text-to-speech/") == 1


def test_probe_checks_the_guide_sources():
    for url in ("https://elevenlabs.io/blog/rss.xml", "https://blog.google/rss/",
                "https://www.figma.com/blog/feed/atom.xml", "https://www.apple.com/newsroom/rss-feed.rss",
                "https://cursor.com/changelog/rss.xml"):
        assert url in PROBE
