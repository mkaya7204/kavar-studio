# Risks and mitigations

Last full review: 2026-10-16. The night audit covered the daily run end to end, plus an
invariant-test design. Keep this file current: when a new failure mode appears, add it here
with its mitigation and the test that covers it. Status: ✅ mitigated and tested, 🟡 mitigated
but not covered by a test, 🔴 open.

## A. The day produces nothing

| Risk | Mitigation | Status |
|---|---|---|
| GitHub starts the scheduled run hours late or skips it (10-13/14/15) | Root cause: GitHub's schedule is best effort, ~5 h late every day (D-25). cron-job.org starts it with `workflow_dispatch` at 06:17 TRT; produce.yml's 3 crons (06:17, 07:47, 09:17 TRT) are the backup. A guard step skips a day already produced, in seconds. `daily.py fetch` takes the newest finished run that has today's queue | ✅ test_guards, test_daily |
| A crashed or empty run marks the day as done and blocks the retries | `state/last_produce.json` is written only when the queue has a ready item | ✅ test_daily |
| The Reel stage crashes or the 120-min job times out after the carousels passed | The queue is saved right after the carousels. The Reel stage is wrapped. Each Reel run times out at 30 min | ✅ test_daily |
| One story raises an unexpected error and stops the whole run | Each story is wrapped; it is logged, marked used, and the next story is tried | ✅ test_daily |
| A Claude Code CLI install is broken (npm left a non-executable binary, 10-15) | Verified after install, 3 retries, fails early | ✅ test_guards |
| The Claude login (CLAUDE_CODE_OAUTH_TOKEN) expires | Writers return None, the editor rejects, and the run logs it. The user must renew the token with `claude setup-token` | 🔴 not detectable ahead of time; check the log at "yükle" |
| Feeds are down or there is no fresh news | `fetch_news` skips dead feeds and the queue stays empty. The tool Reel is still made | 🟡 |
| HF Space or OpenRouter is slow or down | Image test budget is 10 min. One failing endpoint ends that Space. Any trial error means "no test" and a normal carousel | ✅ test_biz_denedik |
| The test's extra writer rules (jargon, ≤2 details) fail every draft | The story is written again as a normal news carousel without the test | 🟡 |

## B. Something against page policy goes out

| Risk | Mitigation | Status |
|---|---|---|
| A price in text, captions or hashtags (incl. "50 Kr", "kuruş", "100 bin TL") | `PRICE_PATTERN` in every writer, plus hashtags. Editor gate | ✅ test_policy |
| A price or logo inside an image (our test output, site crop) | Image prompts forbid text, prices and logos. The judge drops unusable outputs. Unjudged outputs are never used. The proof-crop prompt forbids them. The editor looks at every slide/frame | ✅ test_policy, test_biz_denedik |
| An unsafe or random user HF Space is called | Official Spaces only (the article's company or HF demo accounts) and a blocked-word list | ✅ test_biz_denedik |
| A wrong model is tested ("gpt-5" → "gpt-5-nano") | Model keys must be ≥4 characters. The note names the exact model id, and the writer must say if it is a smaller variant | ✅ (matching) / 🟡 (wording) |
| Overstated cover or claims | Writers keep to the article's facts and numbers (number check). Editor gate. Lesson in rules/editor_lessons.md | 🟡 |
| Our test output credited to the publisher, or vice versa | Our figures and cover are credited "KAVAR denemesi". In the Reel the source label is "KAVAR denemesi" | ✅ |
| Unedited, unchecked content posted | Nothing is queued without the editor's "publish". Without an editor the verdict is "reject" | ✅ test_decisions |

## C. Agreed decisions get lost

| Risk | Mitigation | Status |
|---|---|---|
| A later session changes a locked decision | CLAUDE.md §1 (loaded every session) and invariant tests on every push (checks.yml); production also runs them | ✅ |
| Heavy work or waiting on the 4 GB PC | `.claude/hooks/block_heavy.py`, now also for trial_reel.py and the carousel renderer | ✅ test_guards |
| An editor rejection is not learned from | §1.3 workflow; rules/editor_lessons.md is loaded by the editor and the writers | ✅ test_guards |
| Numbers quoted from old notes | CLAUDE.md §0 "verify before claiming" | 🟡 (behavioural) |

## D. Known open items (not fixed tonight; see Claude's open-items list)

- The LLM route of "Biz denedik" needs the user's free OPENROUTER_API_KEY secret. Until then only image models are tested.
- The Instagram API token is missing, so publishing is manual via Business Suite (Chrome Profile 2, low RAM).
- Hook scenes can be static for 2.5-5 s (the editor notes it); caption grouping can split long names (e.g. "KLEIN BLACK"). The Reel writer now uses short model names.
- The ELEVENLABS_VOICE_ID secret would override George if someone set it. It is not set today.
- Editor lessons grow; past `LESSONS_MAX_CHARS` (src/skill_rules.py) the oldest stop reaching the editor and writers. Raised 8000 → 16000 on 10-17 when the file hit 10 kB; tests/test_guards.py checks the oldest lesson still arrives.
- OpenAI pages refuse the cloud (403). They are read through r.jina.ai (D-28). If the reader goes down or limits us, OpenAI news is skipped again with "refuses this machine" and costs no try; the other sources are not affected.
- D-30: the editor approves a Reel built on a silent draft voice with estimated timings; the real voice can be a little longer or shorter, so scene cuts move slightly. The voiced Reel is checked again for a blank first frame and the 14-26 s length before it is queued, but the editor does not look at it a second time.
