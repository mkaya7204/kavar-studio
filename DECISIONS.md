# KAVAR decision log (karar defteri)

One entry per decision: **when**, **who said what** (the user's own words where we have them),
**what was built**, and **where it lives / what guards it**. Newest at the bottom.

When you change how something works, add an entry here in the same commit. If a decision is
replaced, don't delete the old entry: add a new one that says "replaces D-xx". CLAUDE.md §1 lists
the decisions that are currently locked; this file explains why they exist and how they got there.

---

## D-01 · 2026-10-11 · No prices, ever
- **User:** pricing "doesn't concern us". The page informs, it doesn't sell. Paid brand collaborations are the only exception, announced by the user per post.
- **Built:** `PRICE_PATTERN` / `price_mentions` / `NO_PRICE_RULE` (src/script_writer.py) used by every writer, the editor, the proof-crop prompt and the "Biz denedik" judge. Extended 2026-10-16 to Kr, kuruş, TRY/GBP, "bin TL", freemium, hashtags, and the hook the judge picks.
- **Guarded by:** tests/test_policy.py. CLAUDE.md §1.1.

## D-02 · 2026-10-13 · Cloud production, editor gate
- **Decision:** production runs in GitHub Actions (produce.yml), not on the PC. Only content the editor (src/editor_review.py) marks "publish" is queued. Carousels get 2 fix rounds, Reels 3 attempts.
- **Guarded by:** tests/test_decisions.py (`FIX_ROUNDS`, `REEL_ATTEMPTS`, editor rejects when it can't review). CLAUDE.md §1.2.

## D-03 · 2026-10-14 (permanent 2026-10-16) · Rejected content is fixed by hand, then taught
- **User:** doesn't fully trust the editor's verdicts yet; real cases first, then teach the editor. 2026-10-16: make it permanent.
- **Built:** during "yükle" Claude reviews each rejection, fixes it in the cloud (rerender.yml, trial-rerender.yml, news-test.yml), shows it to the user, then writes a lesson in rules/editor_lessons.md, which the editor and writers load (`skill_rules.editor_lessons()`).
- **Guarded by:** CLAUDE.md §1.3. Lessons are never deleted without the user's approval.

## D-04 · 2026-10-15 · Cloud-first on a 4 GB PC
- **User:** "the PC ran out of memory" is not an acceptable answer; agreed things must not be re-decided alone.
- **Built:** `.claude/hooks/block_heavy.py` blocks ffmpeg, renders, main.py, carousel.py, trial_reel.py, `daily.py produce`, sleep and polling loops locally.
- **Guarded by:** the hook itself. CLAUDE.md §0.

## D-05 · 2026-10-15 · Free model access only
- **User:** "Sadece ücretsiz yollar". No paid AI APIs for model tests.
- **Built:** model_trial uses OpenRouter `:free` models and official Hugging Face Spaces only. The OpenRouter key was created 2026-10-16 with a 1 dollar limit and no credits.

## D-06 · 2026-10-15/16 · "Biz denedik": we run new models ourselves
- **User:** "kalıcı ... ilerde tekrar kavga etmeyelim".
- **Built:** `testable_first()` ranks runnable releases first; `run_trial()` runs the model (LLM via OpenRouter, image via official Spaces); `_judge` drops outputs with prices, logos, real people or unsafe content; news_writer leads with the test; src/trial_reel.py makes the 20:30 Reel from it.
- **Fixes the same day:** answers cut by our token limit are never shown (they blamed the model for our cap); answer cards are shown whole and stay inside what the hook zoom leaves visible (`PROOF_SAFE`).
- **Guarded by:** tests/test_biz_denedik.py. CLAUDE.md §1.4.

## D-07 · 2026-10-16 · Reel voice = ElevenLabs "George"
- **User:** "ses iyi, onu kullan". Don't propose another voice.
- **Built:** `ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"`. Since the audit (D-14), ElevenLabs is the only provider: no fallback voice, no env override. If ElevenLabs fails, no Reel is made.
- **Guarded by:** tests/test_decisions.py (`test_voice_is_george`, `test_only_george_ever_speaks`). CLAUDE.md §1.6.

## D-08 · 2026-10-16 · Reel outro keeps @thekavar.ai + "TAKİP ET"
- **Why:** it was removed once without asking (2026-10-14) and brought back (11dcfdc).
- **Guarded by:** tests/test_decisions.py (`test_reel_outro_keeps_handle_and_follow_pill`). CLAUDE.md §1.8.

## D-09 · 2026-10-16 · Two Reels a day
- **User:** "Reel 11.45 de olsun carusel 12.30 bunu artık standart hale getirelim her gün olucak". Reason: "günde tek reels yeterince takipçi getirmiyor".
- **Built:** schedule.json has 11:45 Reel, 12:30 carousel, 18:00 carousel, 20:30 Reel. `_build_queue` puts the best Reel ("Biz denedik") at 20:30 and a tool Reel at 11:45. A job time budget stops new renders when time runs out.
- **Guarded by:** tests/test_decisions.py (`test_schedule_slots`), tests/test_daily.py. CLAUDE.md §1.7.
- **Open:** the ElevenLabs free quota (10,000 credits/month) can't carry two Reels a day; the user will decide later (D-15).

## D-10 · 2026-10-16 · Hooks: the model is the clear subject
- **User:** "çocuğa açıklattık" read as if something was done to a child.
- **Built:** the Nemotron Reel was fixed by hand to "Yapay zekâ atasözünü iki cümlede açıkladı" (rerender/2026-10-16_nemotron-3-5.json).
- **Still to do:** turn this into a writer rule and a lesson.

## D-11 · 2026-10-16 · Browser uploads stay under 10 MB
- **Why:** the Chrome extension uploads at most 10 MB; the GLM Reel was 16 MB.
- **Built:** produce.yml writes `upload.mp4` (two-pass, about 9 MB) next to every Reel; shrink.yml does the same for hand-fixed Reels. "Yükle" uploads `upload.mp4` and cover.jpg.

## D-12 · 2026-10-16 · No press-site photos
- **User:** "Hayır, kendi görselimiz". Reason from the report: Instagram's 2026 originality rule and copyright (press photos are often Getty).
- **Built:** The Verge and TechCrunch were removed from news_sources.json. Qwen, Google Research and Microsoft Research were added. News now comes only from the companies' own blogs, whose images are their own press assets, or from our own test outputs.
- **Guarded by:** tests/test_policy.py (`test_no_press_sites_as_news_sources`). CLAUDE.md §1.9.

## D-13 · 2026-10-16 · The 940 followed accounts
- **User:** "Takibi yavaş yavaş azalt".
- **How:** the user unfollows by hand, slowly, below Instagram's limits. Claude never unfollows on the account's behalf.

## D-14 · 2026-10-16 · Status report and audit
- **What:** research on Instagram growth and on agent architecture, a full code audit, and live Business Suite numbers. Report: https://claude.ai/artifact/45e9rTLCApk6NfLAMzqREF. The user: "çok yerinde tespitler".
- **Agents:** no "manager + supervisor per agent" system. The pipeline already follows the recommended workflow + evaluator pattern. Use parallel candidates + a picker where it helps, and separate researchers for research like this report.
- **Built the same day:**
  - George only (D-07); voice capped at 23.5 s before any credits are spent.
  - The judged hook is price-checked.
  - Caption checks: no broken hashtags ("#İ#nvida" went live), no hashtag-only captions.
  - Claude Code CLI pinned to 2.1.301.
  - The test that wrote into the real day log now uses a sandbox.
  - Feedback loop: state/metrics/posts.json (src/post_metrics.py), seeded with 18 posts, filled at every "yükle". Trial Reels are logged as their own kind.
- **Guarded by:** tests/test_policy.py, tests/test_decisions.py, tests/test_metrics.py.

## D-15 · 2026-10-16 · Deferred by the user ("sonra ele alalım")
- The ElevenLabs quota: 17 of 10,000 credits left, so no Reel until it resets or the plan changes.
- The Instagram API setup.
- Labelling 40-60 past items to calibrate the editor.
- Collab outreach.
- **Rule:** don't push these. Mention the voice quota only when it blocks a Reel.

## D-16 · 2026-10-16 · Every change is logged here
- **User:** "Yaptıklarını kayıt altına alıyor musun ... şöyle karar aldık şunu uyguluyoruz".
- **Rule:** every decision, and every change to how the page works, gets an entry here in the same commit. CLAUDE.md points to this file.

## D-17 · 2026-10-16 · Openings and covers follow research, not trial and error
- **User:** "derinlemesine ... araştırmalara bakıp stratejimizi ona göre yapalım böyle deneme yanılma ile zaman kaybetmeyelim".
- **Research:** 30+ sources (Meta/Nielsen, TikTok Marketing Science, Google ABCD, YouTube, vidIQ/1of10, eye-tracking and curiosity studies). Strategy page: https://claude.ai/artifact/PjdHvauHUEz7Y1nS8HiRyz
- **Proposed spec (waiting for the user's approval):**
  - Frame 0 shows the result (our test output) on 60-70% of the screen.
  - The headline is 2 lines and 3-6 words.
  - The voice starts on frame 0, the first related change comes at 1.0-1.3 s, and the curiosity is answered at 2.5-3 s.
  - No logo or name chip in the opening.
  - Everything sits inside the 3:4 band.
  - Covers have 1-5 words; carousel slide 1 has at most 6 words plus a swipe cue.
- **Testing:** Trial Reels change only the first 3 s. Skip rate is the main metric. Each test is repeated 3-4 times because reach is small. It waits for the voice quota (D-15).
- **Status:** branch hook-motion has only the "first change at ~1.1 s" part; not merged.

## D-18 · 2026-10-16 · D-17 approved and built (branch hook-motion)
- **User:** "Tamam bunlara sadık kalınarak yap".
- **Built:**
  - Reel: headline 3-6 words / at most 32 characters on 2 lines (script_writer check, reel-hook-writer and reel-cover-designer skills).
  - Reel frame 0: the result box is 920x660 (`PROOF_SIZE`), the biggest thing in the frame. At ~1.1 s the headline becomes a small label, the result steps forward, and the source stamp appears on it.
  - Carousel cover: 3-6 words (`HEADLINE_WORDS = 6`), bigger type, "KAYDIR →" pill.
- **One deviation, told to the user:** the research asked for the result on 60-70% of the frame AND for safe zones. Instagram's caption overlay covers the bottom ~35% (also an editor rule), so the result box ends above it: about 1.4x the old box instead of 60-70%.
- **Before production:** silent design previews (trial-rerender `silent=yes`, news-test) are shown to the user. Merge only after the user's yes.

## D-19 · 2026-10-16 · Version B = the report's spec (b), word for word (branch hook-research)
- **User:** "raporu olduğu gibi yap ... en ufak bir değişiklik yapma kesin ve net". Then: "Sonra ikisini karşılaştırma yaparız" (A = hook-motion, B = hook-research).
- **B, line by line from the report:**
  - Frame 0: the result box is ~60% of the frame, inside the 3:4 band (920x1100, y 575-1675). The headline is 2 lines at 130 px from y 240. The voice starts on frame 0. A small source stamp, no logo or handle.
  - 0.0-0.4 s: a punch-in from 1.00 to 1.06.
  - ~1.0 s: the headline steps back to a top label, with a zoom onto the detail (1.06 -> 1.2).
  - 0.5 s onward: captions, the hook included. 3-word chunks, clear of the bottom ~20%.
  - The handle and the follow pill appear only in the outro.
  - The headline is 3-4 words, because frame 0 takes 3-6 and the cover takes 1-4 and the cover is frame 0. At most 22 characters.
  - The editor checks the cover at 10% size and in the 3:4 crop.
- **Where the report gives a range or a choice:**
  - 130 px is the only size in "130-160 px" that fits 2 lines plus the result box in the band.
  - "zoom onto the key detail" was picked over "a second output", so the change stays about output 1, which the voice is talking about.
- **A vs B:** both are shown as silent previews and the user compares them. Nothing goes to main before that.
