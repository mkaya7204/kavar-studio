"""Image pipeline: tool -> site capture -> carousel + story text -> rendered JPEGs.

The video pipeline (main.py) is untouched; this shares its fetcher, capturer and
script writer helpers. You upload the result to Instagram by hand.

    python carousel.py                     # latest SaaS/AI tool from Product Hunt
    python carousel.py --sample            # built-in sample tools
    python carousel.py --video-script output/temp/script.json
                                           # same tool as a Reel: reuses its facts
    python carousel.py --carousel output/temp/carousel_letra.json
                                           # ready-made carousel JSON (e.g. written in a
                                           # Claude Code session); no Claude call
    --reuse-capture                        # use the last site capture in output/temp
                                           # (from the video run) instead of capturing again

Output: output/carousel/<date>_<tool>/
    carousel/01.jpg ...   feed slides, 1080x1350, upload in this order
    story/01.jpg ...      story frames, 1080x1920
    caption.txt           caption, hashtags, alt texts, story sticker notes
    carousel.json         the text, qa.json the layout checks
"""

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from carousel_renderer import RenderError, load_brand, render  # noqa: E402
from carousel_writer import CarouselScript, generate_carousel, revise_carousel  # noqa: E402
from distribution import build_affiliate_link  # noqa: E402
from fetcher import fetch_latest_tools  # noqa: E402
from article_capture import capture_article  # noqa: E402
from media_capturer import CaptureError, capture_site  # noqa: E402
from model_trial import run_trial  # noqa: E402
from news_fetcher import fetch_news, mark_used  # noqa: E402
from news_writer import NewsScript, generate_news, revise_news  # noqa: E402
from pydantic import ValidationError  # noqa: E402

TEMP_DIR = ROOT / "output" / "temp"
OUT_ROOT = ROOT / "output" / "carousel"
CANDIDATES = 3
REVISIONS = 2  # rewrite rounds when rendered slides don't fit
# Problems Claude can fix by rewriting text; the rest are template / asset bugs.
TEXT_PROBLEMS = {"overflow", "small", "collision"}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "arac"


def _last_capture() -> dict:
    shot, full, logo = TEMP_DIR / "screenshot.png", TEMP_DIR / "fullpage.png", TEMP_DIR / "logo.png"
    if not (shot.exists() and full.exists()):
        raise CaptureError("no previous capture in output/temp; run without --reuse-capture")
    return {"screenshot_path": str(shot), "fullpage_path": str(full),
            "logo_path": str(logo) if logo.exists() else None}


def _caption_txt(script: dict, brand: dict) -> str:
    news = script.get("kind") == "news"
    link = {"url": script["website_url"]} if news else build_affiliate_link(script["tool_name"],
                                                                             script["website_url"])
    lines = [script["caption"], "", " ".join(script["hashtags"]), ""]
    if news:
        lines += [f"Kaynak haber: {script['title']} — {script['website_url']}", ""]
    lines += ["-" * 40, "ALT METİNLER (Gelişmiş ayarlar > Erişilebilirlik, slayt slayt):"]
    lines += [f"{i:02d}. {s['alt_text']}" for i, s in enumerate(script["slides"], 1)]
    lines += ["", "-" * 40, "STORY (sırayla paylaş):"]
    for i, f in enumerate(script["story"], 1):
        note = f"{i}. {f['title']}"
        if f["role"] == "poll":
            note += (f"\n   → ANKET sticker'ı ekle, parlayan boş alana koy. Soru: {f['title']} | "
                     f"Seçenekler: {' / '.join(f['poll_options'])}")
        if f["role"] == "link":
            note += f"\n   → LİNK sticker'ı ekle, parlayan boş alana koy: {link['url']}"
        lines.append(note)
    lines += ["", f"Hesap: {brand['handle']}"]
    return "\n".join(lines) + "\n"


def _render_with_revisions(script: dict, capture: dict, out: Path, brand: dict, revise) -> tuple[dict, dict]:
    """Render; while slides don't fit and `revise` (a Claude rewrite) is given, rewrite and render again."""
    for round_ in range(REVISIONS + 1):
        # saved before every render, so a crash never loses a Claude draft (--rerender uses it)
        (out / "carousel.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
        print("▶ Rendering...", flush=True)
        result = render(script, capture, out, brand)
        fixable = [q["msg"] for q in result["qa"] if q["kind"] in TEXT_PROBLEMS]
        print(f"   {len(result['carousel'])} + {len(result['story'])} frames in {result['seconds']}s, "
              f"{len(result['qa'])} layout problems")
        for q in result["qa"]:
            print(f"   ✖ [{q['mode']}] {q['msg']}")
        if not fixable or revise is None or round_ == REVISIONS:
            break
        print(f"▶ Asking Claude to shorten {len(fixable)} slides (round {round_ + 1})...", flush=True)
        revised = revise(script, fixable)
        if revised is None:
            break
        script = revised
    return script, result


def _finish_run(out: Path, script: dict, result: dict, brand: dict, label: str, t0: float) -> Path:
    (out / "carousel.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "qa.json").write_text(json.dumps(result["qa"], indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "caption.txt").write_text(_caption_txt(script, brand), encoding="utf-8")
    files = [Path(f).name for f in result["carousel"]]
    print("\n" + "=" * 60)
    print(f"{'✅' if not result['qa'] else '⚠'} Done in {time.perf_counter() - t0:.0f}s — {label}")
    print(f"   Folder : {out}")
    print(f"   Upload : carousel/{files[0]} … {files[-1]} in order"
          + (" (includes video slides)" if any(f.endswith('.mp4') for f in files) else "")
          + ", then story/ frames")
    print(f"   Text   : caption.txt")
    if result["qa"]:
        print(f"   Layout : {len(result['qa'])} problems left, see qa.json; check those slides by eye")
    print("=" * 60)
    return out


def produce_news(item: dict) -> Path:
    """News mode: article -> capture -> Claude news carousel -> render."""
    t0 = time.perf_counter()
    out = OUT_ROOT / f"{date.today().isoformat()}_haber-{_slug(item['title'])[:40]}"
    out.mkdir(parents=True, exist_ok=True)
    brand = load_brand()
    print(f"\n▶ Capturing article: {item['title']}\n   {item['url']}", flush=True)
    article = capture_article(item["url"], out / "article")
    print(f"   {article['publisher']}, {len(article['text'])} chars, {len(article['figures'])} images, "
          f"{len(article['videos'])} videos, cover={'yes' if article['cover_path'] else 'no'}")
    if not article["cover_path"] or len(article["text"]) < 600:
        raise CaptureError("article has no cover image or too little text")
    print("▶ Can we run the new model ourselves? (Biz denedik)", flush=True)
    if trial := run_trial(article, out / "article" / "trial"):
        for f in trial["figures"]:  # our outputs become the last figures, credited "KAVAR denemesi"
            article["figures"].append({**f, "n": len(article["figures"]) + 1})
        article["trial_note"] = trial["note"]
    (out / "article" / "article.json").write_text(json.dumps(article, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    print("▶ Writing the news carousel...", flush=True)
    script = generate_news(article)
    if script is None:
        raise CaptureError("no Claude source wrote a valid news carousel (news mode has no mock)")
    print(f"   source={script['source']}, {len(script['slides'])} slides, headline: \"{script['slides'][0]['title']}\"")
    script, result = _render_with_revisions(script, article, out, brand,
                                            lambda sc, probs: revise_news(sc, probs, article))
    mark_used(item["url"])
    return _finish_run(out, script, result, brand, article["publisher"] + ": " + item["title"], t0)


def produce(tool: dict, capture: dict | None, video_script: dict | None,
            carousel: dict | None) -> Path:
    t0 = time.perf_counter()
    out = OUT_ROOT / f"{date.today().isoformat()}_{_slug(tool['tool_name'])}"
    out.mkdir(parents=True, exist_ok=True)
    brand = load_brand()

    if capture is None:
        print(f"\n▶ Capturing {tool['website_url']}...", flush=True)
        capture = capture_site(tool["website_url"], out_dir=out / "capture", scroll_seconds=None)

    written_here = carousel is None  # a ready-made carousel is fixed by its author, not rewritten
    if written_here:
        print(f"▶ Writing carousel + story for {tool['tool_name']}...", flush=True)
        carousel = generate_carousel(tool, video_script)
    print(f"   source={carousel['source']}, {len(carousel['slides'])} slides, "
          f"{len(carousel['story'])} story frames, cover: \"{carousel['slides'][0]['title']}\"")

    revise = None
    if written_here and carousel["source"] != "mock":
        def revise(sc, probs):
            return revise_carousel(sc, probs, tool, video_script)
    carousel, result = _render_with_revisions(carousel, capture, out, brand, revise)
    return _finish_run(out, carousel, result, brand, tool["tool_name"], t0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an Instagram carousel + story set.")
    parser.add_argument("--sample", action="store_true", help="use built-in sample tools")
    parser.add_argument("--video-script", type=Path, help="the Reel's script JSON for the same tool")
    parser.add_argument("--carousel", type=Path, help="ready-made carousel JSON; skips writing")
    parser.add_argument("--reuse-capture", action="store_true", help="use the last capture in output/temp")
    parser.add_argument("--news", action="store_true", help="news mode: the freshest AI news from news_sources.json")
    parser.add_argument("--news-url", help="news mode for this article URL")
    parser.add_argument("--rerender", type=Path, metavar="RUN_DIR",
                        help="render a news run folder again from its carousel.json (after editing it); no Claude call")
    args = parser.parse_args()
    print("=" * 60 + "\n carousel + story pipeline\n" + "=" * 60)

    if args.rerender:
        t0 = time.perf_counter()
        try:
            script = json.loads((args.rerender / "carousel.json").read_text(encoding="utf-8"))
            article = json.loads((args.rerender / "article" / "article.json").read_text(encoding="utf-8"))
            script = NewsScript.model_validate(script).model_dump(mode="json")
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            print(f"✖ Can't re-render {args.rerender}: {exc}")
            return 1
        brand = load_brand()
        script, result = _render_with_revisions(script, article, args.rerender, brand, None)
        _finish_run(args.rerender, script, result, brand, script["title"], t0)
        return 0

    if args.news or args.news_url:
        items = ([{"title": args.news_url.rstrip("/").rsplit("/", 1)[-1], "url": args.news_url}]
                 if args.news_url else fetch_news(5))
        if not items:
            print("✖ No fresh, unused news in the feeds (see news_sources.json).")
            return 1
        for item in items:
            try:
                produce_news(item)
                return 0
            except (CaptureError, RenderError) as exc:
                print(f"   skipping: {exc}")
        print("✖ No news item could be turned into a carousel.")
        return 1

    video_script = carousel = None
    try:
        if args.video_script:
            video_script = json.loads(args.video_script.read_text(encoding="utf-8"))
        if args.carousel:
            carousel = CarouselScript.model_validate_json(
                args.carousel.read_text(encoding="utf-8")).model_dump(mode="json")
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"✖ Invalid input file: {exc}")
        return 1

    known = carousel or video_script
    try:
        capture = _last_capture() if args.reuse_capture else None
        if known:
            tool = {"tool_name": known["tool_name"], "website_url": known["website_url"],
                    "tag_line": "", "description": ""}
            produce(tool, capture, video_script, carousel)
            return 0
        tools = [t for t in fetch_latest_tools(limit=CANDIDATES, use_sample=args.sample)
                 if "producthunt.com" not in t["website_url"]] or fetch_latest_tools(CANDIDATES, use_sample=True)
        for tool in tools:
            try:
                produce(tool, capture, None, None)
                return 0
            except CaptureError as exc:
                print(f"   skipping {tool['tool_name']}: {exc}")
        print("✖ No candidate could be captured.")
        return 1
    except (CaptureError, RenderError) as exc:
        print(f"✖ Failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
