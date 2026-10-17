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

- **Log every decision in `DECISIONS.md`** (user, 2026-10-16): date, the user's words, what was
  built, where it lives, what test guards it. Same commit as the change. Never delete an entry.

## 1. Locked decisions (date and source: the user)
1. **No prices, ever** (2026-10-11): no prices, currencies, payment models, free/paid, trials or
   discounts in any post, image, caption or voiceover. The only exception is a paid collaboration
   the user announces per post. Enforced by `PRICE_PATTERN` / `price_mentions` (src/script_writer.py),
   writers, the proof-crop prompt, the "Biz denedik" judge, and the editor.
2. **Editor gate** (2026-10-13): only content the editor review (src/editor_review.py) marks
   "publish" is queued. FIX_ROUNDS = 2 for carousels, REEL_ATTEMPTS = 3.
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
7. **Schedule** (schedule.json): 07:30 Reel (Turkey), 11:45 Reel, 12:30 carousel, 18:00 carousel, 20:30
   Reel. Two Reels a day since 2026-10-16 ("günde tek reels yeterince takipçi getirmiyor"); the 07:30
   Reel since 2026-10-17 (D-29): AI and technology in Turkey only (src/tr_reel.py), produced FIRST in
   its own stage, the rest after it is scheduled (08:00 at the latest). The best Reel ("Biz denedik")
   takes 20:30, a tool Reel 11:45 (`_build_queue`). In every slot, content_ranker picks what reaches
   more people inside the slot's concept; the concepts don't change.
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
1. `python daily.py fetch`: git pull, download today's cloud run, unpack. If today's run is
   missing or late, start `gh workflow run produce.yml` and track it with a session cron. Don't
   ask the user "bitti mi".
2. Read `output/logs/<date>.log`. Handle each rejected item with the §1.3 workflow.
3. Record yesterday's numbers (the page's only feedback loop, audit 2026-10-16): in Business Suite
   Content -> Published, copy Reach / Views / Follows / Likes / Comments / Shares / Saves / average
   watch for every post at least a day old into `python src/post_metrics.py add rows.json`
   (kinds: reel, trial_reel, carousel, trial_carousel). Never quote numbers that aren't there.
4. Schedule the queue at its times. For a Reel, upload `upload.mp4` (under the 10 MB browser upload
   limit; made by produce.yml) and cover.jpg as the thumbnail. For a hand-fixed Reel, `shrink.yml`.

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
