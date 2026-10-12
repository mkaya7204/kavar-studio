# Design and Editorial Principles for Instagram Carousels and Story Sets (rules for a code-based template system)

Research date: 2026-10-11. Most web sources here are marketing or design-tool blogs. Instagram/Meta does not publish official safe-zone measurements, so treat px values as community consensus. Two items were verified locally rather than from the web: (1) Turkish glyph coverage, checked by parsing the cmap table of the Google Fonts TTFs served on 2026-10-11, and (2) the OFL license, checked by confirming that each family has an `ofl/<family>/OFL.txt` file in the google/fonts GitHub repo.

## 1. Grid systems, canvas sizes and Instagram UI safe zones

### Takeaway
Design carousels at 1080x1350 (4:5) with the key content inside a centred 1012x1350 (3:4) column, or design natively at 1080x1440 (3:4) if posting from the app. Stories are 1080x1920. Keep text and stickers out of roughly the top 250px and bottom 340px, with about 65px of side margin.

### Cited Findings
- Instagram switched the profile grid from square to 3:4 tiles in January 2025, and the grid crops every thumbnail to 3:4 (1080x1440). A 1080x1440 post shows on the grid without a crop. — [Inro (via search summary)](https://www.inro.social/blog/instagram-post-size); [Hopper HQ](https://help.hopperhq.com/en/articles/10907941-instagram-s-vertical-grid)
- A 4:5 image loses about 34px from each side in the 3:4 grid preview. One guide recommends designing at 1080x1350 and keeping important elements inside a centred 3:4 safe zone. — [Inro](https://www.inro.social/blog/instagram-post-size); [Krumzi](https://www.krumzi.com/blog/instagram-carousel-size-guide)
- Mosseri reportedly said in May 2025 that Instagram "now supports 3:4 aspect ratio photos" for single photos and carousels. A separate search could not find the original announcement, so this is unverified. — [Inro](https://www.inro.social/blog/instagram-post-size); not confirmed by [PostNitro](https://postnitro.ai/blog/post/post-multiple-photos-instagram-2026)
- Meta's Graph API still lists a 4:5 to 1.91:1 range, so schedulers posting via the API may crop 1080x1440 to 1080x1350. The API allows 10 slides per post, while the in-app limit is 20 (raised from 10 in August 2024). — [Inro](https://www.inro.social/blog/instagram-post-size); [PostNitro](https://postnitro.ai/blog/post/post-multiple-photos-instagram-2026); [Spur](https://www.spurnow.com/blogs/what-is-carousel-post)
- The first slide's aspect ratio sets the ratio for every slide in the carousel. Only the first slide appears on the profile grid. — [PostNitro](https://postnitro.ai/blog/post/post-multiple-photos-instagram-2026); [Inro](https://www.inro.social/blog/instagram-post-size)
- Story canvas is 1080x1920 (9:16). The common community figure is about 250px of UI at the top and bottom, which leaves a centre of about 1080x1420. — [Argil](https://argil.ai/blog/instagram-story-dimensions); [Outfy](https://www.outfy.com/blog/?p=11295); [Lilach Bullock](https://www.lilachbullock.com/instagram-story-size-best-results/)
- Argil gives different Story margins: top 250px (profile bubble, name, timestamp, progress bars), bottom 340px (reply field, send/share, link sticker landing), sides about 65px (its own convention, not a Meta spec). Its recommended design block is a centred 1080x1330. It cites Sprout Social and Hootsuite for 250/340, and also mentions a 1080x1610 safe area (about 155px top and bottom). — [Argil](https://argil.ai/blog/instagram-story-dimensions)
- Story ads have a tighter safe zone because of the CTA button and the "Sponsored" label. Reels use different buffers: 108px top, 320px bottom, 60px left, 120px right. — [First Pier](https://www.firstpier.com/resources/instagram-ad-safe-zones); [search summary of story spec guides](https://videobgremover.com/blog/instagram-story-specs)

### Inferences (proposed enforceable rules)
- **Carousel 1080x1350:** outer margin 72–96px on all sides (8–9% of width). Put critical content inside x ∈ [34, 1046] for the grid crop, which a 72px+ margin already covers. Use a 12-column grid at 1080 width (column 64px, gutter 24px, margin 72px → 12×64 + 11×24 = 1032, so use 60px columns or a 76px margin to make it fit) or a simpler 6-column grid. Use an 8px baseline unit and make every spacing token a multiple of 8.
- **Carousel 1080x1440:** use the same side margins. There is no grid crop, but leave 96px or more at the bottom so the counter and handle sit clear of content.
- **Slide-1 profile-grid crop:** 3:4 (current grid) crops nothing at 1440 and 34px per side at 1350. If an older 1:1 view applied, a 1350 slide would lose 135px top and bottom (my arithmetic, not from a source). Keep slide-1 headlines vertically centred within y ∈ [180, 1170] to survive any crop.
- **Story 1080x1920:** text safe area x ∈ [65, 1015], y ∈ [250, 1580] (top 250 / bottom 340). Interactive stickers (poll, link, question) go in a reserved block of about 900x300 around y ≈ 1150–1450, never in y < 250 or y > 1580.
- Carousel dots render **below** the image in the feed, not over it. I found no source confirming this (see Gaps), so don't reserve in-image space for them. A slide counter drawn inside the design ("03/08") is a brand choice.

### Gaps
- No official Meta document with Story safe-zone px values was found, and the sources conflict on the bottom margin (250 vs 340). The conservative 340 is recommended.
- No source confirmed where carousel pagination dots render or any overlay of the carousel "1/8" counter badge (top-right in the app). Reserving about 120x80px top-right on carousels is a cautious guess, not sourced.
- Mosseri's 3:4 announcement was not found as a primary source.

## 2. Typographic hierarchy, sizes, line length, words per slide

### Takeaway
Treat body text below 28px (on a 1080-wide canvas) as unreadable. Practical tiers are headline 64–110px, subhead 40–56px, body 30–40px and caption 22–26px. Use line-height around 1.05–1.2 for headlines and 1.3–1.5 for body, short lines of about 20–40 characters, and a hard word budget per slide.

### Cited Findings
- On a 1080px canvas, assume slides are viewed at about one-third size. Recommended sizes: headlines 60–90px, section headers 40–55px, body 28–36px, captions 20–26px. Anything under 28px is a readability problem, and the advice is to cut text rather than shrink it. — [search summary of PostNitro/Contentdrips/AdaptlyPost guides](https://postnitro.ai/blog/post/instagram-carousel-mobile-optimization-complete-guide-2024); [Contentdrips](https://contentdrips.com/blog/2026/05/instagram-carousel-size-format/)
- Point-based guidance from other blogs: headlines 30–36pt, body 24–28pt, body minimum 24pt, headings 36pt+. The units are ambiguous. — [AdaptlyPost](https://adaptlypost.com/blog/text-overlays-on-instagram-carousels); [PostNitro](https://postnitro.ai/blog/post/carousel-typography-guide-perfecting-font-sizes-and-spacing)
- Word budgets vary: more than 10 words at body size is a warning sign, and 30–50 words per slide is the maximum. — [search summary of carousel guides](https://postnitro.ai/blog/post/instagram-carousel-mobile-optimization-complete-guide-2024)
- Line height: body 1.4–1.6, headings 1.2–1.3, compact 1.0–1.2. Letter-spacing: large bold headlines −0.5 to −1px, all-caps +0.5 to +1px, short punchy phrases +1.5 to +2px. — [PostNitro typography guide](https://postnitro.ai/blog/post/carousel-typography-guide-perfecting-font-sizes-and-spacing)
- Butterick: line spacing should be 120–145% of point size, and line length should average 45–90 characters including spaces. Set CSS `line-height` without units. — [Practical Typography: line spacing](https://practicaltypography.com/line-spacing.html); [Practical Typography: line length](https://practicaltypography.com/line-length.html)
- Example em hierarchy from one tool: title 4em, body title 3em, description 1.5em, minimum body 1.2em. This implies a headline/body ratio of about 2.7–3.3×. — [PostNitro](https://postnitro.ai/blog/post/carousel-typography-guide-perfecting-font-sizes-and-spacing)
- 2026 trend pieces call expressive, oversized typography "the loudest trend", with headlines treated as the primary visual element. — [Made Good Designs](https://madegooddesigns.com/graphic-design-trends-2026/)

### Inferences (proposed enforceable rules)
- **Scale math:** a phone shows a 1080px slide at about 390–430pt wide (about 2.5–2.75 canvas px per pt). So 28px on the canvas ≈ 10–11pt on screen (the bare minimum), and 40px ≈ 15pt, close to iOS body text at 17pt. **Body default: 36–40px. Hard floor: 28px for any text, 24px only for legal/source lines.**
- **Type scale (ratio about 1.333, perfect fourth, from a 36px base):** caption 24 / body 36 / lead 48 / H2 64 / H1 85 / display 112–140. Cover (slide 1) headline 96–140px, at most 3 lines.
- **Line height:** display 0.95–1.1, H1/H2 1.1–1.2, body 1.35–1.45. Headline tracking −1% to −3% (−0.01em to −0.03em). All-caps labels +4% to +8%.
- **Line length:** Butterick's 45–90 characters is for long-form reading. With body at 36–40px in a 900–936px text column, lines run about 40–50 characters, so keep body columns at or below 900px and never more than 55 characters per line.
- **Word budget per slide:** cover at most 12 words (headline at most 8 plus kicker), content slides at most 40 words (headline at most 10 plus body at most 30), CTA slide at most 15. If the text overflows, the template should fail validation and not auto-shrink below the floor.
- **Weights:** at most 2 families and at most 3 weights per set (for example 800 headline, 500 body, 400 caption/mono).

### Gaps
- No primary or academic source specific to Instagram carousel type sizes. All size figures come from vendor blogs and partly contradict each other (pt vs px).

## 3. Fonts with full Turkish support, licensing, and Turkish casing pitfalls

### Takeaway
Every candidate font tested contains the full Turkish set (ç Ç ğ Ğ ı İ ö Ö ş Ş ü Ü plus â î û) and is SIL OFL, so all are free for commercial use. The real risk is casing: uppercase must be done with `lang="tr"` / `toLocaleUpperCase('tr')`, or "i" becomes "I" instead of "İ".

### Cited Findings
- Google Fonts metadata (fetched 2026-10-11) lists the `latin-ext` subset, which contains the Turkish glyphs, for Inter, Inter Tight, Manrope, Plus Jakarta Sans, Space Grotesk, Sora, DM Sans, Outfit, Bricolage Grotesque, Geist, Geist Mono, JetBrains Mono, IBM Plex Sans, Instrument Sans/Serif, Onest, Figtree, Urbanist, Lexend, Archivo, Schibsted Grotesk, Space Mono, Fraunces, Unbounded, Syne, Hanken Grotesk, Mona Sans, Hubot Sans, Funnel Display, Host Grotesk and others. — [Google Fonts metadata endpoint](https://fonts.google.com/metadata/fonts)
- **Local glyph verification:** cmap tables of the 700-weight TTFs served by fonts.googleapis.com were parsed for `çÇğĞıİöÖşŞüÜâÂîÎûÛ`. All of these pass: Inter, Manrope, Plus Jakarta Sans, Space Grotesk, Sora, DM Sans, Outfit, Bricolage Grotesque, Geist, Geist Mono, JetBrains Mono, Onest, Figtree, Instrument Sans, Mona Sans, Space Mono, Syne, Unbounded. Instrument Serif could not be tested because it has no 700 weight. — local test against [Google Fonts CSS API](https://fonts.googleapis.com/css2?family=Inter:wght@700)
- **License:** each of Inter, Manrope, Plus Jakarta Sans, Space Grotesk, Sora, DM Sans, Outfit, Bricolage Grotesque, Geist, Geist Mono, JetBrains Mono, Onest, Figtree, Mona Sans and Instrument Serif has an `OFL.txt` in the google/fonts repo (SIL Open Font License, which permits commercial use and embedding in images/video). — [google/fonts repo, ofl/ directory](https://github.com/google/fonts/tree/main/ofl)
- Variable axes worth using: Inter (opsz 14–32, wght 100–900), DM Sans (opsz 9–40, wght 100–1000), Bricolage Grotesque (opsz 12–96, wdth 75–100, wght 200–800), Mona Sans/Hubot Sans (wdth 75–125), Fraunces (opsz 9–144, SOFT, WONK). — [Google Fonts metadata](https://fonts.google.com/metadata/fonts)
- Unicode CLDR Turkish casing maps i→İ and ı→I. In JS, `"istanbul".toUpperCase()` gives "ISTANBUL", while `toLocaleUpperCase("tr")` gives "İSTANBUL". — [CLDR tr-Upper](https://unicode.org/cldr/cldr-aux/charts/28/delta/transform-tr-Upper.html); [Lingo.dev](https://lingo.dev/en/javascript-i18n/convert-text-case-locale-rules)
- CSS `text-transform: uppercase` applies Turkish rules only when the element or an ancestor has `lang="tr"`. Firefox implemented this in v14, WebKit in changeset r156948, and WPT tests cover it. — [Mozilla Bugzilla](https://bugzilla.mozilla.org/show_bug.cgi?id=1108616); [WebKit r156948](https://trac.webkit.org/r156948); [WebKit bug 21312](https://www2.webkit.org/show_bug.cgi?id=21312); [WPT test](https://searchfox.org/firefox-main/source/testing/web-platform/tests/css/css-text/text-transform/text-transform-upperlower-041.html)

### Inferences (proposed enforceable rules)
- Set `<html lang="tr">` on every template. For text uppercased in JS/Python before rendering, use `toLocaleUpperCase('tr-TR')`. In Python, `str.upper()` is not locale-aware, so map `i→İ` and `ı→I` manually before `.upper()`.
- Load fonts with `&subset=latin-ext` or the full family, and self-host the TTF/WOFF2 for headless rendering. If `font-display` or loading fails, fallback fonts can drop to a system face that renders differently. Add a render-time check that `document.fonts.check('700 64px Inter', 'İĞŞ')` returns true.
- Uppercase Turkish words grow taller because of the İ dot and the Ğ/Ş/Ç diacritics. Give all-caps or display lines at line-height ≥ 1.0 (≥ 1.05 when stacked) so the İ dot doesn't collide with the line above, and don't clip text containers with `overflow:hidden` tight to the cap height.
- **Suggested tech pairings (all verified for Turkish):**
  - Space Grotesk 700 headlines + Inter 400/500 body + JetBrains Mono for code/labels
  - Bricolage Grotesque (opsz 96, wdth 75–85) display + Geist body + Geist Mono
  - Manrope 800 + Manrope 500 (single family)
  - Sora 700 + DM Sans
  - Mona Sans wide 800 + Inter
- Avoid Inter as the only headline face if the goal is to avoid a generic look. That is a matter of taste: Inter is the de-facto default UI font, but I found no source on this.

### Gaps
- Kerning and mark-positioning quality for ğ/ş at display sizes was not evaluated, only glyph presence. Visually check the Ş/Ç cedilla at weights of 800 and up.

## 4. Swipe-through and seamless panorama carousels

### Takeaway
Build one master canvas of width 1080×N (by 1350 or 1440 height) and slice at every 1080px. Place a "bridge" element across each seam so part of it peeks into the next slide. Seams should fall on calm areas, not on faces or text.

### Cited Findings
- Master canvas width is 1080 × slide count, height 1350. All slides must be the same size or the seam jumps. Add a guide every 1080px, design the whole scene first, then slice. — [Blendnow](https://www.blendnow.com/blog/hwo-to-create-seamless-instagram-carousel); [Krumzi](https://www.krumzi.com/blog/seamless-instagram-carousel)
- Instagram shows a thin gap between slides during the swipe, so put seams over plain areas and not over faces or text. Sources disagree on how visible the gap is. — [Krumzi](https://www.krumzi.com/blog/seamless-instagram-carousel)
- Placing elements on the boundary between two slides creates an overlap that makes people curious. Connecting backgrounds and flowing shapes are also recommended. — [search summary of seamless-carousel guides](https://bloggingguide.com/how-to-create-a-seamless-instagram-carousel-in-canva/); [RFG Creative](https://rfgcreative.com/misc/how-to-create-seamless-instagram-carousel.html)
- Three panorama slides is often called the sweet spot, rather than stretching one image over seven. — [Krumzi](https://www.krumzi.com/blog/seamless-instagram-carousel)
- A small arrow or "Swipe to learn more" on early slides encourages the first swipes. — [MeetEdgar / search summary](https://meetedgar.com/blog/instagram-carousel-tips)
- Tools like Storrito slice panoramas into up to 20 seamless slides. — [Storrito](https://storrito.com/tools/instagram-carousel/)

### Inferences (proposed enforceable rules)
- In code, render one wide DOM canvas and screenshot each slide with a `clip` at x = i×1080. This guarantees pixel-exact seams.
- Continuity devices:
  - a line, path or timeline that crosses each seam
  - a card or screenshot overhanging the seam by 80–200px
  - a gradient background that drifts in hue across slides
  - an oversized number or headline split across a seam (only on the cover-to-2 seam)
- Validation rule: no text glyph box may intersect x = k×1080 ± 24px. Only decorative or graphic elements may cross seams.
- Swipe cue on slide 1 (and optionally 2): an arrow or "Kaydır →" placed bottom-right inside the margins, 28–36px, at 60–80% opacity. Drop it from slide 3 onward.

### Gaps
- No measured engagement data comparing seamless and discrete carousels was found.

## 5. Color, contrast, dark-mode tech aesthetics, texture and trends

### Takeaway
Hold WCAG AA as the floor: 4.5:1 for body text and 3:1 for large text (24px+ regular or about 19px+ bold, measured in CSS px). On a 1080 canvas viewed at about 1/2.7 scale, apply 4.5:1 to all text. In 2026, grain and print texture, bold saturated colour and oversized type are in. Purposeless glassmorphism, soft gradient blobs and glossy 3D now read as AI-generic.

### Cited Findings
- WCAG SC 1.4.3 (AA): 4.5:1 for normal text, 3:1 for large text. Large means at least 18pt (24 CSS px) regular or 14pt (about 18.66px) bold. The criteria are unchanged from 2.1 to 2.2. Contrast = (L1+0.05)/(L2+0.05), range 1–21. — [DisabilityWorld WCAG 2.2](https://www.disabilityworld.org/toolkit/standards/wcag/1-4-3-contrast-minimum/); [TestParty](https://testparty.ai/blog/wcag-contrast-ratio-guide-2025); [Lea Verou contrast-ratio](https://github.com/leaverou/contrast-ratio)
- Carousel guides also recommend at least 4.5:1 for body text and note that contrast can matter more than size. — [AdaptlyPost](https://adaptlypost.com/blog/text-overlays-on-instagram-carousels)
- 2026 trends:
  - "Anti-AI texture and imperfection" (grain, paper, risograph, halftones) is in. It signals that "a person made this".
  - Bold, maximalist colour and expressive oversized type are in.
  - Out: "generic AI-default aesthetics" (the "soft-gradient, glossy 3D blob" look), "over-engineered gradients and glassmorphism … applied without purpose", Corporate Memphis, and sterile thin-sans minimalism.
  — [Made Good Designs](https://madegooddesigns.com/graphic-design-trends-2026/)
- Other trend roundups agree that anti-AI human craft is the defining movement: "flawlessness … starts signalling that a machine made it". Glassmorphism is described elsewhere as "back" in web design, which is a conflicting signal. — [DesignCloud](https://designcloud.app/blog/graphic-design-trends); [VCAD](https://www.vcad.ca/about/spotlights/graphic-design-trends-2026-the-human-side-of-ai/); [Aufait UX](https://www.aufaitux.com/blog/latest-web-design-trends/)

### Inferences (proposed enforceable rules)
- **Dark tech base:** use a near-black background with a slight hue, not #000 (for example #0B0D12 or #0E1116), and off-white text (#EDEEF2 / #F5F5F0, about 17–18:1). Muted text should stay at or above 7:1 (for example #A8AEBB on #0E1116, which needs checking). Use one saturated accent (electric lime, signal orange, cobalt) for at most 10–15% of the area, and verify accent-on-bg contrast ≥ 3:1 for UI and ≥ 4.5:1 if it carries text.
- Contrast check in CI: compute WCAG contrast for every text node against its sampled background (render, then sample the pixels behind the bbox). Fail anything below 4.5:1. Text over photos or gradients needs a scrim of 40–60% black or a solid chip.
- **Grain:** an SVG `feTurbulence` (baseFrequency 0.8–0.9, numOctaves 2–3) overlay at 4–8% opacity with `mix-blend-mode: overlay` or soft-light. Keep it under text at low strength. Export as high-quality JPG or PNG; Instagram recompression will smear heavy grain, so 6% or less is safer (an assumption, untested).
- Avoid the AI-template look:
  - no default purple-to-blue mesh gradients, no glossy 3D blobs, no stock emoji icons
  - use a fixed brand palette of 1 bg, 1 surface, 1 text, 1 muted and 1–2 accents
  - use asymmetric layouts on a grid, with real screenshots or data
  - use editorial devices such as kicker labels, rules and footnote-style sources
- Glass panels: only over real content (a screenshot) with backdrop blur of 20–40px, a 1px border at rgba(255,255,255,0.12) and text contrast still verified.

### Gaps
- No primary data on how much Instagram's JPEG recompression degrades grain or noise. Trend sources are agency blogs without data.

## 6. Presenting product screenshots

### Takeaway
Always frame screenshots: a minimal browser frame for web, a device frame for mobile. Use generous padding (80–100px+), a brand-colour background, large readable UI, and zoom or crop to the one area that matters. Callouts and annotations explain it, and sensitive data is removed.

### Cited Findings
- A bare screenshot is ambiguous (desktop app? mobile? mockup?), and a browser frame removes that ambiguity. Raw captures also pick up bookmarks and extension icons. — [Screenhance](https://screenhance.com/blog/browser-mockup-best-practices); [BrightCoding](https://blog.brightcoding.dev/2025/12/08/from-boring-screenshots-to-viral-mockups-the-ultimate-2025-guide-to-creating-stunning-mobile-browser-mockups)
- Match the frame to the platform: browser or MacBook for web, iPhone for iOS, Pixel/Samsung for Android. Minimal frames (window dots plus a border) are the default. Full chrome with tabs and a URL bar only makes sense when the URL is part of the story. Skip frames for isolated components. — [Screenhance](https://screenhance.com/blog/browser-mockup-best-practices)
- "Use more padding than you think. Default 60px, try 80–100px." Gradient backgrounds work better than solid ones in feeds. — [Screenhance](https://screenhance.com/blog/website-screenshot-mockup-guide)
- Key content should be recognizable at small (feed) sizes: large UI elements, high contrast. Export at 2× as PNG for sharpness. Remove passwords and personal info. — [Screenhance](https://screenhance.com/blog/browser-mockup-best-practices); [WildAndFreeTools](https://wildandfreetools.com/blog/screenshot-mockup-generator-free-no-watermark/)

### Inferences (proposed enforceable rules)
- A full-page desktop screenshot shrunk to 900px wide makes UI text about 6–8px, which is illegible. Rule: a screenshot's native UI text must render at 22px or more on the canvas. Otherwise crop or zoom (scale ≥ 1.5× on a 1440-wide capture) and focus on one region.
- **Zoom-in callout pattern:** the full frame dimmed to 40% opacity in the background, plus a magnified crop card (radius 24px, 1–2px border, accent ring) and a connector line from the source region.
- **Annotations:**
  - numbered accent circles (48–56px) tied to short labels (at most 6 words)
  - hand-drawn-style arrows for the "human" feel
  - highlight boxes with a 3–4px accent stroke, radius 12px
- **Shadows:** a soft layered shadow (for example `0 24px 64px rgba(0,0,0,.35), 0 4px 12px rgba(0,0,0,.2)`) on dark backgrounds, plus a 1px inner border so the frame separates from a dark bg.
- **Bleed crop:** let a device or browser frame run off one edge (crop 15–30%) for dynamism. This doubles as a seam-crossing element (Section 4).
- Capture screenshots at deviceScaleFactor 2 and downscale.

### Gaps
- No authoritative (non-vendor) source on screenshot presentation for social media was found. Engagement claims such as "300% CTR" are unverified and were excluded.

## 7. Editorial: hooks, one idea per slide, story arc, CTA, brand system

### Takeaway
Slide 1 is an ad for the carousel: a bold promise or curiosity gap in at most 8–10 words with high contrast. Then give one idea per slide in a hook → context → value → proof → CTA arc, with a consistent brand frame (logo or handle, counter, progress) on every slide.

### Cited Findings
- The first slide makes or breaks the carousel: lead with a bold headline that creates an information gap and a clear promise. Hook types: striking visual, pain point, shocking stat, provocative question, using bold colours, large fonts and high contrast. — [PostNitro viral carousels](https://postnitro.ai/blog/post/viral-instagram-carousels-strategies-2025); [Pippit](https://www.pippit.ai/resource/increasing-engagement-with-carousels-a-2025-instagram-guide)
- **Suggested arc:** slide 1 hook/problem, slides 2–4 context and solutions, slides 5–7 proof (cases/stats), final slide CTA (save, share, comment, next step). — [Pippit](https://pippit.capcut.com/resource/increasing-engagement-with-carousels-a-2025-instagram-guide); [Sked Social](https://skedsocial.com/blog/creative-ways-to-use-instagram-carousels-in-2025?Sid=1)
- Too much text per slide makes content hard to read on a phone, and too many fonts or colours cause visual fatigue. — [MeetEdgar](https://meetedgar.com/blog/instagram-carousel-tips)
- Mosseri has said carousels "often get more reach" than static posts. — [PostNitro](https://postnitro.ai/blog/post/post-multiple-photos-instagram-2026)
- An explicit "one idea per slide" principle was **not** found stated in the sources searched (see Gaps). — [Learn Social Media substack (strategy context)](https://learnsocialmedia.substack.com/p/carousel-strategy-101-what-works)

### Inferences (proposed enforceable rules)
- **Template schema per carousel** (6–10 slides; 7–8 is ideal for news/tech):
  1. Cover: kicker (category, 24–28px caps) + headline (≤ 8 words, 96–140px) + optional visual + swipe cue.
  2. "Why it matters" / context.
  3. to N−2. One idea each: headline ≤ 10 words + ≤ 30 words body or 1 visual.
  N−1. Summary or takeaway.
  N. CTA: one action only ("Kaydet", "Takip et @handle", "Yorumda X yaz"), handle and logo large, optional preview of the next post.
- **Rhythm:** alternate dense and airy slides (text slide → visual or big-number slide). Every 3rd slide should be a "breather": a big stat, quote or screenshot.
- **Brand frame on every slide:**
  - logo or handle at the top-left or bottom-left (28–32px, 60% opacity)
  - counter "03/08" at the bottom-right in mono, 24–28px
  - optional thin progress bar (4–6px) at the bottom margin
  Keep the frame identical in position across slides so swiping feels anchored. Put a source line (≤ 22–24px, muted) at the bottom of fact slides.
- The cover should work as a standalone grid thumbnail. Test by downscaling to 360×480: the headline must still be legible.

### Gaps
- No primary research or platform data supports specific slide counts or word counts. The "71% engage more deeply" claim found in searches came from an untrustworthy domain and was excluded.

## 8. Story-specific design: sequencing, sticker placeholders, text placement

### Takeaway
Treat a Story set as 3–7 frames with one message each. Keep text in the 250–1580px vertical band, reserve a clear zone in the centre to lower-middle for stickers (link, poll), and never place stickers near the top-left avatar or the bottom reply bar.

### Cited Findings
- Link stickers have been available to all accounts since 2023. Place them near the centre or lower third, away from edges and from other interactive stickers. Replace the URL with a short descriptive label, pair it with CTA visuals (a sticker on a blank background gets fewer taps), and don't let it block key content. — [Linkly](https://linklyhq.com/blog/how-to-share-link-instagram-story); [SocialBee](https://socialbee.com/blog/how-to-add-link-to-instagram-story); [Flick](https://www.flick.social/learn/blog/post/how-to-get-more-engagement-on-your-instagram-link-stickers)
- Keep poll stickers out of the top-left corner (avatar) and off key imagery. Custom answer labels and emojis help. — [Animoto](https://animoto.com/blog/news/how-to-news/how-to-set-up-instagram-story-poll); [Shopify](https://www.shopify.in/blog/instagram-stickers)
- The bottom ~340px holds the reply field, share controls and the link sticker landing area. The top ~250px holds the progress bars and profile. — [Argil](https://argil.ai/blog/instagram-story-dimensions)

### Inferences (proposed enforceable rules)
- **Frame sequence for a news or tech Story set:**
  1. Hook frame (big headline, 88–120px)
  2. 1–3 detail frames (one fact each; screenshot plus ≤ 25 words)
  3. Interaction frame (poll/quiz placeholder)
  4. CTA frame (link sticker placeholder "Detaylar →" or "Carousel'ı gör")
- Story text sizes run larger than in carousels because the format is full-screen: body 40–48px, headline 80–120px, floor 32px. Text column x 80–1000 (920px wide).
- **Sticker placeholder:** a dashed or ghost rectangle of about 840×260 (poll) or 600×140 (link), centred at y ≈ 1250–1400. In the export, either omit it or keep it as a subtle guide card with a label ("Ankete katıl ↓"). Make sure no text lies under the placeholder.
- Keep progress continuity across frames: identical brand-bar position, the same background family, and optional frame numbers ("1/4") just below y = 250.
- Every frame must be understandable in about 5 seconds (the default story duration for images, which needs verifying): ≤ 25 words.

### Gaps
- No sourced guidance on optimal Story set length or sequencing was found. The 5-second default display for image Stories was not verified in this session.
- No official sticker dimensions. The placeholder sizes above are estimates.

## 9. Accessibility: alt text, contrast, not relying on colour

### Takeaway
Write per-slide alt text at publishing time (Advanced settings → Accessibility → Write alt text, with one field per carousel image). Meet 4.5:1 contrast, and pair colour coding with icons or labels.

### Cited Findings
- Mobile flow: after editing, open Advanced settings → Accessibility → Write alt text. The option is available during creation and editing. Carousels show a thumbnail and text field for each image, so each slide gets its own alt text. — [Kapwing](https://kapwing.com/resources/alt-text-instagram); [Carleton](https://carleton.ca/webservices/2023/how-to-add-alt-text-to-social-media-posts); [Elgin](https://elgin.edu/accessibility/social-media/instagram/)
- Desktop: the Accessibility accordion sits below the caption on the final publishing screen. Existing posts can be edited via ⋯ → Edit → Edit alt text (unconfirmed against Instagram docs). — [Accessible Social](https://accessible-social.com/images-and-visuals/alt-text/instagram); [Socialk.it](https://socialk.it/en/blog/instagram-alt-text)
- Contrast thresholds: 4.5:1 for body text and 3:1 for large text (WCAG 1.4.3). — [DisabilityWorld](https://www.disabilityworld.org/toolkit/standards/wcag/1-4-3-contrast-minimum/)
- The Graph API alt-text field was not researched (see Gaps).

### Inferences (proposed enforceable rules)
- The template system should output an `alt_text[]` array alongside the PNGs, one per slide. Generate it from the slide's own text plus a short description of the visual, ≤ 125 characters for the visual part, and in Turkish.
- Never encode meaning only in colour (for example a red/green good/bad comparison). Add ✓/✗ icons, labels or position. Test palettes against deuteranopia simulation.
- Avoid text baked over busy imagery without a scrim. Avoid thin weights (< 400) below 40px on dark backgrounds. Body text should be sentence case; reserve all-caps for short labels of ≤ 4 words.
- Repeat critical slide text in the caption, because screen readers read the caption and alt text, not the pixels.

### Gaps
- Whether the Instagram Graph API (used by schedulers) supports setting alt text per carousel child was not verified.
- The official Instagram Help Center page for alt text was not retrieved directly. The flow is described by third-party guides.
