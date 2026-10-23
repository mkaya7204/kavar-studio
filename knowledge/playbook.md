# KAVAR playbook: problem -> cause -> right fix

The knowledge base of KAVAR's own fixing agent (D-44, the user 2026-10-23: "herşeyi öğret ... karşılaşmamış
olan hatalarında araştırıp ... öğret"). Built from every record we have, not from memory:
state/metrics/reels.json (35 Reels, 10-13..10-23: 12 passed, 23 rejected), state/failures.json (39 outcomes),
rules/editor_lessons.md (13 lessons), the user's 5 notes on the calibration page (D-24), DECISIONS.md
(D-01..D-43) and the web research in part B (sources listed, with how far to trust them).

How to use it: when a draft is rejected or a measurement fails, find the problem below, check the listed
cause first, apply the fix, then run the check again. A problem that is not here: look at the frames
yourself, name the cause in one sentence, fix it, and Claude adds it here the next morning (part D).

Hard limits (never "fix" these away): no prices, currencies, free/paid, trials or discounts (D-01, D-32);
voice = ElevenLabs George only (§1.6); only the editor's "publish" goes out (§1.2); only our own or the
companies' own pictures (§1.9); the outro keeps @thekavar.ai + "+ TAKİP ET" (§1.8).

---------------------------------------------------------------------------------------------------------

## A. Problems we have seen (most frequent first)

### A1. The proof does not prove the hook (20 of 23 rejected Reels)
- **Looks like:** the picture under the hook is a slogan card ("Work with most powerful agents", Craft
  Agents 10-17; "Your inbox, wherever you work", Inbox Zero 10-19), a feature list (Salience 10-18), a
  changelog line (Ultracite 10-17), a Dock bar instead of the notch (Korinotch 10-18), a model name with
  no result (Step 5 Preview 10-18), an abstract "4" (Gemini 10-19), another model's announcement
  (EmbeddingGemma 10-13), a header photo that shows no translation (Meet 10-23).
- **Causes found:** (1) tool sites show marketing, not the product working; (2) the hook was written
  before anyone looked at the pictures, so it promised something no picture shows; (3) a page with one
  picture gave the same picture three times.
- **Right fix, in this order:**
  1. Look at every picture we have (figures, video stills, product screens, README, feature pages) and
     pick the one that shows the product DOING the thing: its interface with real content, its output,
     a before/after.
  2. If none shows the promise: rewrite the hook and cards to promise what the best picture really
     shows (a smaller, true promise beats a big unproven one).
  3. If no picture shows the product at all (only logos, slogans, mascots): the topic is not filmable.
     Drop it and take the next candidate; never ship a Reel without proof.
- **Check:** describe the proof picture in one sentence without reading the hook; the hook must follow
  from that sentence.

### A2. Cut text (14 of 23 rejected Reels; 4 days in a row)
- **Looks like:** "odo.is" for todo.is (10-21), "in Google Mee" (10-22, 10-23), a chat bubble cut at
  the side (bonds 10-21), the top line of a site cut (Composio 10-21), "workspaceupdates.googleb…" at the
  tag's edge (10-23), an answer card ending mid-sentence (Nemotron 10-16).
- **Causes found (all fixed in code, D-36..D-43):** ImageOps.fit / centre crops; fixed-step page windows
  that ran through a line; the 1.12 zoom pushing a 960 px picture to 1075 of 1080 px; a long domain wider
  than its tag; the hook zoom cropping inside the proof box.
- **Right fix:** never crop to fill; show the picture whole and smaller (letterbox on the template blue);
  a page window ends in a gap between lines; leave 48 px free at every frame edge at full zoom; long
  labels shrink to fit; if it still touches an edge, build the Reel without zoom (capture "still").
- **Check (measured, D-43):** `reel_qa.cut_frames`: sharp detail in the outer 24 px of the frame in two
  frames in a row = cut (clean 0.3-0.83, cut 1.68-3.23 on the real frames). Also look at the hook box
  edges at 0, 1 and 2.5 s.

### A3. Text over text / overlapping elements (6 rejected Reels)
- **Looks like:** a caption pill on the site's own text (Kai, Pancake, Salience), the shrinking headline
  under the proof box at 2.5 s (Train with Pasta, Craft Agents, Krea 3), the domain stamp on the proof's
  text (Craft Agents).
- **Causes found:** captions on during site shots; a fixed 150 px lift of the proof box; the stamp placed
  on the box.
- **Right fix:** captions hide while a picture speaks (D-30 era template); the box lifts only into the
  room the headline frees; stamps sit under the box. Never shorten a good headline to dodge a template
  fault: fix the layout.
- **Check:** frames at 2.5 s and in the middle of each shot: no two text blocks touch.

### A4. Claims stronger than the source (Pancake 10-15, Krea 10-19, captions 10-16, the user's notes)
- **Looks like:** "Tekrarlayan satış işi ajana kalıyor" when the source never says it; "Düzenleme 8
  saniyenin altında" with no "şirkete göre" on screen; "kusursuz" for a test with a visible flaw; "35
  süper bilgisayar geliştiriyor" for "is used in".
- **The user's own rules (calibration notes, 10-17):** a strong quote must keep its meaning ("compromised"
  does not mean every model was hacked); a company's own label ("ilk frontier modeli") is not a fact;
  "açıyor", "yardım ediyor", "ölçeklendiriyor" are different claims, and plan, current product and achieved
  result must never be mixed; "hazır" must not suggest a whole ecosystem when only some partners are
  named; "güvenli geliştirildi" is not "güvenli olduğu kanıtlandı".
- **Right fix:** use the source's own verb and actor; put the attribution ("şirkete göre", "OpenAI'a
  göre") on every surface where the claim appears (cover, card, caption, story); name the scope (which
  countries, which customers, which plan); no superlatives the source doesn't use.
- **Check:** for each claim on screen, quote the sentence in the source that says it. No quote = remove
  or soften.

### A5. Prices and money on screen (Knocket 10-13, Kai "No credit card required" 10-14, FLUX "50 Kr"
  10-16, Docs "$1,730.00" 10-23)
- **Cause:** prices inside pictures (pricing tables, phone screens with budgets, generated signs).
- **Right fix:** choose another picture; if the only picture has money in it, drop the topic. Never blur
  or cover it (it still reads as a price box). Plans / beta / "kredi harcıyor" without amounts are allowed
  (D-32).
- **Check:** read every number in every picture; any currency sign, amount, "free", "trial", "credit card"
  = reject the picture.

### A6. Length and pacing (Vincentt 29.9 s, MentionBird 27.2 s; static 7.8 s, 3.8 s, 3.17 s)
- **Right fix:** voiceover 34-42 words (14-26 s); a visual change at least every 2-3 s; no scene longer
  than ~3 s without movement.
- **Check:** `pacing_report`: duration 14-26 s, longest static stretch.

### A7. Ad look in the first seconds (Knocket logo bar, ngram "Create video" button, Popcraft "Try Now",
  Product Hunt badge)
- **Right fix:** frame 0 = one clear message + proof; no tool logo, CTA button, badge or "NEW" sticker in
  the first 3 s; the tool name not in the first sentence.

### A8. Text and voice disagree (Ultracite card 02/03, Inbox Zero 10-19)
- **Right fix:** card N is on screen while point N is spoken: same benefit, same order, one benefit per
  point (`card_voice_mismatch`).

### A9. Small text faults that cost a whole Reel
- Misspelled hashtag (#applentelligence), broken Turkish caption with a wrong subject (Gemini 10-19),
  a headline whose subject can be misread (Nemotron "atasözünü çocuğa açıklattık"), wrong date from the
  page (HF 10-17).
- **Right fix:** these are the fixer's easiest wins: rewrite the line, keep everything else.

### A10. Empty or wrong pictures
- An empty card caught mid-entrance (Ultracite: look 1 s later before calling it empty), a play-button
  still (Copilot 10-20), a gradient or blank figure (OpenAI reader 10-20), a picture placed on the wrong
  slide (FairStress 10-22), a shrunk unreadable page (WhatsApp guide 10-18).
- **Right fix:** only pictures `article_capture.informative()` accepts; each picture placed where its
  own caption / alt text matches the slide; a page screenshot only where its text is readable on a phone.

### A11. Off concept
- No AI in it (WhatsApp guest links, MeetPaw, Tower); developer-only; a viewer cannot try it.
- But: the ranker also threw out clear AI tools (10-23: Claude Duet, Bits, Playad). An AI tool the
  ranker doubts is tried last, not dropped (D-42); the editor decides.

---------------------------------------------------------------------------------------------------------

## B. Research for problems not seen yet (2026-10-23)

Trust levels: **official** = Instagram / Meta's own pages; **reported** = a named Instagram executive
quoted by trade press; **heuristic** = marketing blogs (rules of thumb, often conflicting).

1. **What Instagram ranks on (reported):** Adam Mosseri, January 2025: the top signals are watch time,
   likes and sends; track average watch time, likes per reach and sends per reach; sends matter slightly
   more for people who don't follow you yet. -> Our page grows from non-followers, so every Reel needs a
   reason to send it ("arkadaşına gönder" must name WHO would want it). The "sends weigh 3-5x" figure has
   no primary source; don't quote it.
   Sources: [Social Media Today](https://www.socialmediatoday.com/news/instagram-shares-algorithm-insights-2025/738034/),
   [Social Samosa](https://www.socialsamosa.com/news-2/instagram-reveals-key-factors-for-boosting-reach-8646916).
2. **Originality (official):** recommendations favour original work (filmed / owned by you, not posted
   on Instagram before); aggregators who repost others' content go down. Our own logo is fine; other
   apps' watermarks reduce reach. -> Our proof pictures must be framed as ours (our design, our test,
   our words), never a re-post of a company video with its watermark; the source's logo is never the
   main element.
   Sources: [Instagram Creators: recommendations and originality](https://creators.instagram.com/recommendations-and-originality),
   [Instagram feed recommendation changes](https://creators.instagram.com/blog/instagram-feed-recommendations-changes-announcement),
   [Mosseri on own logos, Social Media Today](https://www.socialmediatoday.com/news/instagram-clarifies-including-your-own-logo-on-a-reel-is-ok/730852).
3. **Recommendation eligibility (official):** content can stay up but not be recommended (low quality,
   sensitive, regulated goods); repeated breaks make the whole account ineligible; Account Status shows
   it. 2021 guidance: Reels that are blurry, low resolution, bordered, mostly covered by text or carry
   another app's watermark are recommended less. -> Check Account Status weekly (Monday page); our
   frames must not be mostly text; no borders around the whole video; pictures sharp.
   Sources: [Instagram Help: recommendations guidelines](https://help.instagram.com/313829416281232),
   [Instagram Creators: eligibility tips](https://creators.instagram.com/blog/instagram-recommendations-eligibility-tips-creators),
   [Tubefilter 2021](https://tubefilter.com/2021/02/10/instagram-reels-with-tiktok-watermark-less-discoverable/).
4. **Safe zones (heuristic, conflicting):** keep text out of the top ~14-15 %, the bottom ~30-35 %
   (~670 px), ~120 px on the right (buttons) and ~48-65 px on the left. Our template uses 270 px top /
   bottom 35 % already; add the right-hand 120 px for any text a viewer must read.
   Sources: [revid.ai checker](https://www.revid.ai/instagram-reels-safe-zone),
   [House of Marketers](https://houseofmarketers.com/guide-to-safe-zones-tiktok-facebook-instagram-stories-reels/),
   [Canadian Tire design system (48 px margins)](https://brand-qa2.canadiantire.ca/en/ctr/design-system/omni-channel/motion/margins-and-safe-space.html).
5. **Opening seconds (heuristic):** no intro, no context first; the hook in the first frame; one idea per
   Reel; the most valuable point early; an ending that loops back invites a rewatch. Matches our rules.
   Sources: [Quso](https://quso.ai/blog/instagram-reels-best-practices.html),
   [Buffer](https://buffer.com/resources/instagram-reels-instructions-and-ideas-for-small-businesses/).
6. **Readable captions (heuristic):** bold sans-serif; on vertical video roughly 6-10 % of frame height
   for key words; at most two lines; ~32-37 characters a line; white with an outline / dark plate over
   moving backgrounds; test on a real phone.
   Sources: [Terra Translations](https://terratranslations.com/?p=4284),
   [Kineclip checklist](https://kineclip.com/blog/caption-readability-checklist-short-videos-2026/).
7. **Carousels (heuristic):** the cover decides; a second slide may be shown to people who skipped the
   first (attributed to Mosseri, no primary quote: make slide 2 able to stand alone); judge by saves and
   swipe-through, not likes; a clear last-slide action.
   Sources: [PostNitro](https://postnitro.ai/blog/post/viral-instagram-carousels-strategies-2025),
   [MeetEdgar](https://meetedgar.com/blog/instagram-carousel-tips).
8. **Claims (newsroom policies):** say where each fact comes from (our test, the company, a third party);
   marketing language is not a verified fact; headlines never overstate the body; AI tools increase the
   duty to double-check. Same as A4 and the user's notes.
   Sources: [MIT Technology Review guidelines](https://technologyreview.com/editorial-guidelines),
   [IT Brief standards](https://itbrief.news/editorial-standards), [Kingy AI](https://kingy.ai/?p=926330).

---------------------------------------------------------------------------------------------------------

## C. What our own numbers say (state/metrics/posts.json, 36 posts recorded through 10-20)
Too few to steer by yet (one follow from 36 posts by 10-22, D-38). Read them every Monday (§2.5); add a
rule here only when at least 3 posts of a kind point the same way.

---------------------------------------------------------------------------------------------------------

## D. Learning loop
- Every rejection, measurement failure and fix is in state/failures.json with its category.
- When the agent cannot fix something, Claude fixes it by hand during "yükle", then adds here:
  the problem as seen, the cause found, the fix that worked, and the check that proves it. A cause in
  code also gets a test on the real example (CLAUDE.md §0).
- A section here is changed only when a new real example shows it is wrong; never deleted without the
  user (same rule as rules/editor_lessons.md).
