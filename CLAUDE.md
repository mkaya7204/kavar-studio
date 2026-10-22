# KAVAR (@thekavar.ai) — project rules

This file loads into every Claude session in this repo. The user is a solo owner who works
outside during the day and often controls the session from the phone. They have had to repeat
agreed decisions too often, so **this file is binding**. Follow it instead of improvising.

## 0. How to work here
- **Agreed = locked.** Never change, undo or "improve away" a decision in §1 without the user's
  explicit approval in chat in the current session. If something seems wrong, say so and ask.
  Don't silently change it.
- **Verify before claiming.** Never state metrics, follower counts, post results or "what works"
  from old notes. Look at the live source (Business Suite / Instagram in Chrome, the run log) or
  say you haven't seen it. Check a note's date against today.
- **Don't assume, check.** Before saying something works, show it working: a cloud run, its log,
  the rendered files. Report failures plainly.
- **Cloud-first (enforced by `.claude/hooks/block_heavy.py`, never weaken it).** The PC has 4 GB
  RAM. No ffmpeg, renders, main.py, `daily.py produce`, sleep or polling loops locally. Start
  cloud runs (`gh workflow run ...`), check once (`gh run view`), and track with a session cron.
  gh is at `C:\Program Files\GitHub CLI\gh.exe`.
- **Production window.** `produce.yml` runs at 03:17, 04:47 and 06:17 UTC (06:17 / 07:47 / 09:17 TRT); later
  ones skip a day that is already produced. Don't push untested changes
  to `main` after 02:30 UTC. Test every change first with `news-test.yml` (and `-f reel=yes` for
  the Reel) and with the invariant tests (§3).

- **Stabilization freeze (D-38, user 2026-10-22: "Evet").** In 11 days: 158 commits, 36 decisions, 15 of
  39 slots filled, 1 follow from 36 posts. Until both daily slots are filled 7 days in a row: no new
  feature, slot, concept or decision. Only fixes of what exists, each with a test. Report the 7-day
  count to the user before proposing anything new.

- **Log every decision in `DECISIONS.md`** (user, 2026-10-16): date, the user's words, what was
  built, where it lives, what test guards it. Same commit as the change. Never delete an entry.

## 1. Locked decisions (date and source: the user)
1. **No prices, ever** (2026-10-11): no prices, currencies, payment models, free/paid, trials or
   discounts in any post, image, caption or voiceover. The only exception is a paid collaboration
   the user announces per post. Enforced by `PRICE_PATTERN` / `price_mentions` (src/script_writer.py),
   writers, the proof-crop prompt, the "Biz denedik" judge, and the editor.
   **D-32 (2026-10-18), allowed:** the plan / package a feature comes in ("Pro planında"), beta or limited
   access, "kredi harcıyor / kullanım hakkından düşüyor" without amounts, and why. Still banned: amounts,
   currencies, discounts, campaigns, trials, "bedava / ücretsiz" as a selling line.
2. **Editor gate** (2026-10-13): only content the editor review (src/editor_review.py) marks
   "publish" is queued. FIX_ROUNDS = 2 for carousels, REEL_ATTEMPTS = 3.
   D-33 (2026-10-18) fixed a rejected silent Reel draft with src/reel_fixer.py. **D-38 (2026-10-22): switched
   off** (REEL_FIX_ROUNDS = 0): its picture fixes cropped the proof (cut text in 12 of 14 fix rounds). A
   rejected Reel draft is rejected; the empty slot is filled from the reserve (D-37) or by hand (§1.3).
   Every picture in a proof box is shown whole, never cropped (`_fit_whole`). Claude failures are logged
   with their reason, and a day with nothing ready ends the cloud run with exit 1.
3. **Rejected content → Claude fixes it by hand, then teaches the editor** (2026-10-14, made
   permanent 2026-10-16). During the morning "yükle", for each rejection:
   - read the verdict and decide whether it was right;
   - fix the post by hand in the cloud (`rerender.yml`, `news-test.yml`);
   - show it to the user before scheduling;
   - add a lesson to `rules/editor_lessons.md` (format in the file).

   The editor and the writers load that file automatically (`skill_rules.editor_lessons()`).
   Never delete a lesson without the user's approval.
4. **"Biz denedik"** (2026-10-15/16, the user: "kalıcı ... ilerde tekrar kavga etmeyelim"): new
   AI models are run by us and the real result leads the post.
   - daily.py: `testable_first()` ranks news. A tested carousel takes the first carousel slot.
     `produce_trial_reel()` makes the 20:30 Reel from it; tool Reels fill the other Reel slots.
   - src/model_trial.py: free routes only (OpenRouter `:free` with OPENROUTER_API_KEY; official
     HF Spaces only). The judge drops outputs with prices, logos, real people or unsafe content,
     and unjudged outputs are never used.
   - src/news_writer.py: the test leads the post, results are stated honestly, at most 2 detail
     slides, no jargon (`_trial_problems`). src/trial_reel.py builds the Reel.
5. **Free model access only** (2026-10-15): no paid AI APIs for tests unless the user says so.
6. **Reel voice = ElevenLabs "George"** `JBFqnCBsd6RMkjVDRZzb` (2026-10-16): "ses iyi, onu kullan".
   Only provider in config.json; no fallback voice, no env override (tests/test_decisions.py). Two
   accounts (D-26): `ELEVENLABS_API_KEY`, then `ELEVENLABS_API_KEY_2` when the first is refused; both speak
   George. If both fail, no Reel is made; tell the user. `probe.yml` shows both accounts' state.
   Don't propose another voice. Voice is spent only on the Reel the editor approved (D-30, 2026-10-18):
   attempts use a silent draft voice, then `src/voice_final.py` voices the approved one once.
   **D-34 (2026-10-18):** George says every product / company name the way Turkish tech people say it, also
   new names: `tts_engine.spoken_text` (hand-checked `rules/pronunciation.json` first, then names Claude
   learns before voicing, kept in `state/pronunciations.json`). Captions and screens keep the real spelling.
7. **Schedule** (schedule.json). **D-38 (2026-10-22), in force now:** 12:30 carousel and 20:30 Reel only,
   until both are filled 7 days in a row. The guide Reel is made first every morning and takes 20:30 when
   there is no "Biz denedik" Reel (then it goes to the reserve). Product Hunt tool Reels are paused
   (`tool_reels: false`); when they come back, a tool with no real product screen is skipped before any
   script (main.py). The text below is the schedule before D-38, kept for when slots are added back.
   Before: 07:30 Reel, 11:45 Reel, 12:30 carousel, 18:00 carousel, 20:30
   Reel. Two Reels a day since 2026-10-16 ("günde tek reels yeterince takipçi getirmiyor"). The best
   Reel ("Biz denedik") takes 20:30, a tool Reel 11:45 (`_build_queue`), news carousel 12:30.
   **D-31 (2026-10-18):** 07:30 Reel and 18:00 carousel = the GUIDE concept: features and right use of
   known AI models / companies' products, in which mode or way they work best (official docs as the
   source, tried by us where possible; never paid/free). The Turkey Reel (D-29) is cancelled. The
   guide Reel went live on `main` on 2026-10-18 after two clean guide Reels (the user: "tamam"); 18:00 stays
   a news carousel until the guide carousel is built. In every slot, content_ranker picks
   what reaches more people inside the slot's concept; the concepts don't change.
8. **Reel outro** shows the handle @thekavar.ai with a small "+ TAKİP ET" pill (11dcfdc). It
   was once removed without asking; never again.
9. **Brand:** handle @thekavar.ai (brand.json). Never use other creators' content. No press-site photos
   (2026-10-16, the user: "kendi görselimiz"): news comes only from the companies' own blogs
   (news_sources.json), whose images are their own press assets, or our own test outputs.
10. **Posting:** during "yükle" Claude schedules the approved queue in Meta Business Suite
    (Chrome Profile 2; open a new tab if one freezes; never kill Chrome). New formats and
    hand-fixed posts are shown to the user first. Sending files to the phone for manual upload
    is a last resort, after asking.

## 2. Morning "yükle"
**D-38 order: publish first, analyse after.** On 10-21 four ready posts never went out because the
session hit its usage limit while still analysing. Steps 1 and 4 come before anything else.

1. `python daily.py fetch`: git pull, download today's cloud run, unpack. If today's run is
   missing or late, start `gh workflow run produce.yml` and track it with a session cron. Don't
   ask the user "bitti mi". Then go straight to step 4 for everything that is ready.
2. Read `output/logs/<date>.log`. Handle each rejected item with the §1.3 workflow.
   **D-37 (2026-10-22):** an empty slot is filled FIRST from `state/reserve.json` (editor-approved posts
   that were never published), if one fits the slot's concept and is still current (fix 'bugün/dün' in the
   caption); only then spend tokens on a fix or a new run. `python daily.py reserve` lists it (files ready
   in reserve/<name>/); `reserve keep HH:MM` keeps today's unposted ready item, `reserve used N` drops a
   posted one. The cloud run's surplus (approved, no slot) is kept automatically by `fetch`.
3. Record yesterday's numbers (the page's only feedback loop, audit 2026-10-16): in Business Suite
   Content -> Published, copy Reach / Views / Follows / Likes / Comments / Shares / Saves / average
   watch for every post at least a day old into `python src/post_metrics.py add rows.json`
   (kinds: reel, trial_reel, carousel, trial_carousel). Never quote numbers that aren't there.
4. Schedule the queue at its times. For a Reel, upload `upload.mp4` (under the 10 MB browser upload
   limit; made by produce.yml) and cover.jpg as the thumbnail. For a hand-fixed Reel, `shrink.yml`.
   **D-39:** read the "self-correct:" lines of the log and `python daily.py failures` (last 7 days per kind,
   paused kinds, skipped hosts); tell the user what the system changed by itself and why.
5. **Mondays (D-38):** one page for the user from `state/metrics/posts.json`: per post reach, views,
   average watch, follows; days with both slots filled. Next week changes only what these numbers show.
   Keep cloud test runs few late in the week: the cloud and this session share one Claude usage limit.

## 3. Safety net
- `tests/` holds offline invariant tests for the decisions above. They run on every push
  (`.github/workflows/checks.yml`) and before production. A failing test means a locked
  decision broke. Fix the code, not the test, unless the user changed the decision.
- `rules/editor_lessons.md` holds the editor and writer lessons (§1.3).
- `RISKS.md` holds the known failure modes and their mitigations. Keep it current when you add
  a new failure mode.

## 4. Map
- produce.yml → `daily.py produce` → news: `carousel.py produce_news` (capture → model_trial →
  news_writer → render) → editor; Reel: `src/trial_reel.py` or `main.py` (script_writer →
  tts_engine → hyperframes_builder) → editor; queue → artifact.
- Test runs: `news-test.yml` (url, reel=yes|no), `rerender.yml` (fix a Reel by hand),
  `probe.yml` (network).
- The user's to-do list lives in Claude's memory (open-items). Start fixing sessions there.
