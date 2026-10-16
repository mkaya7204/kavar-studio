---
name: carousel-designer
description: Produce, write or review the Instagram carousel (feed) and story image set for an AI tool / tech news post in this project. Use when the user asks for "görsel", "carousel", "kaydırmalı post", "story", or to fix / improve rendered slides. Acts as the page's designer and editor - the video pipeline (main.py) is separate.
---

# Carousel + story designer / editor

The image pipeline is `python carousel.py`. It shares the fetcher, the site capture and the Claude
helpers with the video pipeline, but never touches `main.py` or `templates/hyperframes_news/`.
The user uploads by hand (no auto-publish). Research behind every rule:
`reports/Carousel ve story görsel sistemi.md`.

## Running

| Situation | Command |
|---|---|
| Same tool as the Reel just made | `python carousel.py --video-script output/temp/script.json --reuse-capture` |
| New tool, from scratch | `python carousel.py` (or `--sample`) |
| You wrote / edited the carousel JSON yourself | `python carousel.py --carousel <file>.json --reuse-capture` |

Never run it while a HyperFrames video render is running (4 GB RAM). A render takes about 20-40 s.
Output: `output/carousel/<date>_<tool>/` with `carousel/NN.jpg`, `story/NN.jpg`, `caption.txt`
(caption, hashtags, alt texts, sticker notes), `carousel.json`, `qa.json`.

## News mode (haber)

| Situation | Command |
|---|---|
| Freshest unused AI news from `news_sources.json` | `python carousel.py --news` |
| A specific article | `python carousel.py --news-url <url>` |
| Edited the run's `carousel.json` by hand / changed the template | `python carousel.py --rerender <run folder>` (no Claude call) |

- **Curation, not reposting:** only primary sources (company blogs) and reputable press in
  `news_sources.json`. Never other creators' Instagram/TikTok/X posts or videos (copyright and
  Instagram's April 2026 originality rule). Retell in our own Turkish, credit every visual.
- `article_capture.py` saves the article's own cover (og:image), its headline area (`page`), up
  to 6 images (`fig_N`) and up to 2 of its own MP4 videos (YouTube/social embeds are skipped).
- `news_writer.py`: cover headline 3-6 words (D-17), `news` slides 20-75 words with `**highlights**`,
  one visual each (figure / page / video / none), one `why` slide, follow `cta`. Every number
  must appear in the article; no prices.
- Template: wide covers (most og:images are 1.91:1) are shown whole over a blurred copy; tall
  ones fill the frame. News slides carry our byline (brand mark + name + handle) instead of the
  corner chrome; a credit line "Görsel/Video: <publisher>, <date>" sits under every visual.
- A `video` slide (at most two per carousel) is rendered as an MP4 (`carousel/NN.mp4`, H.264, max
  15 s, source audio kept) with the clip playing inside the slide's card; the card's VIDEO and
  @handle tags are stamped back over the clip. Upload it in its place in the carousel.
- Editorial checks before publishing: every sentence must be in the source (no guesses such as
  "when it reaches Turkey"); a cover must not promise readers something they can't use (region /
  age limits); no still image with a play button that doesn't play; avoid 4+ text-only slides in a row.
- `output/news_history.json` stops the same article from running twice.

## Pipeline guarantees (don't re-check by hand, they are measured)

- `carousel_writer.py` rejects drafts that break the editorial rules (6-10 slides, hook first, cta
  last, word budgets per role, 3-5 hashtags, poll = 2 options) or contain a figure that is not in
  the tool data / video script. Rejections are fed back to Claude, up to 3 drafts.
- The template fits type down its own size scale, then measures every frame: content overflow, a
  word wider than its box, font under 28 px (story 32 px), text outside the safe zone, text running
  into a screenshot, contrast under 4.5:1. Fixable problems go back to Claude for a shorter
  rewrite (2 rounds). Problems left over are printed and saved in `qa.json`.
- JPEG q90, 4:4:4, sRGB, 1080x1350 (4:5, the API's limit; not 3:4) and 1080x1920. Brand
  copyright in EXIF.

## When you write or edit a carousel JSON yourself (editor)

Schema: `src/carousel_writer.py` (`Slide`, `StoryFrame`). Fill every field; `""`, `[]`, `0` when
unused. Rules a script can't fully judge:

1. **Cover (slide 1, `hook`)** must read as a small grid tile: a concrete outcome or a question,
   ideally 8 words max, uppercase is applied automatically. `accent` = the payoff words.
2. **Slide 2** is a second hook that works alone (Instagram may re-show the post from slide 2).
3. **One idea per slide.** Benefit first, feature second. Spoken, natural Turkish, "sen" form.
4. **Not the Reel again:** reuse its facts and screenshots, but write steps, comparisons and a
   recap: something worth saving.
5. **Arc:** hook, context, reveal, 2-4 feature/stat/compare, recap, cta. Never two identical roles
   in a row except feature. `stat` only with a real figure from the data.
6. **CTA:** save or send ("Kaydet, lazım olur", "… arkadaşına gönder"), never "takip et". The
   template adds the handle and follow line.
7. **Feature kicker:** `"01"`, `"02"` gives the big outlined numeral; a word gives a label pill.
8. **Story:** frame 1 is the strongest line (highest exit rate); poll and link frames leave a
   glowing empty area for the sticker the user adds by hand. Max 25 words per frame.
9. No emojis, hashtags or URLs on slides; the domain and handle are drawn by the template.
10. **No prices, ever** (page policy): no price, currency, one-time/subscription, free/paid,
    trial or discount, on slides, story, caption or alt text. The writer rejects them
    (`price_mentions`). Exception: the user announces a paid collaboration with that brand;
    then write it as a marketer, present the brand with care, and label it as a collaboration
    (#işbirliği). That mode is not built yet.

## Visual review (designer) - always do this before reporting a render as done

Make a contact sheet (all slides at ~1/3 size, like the phone shows them) and look at it:

```
python -c "from PIL import Image;import glob;fs=sorted(glob.glob('output/carousel/<run>/carousel/*.jpg'));w,h=432,540;s=Image.new('RGB',(w*5,h*2));[s.paste(Image.open(f).resize((w,h)),((i%5)*w,(i//5)*h)) for i,f in enumerate(fs)];s.save('<scratchpad>/sheet.jpg')"
```

Check, as a senior designer would:
- **Grid test:** is the cover readable at thumbnail size and does it promise one clear thing?
- **Hierarchy:** one dominant element per slide; accent words are the payoff, not filler.
- **Rhythm:** layouts alternate (text / visual / big number / list); no three look-alikes in a row.
- **Screenshot crops:** the card shows a meaningful part of the site, not white space, a cookie
  banner or a headline sliced at the top. Crops are chosen automatically by edge density
  (`_page_offsets` in `carousel_renderer.py`); if one is bad, change that slide's `page_section`
  (1-3) or set `visual` to `"none"`.
- **Turkish:** dotted İ in uppercase (VİDEO, not VIDEO), suffix apostrophes (Letra'yı), grammar.
- **Brand:** handle top-left and counter top-right on every slide; handle tag on every screenshot.

Fix text problems in the JSON and re-render with `--carousel`; fix layout problems in
`templates/carousel/index.html` (one template, roles are branches of the frame loop).

## Brand

The page is **KAVAR** (`@kavar.ai`). `brand.json` holds name, handle, `logo` (brand/kavar_icon.svg,
the K monogram) and `wordmark` (brand/kavar_wordmark.svg, KΛVΛR with the neon V), follow line and
copyright; carousel, story and video all read it. Never locale-uppercase or retype the name: use the
wordmark file. The icon is the corner mark and byline avatar; the wordmark sits in bylines and on
every closing card; the handle tag sits on every screenshot. Logo rules: dark ground (#04060C), the V
and the K's chevron are the only neon parts, keep clear space of one stem width around the mark.
