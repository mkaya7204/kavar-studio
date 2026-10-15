""""Biz denedik" Reel: the same test as the day's news carousel, as a Reel (posts reach few people).

Same composition, voice (ElevenLabs "George", the user's choice), captions, music and editor as
the tool Reels (hyperframes_builder); only the story and the pictures differ:
  hook          the most striking test result as the headline, over our own test output (= cover)
  card1, shot1  the first test: what we asked, what came out; then the output itself
  card2, shot2  the second test, the same way (honest about what went wrong)
  card3         one thing the model can do (from the article)
  why, outro
Writes the same files as main.py (output/temp/script.json, tool.json; output/final/...), so
daily.py queues and reviews it like any Reel. Heavy (render): runs in the cloud only.

    python src/trial_reel.py output/carousel/<run>     # a news run with our test outputs
"""

import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carousel_writer import _ask, _revision_prompt  # noqa: E402
from distribution import build_post  # noqa: E402
from hyperframes_builder import FINAL_PATH, PROOF_SIZE, SHOT_NAMES, _shot_frame, build_video_hyperframes  # noqa: E402
from script_writer import (NO_PRICE_RULE, SYSTEM_PROMPT, ScriptDraft, VideoScript,  # noqa: E402
                           _load_language, _save_history, _script_price_mentions, judge_hooks, reel_rule_problems)
from tts_engine import synthesize, voice_for  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMP_DIR = ROOT / "output" / "temp"
ATTEMPTS = 3
# 50 words read in 26.8 s and the Reel ran 27.9 s (rule: 14-26 s, editor rejected, 2026-10-16)
WORDS = (32, 38)

TRIAL_RULES = """

THIS REEL IS DIFFERENT: it is not about a tool's website. It is KAVAR's own test of a new AI \
model ("Biz denedik"): we really ran the model and the pictures in the Reel are its real, \
unedited outputs. The "tool" is the model.
- hook: EVERY hook candidate is about OUTPUT 1, the picture behind the headline on frame 0 \
(and the cover): its result in plain words, no model name ("Yeni modele KAVAR yazdırdık", \
"Yapay zekâya İstanbul'u çizdirdik"). A hook about the other output would not match the picture.
- point1: names the model by its SHORT name (e.g. "FLUX.3", not the full name plus company: \
long names break the captions) and what kind of model it is, then output 1's result. Two short \
sentences at most (~3 s).
- point2: output 2 the same way (shot2); say plainly what went wrong if something did. With only \
one output, a second honest observation about it.
- point3: one thing the model can do, from the article, in plain words (no developer jargon).
- key_points: card1 = output 1's result, card2 = output 2's result, card3 = the capability.
- No claims about the past or about other models ("artık", "eskiden", "hep bozuyordu") unless the \
article says so.
- "denedik", "yazdırdık", "sorduk", "çizdirdik" are allowed here, only about these tests (we did \
them; "we" = the page). Never praise beyond the editor's verdict on each output.
- Facts only from the article and the KAVAR TEST section. Never mention our internal checks.
- caption: the same verdicts and verbs as the voiceover, never stronger. No superlatives ("kusursuz", "mükemmel", "harika", "inanılmaz") unless the editor's verdict says exactly that."""


def short_name(model: str) -> str:
    """The name said in the Reel: "FLUX.3 Image Klein" -> "FLUX.3", "Gemma 4" -> "Gemma 4".
    Long names broke the 3-word captions ("ADI FLUX.3 IMAGE")."""
    words = model.split()
    if words and any(c.isdigit() for c in words[0]):
        return words[0]
    return " ".join(words[:2])


def _model_name(article: dict) -> str:
    if article.get("trial_model"):
        return article["trial_model"]
    m = re.search(r"KAVAR TEST: we ran (.+?) ourselves", article.get("trial_note", ""))
    return m.group(1) if m else article["title"]


def _ours(article: dict) -> list[dict]:
    """Our test output figures, the cover one first (it is the hook's picture and shot1)."""
    ours = [f for f in article["figures"] if f.get("credit")]
    cover = next((f for f in ours if article.get("cover_credit") and f["path"] == article["cover_path"]), None)
    if cover:
        ours.remove(cover)
        ours.insert(0, cover)
    return ours


def _outputs(article: dict) -> list[Path]:
    return [Path(f["path"]) for f in _ours(article)]


def _output_order(article: dict) -> str:
    """Which test each Reel output is ("KAVAR TEST n" as in the test notes)."""
    return "\n".join(f"output {i}: {f['caption'].split(':')[0]}" for i, f in enumerate(_ours(article), 1))


def _frames(outputs: list[Path], folder: Path) -> dict:
    """proof.png (the hook box) and shot1/shot2 frames from our outputs, as hyperframes_builder expects."""
    folder.mkdir(parents=True, exist_ok=True)
    proof = folder / "proof.png"
    with Image.open(outputs[0]) as img:
        ImageOps.fit(img.convert("RGB"), PROOF_SIZE, Image.LANCZOS, centering=(0.5, 0.0)).save(proof)
    for name, src in zip(SHOT_NAMES, [outputs[0], outputs[min(1, len(outputs) - 1)]]):
        with Image.open(src) as img:
            img = img.convert("RGB")
            img.thumbnail((960, 1300), Image.LANCZOS)
            _shot_frame(img, folder / name)
    return {"screenshot_path": str(folder / SHOT_NAMES[0]), "fullpage_path": str(folder / SHOT_NAMES[1]),
            "proof_path": str(proof), "logo_path": None, "domain_label": "KAVAR denemesi"}


def write_script(article: dict) -> dict | None:
    language = _load_language()
    low, high = WORDS
    full = _model_name(article)
    model = short_name(full)
    prompt = (f"Write the Reel in language code '{language}', voiceover {low}-{high} words (hard limit: "
              f"the Reel must stay under 26 seconds).\n\n"
              f"Model: {full}; say it as \"{model}\"\nSource: {article['publisher']}, published {article.get('published') or '?'}\n"
              f"Article title: {article['title']}\n\nArticle text:\n{article['text'][:5000]}\n\n"
              f"{article['trial_note']}\n\nOutput order in the Reel (the hook is about output 1):\n"
              f"{_output_order(article)}")
    system = SYSTEM_PROMPT + TRIAL_RULES
    fallback = None
    for attempt in range(1, ATTEMPTS + 1):
        draft, used_model, source = _ask(prompt, system, ScriptDraft)
        if draft is None:
            return fallback
        try:
            script = VideoScript(**draft, tool_name=model, website_url=article["url"],
                                 source=source, model=used_model)
        except ValueError as exc:
            problems = str(exc)[:600]
        else:
            if script.voiceover_words > high:
                problems = f"voiceover has {script.voiceover_words} words; max {high}: cut a sentence"
            elif bad := _script_price_mentions(script):
                problems = f"remove every price mention ({', '.join(bad)}). {NO_PRICE_RULE}"
            elif rules := reel_rule_problems(script):
                fallback = fallback or script
                problems = "; ".join(rules)
            else:
                return script.model_dump(mode="json")
        print(f"[trial_reel] draft {attempt} rejected: {problems[:400]}")
        prompt = _revision_prompt(prompt, draft, problems).replace("carousel", "Reel script")
    return fallback.model_dump(mode="json") if fallback else None


def make_trial_reel(run: Path) -> int:
    article = json.loads((run / "article" / "article.json").read_text(encoding="utf-8"))
    outputs = _outputs(article)
    if not article.get("trial_note") or not outputs:
        print("✖ this run has no test outputs of ours")
        return 1
    tool = {"tool_name": short_name(_model_name(article)), "model_full_name": _model_name(article),
            "website_url": article["url"],
            "kind": ("Biz denedik: the page really ran these tests on the new model, so first-person-plural "
                     "lines about them ('denedik', 'yazdırdık', 'sorduk') are TRUE, not a fake use claim. "
                     "Frame 0 shows output 1 behind the headline, so the hook must be about output 1."),
            "output_order": _output_order(article), "article": article["text"][:4000],
            "kavar_test": article["trial_note"]}
    print(f"▶ Biz denedik Reel: {tool['tool_name']} ({len(outputs)} outputs)", flush=True)
    script = write_script(article)
    if script is None:
        print("✖ no valid Reel script")
        return 1
    script = judge_hooks(script, tool)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (TEMP_DIR / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    (TEMP_DIR / "tool.json").write_text(json.dumps(tool, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"   hook: \"{script['hook']}\", {script['voiceover_words']} words")
    voice = synthesize(script["voiceover"], voice=voice_for(_load_language()))
    print(f"   voice {voice['duration_sec']}s ({voice['voice']})")
    capture = _frames(outputs, TEMP_DIR / "trial_frames")
    video = build_video_hyperframes(script, capture, voice["audio_path"], FINAL_PATH)
    print(f"   {video['duration_sec']}s, {video['scenes']}")
    _save_history(VideoScript.model_validate(script))
    post = build_post(script, video)
    (FINAL_PATH.parent / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Reel: {FINAL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(make_trial_reel(Path(sys.argv[1])))
