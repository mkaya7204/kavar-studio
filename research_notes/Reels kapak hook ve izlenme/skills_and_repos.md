# Skills, MCP servers and open-source repos for Reels hooks, covers, captions and retention

Research date: 2026-10-12. Research only. Nothing was installed or run.
Star counts are approximate and come from the GitHub pages on the research date. GitHub often hid the "last commit" date, so where it says "date not shown", activity was judged from the commit count and the release page.

Verdict key:
- **ADOPT**: install or use it as is (after reading the code).
- **BORROW**: read it and copy the ideas into our own skill or Python code. Do not install it.
- **SKIP**: not worth it for us.

Our setup: Windows 10 with 4 GB RAM. The pipeline is Python: news → Claude script (Turkish) → ElevenLabs TTS with timestamps → HyperFrames (HTML/GSAP, headless Chrome) → ffmpeg → Instagram Graph API. Carousels are rendered with Playwright. We already have a carousel-designer skill and an editor review step (`claude -p`).

---

## 0. Most important finding: we already have most of the tooling

- The **HyperFrames skills are already installed** in this Claude Code session: hyperframes, hyperframes-cli, embedded-captions, faceless-explainer, motion-graphics, hyperframes-animation, hyperframes-studio, media-use and others.
  - Repo: https://github.com/heygen-com/hyperframes (about 61.7k stars, Apache-2.0, about 5.5k commits, very active, maintained by HeyGen).
  - Ships 21 agent skills.
  - The CLI has `lint`, `check`, `snapshot`, `compare`, `keyframes` and `transcribe`.
  - The `hyperframes-studio` skill documents **caption tracks and safe zones**.
  - **Verdict: ADOPT (already in place).** Use `hyperframes check` and `snapshot` for frame-based visual review before writing our own. Read the safe-zone and caption guidance in hyperframes-studio and hyperframes-animation (it has 24 named text-animation effects) before writing the retention-editor skill.
- Word-level captions: we already get word timestamps from ElevenLabs. **We do not need Whisper, WhisperX, captacity or similar.** Every caption repo below is useful only for its *styling and paging logic*.

---

## 1. Claude / Agent Skills

### anthropics/skills (official)
- URL: https://github.com/anthropics/skills
- About 180k stars. Maintained by Anthropic. Most skills are Apache-2.0; the document skills (docx, pdf, pptx, xlsx) are source-available, not open source.
- Contains 19 skills: academy-guide, algorithmic-art, brand-guidelines, canvas-design, claude-api, discernment-nudge, doc-coauthoring, docx, frontend-design, internal-comms, mcp-builder, pdf, pptx, skill-creator, slack-gif-creator, theme-factory, web-artifacts-builder, webapp-testing, xlsx.
- **No video, hook or social-media skill.**
- Relevant pieces:
  - `skill-creator` (already installed as anthropic-skills:skill-creator): use it to **write and eval our hook-writer, cover-designer and retention-editor skills**.
  - `frontend-design`: anti-generic-design rules for the HTML templates we build covers from.
  - `canvas-design` and `theme-factory`: ideas for the cover look.
- Security: official, low risk.
- **Verdict:** ADOPT skill-creator for building and evaluating our skills. BORROW frontend-design rules for the cover and first-frame skill. SKIP the rest.

### coreyhaines31/marketingskills
- URL: https://github.com/coreyhaines31/marketingskills
- About 54k stars, MIT, about 1,000 commits, active in 2026. Maintainer: Corey Haines (well-known SaaS marketer).
- Includes skills named copywriting, copy-editing, social, video and image, each with `references/` and `evals/` folders.
- The `social` SKILL.md is moderately substantive:
  - Hook types: curiosity, story, value and contrarian, with templates.
  - A "No AI Tells" anti-pattern list.
  - A "3-second rule": visual hook, verbal hook and text overlay all land in the first second.
  - Second-by-second structures for 15–30 s and 30–60 s videos.
  - Caption rule: at most 2 lines and 3–5 words per line, high contrast, timed to speech.
- Weaknesses: generic, English and SaaS-oriented. Instagram guidance is thin. Some stats are unsourced (for example "captions +25-40% watch time").
- Security: pure markdown, low risk.
- Overlap: partly with our carousel-designer and editor review.
- **Verdict: BORROW.** Copy the "No AI Tells" list, the 3-second rule and the caption-line limits into our hook-writer and retention-editor skills, translated and adapted for Turkish. Installing all ~40 marketing skills would only add trigger noise.

### remotion-dev/skills (Remotion official agent skills)
- URL: https://github.com/remotion-dev/skills
- About 5.1k stars, 89 commits, maintained by the Remotion team.
- Skills include remotion-best-practices, remotion-captions, remotion-markup and remotion-render.
- Remotion uses React. Its own license is **not** plain open source: it is free for individuals and small companies, and larger companies need a paid license.
- We do not use Remotion, and the HyperFrames remotion-to-hyperframes skill covers porting if we ever need it.
- Useful idea: `@remotion/captions` → `createTikTokStyleCaptions()` (https://www.remotion.dev/docs/captions/create-tiktok-style-captions). It groups word timestamps into "pages" with three rules:
  - `combineTokensWithinMilliseconds` sets the maximum page length.
  - `breakOnSilenceAfterMilliseconds` starts a new page on a pause.
  - Each page stays on screen until the next page starts, so captions never flicker off during pauses.
  - This is about 30 lines to reimplement in Python on top of the ElevenLabs alignment.
- **Verdict: BORROW the caption-paging algorithm only. SKIP installing.**

### vyralcontent/content-skills
- URL: https://github.com/vyralcontent/content-skills
- About 136 stars, MIT, **only 1 commit** (a one-off upload).
- Seven skills: viral-short-form, viral-tiktok-content, viral-youtube-shorts, viral-instagram-reels (includes Trial Reels testing), viral-hooks, viral-short-form-ideas, viral-captions-and-ctas.
- viral-hooks uses a "three-layer hook" (visual + verbal + on-screen text) and creator archetypes (Kallaway, MrBeast, Hormozi).
- Credibility: low (small, single commit, marketing-funnel author).
- **Verdict: BORROW.** Skim viral-hooks and viral-instagram-reels for archetype names and anti-patterns. Do not install.

### arhamhi/hooksmith
- URL: https://github.com/arhamhi/hooksmith
- **2 stars**, MIT, 8 commits. Also listed on claudskills.com, whose static scan graded it "A".
- Content is surprisingly well structured:
  - Every opening is built as "spoken hook + on-screen text + open loop + **rehook** (attention reset within 3–10 s) + visual anchor + payoff".
  - Six hook families and ten named patterns.
  - A 50-point audit rubric.
  - An anti-pattern list and a filler test.
  - Commands: init, generate, audit, rewrite, rehook, caption.
- Credibility: very low (unknown solo author). The ideas match what other sources say.
- **Verdict: BORROW.** The "rehook" concept and the 50-point audit-rubric shape fit our best-of-5 hook selection and retention editor well. Write our own Turkish version.

### charlie947/social-media-skills
- URL: https://github.com/charlie947/social-media-skills
- About 4k stars, MIT, 18 commits, packaged as a Claude plugin.
- Mostly LinkedIn-focused.
- Relevant skills:
  - hook-generator: six hook angles per topic.
  - post-scorer: scores drafts against your **own post history**.
  - reels-scripting: analyses a reference Reel.
  - youtube-thumbnail: produces a Gemini prompt.
  - voice-builder: voice.md and about-me.md files that every other skill reads.
- **Verdict: BORROW.** Two ideas are worth copying:
  - The "voice.md read by every skill" pattern: a single Turkish voice and style file shared by the hook writer, script writer and editor.
  - The "post-scorer against own history" pattern: the base for our metrics feedback loop.

### ComposioHQ/awesome-claude-skills (discovery list)
- URL: https://github.com/ComposioHQ/awesome-claude-skills
- About 75k stars (according to a mirror).
- Relevant entries:
  - instagram-automation, tiktok-automation, youtube-automation: these run through **Composio's hosted service** (your account tokens go to a third party; one link returned 404).
  - content-research-writer: generic.
  - twitter-algorithm-optimizer: X only.
  - video-downloader.
- **Verdict:** use it for discovery only. SKIP the Composio automation skills: we already publish through the official Graph API, and they would add a third-party token holder.

### Commercial "free" skill packs (Blotato viral-hooks, claudskills.com registry entries)
- These are lead magnets for paid SaaS.
- **Verdict: SKIP** (at most, read them for ideas).

---

## 2. Open-source repos (captions, auto-editing, covers, hooks, retention, quality)

### Auto-editing and clipping
- **auto-editor**: https://github.com/WyattBlue/auto-editor
  - About 5.5k stars, public domain (Unlicense), written in Nim, active.
  - Cuts silence and dead space based on loudness or motion.
  - Our videos are TTS with no dead air.
  - **Verdict: SKIP.** If we ever want tighter pacing, ElevenLabs timestamps plus ffmpeg `silencedetect` do the same job without new code.
- **SupoClip** (open-source OpusClip alternative): https://github.com/FujiwaraChoki/supoclip
  - About 1.3k stars, **AGPL-3.0**, about 350 commits.
  - Stack: Docker, FastAPI, Next.js, AssemblyAI.
  - The LLM gives each clip **hook / engagement / value / shareability** scores, and an AI hook title is overlaid on the first seconds.
  - Too heavy for 4 GB RAM (Docker plus a web stack), and long-video clipping is not our use case.
  - **Verdict: BORROW the 4-axis scoring rubric** for the best-of-5 hook selection. SKIP the code (and AGPL).
- **MoneyPrinterTurbo**: https://github.com/harry0703/MoneyPrinterTurbo
  - About 130k stars, MIT, very popular, mostly Chinese community.
  - Flow: topic → script → TTS → stock footage → subtitles. Officially runs on 4 GB RAM and Windows.
  - It is a cruder version of what we already have, with no hook logic.
  - **Verdict: SKIP.** At most, look at its subtitle style options (outline, background, position).
- autoclip and other "clip-generator" repos: subtitle-based highlight finders for long videos. **SKIP** (not our use case).

### Word-level animated captions
- **captacity**: https://github.com/unconv/captacity
  - 139 stars, MIT. Uses Whisper and MoviePy.
  - We already have word timestamps and render in HTML.
  - **Verdict: SKIP.**
- Remotion `createTikTokStyleCaptions`: **BORROW the paging logic** (see section 1).
- HyperFrames `embedded-captions` skill (already installed) has a 35-style caption catalog.
  - It is built for talking-head footage, but its quiet "anchor rail" default and style names are a good reference for our caption look.
  - **Verdict: ADOPT for reference.**

### Covers and thumbnails
- No credible open-source "thumbnail generator" stood out; most are wrappers that call an image API.
- Our approach (HTML template → Playwright or HyperFrames `snapshot`) is already the best fit for 4 GB RAM.
- Ideas to borrow:
  - anthropics `frontend-design` and `canvas-design` (anti-generic design rules).
  - charlie947 `youtube-thumbnail` (title → visual concept).
- **Verdict: BORROW ideas only.**

### Hook libraries and datasets
- **No credible open hook dataset exists.** What exists:
  - Paid packs (Gumroad and similar).
  - Commercial APIs (Virlo "600k hooks", OverseerOS): unverifiable and paid.
  - Small markdown skills (hooksmith, vyralcontent).
- The most reliable "dataset" is **our own**: log every hook we post together with its Reel metrics (see section 3, `reels_skip_rate`), then feed the top and bottom examples back into the hook-writer prompt.
- **Verdict: SKIP external datasets; build our own.**

### Retention analysis and Instagram insights collection
- See section 3. No standalone OSS repo is needed; it is about 50 lines of Python against the Graph API we already use for publishing.

### Video quality scoring (blank frames, freezes, safe zones)
- **ffmpeg built-in filters** (we already have ffmpeg). **Verdict: ADOPT.**
  - `blackdetect`: black or blank frames.
  - `freezedetect`: frozen or stuck animation.
  - `silencedetect`: audio gaps.
  - `signalstats` (YLOW/YHIGH): washed-out frames.
  - `ebur128`: loudness check, target about -14 LUFS.
  - All run in one ffmpeg pass on the final MP4, need no new dependency and use little RAM.
- **PySceneDetect**: https://github.com/Breakthrough/PySceneDetect
  - About 5.2k stars, BSD-3, release v0.7.2 on 2026-10-11 (active).
  - Detects cuts and fades, so it can measure **cut or visual-change frequency** (pacing). Pip-installable and runs on CPU, but it adds OpenCV (about 100 MB+ RAM while running).
  - **Verdict: optional ADOPT later.** Start with ffmpeg `select='gt(scene,0.3)'`, which gives scene-change timestamps with no new package. Move to PySceneDetect only if that is not enough.
- **Text safe-zone check**: no good OSS tool exists.
  - Since we render HTML, check it **in the DOM before rendering**: Playwright reads `getBoundingClientRect()` of text elements and checks them against the Reels UI-safe box (the top ~14% and bottom ~20-35% are covered by UI; the right edge is covered by the action buttons).
  - Then do a frame-based visual review: extract 4–6 frames with ffmpeg and give them to Claude for review.
  - **Verdict: build our own** (cheap, about 40 lines).

---

## 3. MCP servers

### Meta / Instagram
- **Official Meta Ads MCP** (`https://mcp.facebook.com/ads`, reported launch 2026-04-29, Business OAuth, about 29 tools).
  - Only secondary sources were found (pasqualepillitteri.it, mcp.directory); I did not see Meta's own page.
  - It is for **ads and campaigns**, not organic Reels insights.
  - **Verdict: SKIP** (we don't run ads; no prices or ads policy).
- Community Instagram MCP servers:
  - AleemHaider/instagram-mcp (6 stars, Python).
  - luminarylane/instagram-mcp-server (TypeScript).
  - ycp64 instagram-mcp and jlbadano/ig-mcp (directory listings).
  - All are tiny, unvetted, single-author projects, and each needs **our long-lived Page access token** (which can publish to the account). That is a real security risk for little gain.
  - **Verdict: SKIP.** Call the Graph API directly from our Python `daily.py` instead.
- **What to collect ourselves (official IG Media Insights, REELS)** (https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights/):

  | Metric | What it means | Status / note |
  |---|---|---|
  | `reels_skip_rate` | Share of views that skipped within the first 3 seconds | Estimated, "in development". **This is our hook-quality metric.** |
  | `ig_reels_avg_watch_time` | Average watch time | Retention proxy |
  | `ig_reels_video_view_total_time` | Total playback time, including replays | "In development" |
  | `views` | Plays on Instagram | "In development" |
  | `reach` | Unique accounts reached | Estimated |
  | `saved`, `shares` | Saves and shares | Strongest distribution signals for Reels |
  | `likes`, `comments`, `total_interactions` | Engagement | `total_interactions` is "in development" |
  | `reposts` | Reposts | |

  - `plays`, `impressions` and `clips_replays_count` were deprecated in April 2025 (v22.0). Do not use them.
  - Plan: pull these about 24 h and 72 h after posting and store them per post next to hook text, hook variant ID, cover variant and length. That table is the metrics feedback loop.
  - Needs permission `instagram_manage_insights` (or the Instagram Login equivalent).

### ElevenLabs
- **elevenlabs/elevenlabs-mcp** (local): https://github.com/elevenlabs/elevenlabs-mcp
  - About 1.5k stars, MIT, **archived on 2026-08-20** and deprecated in favour of the hosted MCP at `https://api.elevenlabs.io/v1/mcp` (OAuth). Tools spend credits.
  - Our pipeline already calls the ElevenLabs API directly, with timestamps.
  - **Verdict: SKIP.**
  - Optional: connect the hosted MCP only for interactive voice experiments in Claude Code. It costs credits, so be careful that the agent doesn't burn them.

### Video tools
- No video MCP server is worth adding. The HyperFrames CLI and skills, ffmpeg and Playwright already cover rendering and inspection.
- **Verdict: SKIP.**

---

## 4. General security notes

- Agent Skills are markdown, but skills can also bundle scripts that Claude may run. **Read every file before copying a skill into `.claude/skills`.** Prefer to rewrite ideas into our own skills.
- Never give the Instagram Page token or the ElevenLabs key to third-party MCP servers or hosted "automation" skills (Composio and similar). The token can publish and delete posts.
- AGPL code (SupoClip): do not copy it into our pipeline.
- Remotion: company licensing rules apply; we don't use it anyway.
- 4 GB RAM: avoid anything that needs Docker, local Whisper or large models. ffmpeg filters and small Python scripts are fine.

---

## 5. Short action list for our new skills

1. **hook-writer skill**
   - Build and evaluate it with skill-creator.
   - Ideas to take: the hooksmith structure (spoken hook + on-screen text + open loop + rehook), the marketingskills "No AI Tells" list, and the SupoClip 4-axis scoring for best-of-5 selection.
   - Feed it a shared Turkish `voice.md` (charlie947 pattern).
2. **cover / first-frame skill**
   - Use the anthropics frontend-design rules and our HTML templates.
   - Check the safe zone in the DOM, then render a snapshot (`hyperframes snapshot` or Playwright).
3. **retention-editor skill**
   - Caption paging rules (Remotion algorithm): at most 2 lines, 3–5 words per line.
   - A rehook every few seconds.
   - Scene-change frequency measured with ffmpeg `scene`.
4. **Visual QA step**
   - One ffmpeg pass with blackdetect, freezedetect, silencedetect and ebur128.
   - Extract 4–6 frames and have `claude -p` review them.
5. **Metrics loop**
   - Graph API → `reels_skip_rate`, `ig_reels_avg_watch_time`, `saved`, `shares`, `views` at 24 h and 72 h.
   - Store them per hook and cover variant, and feed the best and worst hooks back into the hook-writer prompt.
