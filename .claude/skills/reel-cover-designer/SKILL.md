---
name: reel-cover-designer
description: Design or check the first frame and the cover image of a KAVAR (@thekavar.ai) Reel - what a viewer sees before deciding to watch (Reels feed, profile grid, Explore, DM shares). Use when changing templates/hyperframes_news, when a Reel looks like an ad or starts blank, or when choosing / uploading a Reel cover in Meta Business Suite or via the API.
---

# Reel first frame + cover designer

Role: the page's art director for the first impression. In the Reels feed the cover is never
shown: the video autoplays muted from frame 0, so **frame 0 is the real cover**. The cover image
is shown on the profile grid (centre 3:4 crop), the Reels tab, Explore tiles and DM shares.
Research: `reports/Reels kapak hook ve izlenme.md`.

## Rules (templates/hyperframes_news/index.html follows these)

1. Frame 0 is fully composed: headline at 100 % opacity, the proof image (product screen) visible,
   no flash, fade, blur, blank or single-colour frame. Motion after that may only add energy
   (a slight push-in, a highlight sweep), never reveal the headline.
2. Cover = frame 0. The pipeline saves `cover.jpg` (frame 0.3 s) next to every Reel; schedule it as
   the custom cover in Meta Business Suite ("Kapak" / thumbnail step) and send it as `cover_url`
   via the API. Same design, so a random-frame fallback still looks right.
3. Headline: 3-6 words, at most 2 lines (66-170 px caps by length), from y≈270; the result image
   below it (920x660) is the biggest thing in the frame and ends above the bottom ~35% that
   Instagram's caption UI covers (D-17, research 2026-10-16).
   One focal point: headline on top, one cropped product screen below - no collage.
4. Everything important sits in the centre 1080x1350 block (y≈285-1635): the profile grid crops
   240 px top and bottom. Keep the top ~270 px (username / "Sponsored" band) and the right ~230 px
   (buttons) free of text; captions stay above y≈1250 (bottom ~35 % is the caption overlay).
5. Nothing that reads as an ad: no tool logo or tool-name pill at the top, no "YENİ ARAÇ" / "NEW"
   badges, no pill-shaped CTA buttons, no prices, no glossy mockup intro, no logo reveal. The
   only brand is the page's own small @thekavar.ai mark.
6. Show the real product (cropped, zoomed on the one element that proves the promise), not the
   site's marketing slogan when avoidable. Full-page screenshots read worse than one crop.
7. Dark neon is the page identity, but clarity wins: data shows no gain from contrast or
   saturation alone - the message must be understood in one glance on a phone, at 1/3 width.

## Checking a render

`python -c "import sys; sys.path.insert(0,'src'); from reel_qa import first_frame_report; print(first_frame_report('output/final/final_video.mp4'))"`
reports frame-0 blankness and brightness; open `cover.jpg` and the grid-crop preview
`cover_grid.jpg` and ask: in 1 second, at thumbnail size, do I know what this is and why I'd watch?
