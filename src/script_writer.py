"""Turn a fetched SaaS / AI tool into a 15-25 second vertical Reel script.

The hook and script rules come from the reel-hook-writer skill (.claude/skills, RULES section).
Claude writes 5 hook candidates; judge_hooks() then picks the strongest in a separate call, so the
first frame and first sentence are chosen by a fresh reader, not by the writer.

Script sources, tried in order, all validated against the same Pydantic schema:
  1. Anthropic API with structured outputs (needs ANTHROPIC_API_KEY in .env)
  2. Local Claude Code CLI, `claude -p --json-schema` (uses Claude Code's login)
  3. Templated mock script, so the pipeline never blocks
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal

import unicodedata

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from fetcher import Tool
from reel_metrics import summary_for_prompt
from skill_rules import editor_lessons, skill_rules

ROOT = Path(__file__).resolve().parent.parent
MODEL = "claude-opus-5-5"
VIDEO_SECONDS = 30  # upper bound; the renderer sizes each Reel to its voiceover (about 17-25 s)
WORDS_PER_SECOND = 2.5  # ~150 wpm, a natural Edge-TTS pace
MAX_VOICEOVER_WORDS = 75  # hard limit; edge-tts AriaNeural reads ~2.0-2.5 words/s
TARGET_WORDS = (50, 62)  # asked of Claude: leaves headroom for slower-reading copy (64 words took 32s)
# Turkish words are longer: tr-TR-AhmetNeural reads ~1.7 words/s (42 words = 25.3s).
# ElevenLabs reads Turkish at ~2.3 words/s (45 words = 19.7 s): 40-50 words is a 17-22 s voice.
TARGET_WORDS_BY_LANGUAGE = {"tr": (40, 50)}
CLI_TIMEOUT = 300  # seconds per `claude -p` call
HISTORY_PATH = ROOT / "state" / "script_history.json"  # recent hooks / CTAs, so videos don't repeat
HISTORY_SIZE = 10


# Page policy: no prices. Prices, payment models (one-time, subscription) and free / paid
# claims stay out of every post. Only a paid collaboration with that brand, decided by the
# user per post, may change this.
PRICE_PATTERN = re.compile(
    r"[$€£₺]|\d\s*(?:TL|USD|EUR)\b|\b(?:dolar\w*|euro\w*|lira\w*|fiyat\w*|ücret\w*|ödeme\w*|"
    r"abonelik\w*|bedava|indirim\w*|price\w*|pricing|subscription\w*|free)\b",
    re.I,
)
NO_PRICE_RULE = ("Page policy: never mention prices, costs, currencies, payment models (one-time "
                 "payment, subscription), free vs paid, trials or discounts - not on screen, not in "
                 "the voiceover, not in the caption. Talk about what the tool does instead.")


def price_mentions(*texts: str) -> list[str]:
    """Price / payment words found in the texts (empty list = policy met)."""
    return sorted({m.group(0) for t in texts for m in PRICE_PATTERN.finditer(t or "")})


def _script_price_mentions(script: "VideoScript") -> list[str]:
    return price_mentions(script.hook, script.voiceover, script.why_it_matters, script.caption,
                          *(f"{p.title} {p.detail}" for p in script.key_points),
                          *(s.on_screen_text for s in script.shots))


# Ad language that makes a Reel read like a sponsored post (reel-hook-writer rule 8) and lines that
# promise a profile link that may not exist.
AD_PATTERN = re.compile(
    r"\byeni araç\b|\bkaçırma\w*|\bhemen (?:dene|indir|kaydol)\w*|\bşimdi indir\w*|link (?:profil|bio)\w*|"
    r"biyografi\w*|daha fazlası için takip|\b(?:denedim|kullandım|çevirdim|bitirdim|hallettim)\b",
    re.I,
)
# Brands whose name is itself the news, so a hook may open with it (rule 2).
FAMOUS_BRANDS = {"openai", "chatgpt", "google", "gemini", "apple", "meta", "anthropic", "claude", "nvidia",
                 "microsoft", "amazon", "tesla", "xai", "grok", "deepmind", "samsung"}


def _fold(text: str) -> str:
    """Lowercase ASCII letters/digits only, so "kōdlo" and "Kodlo'yu" both contain "kodlo"."""
    text = unicodedata.normalize("NFKD", text.replace("ı", "i").replace("İ", "i"))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)).lower())


def reel_rule_problems(script: "VideoScript") -> list[str]:
    """Measurable reel-hook-writer rules a draft breaks (empty list = all met)."""
    problems = []
    seg = script.voiceover_segments
    spoken = seg.hook if seg else script.voiceover.split(".")[0]
    name = _fold(script.tool_name)
    if name and len(name) >= 3 and name not in FAMOUS_BRANDS:
        if name in _fold(script.hook) or name in _fold(spoken):
            problems.append(f"the tool name '{script.tool_name}' is in the headline or the spoken hook; "
                            "lead with the outcome / pain and name the tool in point1")
        if seg and name not in _fold(seg.point1) and name not in _fold(seg.point2):
            problems.append(f"name the tool '{script.tool_name}' in point1 (with what kind of product it is)")
    if len(script.hook.split()) > 7:
        problems.append(f"headline has {len(script.hook.split())} words; max 7")
    if len(spoken.split()) > 10:
        problems.append(f"spoken hook has {len(spoken.split())} words; max 9")
    high = TARGET_WORDS_BY_LANGUAGE.get(_load_language(), TARGET_WORDS)[1]
    if (words := len(script.voiceover.split())) > high + 2:  # 55 Turkish words rendered a 29.9 s Reel (max 26)
        problems.append(f"voiceover has {words} words; max {high} - cut a sentence")
    if len(script.hook_candidates) < 3:
        problems.append("write 5 hook_candidates (one per pattern) before choosing the hook")
    texts = [script.hook, script.voiceover, script.caption, script.why_it_matters,
             *(f"{p.title} {p.detail}" for p in script.key_points)]
    if ads := sorted({m.group(0) for t in texts for m in AD_PATTERN.finditer(t or "")}):
        problems.append(f"remove ad language: {', '.join(ads)}")
    return problems


class HookCandidate(BaseModel):
    pattern: Literal["result", "pain", "question", "curiosity", "news"]
    headline: str  # on-screen, at most 7 words
    spoken: str  # first spoken sentence, 5-9 words


class Shot(BaseModel):
    start_sec: float
    end_sec: float
    type: Literal["screen_recording", "screenshot", "b_roll", "text_overlay"]
    direction: str  # what to capture / show, e.g. "Scroll the pricing page"
    on_screen_text: str  # short caption burned into the frame ("" for none)


class KeyPoint(BaseModel):
    title: str  # card headline, under 6 words
    detail: str  # one short supporting sentence, under 14 words


class VoiceSegments(BaseModel):
    """The voiceover split by scene, so the renderer can cut each scene where its part is spoken."""

    hook: str
    point1: str
    point2: str
    point3: str
    why: str
    cta: str

    def parts(self) -> list[str]:
        return [self.hook, self.point1, self.point2, self.point3, self.why, self.cta]


class ScriptDraft(BaseModel):
    """The part Claude writes. Kept simple so it maps cleanly to a JSON schema."""

    hook_candidates: list[HookCandidate] = []  # written first; the winner becomes hook + segments.hook
    hook_pattern: str = ""
    hook: str
    voiceover: str
    voiceover_segments: VoiceSegments | None = None  # when set, voiceover is their concatenation
    shots: list[Shot]
    key_points: list[KeyPoint]  # exactly 3, shown as animated cards from 3s to 20s
    why_it_matters: str  # shown from 20s to 27s
    caption: str
    hashtags: list[str]


class VideoScript(ScriptDraft):
    tool_name: str
    website_url: str
    source: Literal["claude", "claude_code", "mock"]  # claude_code: written in a Claude Code session
    model: str | None = None
    voiceover_words: int = 0
    est_duration_sec: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _fill_story_fields(cls, data):
        """Scripts written before key_points / why_it_matters existed: derive them from the shots."""
        if not isinstance(data, dict) or (data.get("key_points") and data.get("why_it_matters")):
            return data
        data = dict(data)
        texts = [s.get("on_screen_text", "") if isinstance(s, dict) else s.on_screen_text
                 for s in data.get("shots", [])]
        texts = [t for t in texts[1:-1] if t] or [t for t in texts if t] or [data.get("hook", "")]
        if not data.get("key_points"):
            data["key_points"] = [{"title": texts[min(i, len(texts) - 1)], "detail": ""} for i in range(3)]
        if not data.get("why_it_matters"):
            data["why_it_matters"] = data.get("caption", "")
        return data

    @field_validator("key_points")
    @classmethod
    def _three_points(cls, points: list[KeyPoint]) -> list[KeyPoint]:
        if len(points) != 3:
            raise ValueError(f"expected exactly 3 key_points, got {len(points)}")
        return points

    @field_validator("hashtags")
    @classmethod
    def _normalise_hashtags(cls, tags: list[str]) -> list[str]:
        cleaned = ["#" + t.strip().lstrip("#").replace(" ", "") for t in tags if t.strip()]
        if len(cleaned) > 5:  # Instagram's limit since December 2025: keep the first five
            cleaned = cleaned[:5]
        if len(cleaned) < 3:
            raise ValueError(f"expected 3-5 hashtags, got {len(cleaned)}")
        return cleaned

    @model_validator(mode="after")
    def _check_timing(self) -> "VideoScript":
        if self.voiceover_segments:
            self.voiceover = " ".join(p.strip() for p in self.voiceover_segments.parts() if p.strip())
        self.voiceover_words = len(self.voiceover.split())
        self.est_duration_sec = round(self.voiceover_words / WORDS_PER_SECOND, 1)
        if self.voiceover_words > MAX_VOICEOVER_WORDS:
            raise ValueError(
                f"voiceover has {self.voiceover_words} words; max {MAX_VOICEOVER_WORDS} for {VIDEO_SECONDS}s"
            )
        if not self.shots:
            raise ValueError("at least one shot is required")
        prev_end = 0.0
        for shot in self.shots:
            if shot.start_sec < prev_end - 0.01 or shot.end_sec <= shot.start_sec:
                raise ValueError(f"shots overlap or are out of order at {shot.start_sec}s")
            prev_end = shot.end_sec
        if prev_end > VIDEO_SECONDS + 0.5:
            raise ValueError(f"shots run to {prev_end}s; video is {VIDEO_SECONDS}s")
        return self


SYSTEM_PROMPT = f"""You write scripts for 15-25 second vertical (9:16) Instagram Reels for KAVAR (@thekavar.ai), a Turkish page about AI tools and AI news. The viewers are Turkish founders, marketers, developers and curious people; nearly all of them don't follow the page yet.

Write for the ear and the thumb: the Reel is decided in its first 2 seconds, on a muted, autoplaying first frame. Follow these rules exactly (they come from the page's hook-writer skill):

{skill_rules("reel-hook-writer")}

Fields:
- hook_candidates: FIRST write 5 candidates, one per pattern (result, pain, question, curiosity, news - for a tool that isn't news, write a second strong candidate of the best pattern instead of news). Each has: pattern, headline (on-screen, at most 7 words, no tool name) and spoken (the first spoken sentence, 5-9 words, no tool name; the headline is its core).
- hook_pattern / hook / voiceover_segments.hook: the winning candidate's pattern, headline and spoken sentence, copied exactly. Pick the one a stranger would stop for and could send to a specific person, that the tool data fully supports.
- voiceover: the full narration, in the word range the user message gives. Plain spoken sentences; no emojis, hashtags, URLs or stage directions.
- voiceover_segments: the same narration split into six parts, joined with spaces they equal the voiceover. Each scene starts when its part is spoken: hook (one sentence, about 2 s), point1 (names the tool for the first time and says what kind of product it is, then the first proof; about 3-4 s), point2 and point3 (one benefit each, about 2.5-3.5 s), why (one short sentence on why it matters to the viewer, about 2.5 s), cta (one short send/save sentence, see the rules).
- name clarity: many tools are niche and their names collide with known brands, so the sentence in point1 that names the tool also says plainly what it is ("Adı kōdlo, yapay zekâlı bir satış CRM'i.").
- key_points: exactly 3, in narration order, shown as cards while point1-3 are spoken. title under 6 words, what the viewer gets (not a bare feature name); detail one sentence under 12 words, never empty.
- why_it_matters: 1-2 short sentences (under 18 words) shown while "why" is spoken.
- shots: 4-6 consecutive shots from 0 to the end without gaps (the renderer uses the site capture; directions document intent). on_screen_text under 7 words or "".
- caption: 1-3 short sentences that add context (not a copy of the voiceover), may include 1-2 emojis, ends with a question or a send reason. No "link profilde".
- hashtags: 3-5 (Instagram allows 5), broad (#yapayzeka, #aitools) plus specific.
- Variety: the page posts daily. If the user message lists recent hooks and CTAs, don't reuse their wording or opening pattern.
- Turkish: natural, grammatical spoken Turkish (check suffixes and agreement), no word-for-word English phrasing.

Only state facts present in the tool data; if something isn't given, keep it general rather than inventing features, prices or numbers.

""" + NO_PRICE_RULE
if _lessons := editor_lessons():  # rules/editor_lessons.md: hand-fixed rejections
    SYSTEM_PROMPT += "\n\n" + _lessons


def _load_language() -> str:
    try:
        return json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("language", "en")
    except (OSError, json.JSONDecodeError):
        return "en"


def _coerce_tool(data: Tool | dict | str) -> Tool:
    """Accept a fetcher Tool, its dict form, or a JSON string of one tool."""
    if isinstance(data, Tool):
        return data
    if isinstance(data, str):
        data = json.loads(data)
    return Tool.model_validate(data)


def _has_credentials(client: anthropic.Anthropic) -> bool:
    if (client.api_key or "").endswith("..."):  # untouched .env placeholder
        return False
    return any(getattr(client, attr, None) for attr in ("api_key", "auth_token", "credentials"))


def mock_script(tool: Tool, language: str = "en") -> VideoScript:
    """Realistic templated script used when Claude isn't available."""
    if language == "tr":
        return _mock_script_tr(tool)
    name = tool.tool_name
    tag_line = tool.tag_line.rstrip(".") or f"{name} streamlines your workflow"
    slug = re.sub(r"[^A-Za-z0-9]", "", name)
    voiceover = (
        # Name and what it is in the same sentence, so niche names aren't mistaken for big brands.
        f"Still doing this the slow way? Meet {name}, a tool that does one thing well: "
        f"{tag_line[0].lower() + tag_line[1:]}. "
        f"Instead of juggling tabs and manual busywork, you open {name} and get it done in minutes. "
        f"Teams use it to move faster without adding headcount. "
        f"It takes seconds to try. Check the link in bio and see if {name} fits your stack."
    )
    shots = [
        Shot(start_sec=0, end_sec=3, type="text_overlay",
             direction="Bold full-screen title card on brand-colour background",
             on_screen_text="Stop doing this manually"),
        Shot(start_sec=3, end_sec=9, type="screen_recording",
             direction=f"Load {tool.website_url} and hold on the homepage hero section",
             on_screen_text=f"Meet {name}"),
        Shot(start_sec=9, end_sec=18, type="screen_recording",
             direction="Slowly scroll through the main features section of the homepage",
             on_screen_text="Minutes, not hours"),
        Shot(start_sec=18, end_sec=24, type="b_roll",
             direction="Generic footage of a team working on laptops in a bright office",
             on_screen_text="No extra headcount"),
        Shot(start_sec=24, end_sec=30, type="screenshot",
             direction=f"Screenshot of {name} homepage with logo centred, zoom-in effect",
             on_screen_text="Link in bio"),
    ]
    return VideoScript(
        tool_name=name,
        website_url=str(tool.website_url),
        hook="This tool kills hours of busywork",
        voiceover=voiceover,
        shots=shots,
        key_points=[
            KeyPoint(title=f"Meet {name}", detail=f"{tag_line}."),
            KeyPoint(title="Minutes, not hours", detail="Skip the tab juggling and manual busywork."),
            KeyPoint(title="No extra headcount", detail="Teams use it to move faster."),
        ],
        why_it_matters="Small teams win on speed. Tools like this give hours back every week.",
        caption=f"{name}: {tag_line} 🚀 Would you add it to your stack?",
        hashtags=["saas", "aitools", "productivity", "startup", slug.lower() or "newtool"],
        source="mock",
    )


def _mock_script_tr(tool: Tool) -> VideoScript:
    """Turkish templated script; the tag line stays in its original language."""
    name = tool.tool_name
    tag_line = tool.tag_line.rstrip(".") or name
    slug = re.sub(r"[^A-Za-z0-9]", "", name)
    voiceover = (
        f"Hâlâ bu işi elle mi yapıyorsun? {name} adlı yeni bir yazılım aracı tek bir işe odaklanıyor. "
        f"Sekmeler arasında kaybolmadan işini dakikalar içinde bitiriyorsun. "
        f"Ekipler bu sayede kadro büyütmeden daha hızlı ilerliyor. "
        f"Küçük ekipler için hız her şey. Kaydet, lazım olur."
    )
    shots = [
        Shot(start_sec=0, end_sec=3, type="text_overlay", direction="Bold title card",
             on_screen_text="Bunu hâlâ elle mi yapıyorsun?"),
        Shot(start_sec=3, end_sec=20, type="screenshot",
             direction=f"Homepage of {tool.website_url} with zoom and pan", on_screen_text=f"{name} ile tanış"),
        Shot(start_sec=20, end_sec=30, type="text_overlay", direction="Why it matters, then follow call",
             on_screen_text="Takip et"),
    ]
    return VideoScript(
        tool_name=name,
        website_url=str(tool.website_url),
        hook="Bu araç saatlerini geri veriyor",
        voiceover=voiceover,
        voiceover_segments=VoiceSegments(
            hook="Hâlâ bu işi elle mi yapıyorsun?",
            point1=f"{name} adlı yeni bir yazılım aracı tek bir işe odaklanıyor.",
            point2="Sekmeler arasında kaybolmadan işini dakikalar içinde bitiriyorsun.",
            point3="Ekipler bu sayede kadro büyütmeden daha hızlı ilerliyor.",
            why="Küçük ekipler için hız her şey.",
            cta="Kaydet, lazım olur.",
        ),
        shots=shots,
        key_points=[
            KeyPoint(title=f"{name} ile tanış", detail=tag_line),
            KeyPoint(title="Saatler değil, dakikalar", detail="Sekmeler ve elle yapılan işler arasında kaybolma."),
            KeyPoint(title="Ek kadro gerekmiyor", detail="Ekipler daha hızlı ilerliyor."),
        ],
        why_it_matters="Küçük ekipler hızla kazanır. Bu tür araçlar her hafta saatler kazandırır.",
        caption=f"{name}: {tag_line} 🚀 Sen olsan kullanır mıydın?",
        hashtags=["yapayzeka", "teknoloji", "saas", "girisim", slug.lower() or "yeniarac"],
        source="mock",
    )


def _load_history() -> list[dict]:
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))[-HISTORY_SIZE:]
    except (OSError, json.JSONDecodeError):
        return []


def _save_history(script: VideoScript) -> None:
    seg = script.voiceover_segments
    entry = {"tool": script.tool_name, "hook": script.hook, "pattern": script.hook_pattern,
             "spoken_hook": seg.hook if seg else "", "cta": seg.cta if seg else ""}
    history = (_load_history() + [entry])[-HISTORY_SIZE:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def _user_message(tool: Tool, language: str) -> str:
    low, high = TARGET_WORDS_BY_LANGUAGE.get(language, TARGET_WORDS)
    msg = (
        f"Write the video script in language code '{language}'. All on-screen text (hook, "
        f"key_points, why_it_matters) and the voiceover are in that language; the voiceover "
        f"should be {low}-{high} words.\n\n"
        f"Tool data:\n{tool.model_dump_json(indent=2)}"
    )
    if history := _load_history():
        lines = "\n".join(f'- [{h.get("pattern") or "?"}] hook: "{h["hook"]}" / spoken: "{h["spoken_hook"]}" / cta: "{h["cta"]}"'
                          for h in history)
        msg += f"\n\nRecently used in earlier videos (don't repeat their wording or opening pattern):\n{lines}"
    if results := summary_for_prompt():
        msg += "\n\n" + results
    return msg


def _ask_claude(client: anthropic.Anthropic, tool: Tool, language: str, feedback: str = "") -> VideoScript | None:
    user_msg = _user_message(tool, language) + feedback
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        output_format=ScriptDraft,
        output_config={"effort": "medium"},
        # On a safety refusal, the API re-runs the request on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        print(f"[script_writer] Claude returned stop_reason={response.stop_reason}.")
        return None
    draft: ScriptDraft = response.parsed_output
    return VideoScript(
        **draft.model_dump(),
        tool_name=tool.tool_name,
        website_url=str(tool.website_url),
        source="claude",
        model=response.model,
    )


def _inline_schema(schema: dict) -> dict:
    """Pydantic JSON schema with $refs inlined and closed objects, for `claude --json-schema`."""
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(dict(defs[node["$ref"].split("/")[-1]]))
            # Drop Pydantic's "title" labels (strings), not a property named "title" (a dict).
            node = {k: walk(v) for k, v in node.items() if not (k == "title" and isinstance(v, str))}
            if node.get("type") == "object":
                node["additionalProperties"] = False
            return node
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def _claude_cli() -> str | None:
    if os.getenv("SCRIPT_WRITER_NO_CLI"):  # opt-out, e.g. for offline tests
        return None
    return shutil.which("claude")


def _ask_claude_cli(tool: Tool, language: str, exe: str) -> VideoScript | None:
    """Write the script with the local Claude Code CLI (`claude -p`), using its own login.

    No API key needed; usage counts against the Claude plan Claude Code is signed in with.
    Tools are disabled, so the CLI can only answer, not touch files. One retry with
    the validation errors fed back if the first draft breaks the timing rules.
    """
    schema = json.dumps(_inline_schema(ScriptDraft.model_json_schema()))
    # Make the CLI use its own login: an API key in the environment (e.g. the .env
    # placeholder loaded by load_dotenv, or a key the API path just failed with)
    # would take precedence over it.
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    prompt = _user_message(tool, language)
    fallback = None
    for attempt in (1, 2):
        try:
            proc = subprocess.run(
                [exe, "-p", "--output-format", "json", "--json-schema", schema,
                 "--system-prompt", SYSTEM_PROMPT, "--tools", "", "--no-session-persistence"],
                input=prompt, capture_output=True, text=True, encoding="utf-8",
                timeout=CLI_TIMEOUT, cwd=ROOT, env=env,
            )
        except subprocess.TimeoutExpired:
            print(f"[script_writer] claude -p timed out after {CLI_TIMEOUT}s.")
            return None
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            print(f"[script_writer] claude -p failed (exit {proc.returncode}): "
                  f"{(proc.stderr or proc.stdout).strip()[:300]}")
            return None
        if out.get("is_error") or out.get("structured_output") is None:
            print(f"[script_writer] claude -p returned no script ({out.get('subtype')}: "
                  f"{str(out.get('result'))[:200]}).")
            return None
        try:
            script = VideoScript(
                **ScriptDraft.model_validate(out["structured_output"]).model_dump(),
                tool_name=tool.tool_name,
                website_url=str(tool.website_url),
                source="claude_code",
                model=next(iter(out.get("modelUsage") or {}), None),
            )
        except ValidationError as exc:
            problems = "; ".join(e["msg"] for e in exc.errors())
        else:
            if bad := _script_price_mentions(script):
                problems = f"remove every price / payment / free-or-paid mention: {', '.join(bad)}. {NO_PRICE_RULE}"
            elif rules := reel_rule_problems(script):
                fallback = fallback or script  # usable if the retry is worse; the editor still reviews it
                problems = "; ".join(rules)
            elif all(p.detail.strip() for p in script.key_points):
                return script
            else:
                fallback = script  # usable, just with empty card details
                problems = "every key_point needs a non-empty detail sentence"
        print(f"[script_writer] claude -p draft {attempt} invalid: {problems}")
        prompt += (f"\n\nYour previous draft was rejected: {problems}. "
                   f"Fix this and return the full script again.")
    return fallback


JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["scores", "best", "reason"],
    "properties": {
        "scores": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 10}},
        "best": {"type": "integer", "minimum": 0},
        "reason": {"type": "string"},
    },
}
JUDGE_SYSTEM = f"""You are the hook judge of KAVAR (@thekavar.ai), a Turkish Instagram page about AI \
tools and news. You did not write these hooks. Picture a Turkish stranger scrolling Reels with the \
sound off: the first frame shows the headline over a screenshot of the product, and the voice says \
the spoken line. Score each candidate 0-10 on: would they stop in the first second, is it instantly \
clear what it is about and what they get, does it avoid looking like an ad, could they send it to a \
specific person, is every claim supported by the tool data, is it natural Turkish. A candidate that \
breaks any rule below scores at most 3.

{skill_rules("reel-hook-writer")}

Return one score per candidate in order, the 0-based index of the best, and a one-sentence reason."""


def judge_hooks(script: dict, tool_data: dict | None = None) -> dict:
    """Let a separate Claude call pick the strongest of the script's hook candidates.

    Returns the script (as a dict) with hook / hook_pattern / voiceover_segments.hook swapped to the
    winner, plus "hook_judge" (scores and reason). Unchanged when there's nothing to judge.
    """
    cands = script.get("hook_candidates") or []
    exe = _claude_cli()
    if len(cands) < 2 or not exe or not script.get("voiceover_segments"):
        return script
    seg = script["voiceover_segments"]
    listing = "\n".join(f'{i}. [{c["pattern"]}] headline: "{c["headline"]}" / spoken: "{c["spoken"]}"'
                        for i, c in enumerate(cands))
    prompt = (f"Tool data:\n{json.dumps(tool_data or {'tool_name': script['tool_name']}, ensure_ascii=False, default=str)}"
              f"\n\nThe Reel continues after the hook with: \"{seg['point1']} {seg['point2']}\"\n\n"
              f"Hook candidates:\n{listing}")
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run(
            [exe, "-p", "--output-format", "json", "--json-schema", json.dumps(JUDGE_SCHEMA),
             "--system-prompt", JUDGE_SYSTEM, "--tools", "", "--no-session-persistence"],
            input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=CLI_TIMEOUT, cwd=ROOT, env=env)
        verdict = json.loads(proc.stdout).get("structured_output")
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        verdict = None
    if not verdict or not 0 <= verdict["best"] < len(cands):
        print("[script_writer] hook judge gave no usable verdict; keeping the writer's choice.")
        return script
    best = cands[verdict["best"]]
    trial = {**script, "hook": best["headline"], "hook_pattern": best["pattern"],
             "voiceover_segments": {**seg, "hook": best["spoken"]}}
    try:
        checked = VideoScript.model_validate(trial)
    except ValidationError as exc:
        print(f"[script_writer] judged hook doesn't validate ({exc.error_count()} errors); keeping the writer's.")
        return {**script, "hook_judge": verdict}
    if reel_rule_problems(checked) and not reel_rule_problems(VideoScript.model_validate(script)):
        return {**script, "hook_judge": verdict}
    print(f"[script_writer] hook judge picked #{verdict['best']} ({best['pattern']}): \"{best['headline']}\" "
          f"- {verdict['reason']}")
    return {**checked.model_dump(mode="json"), "hook_judge": verdict}


def generate_script(
    tool_data: Tool | dict | str,
    client: anthropic.Anthropic | None = None,
    use_mock: bool = False,
) -> dict:
    """Return a validated 30s video script for one tool as a JSON-serialisable dict.

    Source order: Anthropic API (if credentials) -> local `claude -p` (if installed) -> mock.
    """
    tool = _coerce_tool(tool_data)
    if use_mock:
        return mock_script(tool, _load_language()).model_dump(mode="json")

    load_dotenv(ROOT / ".env")
    language = _load_language()
    script = None
    client = client or anthropic.Anthropic()
    if _has_credentials(client):
        try:
            script = _ask_claude(client, tool, language)
            if script and (bad := _script_price_mentions(script)):
                print(f"[script_writer] Draft mentions prices ({', '.join(bad)}); asking again.")
                script = _ask_claude(client, tool, language,
                                     f"\n\nA previous draft broke the page policy with: {', '.join(bad)}. "
                                     + NO_PRICE_RULE)
                if script and _script_price_mentions(script):
                    script = None
            if script and (rules := reel_rule_problems(script)):
                print(f"[script_writer] Draft breaks hook rules ({'; '.join(rules)}); asking again.")
                retry = _ask_claude(client, tool, language,
                                    f"\n\nA previous draft was rejected: {'; '.join(rules)}. Fix this.")
                if retry and not _script_price_mentions(retry):
                    script = retry
        except anthropic.APIConnectionError as exc:
            print(f"[script_writer] Network error reaching Anthropic ({exc}).")
        except anthropic.APIStatusError as exc:
            print(f"[script_writer] Anthropic API error {exc.status_code}: {exc.message}.")
        except ValidationError as exc:
            print(f"[script_writer] Claude's script failed validation ({exc.error_count()} errors).")
    else:
        print("[script_writer] No Anthropic API key; trying Claude Code CLI.")

    if script is None and (exe := _claude_cli()):
        print("[script_writer] Writing script with `claude -p`...")
        script = _ask_claude_cli(tool, language, exe)

    if script is None:
        print("[script_writer] No Claude source available; using mock script.")
        return mock_script(tool, language).model_dump(mode="json")
    judged = judge_hooks(script.model_dump(mode="json"), tool.model_dump(mode="json"))
    _save_history(VideoScript.model_validate(judged))
    return judged


def generate_script_json(tool_data: Tool | dict | str, **kwargs) -> str:
    return json.dumps(generate_script(tool_data, **kwargs), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    from fetcher import fetch_latest_tools

    tools = fetch_latest_tools(limit=1)
    print(f"=== Fetched: {tools[0]['tool_name']} ({tools[0]['website_url']}) ===")

    for label, kwargs in (("Auto (Claude if configured)", {}), ("Forced mock", {"use_mock": True})):
        script = generate_script(tools[0], **kwargs)
        VideoScript.model_validate(script)  # round-trip: output must re-validate
        assert script["tool_name"] == tools[0]["tool_name"]
        print(f"\n=== {label}: source={script['source']}, "
              f"{script['voiceover_words']} words ≈ {script['est_duration_sec']}s, "
              f"{len(script['shots'])} shots ===")
        print(json.dumps(script, indent=2, ensure_ascii=False))

    # JSON-string input path
    assert generate_script(json.dumps(tools[0]), use_mock=True)["source"] == "mock"
    print("\nAll script_writer checks passed.")
