# KAVAR carousel design quality (learned 2026-11-21, D-85)

The user (2026-11-21): "stilin çok basit yapay ... neon yazı renkleri çok yapay görünüyor ... skiller edin geliştir kendini".
Sources studied: the user's sample Reel (@aykutucesai, "4 ücretsiz skill"); Impeccable (pbakaus/impeccable,
Apache-2.0: craft-floor, typeset); tasteskill (Leonxlnx/taste-skill, MIT); UI UX Pro Max (nextlevelbuilder,
MIT: banner-design); Jakub Krehel skills (jakubkrehel/skills, MIT: better-typography, better-colors,
better-layout; copied to .claude/skills/). Real pages: reports/karusel-arastirma-2026-11-21.html.
These are rules distilled from them, not their code. Nothing here is executed.

## What made our slides look AI-made (remove)

| Old habit | Why it reads as AI | Replace with |
|---|---|---|
| Cyan neon text-shadow, radial glows | A zero-offset coloured halo is decoration, not depth (Impeccable) | No glow at all. Depth only from real pictures and a soft offset shadow under a frame |
| Grid lines on a near-black ground | Dark chosen because "it is tech", the category default | Pick the ground from the scene: a phone feed in daylight among dark AI pages. A light paper ground stands out |
| "NEDEN ÖNEMLİ?" pill above a heading | Eyebrow/kicker above a heading is banned outright (Impeccable) | Let the heading carry it |
| Gradient bars, gradient rules | Gradient as ornament | A plain 2 px ink rule, or nothing |
| One sans for everything, all bold | No contrast between roles | A grotesk for headlines + one italic serif accent word; body regular weight |
| "Görsel: site, tarih" under every picture | Captions under pictures (tasteskill rule 1) | One credit line on the last slide, or a tiny source mark in the frame corner |
| 6 of 10 slides text only | "Every screen shows the real thing" (tasteskill) | Every slide has one real picture: product screen, demo frame, photo, chart |
| 50-70 words a slide | Wall of text, nobody swipes | Heading ≤ 8 words, body ≤ 35 words |
| Emoji as icons, purple-blue gradients | Classic AI tells | Real logos in their own colours; no violet |

## The new look (rules for templates/carousel)

- **Ground and colour.** Warm light paper ground, near-black ink, ONE accent used for one job only (the
  highlighted word and the progress mark). Neutrals tinted toward the accent, never pure grey. No neon,
  no glow, no violet. Text contrast ≥ 4.5:1 measured on the rendered pair.
- **Type.** Headline: heavy grotesk, tracking -0.02em, line-height 1.05-1.1, `text-wrap: balance`. One or two
  words of each headline set in an italic serif inside a flat marker block (the accent). Body: regular
  (400-500) weight, line-height 1.45, ≤ 35 words. Turkish casing with `lang="tr"` (İ/ı), curly quotes,
  real ellipsis and dashes.
- **Cover.** One big real picture (the person behind it, the product, the result) filling most of the
  frame; the company's real logo as a round badge; the headline in 2-3 lines at the bottom with one
  accent word; a small "Kaydır →" cue. Headline types that worked on real pages: a number ("14 örnek",
  "4 kat hızlı"), a curiosity question ("neden ...?"), the reader's gain. Never a technical phrase.
- **Inner slide.** Heading + short body at the top, ONE big picture below in a plain browser or phone frame
  with a thin ink border and a soft offset shadow. When the number is the point, a big-number card
  ("4,4×" + one line). A list of problems may use flagged rows (the sample Reel's "×" rows), at most 4.
- **Video slide.** When the company's own page has a demo video, one slide carries 5-10 s of it.
- **Progress.** A thin progress bar or dots, not "03/10" text.
- **Last slide.** One question for comments ("Sen hangisini denerdin?"), the handle and the follow pill.
- **Brand.** The crow sign-off (D-69) and @thekavar.ai stay; the logo is drawn in ink on the light ground.

## Check before a carousel ships (editor and Claude)

1. Does the cover stop the scroll without the headline? (a real, big, specific picture)
2. Is any slide text only? → add the picture or merge the slide.
3. Any glow, gradient text, eyebrow pill, purple, emoji icon, caption under a picture? → remove.
4. Heading ≤ 8 words, body ≤ 35 words, one accent word per headline.
5. Contrast measured, Turkish casing right, nothing in the outer 6 % of the frame. With `text-transform:
   uppercase` under `lang="tr"`, an English brand name turns "Hugging" into "HUGGİNG": wrap brand names
   in `lang="en"` (seen in the 11-21 mock).
6. A cover picture that is the company's own banner carries its English title: crop / zoom to the
   picture part, never show half an English sentence.
