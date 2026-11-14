"""D-73 (user 2026-11-14): "A da bizim gerçekten deneme şansımız yok ama denenmiş olunmuş hallerini bulabilirmişiz,
kullanıcı deneyimleri veya bunları denenmiş kurumlar veya platformlar".

Before a tool Reel is written, Claude searches the web for what real people found when they TRIED the tool: user
reviews and comments (Product Hunt, Reddit, Hacker News, G2, app stores) and independent reviewers' tests. The
writer may lead with one of them, attributed ("Product Hunt'ta deneyenler ... diyor"), in our own words. Never the
maker's own claims, never their images or videos (CLAUDE.md §1.9), never "denedik" (we didn't try it), never prices.

    find_experiences(tool) -> [{"source", "url", "finding", "tone"}]   (empty when nothing real was found)
"""

import json
import os
import shutil
import subprocess
from urllib.parse import urlsplit

from claude_usage import record as record_usage
from script_writer import price_mentions

TIMEOUT = 240  # seconds for the search
MAX_FINDINGS = 3
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["findings"],
    "properties": {"findings": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["source", "url", "finding", "tone"],
        "properties": {"source": {"type": "string"}, "url": {"type": "string"}, "finding": {"type": "string"},
                       "tone": {"type": "string", "enum": ["positive", "negative", "mixed"]}}}}},
}
PROMPT = """Find what real people reported after actually TRYING the software product "{name}" ({url}, "{tag}").
Look for: user reviews and comments (Product Hunt reviews and launch comments, Reddit, Hacker News, G2, Capterra, app \
store reviews) and independent reviewers who tested it (tech sites, blogs, YouTube video descriptions or transcripts).
Rules:
- Only first-hand experience of THIS exact product: what worked, what didn't, how fast, what surprised them. Not the \
maker's own site, press release, ads or "top 10 tools" listicles, and never a similarly named product.
- Open the pages you cite (WebFetch) and keep only what they really say.
- Each finding: source = the platform and, if public, who ("Product Hunt yorumları", "Reddit r/SaaS", "TechCrunch \
incelemesi"); url = the exact page; finding = ONE Turkish sentence in your own words saying what they found, no \
quotes longer than 6 words, no prices, costs, plans, trials or discounts; tone = positive / negative / mixed.
- At most {n} findings, the most concrete first. Return an empty list if you find no real first-hand report."""


def _claude() -> str | None:
    return None if os.getenv("SCRIPT_WRITER_NO_CLI") else shutil.which("claude")


def clean(findings: list[dict], site: str) -> list[dict]:
    """Keep real, attributed, price-free findings that are not from the maker's own site."""
    own = (urlsplit(site).hostname or "").removeprefix("www.")
    out = []
    for f in findings:
        host = (urlsplit(f.get("url", "")).hostname or "").removeprefix("www.")
        if not f.get("url", "").startswith("http") or not f.get("finding", "").strip() or not f.get("source"):
            continue
        if own and (host == own or host.endswith("." + own)):
            continue  # the maker's own words are not an experience
        if price_mentions(f["finding"]):
            continue  # §1.1: no prices, ever
        out.append({k: f[k].strip() for k in ("source", "url", "finding", "tone")})
    return out[:MAX_FINDINGS]


def find_experiences(tool: dict) -> list[dict]:
    exe = _claude()
    if not exe:
        return []
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    prompt = PROMPT.format(name=tool["tool_name"], url=tool["website_url"], tag=tool.get("tag_line", ""),
                           n=MAX_FINDINGS)
    if tool.get("discussion_url"):  # D-74: the Show HN thread where people who tried it comment
        prompt += (f"\nStart with this discussion, where people who tried it commented: {tool['discussion_url']} "
                   "(the maker's own comments there are not experiences).")
    try:
        proc = subprocess.run([exe, "-p", "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
                               "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch",
                               "--no-session-persistence"],
                              input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT, env=env)
        record_usage("tool_experiences", proc.stdout)
        found = (json.loads(proc.stdout).get("structured_output") or {}).get("findings") or []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []
    return clean(found, str(tool["website_url"]))
