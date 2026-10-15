""""Biz denedik": run the news' new model ourselves on a free endpoint and show what it made.

When a news article announces a model that can be run for free today, it gets a fixed
test (Turkish questions for language models, two prompts for image models) and its real
outputs become extra figures of the news carousel, credited "KAVAR denemesi". Free routes:
  - language models: OpenRouter's ':free' variants (OPENROUTER_API_KEY from a free account)
  - image models: the model's public Hugging Face Space through gradio_client
    (HF_TOKEN optional: a free account gets more daily GPU time than anonymous calls)
Nothing runnable for free -> None, and the carousel is made exactly as before.
Outputs are never edited: an answer card shows the model's text as returned (cut with "…").

    python src/model_trial.py <article.json>     # try it on a captured article
"""

import json
import os
import re
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Literal

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "templates" / "hyperframes_news" / "assets" / "fonts"
OPENROUTER = "https://openrouter.ai/api/v1"
HF_API = "https://huggingface.co/api/spaces"
BG, PANEL, NEON, INK, MUTED = "#04060c", "#0a101e", "#1fd5ff", "#f4f8ff", "#a9b8d0"

# The same test every time, so models can be compared with each other.
LLM_TESTS = [
    {"prompt": "\"Damlaya damlaya göl olur\" atasözünü 10 yaşındaki bir çocuğa iki cümleyle açıkla.",
     "check": "a correct, natural Turkish explanation in two sentences"},
    {"prompt": "Bir trende 3 vagon var, her vagonda 42 koltuk var. İki vagon tamamen dolu, üçüncüsü "
               "yarı dolu. Trende kaç yolcu var? Kısa açıkla.",
     "check": "the correct answer is 105 (42 + 42 + 21)"},
]
IMAGE_TESTS = [
    "A cinematic photo of a simit seller on the Galata Bridge in Istanbul at sunrise, seagulls, "
    "the Bosphorus in the background. No signs, no written text, no prices, no logos",
    "A rainy street at night with a neon shop sign that reads \"KAVAR\" in large letters. No other "
    "readable text, no prices, no logos",
]


class TrialPick(BaseModel):
    kind: Literal["llm", "image", "none"]
    model_name: str  # as the article names it, e.g. "Gemma 4"
    search_terms: list[str]  # 1-3 short lowercase names to find it, e.g. ["gemma-4", "gemma 4"]


PICK_SYSTEM = """You decide whether a news article announces one specific new AI model that \
anyone could run and test today: a language model (chat / text) or an image generation model. \
kind "llm" or "image" only for such a model release (open weights, a public demo or an API). \
kind "none" for company news, funding, partnerships, hardware, policy, research without a model, \
apps and agents that are not a model, and video, music or speech models. search_terms: 1-3 short \
lowercase forms of the model's name as it would appear in a model id ("gemma-4", "gemma 4"); \
[] for none."""


class Testable(BaseModel):
    indices: list[int]  # 0-based indices of the candidates that announce a testable model, best first


def testable_first(candidates: list[dict]) -> list[dict]:
    """The day's news candidates with likely testable model releases moved to the front
    (one Claude call on titles + summaries); the order is unchanged if the call fails."""
    from carousel_writer import _ask

    if not candidates:
        return candidates
    listing = "\n".join(f"{i}. [{c['source']}] {c['title']} - {c.get('summary', '')[:300]}"
                        for i, c in enumerate(candidates))
    try:
        draft, _, _ = _ask(listing, PICK_SYSTEM + "\n\nYou get a numbered list of news items instead of one "
                           "article. Return the indices of the items that are such a model release "
                           "(kind llm or image), best first; [] if none.", Testable)
    except Exception as exc:  # noqa: BLE001
        print(f"[trial] ranking failed: {type(exc).__name__}")
        return candidates
    picked = [i for i in dict.fromkeys((draft or {}).get("indices", [])) if 0 <= i < len(candidates)]
    return [candidates[i] for i in picked] + [c for i, c in enumerate(candidates) if i not in picked]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / ("seguibl.ttf" if bold else "seguisb.ttf")), size)


def _pick(article: dict) -> TrialPick | None:
    from carousel_writer import _ask

    prompt = f"Title: {article['title']}\nSource: {article['publisher']}\n\n{article['text'][:6000]}"
    draft, _, _ = _ask(prompt, PICK_SYSTEM, TrialPick)
    return TrialPick(**draft) if draft else None


# --- language models (OpenRouter free variants) -------------------------------------------------

def _free_llm(terms: list[str]) -> str | None:
    models = requests.get(f"{OPENROUTER}/models", timeout=20).json()["data"]
    keys = [_norm(t) for t in terms if _norm(t)]
    hits = [m["id"] for m in models if m["id"].endswith(":free")
            and any(k in _norm(m["id"]) or k in _norm(m.get("name", "")) for k in keys)]
    return min(hits, key=len) if hits else None  # the shortest id is the base model, not a variant


def _ask_llm(model: str, prompt: str) -> str | None:
    r = requests.post(f"{OPENROUTER}/chat/completions", timeout=120,
                      headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
                      json={"model": model, "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 600})
    if r.status_code != 200:
        print(f"[trial] {model}: HTTP {r.status_code} {r.text[:200]}")
        return None
    text = (r.json()["choices"][0]["message"].get("content") or "").strip()
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip() or None


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines = []
    for para in text.replace("**", "").replace("#", "").splitlines() or [""]:
        line = ""
        for word in para.split():
            test = f"{line} {word}".strip()
            if draw.textlength(test, font=font) <= width:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def _answer_card(model: str, prompt: str, answer: str, path: Path) -> Path:
    """A 1080x1080 card: our question, then the model's answer as returned."""
    img = Image.new("RGB", (1080, 1080), BG)
    d = ImageDraw.Draw(img)
    small, q_font, a_font = _font(30), _font(36), _font(38)
    d.text((70, 60), "KAVAR DENEMESİ", font=_font(30, True), fill=NEON)
    d.text((70, 104), model.removesuffix(":free"), font=small, fill=MUTED)
    q_lines = _wrap(d, prompt, q_font, 900)
    d.rounded_rectangle((60, 170, 1020, 210 + 48 * len(q_lines)), 28, fill=PANEL, outline=NEON, width=2)
    for i, line in enumerate(q_lines):
        d.text((90, 190 + 48 * i), line, font=q_font, fill=INK)
    top = 250 + 48 * len(q_lines)
    a_lines = _wrap(d, answer, a_font, 920)
    room = (1010 - top) // 54
    if len(a_lines) > room:
        a_lines = a_lines[:room - 1] + [a_lines[room - 1].rstrip(" .,") + " …"]
    d.text((70, top), "Cevap:", font=_font(32, True), fill=NEON)
    for i, line in enumerate(a_lines):
        d.text((70, top + 50 + 54 * i), line, font=a_font, fill=INK)
    img.crop((0, 0, 1080, min(1080, max(760, top + 50 + 54 * len(a_lines) + 70)))).save(path)
    return path


def _run_llm(model: str, out: Path) -> dict | None:
    figures, notes = [], []
    for i, test in enumerate(LLM_TESTS, 1):
        answer = _ask_llm(model, test["prompt"])
        if not answer:
            continue
        path = _answer_card(model, test["prompt"], answer, out / f"trial_{i}.png")
        with Image.open(path) as im:
            size = list(im.size)
        figures.append({"path": str(path), "size": size, "credit": "KAVAR denemesi",
                        "alt": f"{model} modeline sorduğumuz soru ve cevabı",
                        "caption": f"KAVAR TEST {i}: our question and {model}'s real answer"})
        notes.append(f"Test {i} question: {test['prompt']}\nWhat a good answer is: {test['check']}\n"
                     f"The model's answer, verbatim:\n{answer}")
    return {"model": model, "route": "openrouter", "figures": figures, "notes": notes} if figures else None


# --- image models (public Hugging Face Space) ---------------------------------------------------

BLOCKED_SPACE_WORDS = ("nsfw", "nude", "naked", "porn", "hentai", "erotic", "sexy", "uncensored", "lewd")


TRUSTED_SPACE_OWNERS = {"huggingface", "multimodalart", "hysts", "gradio"}  # HF staff demo accounts


def _spaces(terms: list[str], article_text: str) -> list[str]:
    """Official demo Spaces only: named after the model AND owned by the company the article is
    about (its name appears in the article) or by Hugging Face's own demo accounts. Random user
    Spaces are never called: their names and outputs can be anything."""
    keys = [_norm(t) for t in terms if len(_norm(t)) >= 4]
    text = _norm(article_text)
    found = []
    for t in terms:
        r = requests.get(HF_API, params={"search": t, "sort": "likes", "limit": 20, "full": "true"}, timeout=20)
        for s in r.json():
            sid = s["id"]
            owner = sid.split("/")[0].lower()
            if (s.get("sdk") == "gradio" and sid not in found and any(k in _norm(sid) for k in keys)
                    and (owner in TRUSTED_SPACE_OWNERS or (len(_norm(owner)) >= 4 and _norm(owner) in text))
                    and not any(w in sid.lower() for w in BLOCKED_SPACE_WORDS)):
                found.append(sid)
    return found[:3]


def _client(space: str):
    """gradio_client.Client across versions (hf_token was renamed token; verbose came and went)."""
    import inspect

    from gradio_client import Client

    params = inspect.signature(Client).parameters
    kw = {}
    if tok := os.environ.get("HF_TOKEN"):
        kw["token" if "token" in params else "hf_token"] = tok
    if "verbose" in params:
        kw["verbose"] = False
    return Client(space, **kw)


def _image_from(result) -> Path | None:
    """The first image file in a gradio result (a path, a dict or a nested list/tuple)."""
    stack = [result]
    while stack:
        x = stack.pop(0)
        if isinstance(x, (list, tuple)):
            stack += list(x)
        elif isinstance(x, dict):
            stack += [x.get("path"), x.get("image"), x.get("value")]
        elif isinstance(x, str) and re.search(r"\.(png|jpe?g|webp)$", x, re.I) and Path(x).exists():
            return Path(x)
    return None


def _space_image(client, prompt: str) -> Path | None:
    """Call the Space's first endpoint that takes a text prompt; other inputs keep their defaults."""
    api = client.view_api(return_format="dict", print_info=False)
    for name, ep in (api.get("named_endpoints") or {}).items():
        params = ep.get("parameters") or []
        first = next((p for p in params if p.get("python_type", {}).get("type") == "str"), None)
        if not first or "prompt" not in (first.get("parameter_name") or first.get("label") or "").lower():
            continue
        try:
            job = client.submit(**{first["parameter_name"]: prompt}, api_name=name)
            return _image_from(job.result(timeout=240))
        except Exception as exc:  # noqa: BLE001  any Space error means "no image", never a crash
            print(f"[trial] {name}: {type(exc).__name__}: {str(exc)[:200]}")
    return None


def _run_image(terms: list[str], article_text: str, out: Path) -> dict | None:
    try:
        import gradio_client  # noqa: F401
    except ImportError:
        print("[trial] gradio_client not installed; image test skipped")
        return None
    spaces = _spaces(terms, article_text)
    print(f"[trial] Spaces to try: {spaces or 'none'}")
    for space in spaces:
        try:
            client = _client(space)
        except Exception as exc:  # noqa: BLE001
            print(f"[trial] {space}: can't connect ({type(exc).__name__}: {str(exc)[:200]})")
            continue
        figures, notes = [], []
        for i, prompt in enumerate(IMAGE_TESTS, 1):
            if src := _space_image(client, prompt):
                path = out / f"trial_{i}{src.suffix.lower()}"
                shutil.copy(src, path)
                with Image.open(path) as im:
                    size = list(im.size)
                figures.append({"path": str(path), "size": size, "credit": "KAVAR denemesi",
                                "alt": "Yeni modelle ürettiğimiz görsel",
                                "caption": f"KAVAR TEST {i}: an image we made with the model, unedited"})
                notes.append(f"Test {i} prompt (written in English for the model): {prompt}")
        if figures:
            return {"model": space, "route": f"huggingface space {space}", "figures": figures, "notes": notes}
    return None


def run_trial(article: dict, out_dir: Path) -> dict | None:
    """{model, route, figures, note} with our real test outputs, or None when nothing could be run."""
    load_dotenv(ROOT / ".env")
    try:
        pick = _pick(article)
        if pick is None or pick.kind == "none" or not pick.search_terms:
            print(f"[trial] not a testable model release ({pick.kind if pick else 'no answer'})")
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[trial] {pick.kind} model: {pick.model_name}, looking for a free way to run it", flush=True)
        if pick.kind == "llm":
            if not os.environ.get("OPENROUTER_API_KEY"):
                print("[trial] OPENROUTER_API_KEY not set; skipped")
                return None
            model = _free_llm(pick.search_terms)
            trial = _run_llm(model, out_dir) if model else None
        else:
            trial = _run_image(pick.search_terms, article["title"] + " " + article["text"], out_dir)
    except Exception as exc:  # noqa: BLE001  the test is a bonus; the carousel never fails because of it
        print(f"[trial] failed: {type(exc).__name__}: {str(exc)[:300]}")
        return None
    if trial is None:
        print(f"[trial] {pick.model_name}: no free way to run it today")
        return None
    trial["kind"] = pick.kind
    notes = trial.pop("notes")
    judged = _judge(pick, notes, trial["figures"], out_dir)
    if not judged:  # unchecked outputs are never shown: an image may carry a price or a logo
        print("[trial] outputs could not be checked; not used")
        return None
    keep = [i for i, r in enumerate(judged["results"]) if r["usable"]]
    for i, r in enumerate(judged["results"]):
        if not r["usable"]:
            print(f"[trial] test {i + 1} dropped: {r['assessment'][:200]}")
    if not keep:
        return None
    cover = judged["cover"] - 1 if pick.kind == "image" and judged["cover"] - 1 in keep else -1
    notes = [f"{notes[i]}\nOur editor looked at the output: {judged['results'][i]['assessment']}" for i in keep]
    trial["figures"] = [trial["figures"][i] for i in keep]
    trial["cover_figure"] = keep.index(cover) + 1 if cover >= 0 else 0
    trial["note"] = (f"KAVAR TEST: we ran {pick.model_name} ourselves ({trial['route']}).\n\n"
                     + "\n\n".join(notes))
    print(f"[trial] done: {len(trial['figures'])} outputs from {trial['model']}"
          + f", judged; cover = output {trial['cover_figure'] or 'none'}")
    return trial


class Judgement(BaseModel):
    class Result(BaseModel):
        test: int
        assessment: str  # 1-2 English sentences: what is right, what is wrong, concretely
        usable: bool  # false: shows a price / currency, another brand's logo, or unsafe content

    results: list[Result]
    cover: int  # the test (1-based) whose output would make a striking, clean cover; 0 for none


JUDGE_SYSTEM = """You check the outputs of a quick test we ran on a new AI model, before they are \
shown on an Instagram page. Use the Read tool to open every image named in the message and look \
closely. For each test, judge the output against what we asked: what is right, what is wrong \
(misspelled text, wrong landmarks, extra fingers, wrong math, unnatural Turkish...). Be concrete \
and fair, no hype, no hedging. usable false if the output shows any price or currency (e.g. \
"50 Kr", "₺", "$"), a real brand's logo other than KAVAR, a real identifiable person, or anything \
sexual, violent or offensive: our page never shows those. cover: the test whose output is striking and clean enough to be \
the post's cover image (no visible flaws, works small); 0 if none is."""


def _judge(pick: TrialPick, notes: list[str], figures: list[dict], out_dir: Path) -> dict | None:
    """Claude looks at the real outputs (Read tool, limited to the trial folder) and judges each."""
    import subprocess

    from carousel_writer import _inline_schema
    from script_writer import CLI_TIMEOUT, _claude_cli

    exe = _claude_cli()
    if not exe:
        return None
    msg = f"Model: {pick.model_name} ({pick.kind}).\n\n" + "\n\n".join(
        f"{note}\nOutput file: {Path(f['path']).name}" for note, f in zip(notes, figures))
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        proc = subprocess.run(
            [exe, "-p", "--output-format", "json",
             "--json-schema", json.dumps(_inline_schema(Judgement.model_json_schema())),
             "--system-prompt", JUDGE_SYSTEM, "--tools", "Read", "--allowedTools", "Read",
             "--no-session-persistence"],
            input=msg, capture_output=True, text=True, encoding="utf-8",
            timeout=CLI_TIMEOUT, cwd=out_dir, env=env)
        out = json.loads(proc.stdout).get("structured_output")
        judged = Judgement(**out).model_dump() if out else None
    except Exception as exc:  # noqa: BLE001  unjudged outputs are still shown, just not interpreted
        print(f"[trial] judge failed: {type(exc).__name__}: {str(exc)[:200]}")
        return None
    if not judged or len(judged["results"]) != len(figures):
        return None
    judged["results"].sort(key=lambda r: r["test"])
    if not 0 <= judged["cover"] <= len(figures):
        judged["cover"] = 0
    return judged


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    art = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    res = run_trial(art, Path(sys.argv[1]).parent / "trial")
    print(json.dumps(res, indent=1, ensure_ascii=False) if res else "no trial")
