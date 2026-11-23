"""D-90 (user 2026-11-23: "bir takım notlarla dikkat edilmesini beklemek büyük bir hata ... kodla ... katmanlar
oluştur ... sınır sistemleri"): the agent's most repeated fixes become gates in code, before any voice or render.

The fixing agent's 56 sessions (state/agent_log.jsonl, 10-24..11-23) fixed the same few causes again and again:
the hook promised what no picture shows (14), a picture that is never proof (12: video stills, faces, mascots, logos,
header / stock photos, blank shells), money in a picture (7), claims, dates and limits the source does not state (13),
a topic with no usable picture or no AI (8). Lessons in a prompt did not stop them: the 07:30 guide Reel took the
page's FIRST picture as proof without anyone looking at it, and the writer never saw the pictures at all.

Layer 1, inspect(): one look at all candidate pictures. Each gets a kind, money yes/no, readable yes/no and one
  sentence of what it shows. Only product screens, outputs, diagrams and readable text panels without money can be
  proof or a shot (usable()); the code decides, not a prompt.
Layer 2, the caller drops the topic when no picture is usable, before a script is written.
Layer 3, menu(): the writer gets the usable pictures, numbered, with what each shows, and the proof first.
Layer 4, check(): after the script is written (and the hook judged), a separate call names the picture that proves
  the headline and copies, for every claim, the source's own words. Code then checks: the headline is proven by a
  usable picture (the proof is moved to it), every quote really is in the source, no date / weekday / year the
  source doesn't have. Problems go back to the writer once; still failing = the topic is dropped, unrendered.
Layer 5 (agent_tools.render): the fixing agent can't put a picture the gate rejected under the hook or in a shot.
"""

import difflib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

PROOF_KINDS = ("output", "product_ui", "diagram", "text_panel")  # best first
NEVER = ("video_still", "person", "mascot", "logo", "header_photo", "stock_photo", "blank", "other_brand", "tiny_page")
KINDS = PROOF_KINDS + NEVER
TIMEOUT = 300
MAX_PICTURES = 12

INSPECT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["pictures"],
    "properties": {"pictures": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["index", "kind", "money", "readable", "shows"],
        "properties": {"index": {"type": "integer"}, "kind": {"type": "string", "enum": list(KINDS)},
                       "money": {"type": "string"}, "readable": {"type": "boolean"}, "shows": {"type": "string"}}}}},
}
INSPECT_PROMPT = """Open {sheet} with the Read tool. It shows {count} numbered pictures (0-{last}) from the pages \
about: {topic}. They are candidates for an Instagram Reel's proof picture (under the headline) and its shots.
For EVERY picture give:
- kind, exactly one of:
  output = something the product made (a generated image, an answer, a result);
  product_ui = the product's own interface showing the feature with real content;
  diagram = a clear chart or workflow diagram of the feature;
  text_panel = a readable block of the page's own text that states what the feature does;
  video_still = a frame of a video (a play button, a presenter, subtitles, a title card);
  person = a person or a face is the main thing;
  mascot = a mascot, character or illustration;
  logo = a logo, a name bar, a badge or an app icon;
  header_photo = the article's header / banner / badge collage / slogan card;
  stock_photo = a lifestyle or stock photo with no product in it;
  blank = empty, mostly blank, an empty app shell or form, a gradient;
  other_brand = another company's product or work;
  tiny_page = a whole page shrunk or slanted so its text can't be read on a phone.
- money: every currency sign, amount, price, "free", "trial", "pricing", "tip", "credit card" you can read in it, \
however small (axes, sample charts, tables), copied; "" if none.
- readable: whether its important text can be read on a phone screen.
- shows: one plain English sentence: what the picture literally shows (not what the article says)."""

CHECK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["hook_picture", "claims"],
    "properties": {
        "hook_picture": {"type": "integer"},
        "claims": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["claim", "source_quote"],
            "properties": {"claim": {"type": "string"}, "source_quote": {"type": "string"}}}}},
}
CHECK_PROMPT = """You check a Turkish Instagram Reel script BEFORE it is voiced. You did not write it.

PICTURES the viewer sees (number: what it literally shows):
{pictures}

SOURCE (the only truth):
<source>
{source}
</source>

SCRIPT
headline: {hook}
spoken hook: {spoken}
voiceover: {voiceover}
cards: {cards}
why it matters: {why}
caption: {caption}

1. hook_picture: the number of the picture that SHOWS what the headline and spoken hook promise, so a viewer \
believes it at a glance. -1 if no picture shows it (a picture of something else, or only the article saying it, is -1).
2. claims: every factual statement in the voiceover, cards, why it matters and caption (a feature, what it does, a \
limit, a country / device / plan, a date or time, a number, a benefit, a comparison, a description of the product or \
company). For each: claim = the Turkish statement, short; source_quote = the exact words from SOURCE that state it, \
copied character for character (4-30 words), or "" when the source does not state it. Opinions, the closing call to \
action and the product's name alone are not claims."""

DATE_WORDS = re.compile(
    r"\b(?:ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık|pazartesi|salı|çarşamba|"
    r"perşembe|cuma|cumartesi|pazar(?=\s|$|[.,!?])|20[2-3]\d)\w*", re.I)
EN_DATES = {"ocak": "january", "şubat": "february", "mart": "march", "nisan": "april", "mayıs": "may",
            "haziran": "june", "temmuz": "july", "ağustos": "august", "eylül": "september", "ekim": "october",
            "kasım": "november", "aralık": "december", "pazartesi": "monday", "salı": "tuesday",
            "çarşamba": "wednesday", "perşembe": "thursday", "cuma": "friday", "cumartesi": "saturday",
            "pazar": "sunday"}
AI_WORDS = re.compile(r"\bAI\b|\bagents?\b|\bGPT|ChatGPT|Claude|Gemini|\bLLM|artificial intelligence|machine learning|"
                      r"\bmodel\b|yapay zek", re.I)
AI_TAGS = {"yapayzeka", "yapayzekâ", "ai", "aitools", "yapayzekaaraçları", "yapayzekaaraclari", "artificialintelligence"}


def _claude() -> str | None:
    return None if os.getenv("SCRIPT_WRITER_NO_CLI") else shutil.which("claude")


def _run(prompt: str, schema: dict, tools: str, cwd: Path | None, stage: str) -> dict | None:
    from claude_usage import record as record_usage

    exe = _claude()
    if not exe:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    args = [exe, "-p", "--output-format", "json", "--json-schema", json.dumps(schema), "--tools", tools]
    if tools:
        args += ["--allowedTools", tools]
    try:
        proc = subprocess.run(args + ["--no-session-persistence"], input=prompt, capture_output=True, text=True,
                              encoding="utf-8", timeout=TIMEOUT, cwd=cwd, env=env)
        record_usage(stage, proc.stdout)
        return json.loads(proc.stdout).get("structured_output") or None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


# ---- layer 1 / 2: what each picture is ----------------------------------------------------------------------------

def _sheet(paths: list[str], out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageOps

    tile = (480, 400)
    sheet = Image.new("RGB", (tile[0] * 2, (tile[1] + 10) * ((len(paths) + 1) // 2)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, p in enumerate(paths):
        x, y = (i % 2) * tile[0], (i // 2) * (tile[1] + 10)
        try:
            with Image.open(p) as img:
                sheet.paste(ImageOps.pad(img.convert("RGB"), tile, color=(235, 235, 235)), (x, y))
        except OSError:
            pass
        draw.rectangle((x, y, x + 54, y + 44), fill="red")
        draw.text((x + 18, y + 10), str(i), fill="white")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=85)
    return out


def inspect(paths: list[str], folder: Path, topic: str) -> list[dict] | None:
    """One entry per picture, in order: {path, kind, money, readable, shows}. None when nobody answered (the caller
    then keeps its old order and logs it; the editor still reviews)."""
    paths = [str(p) for p in paths][:MAX_PICTURES]
    if not paths:
        return []
    sheet = _sheet(paths, folder / "_picture_check.jpg")
    out = _run(INSPECT_PROMPT.format(sheet=sheet.name, count=len(paths), last=len(paths) - 1, topic=topic[:200]),
               INSPECT_SCHEMA, "Read", sheet.parent, "picture_check")
    if not out:
        return None
    by_index = {p.get("index"): p for p in out.get("pictures", []) if isinstance(p, dict)}
    infos = []
    for i, path in enumerate(paths):
        p = by_index.get(i) or {"kind": "blank", "money": "", "readable": False, "shows": "(not described)"}
        infos.append({"path": path, "kind": p.get("kind", "blank"), "money": str(p.get("money") or "").strip(),
                      "readable": bool(p.get("readable")), "shows": str(p.get("shows") or "")[:300]})
    return infos


def usable(info: dict) -> bool:
    """Code decides what may be proof or a shot (the agent's 12 + 7 fixes): a proof kind, readable, no money."""
    from script_writer import price_mentions

    return (info.get("kind") in PROOF_KINDS and bool(info.get("readable")) and not info.get("money")
            and not price_mentions(info.get("shows", "")))


def order(infos: list[dict]) -> list[dict]:
    """The usable pictures, best kind first (an output or the product's screen before a diagram or text)."""
    return sorted((i for i in infos if usable(i)), key=lambda i: PROOF_KINDS.index(i["kind"]))


def reasons(infos: list[dict]) -> str:
    """Why each picture was refused, for the log."""
    return "; ".join(f"{Path(i['path']).name}: {i['kind']}" + (f", money '{i['money'][:30]}'" if i.get("money") else "")
                     + ("" if i.get("readable") else ", unreadable") for i in infos if not usable(i))


def menu(pictures: list[dict]) -> str:
    """Layer 3: what the writer must write from."""
    lines = "\n".join(f"{n}. {'(UNDER THE HEADLINE) ' if n == 0 else ''}{p['shows']}" for n, p in enumerate(pictures))
    return ("PICTURES THE VIEWER WILL SEE (chosen before you write; numbered, 0 is under the headline):\n" + lines +
            "\nWrite the headline and the spoken hook ONLY about what picture 0 shows. Each point must be about "
            "something a picture above shows or the source states; a feature no picture shows is at most a short side "
            "line, never the hook.")


# ---- layer 4: the written script against its pictures and its source ----------------------------------------------

def _norm(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^\w']+", " ", text).strip()


def in_source(quote: str, source: str) -> bool:
    q, s = _norm(quote), _norm(source)
    if len(q.split()) < 3:
        return False
    if q in s:
        return True
    m = difflib.SequenceMatcher(None, s, q, autojunk=False).find_longest_match(0, len(s), 0, len(q))
    return m.size >= 0.85 * len(q)


def date_problems(texts: list[str], source: str) -> list[str]:
    """A month, weekday or year in the script that the source doesn't have (opera 11-19, elevenlabs 11-23)."""
    low = source.lower()
    bad = []
    for t in texts:
        for m in DATE_WORDS.finditer(t or ""):
            word = m.group(0).lower()
            stem = next((k for k in EN_DATES if word.startswith(k)), None)
            if stem and (stem in low or EN_DATES[stem] in low):
                continue
            if not stem and word[:4] in low:
                continue
            bad.append(m.group(0))
    return [f"remove the date / day '{w}': the source doesn't give it" for w in sorted(set(bad))]


def drop_ai_tags(script: dict, source: str) -> dict:
    """#yapayzeka / #aitools only when the source itself says AI (any-video-to-text 11-07, sequence 11-08)."""
    if AI_WORDS.search(source):
        return script
    tags = [t for t in script.get("hashtags", []) if t.lstrip("#").lower() not in AI_TAGS]
    return {**script, "hashtags": tags} if tags != script.get("hashtags") else script


def check(script: dict, pictures: list[dict], source: str) -> tuple[list[str], int]:
    """Problems with the script (empty = it passes) and the index of the picture that proves the headline (0 = the
    proof as chosen). With no answer from Claude only the code checks run (logged by the caller)."""
    seg = script.get("voiceover_segments") or {}
    cards = " | ".join(f"{p.get('title', '')}: {p.get('detail', '')}" for p in script.get("key_points", []))
    texts = [script.get("hook", ""), script.get("voiceover", ""), cards, script.get("why_it_matters", ""),
             script.get("caption", "")]
    problems = date_problems(texts, source)
    if not pictures:
        return problems, 0
    listing = "\n".join(f"{n}. {p['shows']}" for n, p in enumerate(pictures))
    out = _run(CHECK_PROMPT.format(pictures=listing, source=source[:8000], hook=script.get("hook", ""),
                                   spoken=seg.get("hook", ""), voiceover=script.get("voiceover", ""), cards=cards,
                                   why=script.get("why_it_matters", ""), caption=script.get("caption", "")),
               CHECK_SCHEMA, "", None, "claim_check")
    if not out:
        print("   [gate] no answer from the claim check: code checks only")
        return problems, 0
    proof = out.get("hook_picture", -1)
    if not isinstance(proof, int) or not 0 <= proof < len(pictures):
        shown = "; ".join(f"{n}: {p['shows']}" for n, p in enumerate(pictures))
        problems.append(f"the headline '{script.get('hook', '')}' promises something no picture shows. Write the "
                        f"headline and spoken hook about what picture 0 shows ({shown})")
        proof = 0
    for c in out.get("claims", []):
        quote = str(c.get("source_quote") or "")
        if not quote or not in_source(quote, source):
            problems.append(f"'{str(c.get('claim', ''))[:120]}' is not in the source: remove it or use the source's "
                            "own words")
    return problems, proof
