"""07:30 morning Reel (D-29, user 2026-10-17): AI and technology developments in Turkey.

One concept only: what Turkish institutions, companies, universities and public services do with AI
and technology, and what changes for people in Turkey. Steps:
  1. candidates   Turkish tech news sites and institutions' own feeds (news_sources.json "tr_feeds"),
                  last 36 h, unused, ranked by content_ranker inside this concept
  2. own page     the story is followed to the institution's own announcement page (Claude, web
                  search). Pictures come only from there: the institution's own images. No own page
                  with an image = the story is skipped (press photos stay banned, CLAUDE.md §1.9)
  3. Reel         script (facts only from the two texts), George voice, the same template and editor
                  as every Reel. Writes output/temp/script.json, tool.json and output/final/ like main.py.

    python src/tr_reel.py            # heavy (render): cloud only
"""

import json
import os
import re
import shutil
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
WORK = ROOT / "output" / "tr"
MAX_AGE_HOURS = 72  # Turkey AI news is slow: 36 h left one candidate (10-17 test)
TRIES = 3  # stories followed to an own page per morning
WORDS = (32, 38)  # same as the "Biz denedik" Reel: under 26 s
AI_OR_TECH = re.compile(r"yapay zek|\bai\b|\bYZ\b|chatgpt|gemini|robot|otonom|algoritma|dil modeli|veri merkez|"
                        r"yazılım|siber|dijital|uydu|5g|yerli (?:çip|işlemci|model)|teknoloji", re.I)

TURKEY = re.compile(r"türk|türkiye|turkcell|telekom|trendyol|hepsiburada|getir|baykar|aselsan|havelsan|tusaş|"
                    r"roketsan|togg|tübitak|teknofest|bakanl|cumhurbaşkan|belediye|üniversite|istanbul|ankara|izmir|"
                    r"türk hava|yerli|milli", re.I)

TR_RULES = """

THIS REEL IS DIFFERENT: it is KAVAR's 07:30 morning Reel about AI and technology developments in \
TURKEY, not a tool's website. The "tool" is the Turkish institution or company in the news.
- hook: the development and what it means for people in Turkey, in plain words; no institution name \
in the hook.
- point1: names the institution and says what it did (~3 s). point2 and point3: one concrete detail \
each, from the texts. key_points follow point1-3 in the same order.
- Facts only from OFFICIAL PAGE and PRESS ARTICLE below. Numbers only if they appear there. If the \
two disagree, use the official page. Neutral and factual: no political praise or criticism, no \
"gurur", "dev adım", "tarihi" unless the official page itself says it, and then as its words.
- The pictures are the institution's own (from its page)."""


def tr_feeds() -> list[dict]:
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8")).get("tr_feeds", [])


def fetch_tr(limit: int = 40) -> list[dict]:
    """Fresh, unused AI / tech stories from the Turkish feeds, newest first."""
    used = set(load_history())
    items = []
    now = datetime.now(timezone.utc)
    for feed in tr_feeds():
        try:
            # a feed may keep its stories longer: a startup profile (Webrazzi Girişim) stays news for two weeks
            items += [{**i, "since": now - timedelta(hours=feed.get("max_age_hours", MAX_AGE_HOURS))}
                      for i in _items(feed)]
        except Exception as exc:  # noqa: BLE001  one dead feed never stops the morning
            print(f"[tr] {feed['name']} skipped: {type(exc).__name__}")
    fresh = [i for i in items if i["date"] and i["date"] >= i.pop("since") and i["url"] not in used
             and AI_OR_TECH.search(f"{i['title']} {i.get('summary', '')}")]
    # Turkey first: "teknoloji" is broad, and generic tech news pushed the Turkey stories past the limit (10-17)
    fresh.sort(key=lambda i: (bool(TURKEY.search(f"{i['title']} {i.get('summary', '')}")), i["date"]), reverse=True)
    for i in fresh:
        i["date"] = i["date"].isoformat()
    return fresh[:limit]


def official_page(item: dict, press_text: str) -> tuple[str, str, str]:
    """(institution, its own page about this story or "", its own site's home or newsroom or "") via
    Claude Code web search."""
    exe = None if os.getenv("SCRIPT_WRITER_NO_CLI") else shutil.which("claude")
    if not exe:
        return "", "", ""
    press_hosts = {urlsplit(f["url"]).hostname for f in tr_feeds()} | {urlsplit(item["url"]).hostname}
    schema = {"type": "object", "additionalProperties": False, "required": ["institution", "story_url", "home_url"],
              "properties": {"institution": {"type": "string"}, "story_url": {"type": "string"},
                             "home_url": {"type": "string"}}}
    prompt = (f"A Turkish tech news site reported this story:\nTitle: {item['title']}\nURL: {item['url']}\n\n"
              f"{press_text[:3000]}\n\nWhich Turkish institution or company is it mainly about? Return:\n"
              f"- institution: its name\n- story_url: THAT institution's own page about this same news (press "
              f"release, announcement, report or blog post on its own official domain), or \"\" if you can't "
              f"find one\n- home_url: the institution's own official website (its newsroom / press page if it "
              f"has one, otherwise its home page)\nNever return a news site, social media, Wikipedia or a "
              f"video site.")
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run([exe, "-p", "--output-format", "json", "--json-schema", json.dumps(schema),
                               "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch",
                               "--no-session-persistence"],
                              input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
        result = json.loads(proc.stdout)
        out = result.get("structured_output") or {}
        if not out:
            print(f"[tr_reel] institution search gave nothing ({result.get('subtype')}): {str(result.get('result'))[:200]}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        print(f"[tr_reel] institution search failed ({type(exc).__name__}): {(proc.stderr if 'proc' in dir() else '')[:200]}")
        return "", "", ""

    def own(url: str) -> str:
        host = urlsplit(url).hostname or ""
        bad = host in press_hosts or re.search(r"youtube|twitter|x\.com|instagram|facebook|linkedin|wikipedia|tiktok", host)
        return url if url.startswith("http") and not bad else ""

    return out.get("institution", "").strip(), own(out.get("story_url", "").strip()), own(out.get("home_url", "").strip())


def _ahash(path: str) -> int:
    with Image.open(path) as img:
        small = ImageOps.grayscale(img).resize((8, 8), Image.LANCZOS)
    px = list(small.getdata())
    avg = sum(px) / len(px)
    return sum(1 << i for i, p in enumerate(px) if p > avg)


def same_picture(a: str, b: str) -> bool:
    """The same image (re-sized or re-compressed by a news site) - 8x8 average hash, <= 6 bits apart."""
    try:
        return bin(_ahash(a) ^ _ahash(b)).count("1") <= 6
    except OSError:
        return False


def pictures_for(press: dict, own_pages: list[dict]) -> list[str]:
    """The institution's pictures, story page first (user, 10-17): the news site's picture only when it is
    one of the institution's own images; otherwise any picture from the institution's own site."""
    own = [p for page in own_pages for p in [page.get("cover_path"), *(f["path"] for f in page.get("figures", []))] if p]
    press_cover = press.get("cover_path")
    if press_cover and any(same_picture(press_cover, p) for p in own):
        own = [press_cover] + [p for p in own if not same_picture(press_cover, p)]
    return own


def _frames(official: dict, pictures: list[str], folder: Path) -> dict | None:
    """proof.png and the two site shots, all from the institution's own site."""
    if not pictures:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    with Image.open(pictures[0]) as img:
        ImageOps.fit(img.convert("RGB"), PROOF_SIZE, Image.LANCZOS, centering=(0.5, 0.35)).save(folder / "proof.png")
    shots = [official["page_path"], pictures[1] if len(pictures) > 1 else pictures[0]]
    for name, src in zip(SHOT_NAMES, shots):
        with Image.open(src) as img:
            img = img.convert("RGB")
            img.thumbnail((960, 1300), Image.LANCZOS)
            _shot_frame(img, folder / name)
    domain = (urlsplit(official["url"]).hostname or "").removeprefix("www.")
    return {"screenshot_path": str(folder / SHOT_NAMES[0]), "fullpage_path": str(folder / SHOT_NAMES[1]),
            "proof_path": str(folder / "proof.png"), "logo_path": None, "domain_label": domain}


def write_script(institution: str, press: dict, official: dict) -> dict | None:
    language = _load_language()
    low, high = WORDS
    prompt = (f"Write the Reel in language code '{language}', voiceover {low}-{high} words (hard limit: under "
              f"26 seconds).\n\nInstitution: {institution}\n\nOFFICIAL PAGE ({official['url']}, published "
              f"{official.get('published') or '?'}):\n{official['text'][:4000]}\n\nPRESS ARTICLE "
              f"({press['publisher']}):\n{press['text'][:3000]}")
    system = SYSTEM_PROMPT + TR_RULES
    fallback = None
    for attempt in range(1, 4):
        draft, used_model, source = _ask(prompt, system, ScriptDraft)
        if draft is None:
            return fallback
        try:
            script = VideoScript(**draft, tool_name=institution, website_url=official["url"],
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
        print(f"[tr_reel] draft {attempt} rejected: {problems[:400]}")
        prompt = _revision_prompt(prompt, draft, problems).replace("carousel", "Reel script")
    return fallback.model_dump(mode="json") if fallback else None


def make_tr_reel() -> int:
    fresh = fetch_tr()
    candidates = [c for c in rank(fresh, "tr_reel", kind_prefix="tr_reel")
                  if (c.get("rank") or {}).get("fits", True) and not (c.get("rank") or {}).get("repeat")]
    print(f"▶ Türkiye Reel: {len(fresh)} fresh AI / tech stories, {len(candidates)} about Turkey", flush=True)
    for c in candidates:
        r = c.get("rank") or {}
        print(f"   rank {r.get('score', '-'):>2} {c['title'][:80]} ({str(r.get('reason', ''))[:80]})")
    for c in candidates[:TRIES]:
        print(f"\n--- {c['source']}: {c['title']}", flush=True)
        try:
            press = capture_article(c["url"], WORK / "press")
        except CaptureError as exc:
            print(f"   capture failed: {exc}")
            continue
        institution, story_url, home_url = official_page(c, press["text"])
        print(f"   institution: {institution or '?'}; own story page: {story_url or '-'}; own site: {home_url or '-'}")
        own_pages = []
        for n, url in (("official", story_url), ("home", home_url)):
            if url:
                try:
                    own_pages.append(capture_article(url, WORK / n))
                except CaptureError as exc:
                    print(f"   {n} page capture failed: {exc}")
        pictures = pictures_for(press, own_pages)
        if not institution or not own_pages or not pictures:
            print("   no picture from the institution's own site: skipped (no press photos)")
            continue
        official = own_pages[0]
        if not story_url:  # the facts come from the news article; the pictures from the institution
            official = {**official, "text": press["text"], "url": own_pages[0]["url"]}
        capture = _frames(own_pages[0], pictures, TEMP_DIR / "tr_frames")
        url = official["url"]
        script = write_script(institution, press, official)
        if script is None:
            print("   no valid script")
            continue
        tool = {"tool_name": institution, "website_url": url,
                "kind": "07:30 Turkey Reel (D-29): the facts must come from the institution's own page "
                        "(official_page) or the press article; the pictures are the institution's own (or the "
                        "news site's picture when it matched one of the institution's images). When the "
                        "institution has no page about the story, official_page holds the news article text.",
                "official_page": official["text"][:4000], "press_article": press["text"][:3000],
                "press_url": c["url"]}
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
        mark_used(c["url"])
        post = build_post(script, video)
        (FINAL_PATH.parent / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Reel: {FINAL_PATH}")
        return 0
    print("✖ no Turkey story with the institution's own page and picture this morning")
    return 1


if __name__ == "__main__":
    sys.exit(make_tr_reel())
