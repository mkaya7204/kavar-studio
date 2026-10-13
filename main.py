"""Run the whole pipeline: fetch tool -> script -> voiceover -> site capture -> final video.

    python main.py              # latest SaaS/AI tool from Product Hunt
    python main.py --sample     # use the built-in sample tools (offline-friendly fetch)
    python main.py --script output/temp/script.json
                                # use a ready-made script (e.g. written in a Claude Code
                                # session); tool and URL come from the script, steps 1 and 3 skipped
    python main.py --renderer ffmpeg
                                # old FFmpeg slideshow instead of the HyperFrames composition

Candidates are tried in order; if a tool's website can't be captured, the next
one is used. Outputs:
    output/final/final_video.mp4   the video
    output/final/post.json         caption, hashtags and tool info for uploading
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from distribution import build_post  # noqa: E402
from fetcher import fetch_latest_tools  # noqa: E402
from hyperframes_builder import BuildError as HFBuildError  # noqa: E402
from hyperframes_builder import best_proof_crop, build_video_hyperframes  # noqa: E402
from media_capturer import CaptureError, capture_site  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from script_writer import VideoScript, _load_history, generate_script  # noqa: E402
from tts_engine import TTSError, synthesize, voice_for  # noqa: E402
from video_builder import FINAL_PATH, build_video  # noqa: E402

TEMP_DIR = ROOT / "output" / "temp"
CANDIDATES = 5  # tools tried in order; one without a clean proof image is skipped
LANGUAGE = json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("language", "en")


class Step:
    """Prints a clear start / done / failed line around each pipeline step."""

    def __init__(self, number: int, title: str):
        self.number, self.title = number, title

    def __enter__(self):
        print(f"\n▶ [{self.number}/5] {self.title}...", flush=True)
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        elapsed = time.perf_counter() - self.t0
        if exc_type is None:
            print(f"✔ [{self.number}/5] {self.title} done ({elapsed:.1f}s)", flush=True)
        else:
            print(f"✖ [{self.number}/5] {self.title} failed after {elapsed:.1f}s: {exc}", flush=True)
        return False  # never swallow the exception


def produce_video(tool: dict, script: dict | None = None, renderer: str = "hyperframes") -> dict:
    """Steps 2-5 for one tool.

    The site is captured first: if it is unreachable or blank, CaptureError is raised
    before any script (a Claude call) or voiceover is spent on it. If `script` is given
    (already validated), step 3 is skipped.
    """
    with Step(2, f"Checking and capturing {tool['website_url']}"):
        capture = capture_site(tool["website_url"], scroll_seconds=None)  # builder animates its own scenes
        print(f"   \"{capture['title']}\", cookie banner clicked={capture['cookie_accept_clicked']}, "
              f"overlays hidden={capture['overlays_hidden']}, logo={'yes' if capture['logo_path'] else 'no'}")

        # The hook's proof image must come from this site, without prices / logos / badges (the
        # editor rejects those). No clean crop = skip the tool before spending a script or a voice.
        proof = best_proof_crop(Path(capture.get("fullpage_path") or capture["screenshot_path"]),
                                TEMP_DIR / "proof.png", f"{tool['tool_name']}: {tool.get('tag_line', '')}")
        if proof is None:
            raise CaptureError("no clean proof image on the site (prices, logos or badges everywhere)")
        capture["proof_path"] = str(proof)

    # the tool data, so the editor review (daily.py) can check the script's facts against it
    (TEMP_DIR / "tool.json").write_text(json.dumps(tool, indent=2, ensure_ascii=False, default=str),
                                        encoding="utf-8")
    if script is None:
        with Step(3, f"Writing script for {tool['tool_name']}"):
            script = generate_script(tool)
            (TEMP_DIR / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"   source={script['source']}, hook: \"{script['hook']}\"")
            print(f"   voiceover: {script['voiceover_words']} words, {len(script['shots'])} shots")
            print(f"   opens: \"{script['voiceover'].split('. ')[0]}.\"")

    with Step(4, "Generating voiceover (ElevenLabs / Azure / edge-tts)"):
        voice = synthesize(script["voiceover"], voice=voice_for(LANGUAGE))
        print(f"   {voice['duration_sec']}s at rate {voice['rate']} ({voice['voice']}) -> {voice['audio_path']}")

    if renderer == "hyperframes":
        with Step(5, "Rendering final video (HyperFrames)"):
            video = build_video_hyperframes(script, capture, voice["audio_path"], FINAL_PATH)
    else:
        with Step(5, "Rendering final video (FFmpeg)"):
            video = build_video(script["hook"], script["tool_name"], script["website_url"],
                                logo_path=capture["logo_path"])
    print(f"   {video['duration_sec']}s, {video['size_mb']} MB, {video['scenes']}, "
          f"rendered in {video['render_seconds']}s")

    post = build_post(script, video)  # affiliate link + per-platform captions (affiliates.json)
    (FINAL_PATH.parent / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
    return post


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a 30s vertical SaaS tool video.")
    parser.add_argument("--sample", action="store_true", help="use built-in sample tools instead of Product Hunt")
    parser.add_argument("--script", type=Path, help="ready-made script JSON; skips fetching and script writing")
    parser.add_argument("--renderer", choices=["hyperframes", "ffmpeg"], default="hyperframes",
                        help="hyperframes: 30s HTML composition (default); ffmpeg: old slideshow")
    parser.add_argument("--live-only", action="store_true",
                        help="fail instead of falling back to the built-in sample tools (daily.py uses this)")
    args = parser.parse_args()

    t0 = time.perf_counter()
    print("=" * 60 + "\n saas-video-automation pipeline\n" + "=" * 60)

    if args.script:
        try:
            script = VideoScript.model_validate_json(args.script.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            print(f"✖ Invalid script file {args.script}: {exc}")
            return 1
        script = script.model_dump(mode="json")
        print(f"\nUsing script {args.script} (source={script['source']}): steps 1 and 3 skipped")
        print(f"   {script['tool_name']} — {script['website_url']}")
        print(f"   hook: \"{script['hook']}\", voiceover: {script['voiceover_words']} words "
              f"≈ {script['est_duration_sec']}s")
        tool = {"tool_name": script["tool_name"], "website_url": script["website_url"]}
        try:
            post = produce_video(tool, script, args.renderer)
        except (CaptureError, TTSError, HFBuildError) as exc:
            print(f"\n✖ Pipeline failed: {exc}")
            return 1
        return _report(post, t0)

    with Step(1, "Fetching latest SaaS/AI tools"):
        used = {h["tool"] for h in _load_history()}  # tools already turned into a Reel
        tools = fetch_latest_tools(limit=CANDIDATES, use_sample=args.sample, exclude=used)
        # A Product Hunt URL means the real site couldn't be resolved: nothing useful to film.
        candidates = [t for t in tools if "producthunt.com" not in t["website_url"]]
        for t in tools:
            mark = "  " if t in candidates else "✖ "
            print(f"   {mark}{t['tool_name']} — {t['website_url']}")
        if args.live_only:  # daily production: never post the built-in sample tools (Notion etc.)
            sample = {t["tool_name"] for t in fetch_latest_tools(limit=99, use_sample=True)}
            candidates = [t for t in candidates if t["tool_name"] not in sample]
            if not candidates:
                print("✖ No live tool from the feed (sample tools are not used in --live-only mode).")
                return 1
        if not candidates:
            print("   no candidate has its own website; falling back to sample tools")
            candidates = fetch_latest_tools(limit=CANDIDATES, use_sample=True)

    for i, tool in enumerate(candidates, 1):
        print(f"\n--- Candidate {i}/{len(candidates)}: {tool['tool_name']} ---")
        try:
            post = produce_video(tool, renderer=args.renderer)
            break
        except (CaptureError, TTSError) as exc:
            print(f"   skipping {tool['tool_name']}: {type(exc).__name__}")
    else:
        print("\n✖ Pipeline failed: no candidate could be turned into a video.")
        return 1
    return _report(post, t0)


def _report(post: dict, t0: float) -> int:
    print("\n" + "=" * 60)
    print(f"✅ Done in {time.perf_counter() - t0:.0f}s — {post['tool_name']}")
    print(f"   Video : {post['video_path']}")
    print(f"   Post  : {FINAL_PATH.parent / 'post.json'}")
    print(f"   Link  : {post['affiliate_link']}"
          + ("  (affiliate)" if post["is_affiliate"] else "  (no affiliate entry — add one in affiliates.json)"))
    print(f"   Script: {post['script_source']}" + ("  (mock — set ANTHROPIC_API_KEY in .env for Claude)"
                                                    if post["script_source"] == "mock" else ""))
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
