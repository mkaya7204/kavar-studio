"""Write a news carousel (feed) + story set from a captured article.

The page's news format: a headline cover over the article's own cover image,
then slides that tell the story in our own Turkish words (date, what happened,
figures, how it works, criticism), each with the source's image or video
credited, then why it matters and a follow ask. Curation from primary sources,
never a translation and never someone else's post re-shared.
Same Claude sources and checks as carousel_writer (no invented figures, no prices).
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from carousel_writer import MAX_HASHTAGS, STORY_FRAMES, STORY_WORDS, StoryFrame, _ask, _revision_prompt
from script_writer import NO_PRICE_RULE, price_mentions

SLIDES = (6, 10)
BODY_WORDS = {"news": (20, 75), "why": (12, 45)}
HEADLINE_WORDS = 12


class NewsSlide(BaseModel):
    role: Literal["cover", "news", "why", "cta"]
    title: str  # cover: the headline; news: optional short heading ("" for none); why/cta: the line
    body: str  # news / why: the text, **key phrases** in double asterisks; cover / cta: "" or one line
    visual: Literal["none", "cover", "page", "figure", "video"]
    visual_index: int  # figure / video number (1-based) when visual is figure / video, else 0
    alt_text: str


class NewsDraft(BaseModel):
    slides: list[NewsSlide]
    story: list[StoryFrame]
    caption: str
    hashtags: list[str]


class NewsScript(NewsDraft):
    kind: Literal["news"] = "news"
    tool_name: str  # the publisher, so shared code that labels a run keeps working
    website_url: str  # the article
    title: str  # the article's original title
    published: str
    source: Literal["claude", "claude_code", "mock"]
    model: str | None = None
    figures: int = 0
    videos: int = 0

    @field_validator("hashtags")
    @classmethod
    def _normalise_hashtags(cls, tags: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys("#" + t.strip().lstrip("#").replace(" ", "") for t in tags if t.strip()))
        if not 3 <= len(cleaned) <= MAX_HASHTAGS:
            raise ValueError(f"expected 3-{MAX_HASHTAGS} hashtags, got {len(cleaned)}")
        return cleaned

    @model_validator(mode="after")
    def _check(self) -> "NewsScript":
        if problems := news_problems(self):
            raise ValueError("; ".join(problems))
        return self


def _words(text: str) -> int:
    return len(text.replace("**", "").split())


def news_problems(c: NewsScript) -> list[str]:
    out = []
    n = len(c.slides)
    if not SLIDES[0] <= n <= SLIDES[1]:
        out.append(f"carousel needs {SLIDES[0]}-{SLIDES[1]} slides, got {n}")
    if c.slides and c.slides[0].role != "cover":
        out.append("slide 1 must have role 'cover'")
    if c.slides and c.slides[-1].role != "cta":
        out.append("the last slide must have role 'cta'")
    if sum(s.visual == "video" for s in c.slides) > 2:
        out.append("at most two video slides")
    for i, s in enumerate(c.slides, 1):
        if s.role == "cover" and not 4 <= _words(s.title) <= HEADLINE_WORDS:
            out.append(f"slide 1: headline needs 4-{HEADLINE_WORDS} words, has {_words(s.title)}")
        if s.role in BODY_WORDS:
            lo, hi = BODY_WORDS[s.role]
            if not lo <= _words(s.body) <= hi:
                out.append(f"slide {i} ({s.role}): body has {_words(s.body)} words, needs {lo}-{hi}")
            if s.body.count("**") % 2:
                out.append(f"slide {i}: unbalanced ** marks")
            if len(re.findall(r"\*\*(.+?)\*\*", s.body)) > 3:
                out.append(f"slide {i}: at most 3 highlighted phrases")
        if _words(s.title) > (HEADLINE_WORDS if s.role == "cover" else 9):
            out.append(f"slide {i}: title too long")
        if s.visual == "figure" and not 1 <= s.visual_index <= c.figures:
            out.append(f"slide {i}: figure {s.visual_index} doesn't exist (the article has {c.figures})")
        if s.visual == "video" and not 1 <= s.visual_index <= c.videos:
            out.append(f"slide {i}: video {s.visual_index} doesn't exist (the article has {c.videos})")
        if len(s.alt_text) > 125:
            out.append(f"slide {i}: alt_text over 125 characters")
    m = len(c.story)
    if not STORY_FRAMES[0] <= m <= STORY_FRAMES[1]:
        out.append(f"story needs {STORY_FRAMES[0]}-{STORY_FRAMES[1]} frames, got {m}")
    if c.story and c.story[0].role != "hook":
        out.append("story frame 1 must have role 'hook'")
    if c.story and c.story[-1].role != "link":
        out.append("the last story frame must have role 'link'")
    for i, f in enumerate(c.story, 1):
        if _words(f.kicker) + _words(f.title) + _words(f.body) > STORY_WORDS:
            out.append(f"story frame {i}: over {STORY_WORDS} words")
        if f.role == "poll" and len(f.poll_options) != 2:
            out.append(f"story frame {i}: a poll needs exactly 2 options")
    texts = [c.caption] + [t for s in c.slides for t in (s.title, s.body, s.alt_text)] + \
            [t for f in c.story for t in (f.kicker, f.title, f.body, *f.poll_options)]
    if bad := price_mentions(*texts):
        out.append(f"page policy, no prices: remove every price / payment mention ({', '.join(bad)})")
    return out


SYSTEM_PROMPT = f"""You are the news editor of a Turkish Instagram page about AI ("Yapay zeka \
dünyasından haberler"). From one source article you write a feed carousel ({SLIDES[0]}-{SLIDES[1]} \
slides, 1080x1350) and a story set ({STORY_FRAMES[0]}-{STORY_FRAMES[1]} frames). Readers come for \
being first to know and for a clear, trustworthy explanation in Turkish.

Journalism rules:
- Retell the story in your own natural Turkish. Never translate sentence by sentence. Keep \
names, product names and quotes accurate; quote short phrases only, attributed.
- Only facts in the article. Every number you write must appear in the article text. If the \
article says something is claimed, write it as a claim ("şirkete göre"). No speculation.
- Give the date of the event (from the article) on slide 2, as "6 Ekim'de" style.
- Turkish readers: if the news is limited to some countries or ages, the headline must not promise the reader they can use it now; say who can use it in a slide instead. Don't guess when it reaches Turkey.
- {NO_PRICE_RULE}

Slides (roles):
- cover (slide 1): title = the headline, 6-12 words, a concrete news sentence with the key \
number or actor ("Bir OpenAI iç modeli 722 matematik makalesi yazdı"), uppercase is applied by \
the template. visual "cover" (the article's own image). body "".
- news (most slides): title "" or a short heading (max 6 words); body 20-75 words telling one \
part of the story: what happened, the details, how it works, the reactions or criticism, what is \
still unknown. Mark the 1-3 phrases a skimming reader must not miss with **double asterisks** \
(drawn bold in neon). Each news slide shows one visual: "figure" with visual_index (the \
article's images, listed in the user message with their captions; use each one where it fits \
the text, at most once), "page" (the article's headline area, good on slide 2), "video" with \
visual_index if the article has a video (at most two, each video once, where the motion matters), or "none" for a \
text-only slide.
- why (one slide, near the end): title "Neden önemli?"-style line, body 12-45 words on what this \
means for the reader.
- cta (last slide): title = a follow ask that fits a news page, e.g. "Yapay zekada olanları ilk \
sen öğren", body "" or one short line; the template draws the page handle and follow button.
Use 8-10 slides when the article has enough substance, fewer when it doesn't. Don't pad.

"Biz denedik" (only when the user message has a KAVAR TEST section): we ran the new model \
ourselves and its real outputs are the figures captioned "KAVAR TEST". Our test is the part \
nobody else has, so it leads the post:
- cover: the headline is about our test and its result, in plain words a non-developer gets \
("Yeni açık modeli denedik: İstanbul'u böyle çizdi", "Yeni modele Türkçe sorduk, hesabı \
şaşırdı"), never library or developer jargon. If "The cover image is our test output" is \
stated, the cover shows it.
- slide 2: what the model is, who released it, the date (the usual what-happened slide).
- slides 3+: each test output on its own news slide (title like "Biz denedik" / "Türkçesi \
nasıl?" / "Yazıyı doğru yazdı mı?"): what we asked and the verdict, taken from "Our editor \
looked at the output" (right or wrong, concretely). Never "kendiniz bakın": state the result. \
Never praise more than the output shows; a wrong answer is news too.
- then at most 2 slides of the other news details, in plain Turkish for a general reader: \
what it can do and who can use it. Leave out developer jargon (GPU names, library, encoder, \
LoRA, checkpoint, quantization) unless one word is essential; 7-8 slides in total is enough.
- then why, cta.
You may write "denedik" only about these tests. Mention the test in the caption, and use the \
test result in story frame 1.

Story set: frame 1 role "hook" (the headline, short), 1-2 "fact" frames, optionally a "poll" \
(question + 2 short answers; the user adds the sticker by hand), last frame role "link" (title \
invites to tap the link sticker; body says the full story is in the post). Story visuals: \
"screenshot" = the cover image, "page" = the article's headline area, "none". Use kicker "" or 1-2 \
words, page_section 0, poll_options [] unless poll. Max {STORY_WORDS} words per frame.

caption: 3-5 short lines: the news in one line with a Turkish search keyword, 1-2 lines of \
context, then "Kaynak: <publisher>". 0-2 emojis. hashtags: 3-{MAX_HASHTAGS}, e.g. #yapayzeka plus \
the company / product.
alt_text: per slide, under 125 characters, Turkish.
Fill every field; "" / 0 / [] when unused."""


def _user_message(article: dict) -> str:
    figs = "\n".join(f"  figure {f['n']}: {f['size'][0]}x{f['size'][1]}, alt: {f['alt'] or '-'}, "
                     f"caption: {f['caption'] or '-'}" for f in article["figures"]) or "  none"
    return (f"Source: {article['publisher']} ({article['domain']}), published {article['published'] or 'unknown'}\n"
            f"Original title: {article['title']}\n"
            f"Images you can show:\n{figs}\nVideos you can show: {len(article['videos'])}\n\n"
            f"Article text:\n{article['text']}"
            + (f"\n\n{article['trial_note']}" if article.get("trial_note") else ""))


def _finish(draft: dict, article: dict, source: str, model: str | None) -> NewsScript:
    try:
        script = NewsScript(**draft, tool_name=article["publisher"], website_url=article["url"],
                            title=article["title"], published=article["published"], source=source, model=model,
                            figures=len(article["figures"]), videos=len(article["videos"]))
    except ValidationError as exc:
        raise ValueError("; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())) from exc
    # no invented figures: every number on a slide or frame must be in the article
    known = (_numbers(article["text"] + " " + article["title"] + " " + article.get("trial_note", ""))
             | _date_numbers(article))
    used = _numbers(" ".join([f"{s.title} {s.body}" for s in script.slides]
                             + [f"{f.kicker} {f.title} {f.body} {' '.join(f.poll_options)}" for f in script.story]))
    if bad := used - known:
        raise ValueError(f"these figures are not in the article, remove or fix them: {', '.join(sorted(bad))}")
    return script


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)*", text)}


def _date_numbers(article: dict) -> set[str]:
    """Day / year of the publication date may be written even if the text doesn't repeat them."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", article.get("published") or "")
    return {m.group(1), str(int(m.group(3)))} if m else set()


def generate_news(article: dict, attempts: int = 3) -> dict | None:
    """A validated news script dict, or None when no Claude source produced a valid one."""
    prompt = _user_message(article)
    for attempt in range(1, attempts + 1):
        draft, model, source = _ask(prompt, SYSTEM_PROMPT, NewsDraft)
        if draft is None:
            return None
        try:
            return _finish(draft, article, source, model).model_dump(mode="json")
        except ValueError as exc:
            print(f"[news_writer] draft {attempt} rejected: {str(exc)[:400]}")
            prompt = _revision_prompt(prompt, draft, str(exc))
    return None


def revise_news(script: dict, problems: list[str], article: dict) -> dict | None:
    draft = NewsDraft.model_validate(script).model_dump()
    prompt = _revision_prompt(_user_message(article), draft,
                              "after rendering, these slides don't fit the design: " + "; ".join(problems)
                              + ". Shorten those slides' text (fewer, shorter words); keep the facts.")
    draft2, model, source = _ask(prompt, SYSTEM_PROMPT, NewsDraft)
    if draft2 is None:
        return None
    try:
        return _finish(draft2, article, source, model).model_dump(mode="json")
    except ValueError as exc:
        print(f"[news_writer] revision rejected: {str(exc)[:300]}")
        return None


if __name__ == "__main__":
    print(json.dumps(NewsDraft.model_json_schema(), indent=1)[:400])
