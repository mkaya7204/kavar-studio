"""Write an Instagram carousel (feed, 6-10 slides) and a story set (3-5 frames) for one tool.

Same sources as script_writer, tried in order, all validated against one Pydantic schema:
  1. Anthropic API with structured outputs (needs ANTHROPIC_API_KEY in .env)
  2. Local Claude Code CLI, `claude -p --json-schema`
  3. Templated mock built from the tool data / video script, so the pipeline never blocks

The carousel is not a copy of the video: it reuses the video script's facts and
screenshots, but is written to be saved and sent (list / step / comparison
structure). The rules come from reports/Carousel ve story görsel sistemi.md.
"""

import json
import re
import subprocess
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from fetcher import Tool
from script_writer import (CLI_TIMEOUT, MODEL, NO_PRICE_RULE, ROOT, _claude_cli, _coerce_tool, _has_credentials,
                           _inline_schema, _load_history, _load_language, price_mentions)

SLIDES = (6, 10)  # the Instagram API publishes at most 10 carousel items
STORY_FRAMES = (3, 5)
MAX_HASHTAGS = 5  # Instagram limit since December 2025
# Word budgets per slide role: (title, body, whole slide)
WORD_BUDGET = {
    "hook": (10, 14, 16),
    "context": (10, 30, 40),
    "reveal": (8, 24, 32),
    "feature": (10, 30, 40),
    "stat": (8, 20, 28),
    "compare": (8, 0, 40),
    "recap": (8, 0, 36),
    "cta": (8, 10, 18),
}
STORY_WORDS = 25
ITEM_WORDS = 7  # one checklist / comparison line

SlideRole = Literal["hook", "context", "reveal", "feature", "stat", "compare", "recap", "cta"]
Visual = Literal["none", "screenshot", "page"]


class Slide(BaseModel):
    role: SlideRole
    kicker: str  # tiny label above the title, 1-3 words ("" for none)
    title: str
    body: str  # "" for none
    accent: str  # word(s) copied verbatim from the title, drawn in the accent colour ("" for none)
    stat: str  # role "stat" only: the big figure, e.g. "3 sn" ("" otherwise; never a price)
    items: list[str]  # recap: 2-4 lines; compare: left column (the old way); else []
    items_right: list[str]  # compare: right column (with the tool); else []
    visual: Visual  # screenshot: the site's first screen; page: a section further down
    page_section: int  # visual "page": which screen of the page, 1-3 (0 otherwise)
    alt_text: str  # Turkish alt text for this slide, under 125 characters


class StoryFrame(BaseModel):
    role: Literal["hook", "fact", "poll", "link"]
    kicker: str
    title: str
    body: str
    visual: Visual
    page_section: int
    poll_options: list[str]  # role "poll": exactly 2 short answers; else []


class CarouselDraft(BaseModel):
    """The part Claude writes."""

    slides: list[Slide]
    story: list[StoryFrame]
    caption: str
    hashtags: list[str]


class CarouselScript(CarouselDraft):
    tool_name: str
    website_url: str
    source: Literal["claude", "claude_code", "mock"]
    model: str | None = None

    @field_validator("hashtags")
    @classmethod
    def _normalise_hashtags(cls, tags: list[str]) -> list[str]:
        cleaned = ["#" + t.strip().lstrip("#").replace(" ", "") for t in tags if t.strip()]
        cleaned = list(dict.fromkeys(cleaned))
        if not 3 <= len(cleaned) <= MAX_HASHTAGS:
            raise ValueError(f"expected 3-{MAX_HASHTAGS} hashtags, got {len(cleaned)}")
        return cleaned

    @model_validator(mode="after")
    def _check_structure(self) -> "CarouselScript":
        problems = carousel_problems(self)
        if problems:
            raise ValueError("; ".join(problems))
        return self


def _words(text: str) -> int:
    return len(text.split())


def carousel_problems(c: CarouselDraft) -> list[str]:
    """Editorial rules a slide set must meet before it is rendered."""
    out = []
    n = len(c.slides)
    if not SLIDES[0] <= n <= SLIDES[1]:
        out.append(f"carousel needs {SLIDES[0]}-{SLIDES[1]} slides, got {n}")
    if c.slides and c.slides[0].role != "hook":
        out.append("slide 1 must have role 'hook'")
    if c.slides and c.slides[-1].role != "cta":
        out.append("the last slide must have role 'cta'")
    if sum(s.role == "cta" for s in c.slides) > 1:
        out.append("only one 'cta' slide")
    for i, s in enumerate(c.slides, 1):
        t_max, b_max, all_max = WORD_BUDGET[s.role]
        total = _words(s.kicker) + _words(s.title) + _words(s.body) + _words(s.stat) + sum(
            _words(x) for x in s.items + s.items_right)
        if not s.title.strip():
            out.append(f"slide {i}: empty title")
        if _words(s.title) > t_max:
            out.append(f"slide {i} ({s.role}): title has {_words(s.title)} words, max {t_max}")
        if _words(s.body) > b_max:
            out.append(f"slide {i} ({s.role}): body has {_words(s.body)} words, max {b_max}")
        if total > all_max:
            out.append(f"slide {i} ({s.role}): {total} words on the slide, max {all_max}")
        if _words(s.kicker) > 3:
            out.append(f"slide {i}: kicker max 3 words")
        if s.accent and s.accent.lower() not in s.title.lower():
            out.append(f"slide {i}: accent '{s.accent}' must be copied from the title")
        if s.role == "stat" and not s.stat.strip():
            out.append(f"slide {i}: a 'stat' slide needs the stat field")
        if s.role == "recap" and not 2 <= len(s.items) <= 4:
            out.append(f"slide {i}: recap needs 2-4 items")
        if s.role == "compare" and not (2 <= len(s.items) <= 4 and len(s.items) == len(s.items_right)):
            out.append(f"slide {i}: compare needs 2-4 items on each side, same count")
        for x in s.items + s.items_right:
            if _words(x) > ITEM_WORDS:
                out.append(f"slide {i}: item '{x}' is over {ITEM_WORDS} words")
        if s.visual == "page" and not 1 <= s.page_section <= 3:
            out.append(f"slide {i}: visual 'page' needs page_section 1-3")
        if len(s.alt_text) > 125:
            out.append(f"slide {i}: alt_text over 125 characters")
    texts = [c.caption, *c.hashtags]
    for s in c.slides:
        texts += [s.kicker, s.title, s.body, s.stat, s.alt_text, *s.items, *s.items_right]
    for f in c.story:
        texts += [f.kicker, f.title, f.body, *f.poll_options]
    if bad := price_mentions(*texts):
        out.append(f"page policy, no prices: remove every price / payment / free-or-paid mention "
                   f"({', '.join(bad)})")
    m = len(c.story)
    if not STORY_FRAMES[0] <= m <= STORY_FRAMES[1]:
        out.append(f"story needs {STORY_FRAMES[0]}-{STORY_FRAMES[1]} frames, got {m}")
    if c.story and c.story[0].role != "hook":
        out.append("story frame 1 must have role 'hook'")
    if c.story and c.story[-1].role != "link":
        out.append("the last story frame must have role 'link'")
    for i, f in enumerate(c.story, 1):
        words = _words(f.kicker) + _words(f.title) + _words(f.body)
        if words > STORY_WORDS:
            out.append(f"story frame {i}: {words} words, max {STORY_WORDS}")
        if f.role == "poll" and (len(f.poll_options) != 2 or any(_words(o) > 3 for o in f.poll_options)):
            out.append(f"story frame {i}: a poll needs exactly 2 options of 1-3 words")
        if f.visual == "page" and not 1 <= f.page_section <= 3:
            out.append(f"story frame {i}: visual 'page' needs page_section 1-3")
    return out


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _norm_number(s: str) -> str:
    return s.replace(",", ".")


def unsupported_numbers(c: CarouselDraft, source_text: str) -> list[str]:
    """Figures on slides that don't appear in the tool data / video script (no invented numbers)."""
    known = {_norm_number(n) for n in _NUMBER.findall(source_text)}
    def kicker(k: str) -> str:  # "01", "02": step numbers, not facts
        return "" if re.fullmatch(r"\s*\d{1,2}\s*", k) else k

    texts = []
    for s in c.slides:
        texts += [kicker(s.kicker), s.title, s.body, s.stat, *s.items, *s.items_right]
    for f in c.story:
        texts += [kicker(f.kicker), f.title, f.body, *f.poll_options]
    found = {_norm_number(n) for t in texts for n in _NUMBER.findall(t)}
    return sorted(found - known)


SYSTEM_PROMPT = f"""You are the editor and designer of a Turkish Instagram page about AI tools and \
tech news. The page already posts a 30-second Reel about each tool. You now write the matching \
feed carousel ({SLIDES[0]}-{SLIDES[1]} slides, 1080x1350) and story set ({STORY_FRAMES[0]}-{STORY_FRAMES[1]} \
frames, 1080x1920) for the same tool. Templates render your text; you choose each slide's role.

Why carousels: Reels bring new people, carousels earn saves and DM sends from people who already \
follow. So the carousel is not the Reel's captions again. Make it a reference worth saving: \
concrete steps, features as benefits, a before/after comparison, a recap. One idea per slide.

Slide roles (pick per slide; vary them, never two identical roles in a row except feature):
- hook (slide 1 only): the cover. A concrete outcome or a question the carousel answers, max 8 \
words ideally (hard max 10). It must work as a small grid tile. kicker: 1-2 words such as "YENİ \
ARAÇ" or the category. body: optional one-line promise (max 14 words total on the slide with \
kicker). visual: usually "screenshot" (the tool's site appears on a phone next to the title).
- context: slide 2, a second hook that also works alone: the problem / situation the viewer knows.
- reveal: the tool appears: title = what it does for you; body = what kind of product it is and \
its platform, in one sentence (names can collide with big brands, so say plainly what it is). \
visual "screenshot".
- feature: one feature or one step, benefit first. title max 10 words, body max 30 words. visual \
"page" with page_section 1-3 to show a part of the site further down, or "none".
- stat: one big figure from the tool data (time, count, size; never a price) in `stat`, and title explains it. \
Only when the data has a real figure.
- compare: items = the old way (2-4 short lines), items_right = with the tool (same count). title \
is the headline of the comparison.
- recap: 2-4 short checklist lines summing up why it matters.
- cta (last slide only): one natural ask that fits a saveable post: "Kaydet, lazım olur", "Bunu \
bilmesi gereken birine gönder", or a comment question. Never "Daha fazlası için takip et". The \
template adds the page's handle and follow line itself.
Recommended arc: hook, context, reveal, 2-4 feature/stat/compare, recap, cta (7-10 slides).

Text rules (the renderer measures every slide and rejects overflow; long text gets sent back):
- Turkish, natural and grammatical, spoken style, "sen" form. Short words beat long words.
- No emojis on slides. No hashtags on slides. No URLs on slides (the template shows the domain).
- accent: 1-3 words copied exactly from the title that carry the payoff; drawn in neon.
- body: mark the 1-2 phrases a skimming reader must not miss with **double asterisks**; they \
are drawn bold in neon. Never mark a whole sentence.
- Never invent figures. Every number on a slide must appear in the tool data or the video script.
- alt_text: per slide, under 125 characters: the slide's message plus what is shown.
- If recent hooks are listed, don't reuse their wording or opening pattern.

Story set: frame 1 role "hook" (the strongest line; exit rate is highest here), then 1-2 "fact" \
frames (one fact each, with a visual), optionally one "poll" frame (title = the question, \
poll_options = 2 short answers; the user adds Instagram's poll sticker by hand over an empty \
area), and the last frame role "link" (title invites to tap the link sticker the user adds by \
hand, body says what they get). Max {STORY_WORDS} words per frame.

caption: the post text. First line repeats the hook with a Turkish keyword people search for \
(Google indexes these posts). 2-4 short lines, 0-2 emojis, ends with the same ask as the cta slide.
hashtags: 3-{MAX_HASHTAGS} targeted ones (Turkish and English mix), e.g. #yapayzeka #aiaraçları.

Field rules: fill every field; use "" or [] or 0 when a field doesn't apply to the role.

""" + NO_PRICE_RULE


def _source_text(tool: Tool, video_script: dict | None) -> str:
    text = tool.model_dump_json()
    if video_script:
        text += "\n" + json.dumps({k: video_script.get(k) for k in
                                   ("hook", "voiceover", "key_points", "why_it_matters", "caption")},
                                  ensure_ascii=False)
    return text


def _user_message(tool: Tool, video_script: dict | None, language: str) -> str:
    msg = (f"Write the carousel and story set in language code '{language}'.\n\n"
           f"Tool data:\n{tool.model_dump_json(indent=2)}")
    if video_script:
        reel = {k: video_script.get(k) for k in ("hook", "voiceover", "key_points", "why_it_matters")}
        msg += ("\n\nThe Reel already posted about this tool (reuse its facts, don't copy its lines):\n"
                + json.dumps(reel, ensure_ascii=False, indent=2))
    if history := _load_history():
        lines = "\n".join(f'- "{h["hook"]}"' for h in history)
        msg += f"\n\nRecently used hooks (don't repeat their wording or opening pattern):\n{lines}"
    return msg


def _finish(draft: dict, tool: Tool, source: str, model: str | None, source_text: str) -> CarouselScript:
    """Validate a draft; raises ValueError listing every problem (fed back to Claude)."""
    try:
        script = CarouselScript(**draft, tool_name=tool.tool_name, website_url=str(tool.website_url),
                                source=source, model=model)
    except ValidationError as exc:
        raise ValueError("; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())) from exc
    if bad := unsupported_numbers(script, source_text):
        raise ValueError(f"these figures are not in the tool data or video script, remove or fix them: "
                         f"{', '.join(bad)}")
    return script


def _ask_api(client: anthropic.Anthropic, prompt: str, system: str, fmt: type[BaseModel]) -> tuple[dict | None, str | None]:
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=fmt,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        print(f"[carousel_writer] Claude returned stop_reason={response.stop_reason}.")
        return None, None
    return response.parsed_output.model_dump(), response.model


def _ask_cli(exe: str, prompt: str, system: str, fmt: type[BaseModel]) -> tuple[dict | None, str | None]:
    import os

    schema = json.dumps(_inline_schema(fmt.model_json_schema()))
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run(
            [exe, "-p", "--output-format", "json", "--json-schema", schema,
             "--system-prompt", system, "--tools", "", "--no-session-persistence"],
            input=prompt, capture_output=True, text=True, encoding="utf-8",
            timeout=CLI_TIMEOUT, cwd=ROOT, env=env,
        )
        out = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        print(f"[carousel_writer] claude -p timed out after {CLI_TIMEOUT}s.")
        return None, None
    except json.JSONDecodeError:
        print(f"[carousel_writer] claude -p failed (exit {proc.returncode}): "
              f"{(proc.stderr or proc.stdout).strip()[:300]}")
        return None, None
    if out.get("is_error") or out.get("structured_output") is None:
        print(f"[carousel_writer] claude -p returned no carousel ({out.get('subtype')}).")
        return None, None
    return out["structured_output"], next(iter(out.get("modelUsage") or {}), None)


def _ask(prompt: str, system: str = SYSTEM_PROMPT,
         fmt: type[BaseModel] = CarouselDraft) -> tuple[dict | None, str | None, str]:
    """One Claude call through the first available source -> (draft, model, source)."""
    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    if _has_credentials(client):
        try:
            draft, model = _ask_api(client, prompt, system, fmt)
            if draft:
                return draft, model, "claude"
        except (anthropic.APIConnectionError, anthropic.APIStatusError, ValidationError) as exc:
            print(f"[carousel_writer] Anthropic API failed: {type(exc).__name__}: {exc}"[:300])
    if exe := _claude_cli():
        print("[carousel_writer] Writing with `claude -p`...")
        draft, model = _ask_cli(exe, prompt, system, fmt)
        if draft:
            return draft, model, "claude_code"
    return None, None, "mock"


def generate_carousel(tool_data: Tool | dict | str, video_script: dict | None = None,
                      use_mock: bool = False, attempts: int = 3) -> dict:
    """Return a validated carousel + story script as a JSON-serialisable dict.

    Drafts that break the editorial rules are sent back with the problems listed.
    """
    tool = _coerce_tool(tool_data)
    language = _load_language()
    source_text = _source_text(tool, video_script)
    if not use_mock:
        prompt = _user_message(tool, video_script, language)
        for attempt in range(1, attempts + 1):
            draft, model, source = _ask(prompt)
            if draft is None:
                break
            try:
                return _finish(draft, tool, source, model, source_text).model_dump(mode="json")
            except ValueError as exc:
                print(f"[carousel_writer] draft {attempt} rejected: {str(exc)[:400]}")
                prompt = _revision_prompt(prompt, draft, str(exc))
    print("[carousel_writer] No Claude draft passed; using the mock carousel.")
    return mock_carousel(tool, video_script).model_dump(mode="json")


def _revision_prompt(prompt: str, draft: dict, problems: str) -> str:
    return (f"{prompt}\n\nYour previous draft:\n{json.dumps(draft, ensure_ascii=False)}\n\n"
            f"It was rejected: {problems}\nFix exactly these problems, keep what works, and "
            f"return the full carousel again.")


def revise_carousel(script: dict, problems: list[str], tool_data: Tool | dict | str,
                    video_script: dict | None = None) -> dict | None:
    """Ask Claude to rewrite slides the renderer measured as broken (overflow, too small...).

    Returns the new validated script, or None if no Claude source could fix it.
    """
    tool = _coerce_tool(tool_data)
    draft = CarouselDraft.model_validate(script).model_dump()
    prompt = _revision_prompt(
        _user_message(tool, video_script, _load_language()), draft,
        "after rendering, these slides don't fit the design: " + "; ".join(problems)
        + ". Shorten the text of those slides (shorter words, fewer words); never just delete the idea.")
    draft2, model, source = _ask(prompt)
    if draft2 is None:
        return None
    try:
        return _finish(draft2, tool, source, model, _source_text(tool, video_script)).model_dump(mode="json")
    except ValueError as exc:
        print(f"[carousel_writer] revision rejected: {str(exc)[:300]}")
        return None


def mock_carousel(tool: Tool, video_script: dict | None = None) -> CarouselScript:
    """Templated carousel from the video script's points (or the tool data), so a run never blocks."""
    name = tool.tool_name
    vs = video_script or {}
    points = vs.get("key_points") or [{"title": f"{name} ile tanış", "detail": tool.tag_line}]
    hook = vs.get("hook") or f"{name} ne işe yarıyor?"

    def cut(text: str, n: int) -> str:
        return " ".join(str(text).split()[:n])

    slides = [
        Slide(role="hook", kicker="YENİ ARAÇ", title=cut(hook, 10), body="", accent="", stat="",
              items=[], items_right=[], visual="screenshot", page_section=0,
              alt_text=cut(f"Kapak: {hook}", 20)[:124]),
        Slide(role="reveal", kicker="TANIŞ", title=cut(f"{name} ne yapıyor?", 8),
              body=cut(tool.tag_line, 24), accent="", stat="", items=[], items_right=[],
              visual="screenshot", page_section=0, alt_text=f"{name} sitesinin ilk ekranı"[:124]),
    ]
    for i, p in enumerate(points[:4], 1):
        slides.append(Slide(role="feature", kicker=f"{i:02d}", title=cut(p["title"], 10),
                            body=cut(p.get("detail", ""), 30), accent="", stat="", items=[], items_right=[],
                            visual="page" if i <= 3 else "none", page_section=min(i, 3),
                            alt_text=cut(p["title"], 18)[:124]))
    recap_items = [cut(p["title"], ITEM_WORDS) for p in points[:4]]
    if len(recap_items) >= 2:
        slides.append(Slide(role="recap", kicker="ÖZET", title="Kısaca", body="", accent="", stat="",
                            items=recap_items, items_right=[], visual="none", page_section=0,
                            alt_text="Özet listesi"))
    while len(slides) < SLIDES[0] - 1:
        slides.append(Slide(role="context", kicker="NEDEN", title="Neden önemli?",
                            body=cut(vs.get("why_it_matters") or tool.description, 30), accent="", stat="",
                            items=[], items_right=[], visual="none", page_section=0,
                            alt_text="Neden önemli"))
    slides.append(Slide(role="cta", kicker="", title="Kaydet, lazım olur", body="", accent="lazım olur",
                        stat="", items=[], items_right=[], visual="none", page_section=0,
                        alt_text="Kaydet çağrısı"))
    story = [
        StoryFrame(role="hook", kicker="YENİ ARAÇ", title=cut(hook, 10), body="", visual="screenshot",
                   page_section=0, poll_options=[]),
        StoryFrame(role="fact", kicker="01", title=cut(points[0]["title"], 10),
                   body=cut(points[0].get("detail", ""), 12), visual="page", page_section=1, poll_options=[]),
        StoryFrame(role="poll", kicker="SENCE", title="Bunu kullanır mıydın?", body="", visual="none",
                   page_section=0, poll_options=["Evet", "Hayır"]),
        StoryFrame(role="link", kicker="DETAYLAR", title="Linke dokun, kendin dene",
                   body=cut(f"{name} sitesi bir dokunuş uzakta.", 12), visual="none", page_section=0,
                   poll_options=[]),
    ]
    return CarouselScript(slides=slides, story=story,
                          caption=f"{hook}\n{name}: {tool.tag_line}\nKaydet, lazım olur.",
                          hashtags=["#yapayzeka", "#aiaraçları", "#teknoloji"],
                          tool_name=name, website_url=str(tool.website_url), source="mock")
