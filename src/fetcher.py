"""Fetch the latest SaaS / AI tools for video scripts.

Primary source is Product Hunt's public Atom feed (no API token needed).
If the feed is unreachable or yields nothing, a static sample list is
returned so the rest of the pipeline can still run.
"""

import html
import json
import os
import re
import shutil
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, urlunsplit

import requests
from pydantic import BaseModel, HttpUrl

FEED_URL = "https://www.producthunt.com/feed"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
HEADERS = {"User-Agent": "Mozilla/5.0 (saas-video-automation)"}
TIMEOUT = 15


class Tool(BaseModel):
    tool_name: str
    tag_line: str
    website_url: HttpUrl
    description: str


SAMPLE_TOOLS = [
    Tool(
        tool_name="Notion",
        tag_line="The connected workspace for docs, wikis and projects",
        website_url="https://www.notion.so",
        description="All-in-one workspace that combines notes, docs, "
        "project management and AI assistance for teams.",
    ),
    Tool(
        tool_name="Zapier",
        tag_line="Automate workflows across 7,000+ apps",
        website_url="https://zapier.com",
        description="No-code automation platform that connects business "
        "apps and runs AI-powered workflows without engineering help.",
    ),
    Tool(
        tool_name="Grammarly",
        tag_line="AI writing assistance wherever you type",
        website_url="https://www.grammarly.com",
        description="AI writing assistant that checks grammar, tone and "
        "clarity across email, docs and browser apps.",
    ),
]


# Physical-product signals. Ambiguous words appear only as phrases, since SaaS
# copy says "full screen reminders", "help desk", "use case", "monitor your apps".
HARDWARE_TERMS = [
    "hardware", "laptop", "laptops", "notebook pc", "keyboard", "keyboards",
    "mouse", "mice", "trackpad", "tablet", "tablets", "smartphone", "headphones",
    "earbuds", "headset", "smartwatch", "wearable", "wearables", "gadget",
    "gadgets", "webcam", "charger", "power bank", "battery pack", "cable",
    "usb hub", "docking station", "screen protector", "phone case",
    "laptop case", "standing desk", "desk mat", "desk setup", "monitor arm",
    "3d printer", "drone", "smart glasses", "motorized", "wheels", "e-reader",
    "console", "robot vacuum", "physical product",
]
SOFTWARE_TERMS = [
    "ai", "saas", "software", "app", "apps", "tool", "tools", "platform", "web",
    "extension", "plugin", "api", "sdk", "mcp", "agent", "agents", "agentic",
    "automation", "automate", "workflow", "workflows", "open-source",
    "open source", "cloud", "llm", "llms", "browser", "dashboard", "chrome",
    "no-code", "low-code", "crm", "analytics", "assistant", "chatbot", "bot",
    "workspace", "infrastructure", "integration", "integrations", "observability",
    "mac", "macos", "windows", "ios", "android", "download", "signup", "sign up",
    "subscription", "subscriptions", "free trial", "editor", "ide", "developer",
    "developers", "github", "model", "models", "transcribe", "transcription",
    "compliance", "notepad", "operating system",
]
HARDWARE_DESC_CHARS = 300  # long marketing copy uses words like "cable" metaphorically


def _match(terms: list[str], text: str) -> list[str]:
    return [t for t in terms if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", text, re.I)]


def classify_tool(name: str, tag_line: str, description: str = "") -> tuple[bool, str]:
    """Decide if a product is a digital SaaS / AI tool. Hardware signals always win.

    Hardware is checked against the name, tag line and the opening of the
    description only; software signals may come from anywhere.
    """
    if hw := _match(HARDWARE_TERMS, f"{name} {tag_line} {description[:HARDWARE_DESC_CHARS]}"):
        return False, f"hardware: {', '.join(hw)}"
    if sw := _match(SOFTWARE_TERMS, f"{name} {tag_line} {description}"):
        return True, f"software: {', '.join(sw)}"
    return False, "no software signal"


def _strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _clean_url(url: str) -> str:
    """Drop query/fragment (e.g. ?ref=producthunt) from a resolved URL."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))


def _meta_description(page_html: str) -> str | None:
    for attr in ("og:description", "description"):
        tag = re.search(
            rf'<meta[^>]+(?:name|property)=["\']{attr}["\'][^>]*>', page_html, re.I
        )
        if tag:
            content = re.search(r'content=["\']([^"\']*)["\']', tag.group(0), re.I)
            if content and content.group(1).strip():
                return html.unescape(content.group(1).strip())
    return None


def _resolve_site(redirect_url: str) -> tuple[str, str | None]:
    """Follow Product Hunt's /r/p/ link to the real site; return (url, meta description)."""
    resp = requests.get(redirect_url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return _clean_url(resp.url), _meta_description(resp.text)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)).lower())


def _find_site_with_claude(name: str, tag_line: str) -> tuple[str, str | None] | None:
    """Product Hunt answers 403 to cloud machines (GitHub Actions), so its /r/p/ redirect can't be
    followed there. Ask Claude Code (web search only) for the product's official site, then accept it
    only if the page loads and names the product."""
    exe = None if os.getenv("SCRIPT_WRITER_NO_CLI") else shutil.which("claude")
    if not exe:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    schema = {"type": "object", "additionalProperties": False, "required": ["url"],
              "properties": {"url": {"type": "string"}}}
    prompt = (f'Find the official website of the software product "{name}" ("{tag_line}"), launched on '
              f"Product Hunt this week. Return its homepage URL, or \"\" if you are not sure it is this "
              f"exact product (not a similarly named one). Never return a producthunt.com, social media or "
              f"app store URL.")
    try:
        proc = subprocess.run([exe, "-p", "--output-format", "json", "--json-schema", json.dumps(schema),
                               "--tools", "WebSearch", "--allowedTools", "WebSearch", "--no-session-persistence"],
                              input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
        url = (json.loads(proc.stdout).get("structured_output") or {}).get("url", "").strip()
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None
    if not url.startswith("http") or "producthunt.com" in url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    if _fold(name)[:12] not in _fold(resp.text[:200_000]):
        return None  # the page doesn't even mention the product: wrong site
    return _clean_url(resp.url), _meta_description(resp.text)


def _parse_entry(entry: ET.Element) -> tuple[Tool | None, str]:
    """Return (tool, reason); tool is None when the entry is skipped."""
    name = (entry.findtext("a:title", "", ATOM_NS)).strip()
    content = html.unescape(entry.findtext("a:content", "", ATOM_NS))
    page_url = entry.find("a:link[@rel='alternate']", ATOM_NS)
    if not name or page_url is None:
        return None, "malformed entry"

    # Content is "<p>tagline</p><p><a>Discussion</a> | <a href=/r/p/..>Link</a></p>"
    paragraphs = re.findall(r"<p>(.*?)</p>", content, re.S)
    tag_line = _strip_tags(paragraphs[0]) if paragraphs else ""

    # Reject obvious hardware before spending a request on the product site.
    is_software, reason = classify_tool(name, tag_line)
    if not is_software and reason.startswith("hardware"):
        return None, reason

    redirect = re.search(r'href="(https://www\.producthunt\.com/r/p/[^"]+)"', content)
    website_url, description = page_url.get("href"), None
    if redirect:
        try:
            website_url, description = _resolve_site(redirect.group(1))
        except requests.RequestException:
            # blocked (cloud IPs get 403): look the site up instead; else keep the Product Hunt page
            if found := _find_site_with_claude(name, tag_line):
                website_url, description = found

    # Re-check with the site's own description, which often reveals what it is.
    is_software, reason = classify_tool(name, tag_line, description or "")
    if not is_software:
        return None, reason

    tool = Tool(
        tool_name=name,
        tag_line=tag_line,
        website_url=website_url,
        description=description or tag_line,
    )
    return tool, reason


def fetch_latest_tools(limit: int = 3, use_sample: bool = False, verbose: bool = False,
                       exclude: set[str] | None = None) -> list[dict]:
    """Return up to `limit` recent SaaS / AI tools as JSON-serialisable dicts.

    Keys: tool_name, tag_line, website_url, description.
    Hardware and other non-software launches are filtered out. If the feed
    fails or yields fewer than `limit` tools, SAMPLE_TOOLS fill the gap.
    """
    tools: list[Tool] = []
    if not use_sample:
        try:
            resp = requests.get(FEED_URL, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            skip = {_fold(n) for n in exclude or ()}
            for entry in root.findall("a:entry", ATOM_NS):
                if _fold(entry.findtext("a:title", "", ATOM_NS)) in skip:
                    continue  # already made into a video
                tool, reason = _parse_entry(entry)
                if verbose:
                    name = entry.findtext("a:title", "?", ATOM_NS).strip()
                    print(f"[fetcher] {'KEEP' if tool else 'SKIP'} {name} ({reason})")
                if tool:
                    tools.append(tool)
                if len(tools) >= limit:
                    break
        except (requests.RequestException, ET.ParseError) as exc:
            print(f"[fetcher] Product Hunt feed failed ({exc}); using sample data.")

    if len(tools) < limit:
        if not use_sample:
            print(f"[fetcher] Only {len(tools)} SaaS tools in feed; filling with sample data.")
        tools += SAMPLE_TOOLS[: limit - len(tools)]
    return [t.model_dump(mode="json") for t in tools]


def fetch_latest_tools_json(limit: int = 3, use_sample: bool = False) -> str:
    return json.dumps(fetch_latest_tools(limit, use_sample), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Hardware pre-filter on real feed wording; software mentioning "screen" / "desk"
    # / "monitor" must not be mistaken for hardware.
    is_hardware = {
        ("Microsoft Surface Laptop Ultra", "Run 120B AI models locally on Microsoft's new Surface"): True,
        ("Amazon Alexa Tablets", "Full Google Play, Alexa+ and a Kindle reading mode"): True,
        ("Moonwalkers Dusk", "Strap-on motorized wheels that let you walk twice as fast"): True,
        ("Ahem!", "Full screen reminders for ADHD, time-blind & focused brains"): False,
        ("Cakie", "Turn screen recordings into prompts for AI agents"): False,
        ("Deskly", "AI help desk platform for support teams"): False,
        ("ProcBoss", "Run, deploy, monitor, and manage your apps across servers"): False,
    }
    for (name, tag), expected in is_hardware.items():
        _, reason = classify_tool(name, tag)
        assert reason.startswith("hardware") == expected, f"classify_tool({name!r}) -> {reason}"
    # A hardware word deep in long marketing copy must not reject real software.
    clippo_desc = "Orchestrate AI agents on a canvas. " + "x " * 200 + "Connect a cable from any note."
    assert classify_tool("Clippo", "Orchestrate AI agent teams", clippo_desc)[0]
    print(f"=== classify_tool: {len(is_hardware)} hardware/software cases OK ===")

    required = {"tool_name", "tag_line", "website_url", "description"}
    for label, sample in (("Product Hunt (live)", False), ("Sample fallback", True)):
        tools = fetch_latest_tools(limit=3, use_sample=sample, verbose=not sample)
        assert tools, f"{label}: no tools returned"
        for t in tools:
            missing = required - t.keys()
            assert not missing, f"{label}: missing keys {missing}"
            assert all(t[k] for k in required), f"{label}: empty field in {t}"
            ok, reason = classify_tool(t["tool_name"], t["tag_line"], t["description"])
            assert ok, f"{label}: non-SaaS tool selected: {t['tool_name']} ({reason})"
            print(f"  ✔ {t['tool_name']} is a SaaS/AI tool ({reason})")
        print(f"=== {label}: {len(tools)} tools OK ===")
        print(json.dumps(tools, indent=2, ensure_ascii=False))
