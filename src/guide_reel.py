"""07:30 guide Reel (D-31, user 2026-10-18): KAVAR as the guide to AI products people already use.

"insanların kafası çok karışık ... biz yol göstericisi olacağız, doğru kullanım, doğru amaçla kullanım
... henüz bilmedikleri özellikler ya da kullanım yerine göre farklı modlarda veya şekillerde kullanılıyor".
One concept only: a feature of a known AI product (ChatGPT, Gemini, Claude, Copilot, YouTube, Android,
WhatsApp...) and how to use it right: where it is, what to ask, which mode fits which job. Steps:
  1. candidates   the companies' own blogs (news_sources.json "feeds"), last GUIDE_DAYS, unused, ranked
                  by content_ranker inside the guide concept (usable today by a Turkish viewer)
  2. page         the company's own post is captured; facts and pictures come only from it (the
                  company's own press images, CLAUDE.md §1.9)
  3. Reel         guide script, silent draft voice, the same template and editor as every Reel; an
                  approved Reel is rebuilt with George (D-30). Writes output/temp and output/final like main.py.

    python src/guide_reel.py         # heavy (render): cloud only
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

from article_capture import capture_article  # noqa: E402
from carousel_writer import _ask, _revision_prompt  # noqa: E402
from content_ranker import rank  # noqa: E402
from distribution import build_post  # noqa: E402
from hyperframes_builder import FINAL_PATH, PROOF_SIZE, SHOT_NAMES, _shot_frame, build_video_hyperframes  # noqa: E402
from media_capturer import CaptureError  # noqa: E402
from news_fetcher import SOURCES_PATH, _items, load_history, mark_used  # noqa: E402
from script_writer import (NO_PRICE_RULE, SYSTEM_PROMPT, ScriptDraft, VideoScript,  # noqa: E402
                           _load_language, _save_history, _script_price_mentions, judge_hooks, reel_rule_problems)
from tts_engine import reel_voice, voice_for  # noqa: E402
from voice_final import save_capture  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMP_DIR = ROOT / "output" / "temp"
WORK = ROOT / "output" / "guide"
GUIDE_DAYS = 14  # a feature stays worth explaining for weeks, unlike a news story
POOL = 60  # candidates sent to the ranker
PER_FEED = 5
TRIES = 6  # pages tried per morning: OpenAI refuses the cloud reader at times, Samsung times out (10-18 dry run)
WORDS = (32, 38)  # same as the other Reels: under 26 s

GUIDE_RULES = """

THIS REEL IS DIFFERENT: it is KAVAR's 07:30 GUIDE Reel, not news and not a new tool. KAVAR shows people \
how to use AI products they already have, the right way: a feature they don't know yet, where it is, \
and which mode or way fits which job. The "tool" is the product the feature belongs to.
- hook: the viewer's goal or problem in plain words ("... yapmak istiyorsan", "... biliyor muydun?"), \
not the company's announcement. No "duyurdu", "tanıttı" in the hook.
- point1: names the product and the feature, and where to find it (~3 s).
- point2: how to use it: what to tap or ask, one concrete step.
- point3: when it is the right choice, or which mode fits which job, or one tip from the page.
- why: what the viewer gains. key_points follow point1-3 in the same order.
- Facts only from the COMPANY PAGE below: never add features, menus, steps or limits it doesn't state. \
If the page says the feature is rolling out, limited to some countries, in beta, or comes with a plan (e.g. Pro, Plus, a subscription) or uses credits, say so briefly (D-32): the viewer must know whether they can use it. Never amounts or free / paid.
- Only what an everyday user does in the app. If the page also covers developers (API, SDK, ADK, \
benchmarks), leave that out: "Kodun gece boyu hızlanıyor" overstated a developer kit (10-18 dry run).
- hashtags: the product and the feature first, one guide tag (#ipucu or #nasılyapılır), #yapayzeka only \
when the feature is AI."""


def fetch_guide(limit: int = POOL) -> list[dict]:
    """Unused posts of the companies' own blogs from the last GUIDE_DAYS, newest first."""
    feeds = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))["feeds"]
    since = datetime.now(timezone.utc) - timedelta(days=GUIDE_DAYS)
    used = set(load_history())
    items = []
    for feed in feeds:
        try:
            items += _items(feed)
        except Exception as exc:  # noqa: BLE001  one dead feed never stops the morning
            print(f"[guide] {feed['name']} skipped: {type(exc).__name__}")
    fresh = [i for i in items if i["date"] and i["date"] >= since and i["url"] not in used]
    fresh.sort(key=lambda i: i["date"], reverse=True)
    # at most PER_FEED posts per blog: OpenAI's customer stories and NVIDIA filled the whole pool, and the
    # Gemini app post never reached the ranker (10-18 dry run)
    per_feed: dict[str, list[dict]] = {}
    for i in fresh:
        per_feed.setdefault(i["source"], []).append(i)
    fresh = sorted((i for posts in per_feed.values() for i in posts[:PER_FEED]), key=lambda i: i["date"], reverse=True)
    for i in fresh:
        i["date"] = i["date"].isoformat()
    return fresh[:limit]


def _video_frames(videos: list[str], folder: Path) -> list[str]:
    """One still from each of the page's own videos (feature demos), taken 40% in, past the title card."""
    out = []
    for n, src in enumerate(videos, 1):
        still = folder / f"video_{n}.png"
        try:
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    src], capture_output=True, text=True, timeout=60)
            at = float(probe.stdout.strip() or 0) * 0.4
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", src, "-frames:v", "1",
                            str(still)], capture_output=True, timeout=120)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
        if still.exists():
            out.append(str(still))
    return out


def _detail(img: Image.Image) -> Image.Image:
    """The middle of a picture, bigger: a second, readable look at the same feature screen."""
    w, h = img.size
    return img.crop((round(w * 0.18), round(h * 0.12), round(w * 0.82), round(h * 0.88)))


def _frames(page: dict, folder: Path) -> dict | None:
    """proof.png and the two shots, all from the company's own page: the feature's own pictures first
    (the article's figures and stills from its videos, usually the product's screen), the cover last.
    The page itself is never used: shrunk or cropped, its text was unreadable (editor, 10-18 dry runs,
    twice), and an abstract cover (a big "4") proved nothing, so it only fills in when nothing else exists."""
    folder.mkdir(parents=True, exist_ok=True)
    pictures = [f["path"] for f in page.get("figures", [])] + _video_frames(page.get("videos", []), folder)
    if page.get("cover_path"):
        pictures.append(page["cover_path"])
    if not pictures:
        return None
    with Image.open(pictures[0]) as img:
        ImageOps.fit(img.convert("RGB"), PROOF_SIZE, Image.LANCZOS, centering=(0.5, 0.35)).save(folder / "proof.png")
    # with too few pictures a shot is a closer look at one of them, never the same frame twice
    shots = [(pictures[1], False) if len(pictures) > 1 else (pictures[0], True),
             (pictures[2], False) if len(pictures) > 2 else (pictures[-1], True)]
    for name, (src, closer) in zip(SHOT_NAMES, shots):
        with Image.open(src) as img:
            img = img.convert("RGB")
            if closer:
                img = _detail(img)
            if img.width < 960:
                img = img.resize((960, round(img.height * 960 / img.width)), Image.LANCZOS)
            img.thumbnail((960, 1300), Image.LANCZOS)
            _shot_frame(img, folder / name)
    domain = (urlsplit(page["url"]).hostname or "").removeprefix("www.")
    return {"screenshot_path": str(folder / SHOT_NAMES[0]), "fullpage_path": str(folder / SHOT_NAMES[1]),
            "proof_path": str(folder / "proof.png"), "logo_path": None, "domain_label": domain}


def write_script(product: str, page: dict) -> dict | None:
    language = _load_language()
    low, high = WORDS
    prompt = (f"Write the Reel in language code '{language}', voiceover {low}-{high} words (hard limit: under "
              f"26 seconds).\n\nProduct / company: {product}\n\nCOMPANY PAGE ({page['url']}, published "
              f"{page.get('published') or '?'}):\n{page['text'][:6000]}")
    system = SYSTEM_PROMPT + GUIDE_RULES
    fallback = None
    for attempt in range(1, 4):
        draft, used_model, source = _ask(prompt, system, ScriptDraft)
        if draft is None:
            return fallback.model_dump(mode="json") if fallback else None
        try:
            script = VideoScript(**draft, tool_name=product, website_url=page["url"], source=source, model=used_model)
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
        print(f"[guide_reel] draft {attempt} rejected: {problems[:400]}")
        prompt = _revision_prompt(prompt, draft, problems).replace("carousel", "Reel script")
    return fallback.model_dump(mode="json") if fallback else None


def make_guide_reel() -> int:
    fresh = fetch_guide()
    # A product we posted news about is still a guide topic ("haberi verdik, şimdi nasıl kullanılır"): the same
    # post is never reused (history), but a "repeat" product is kept, after the fresh ones (10-18: Gemini 4
    # Argon in the Gemini app was dropped as a repeat of the news carousel).
    ranked = [c for c in rank(fresh, "guide_reel", kind_prefix="guide_reel") if (c.get("rank") or {}).get("fits", True)]
    candidates = sorted(ranked, key=lambda c: bool((c.get("rank") or {}).get("repeat")))
    print(f"▶ Rehber Reel: {len(fresh)} company posts, {len(candidates)} fit the guide concept", flush=True)
    for c in candidates[:10]:
        r = c.get("rank") or {}
        print(f"   rank {r.get('score', '-'):>2} [{c['source']}] {c['title'][:70]} ({str(r.get('reason', ''))[:80]})")
    for c in candidates[:TRIES]:
        print(f"\n--- {c['source']}: {c['title']}", flush=True)
        try:
            page = capture_article(c["url"], WORK / "page")
        except CaptureError as exc:
            print(f"   capture failed: {exc}")
            continue
        capture = _frames(page, TEMP_DIR / "guide_frames")
        if capture is None:
            print("   no picture on the company's page: skipped")
            continue
        product = (c.get("rank") or {}).get("company") or c["source"]
        script = write_script(product, page)
        if script is None:
            print("   no valid script")
            continue
        tool = {"tool_name": product, "website_url": page["url"],
                "kind": "07:30 GUIDE Reel (D-31): how to use a feature of a known AI product the right way. "
                        "Facts, steps and pictures come only from the company's own page (article).",
                "article": page["text"][:6000]}
        script = judge_hooks(script, tool)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        (TEMP_DIR / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
        (TEMP_DIR / "tool.json").write_text(json.dumps(tool, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"   hook: \"{script['hook']}\", {script['voiceover_words']} words")
        voice = reel_voice(script["voiceover"], voice=voice_for(_load_language()))
        save_capture(capture)
        video = build_video_hyperframes(script, capture, voice["audio_path"], FINAL_PATH)
        print(f"   {video['duration_sec']}s, {video['scenes']}")
        _save_history(VideoScript.model_validate(script))
        mark_used(c["url"])  # the news carousels never take the same post
        post = build_post(script, video)
        (FINAL_PATH.parent / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Reel: {FINAL_PATH}")
        return 0
    print("✖ no company post fit for a guide Reel this morning")
    return 1


if __name__ == "__main__":
    sys.exit(make_guide_reel())
