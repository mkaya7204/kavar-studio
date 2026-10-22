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
- **Made permanent (2026-10-16):** rule 12 in the reel-hook-writer RULES (loaded by the script writer and the hook judge) and a lesson in rules/editor_lessons.md.

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

## D-20 · 2026-10-16 · Version A chosen for Reel openings
- **User:** "A daha iyi". About B: "B kötü duruyor".
- **Why B looked bad:** B followed the report. Its one difference was a 3-line headline instead of 2, because Turkish words don't fit 2 lines at 130 px. A tall result box around a wide answer card leaves empty space above and below the card. So the report's spec suits our content poorly; the implementation wasn't the problem.
- **Merged to main:** A (branch hook-motion), with the carousel cover (3-6 words, "KAYDIR →") and the silent-preview mode. B stays on branch hook-research and is not used.
- **Note:** A's headline also ran to 3 lines in the preview ("YAPAY ZEKÂ / ATASÖZÜNÜ / AÇIKLADI", 100 px). The user saw it like that and chose A.
- **Next:** test openings with Trial Reels once the voice quota allows Reels again (D-15, D-17).

## D-21 · 2026-10-16 · The editor knows the new design
- **User:** "Bunları editörde biliyor mu sonra çakışma olmasın".
- **Found:** two places where the editor could read the new design as a rule break. The Reel rule "no badge or button in the first 3 s" would hit the "KAVAR denemesi" stamp at ~1.3 s. The carousel cover's "KAYDIR →" pill could look like a CTA button.
- **Built:** the Reel editor rules (reel-retention-editor RULES) and the carousel editor SYSTEM now describe the agreed opening and cover as intended. A test keeps them there (`test_editor_knows_the_agreed_opening_and_cover`). The stale metrics path in the editor skill was also fixed.

## D-22 · 2026-10-16 · What is still open from the report (status check)
- **User:** "unuttuğumuz yapmadığımız herhangi bir şey kaldı mı".
- **Done today:**
  - measurement (D-14)
  - George-only voice, voice cap, hook price check, caption checks, CLI pin
  - press photos out (D-12)
  - new opening A and carousel cover (D-20); the editor knows both (D-21)
  - two Reels a day (D-09)
  - decision log (D-16)
  - the hook-subject rule and lesson (D-10)
- **Open, Claude can do them, in this order:**
  1. The editor's fixes reach the caption and story too. After a fix, the number check runs again, and a fresh review (not the same call) approves it.
  2. News ranking:
     - interest for Turkish readers
     - at most 1 story per company per day (3 of 4 carousels were NVIDIA)
     - no repeat of the same story from another site the next day
  3. Rotate the "Biz denedik" tests (a test bank; record which model got which test).
  4. Tool Reels: AI tools only, and a longer used-tool history (10 is too short).
  5. A later cron makes a missing Reel when the day is "done" with an empty Reel slot.
  6. Failing invariant tests stop or alert production (today they only log: `continue-on-error`).
  7. Phone notification when production ends or fails.
  8. One rules source with rule IDs. Clean up dead code (the old video path, Windows tasks, affiliate captions, unused libraries) and stale docs (RISKS.md D/A1, the daily.py docstring).
  9. A closing "send it to someone" line in carousels too. Reels already have one.
  10. Check that the official HF Space owner is on an explicit allow-list, not any word found in the article.
- **Waiting for the user (D-15):**
  - the ElevenLabs quota (no Reels until then)
  - the Instagram API setup
  - labelling 40-60 items for the editor
  - collab outreach
  - whether the 11:45 Reel goes out as a Trial Reel
  - unfollowing slowly (D-13, by hand)

## D-23 · 2026-10-16 · Voice quota, API, 11:45 Reel, unfollowing
- **ElevenLabs quota (user):** "başka hesabım da var onu da bağlarız, hangisi biterse diğerine geçersin ... sonra böyle yapıcaz". **Plan:** a second key (secret `ELEVENLABS_API_KEY_2`) with the same George voice, a premade voice available in every account. When one account's quota runs out, the next key is used. This is still George, so D-07 holds. Built when the user adds the key.
- **Instagram API (user):** "şimdi alamıyorum, en kısa sürede halledicem". It is the user's step; Claude doesn't push it.
- **11:45 Reel (user):** "bozmadan olduğu gibi olsun, zamanla karar veririz". It goes out as a normal Reel, not as a Trial Reel, until the user decides.
- **Unfollowing (user):** "takipten yavaş yavaş çıkıyorum". In progress, by hand (D-13).

## D-24 · 2026-10-16 · Editor calibration page
- **User:** "hazırla, bir not düşecek bir yer yap ... değerlendirmeye baktığında incelersin gerekçemi".
- **Built:** https://claude.ai/artifact/CWRtL7nPCKCBXi2nwaU2xY. It shows 42 posts from 10-12 to 10-16 (production and dry runs: 17 carousels, 25 Reels), each with the editor's verdict and reasons. The user marks "Olur / Olmaz" and can write a free note per post, plus a general note.
- **Where the answers live:** the artifact's database. Each post is a doc in collection `labels` ({item, ok, note, updatedAt}); the general note is `notes/general`. Claude reads them with ArtifactData `list labels`.
- **Next, when the user has marked them:** compare the editor with the user, per rule (false rejects vs. missed problems). Read every note as the user's reasoning. 13 production posts show no editor verdict: the 10-12/10-13 ones predate the editor, and some later ones are likely log-parse misses, so check the day logs first and run today's editor in the cloud only where no verdict exists. Then loosen or tighten rules, with the user's approval.
- **Kept for later sessions (user: "başka birşey anlayıp yanlış değerlendirme yapmayasin"):** `state/calibration/items.json` holds every item's id, verdict and review history (no images). Claude's memory note `editor-calibration` holds the why, the method and the traps.

## D-25 · 2026-10-17 · Production is started from outside, on the minute
- **User:** "hergün aynı şey üretim saatinde başlamıyor bunun temel sebebini öğren ve çözümü yap". Chosen option: "cron-job.org".
- **Root cause (gh run list):** GitHub's `schedule` trigger is best effort. Our runs started about 5 h late every day: 10-13 at 10:57, 10-14 at 08:58, 10-15 at 08:33 UTC. On 10-16 all three crons were late (03:17→08:09, 04:47→09:18, 06:17→11:34). On 10-17 none had started by 04:00 UTC. Manual `workflow_dispatch` runs start within seconds.
- **Built:** cron-job.org calls `POST /repos/mkaya7204/kavar-studio/actions/workflows/produce.yml/dispatches` (`{"ref":"main","inputs":{"auto":"yes"}}`) daily at 06:17 TRT. With `auto=yes` the run behaves like a scheduled one: the guard skips a day already produced (the first test without it started a second full production; Claude cancelled it). Manual runs still force. The user created the account and a fine-grained token (this repo only, Actions: read and write). The token stays with the user and cron-job.org, never in chat or the repo. The GitHub crons stay as backup; the guard step skips a day that is already produced.
- **Guarded by:** tests/test_guards.py (`test_cron_job_org_start_is_guarded`), RISKS.md A1. During "yükle", a missing run is still started by hand (CLAUDE.md §2.1).

## D-26 · 2026-10-17 · Second ElevenLabs account connected
- **User:** "yeni hesabı bağlıcam" (the D-23 plan: "hangisi biterse diğerine geçersin").
- **Built:** src/tts_engine.py tries `ELEVENLABS_API_KEY`, and on HTTP 401/402/403 (key or quota) `ELEVENLABS_API_KEY_2`. Both use the locked George voice, so D-07 holds. The user added the secret; the key needed the "Text to Speech: Access" permission (the first try returned "missing the permission text_to_speech"). All workflows that speak pass both keys. `probe.yml` makes George say one word per key and prints the first account's credits.
- **Verified (probe run 39012493164):** key 1 HTTP 200, 9,991 of 10,000 credits used; key 2 HTTP 200.
- **Guarded by:** tests/test_decisions.py (`test_second_elevenlabs_account_takes_over_with_george`).

## D-27 · 2026-10-17 · Rejected Reels fixed by hand, editor taught
- **User:** "diğer red edilen reel incele düzeltilecek doğru şekilde düzelt editörede öğret nasıl yapacağını ... kuralına göre doğru bizim istediğimiz şekilde".
- **Built:** templates/hyperframes_news lifts the hook's proof box only into the room the shrinking headline frees (`LIFT`, was a fixed 150 px), and the domain stamp sits under the box. rerender.yml now runs the editor and uploads its verdict. Four lessons in rules/editor_lessons.md (2.5 s overlap, empty card, proof that proves the hook, hashtag spelling).
- **Result:** Train with Pasta passed the editor after the hand fix; Claude checked the 2.5 s frame and the site (hands-free, Apple Intelligence and plans are on pppasta.com, no prices). Craft Agents (no clean proof on a fresh capture) and Ultracite v8 (same changelog proof, empty card) were dropped.
- **Open item closed (same day, user: "açık kalanı yapalım"):** there was no empty card. frames.yml (new: a cloud contact sheet of any stretch of a Reel) showed card 02 enters at 12.0 s and is full by 12.75 s; the editor's single middle frame (12.05 s) fell on the entrance. The editor now also sees the frame 1 s later, and the lesson was corrected.
- **Guarded by:** tests/test_biz_denedik.py (`test_hook_box_never_rises_into_the_headline`).
- **Also (user: "bak"):** Ultracite's cards ran one step ahead of the voice. The writer now rejects a draft whose card N doesn't match pointN (`card_voice_mismatch`, 0 false alarms on 18 past Reels; test `test_cards_must_match_the_voice_under_them`), and a lesson tells the editor to compare them.

## D-28 · 2026-10-17 · Audit: problems nobody had noticed
- **User:** "başka yerlerde de aklımıza gelmeyen birtakım sorunlar hatalar eksikler varmı diye derinlemesine kapsamlı inceleme yapsak".
- **Found and fixed (each with a test):**
  1. `daily.py fetch` unpacked a second run of the day over the first: the Reel-only run replaced the morning queue (carousels showed "empty") and the morning log with the editor's verdicts. Now the queue is merged slot by slot and the log appended (`_unpack_keeping_today`).
  2. The "Biz denedik" answer card cut long answers with an ellipsis, against the 2026-10-16 lesson. Now the font shrinks (38 to 27 px) and an answer that still doesn't fit is not shown (`_answer_card`).
  3. The price check missed "trial", "paid", "discount", "premium" and credit amounts ("500 kredi", "10,000 credits"). Added; no false alarm on past posts.
  4. Used tools were only the last 10 Reels, matched by exact name: a tool could come back after ~3 days, and "Nemotron 3.5 Super VL" was a candidate the day after the "Nemotron 3.5" Reel. Now `state/used_tools.json` keeps 500 names (seeded with all 19 past Reels) and a longer or shorter form of a name counts (`already_used`).
  5. openai.com refuses the cloud (HTTP 403): 3 of the 6 news tries on 10-17 went to OpenAI and failed. A site that refuses is now skipped for the rest of the run and the refusal doesn't use a try.
- **Carousel cover headline (found by the OpenAI test):** a long cover headline grew upward into a wide cover image at full size, and the layout check said "0 problems": the cover box is bottom-aligned, and the overflow check (scrollHeight) never sees text above the box. Now the box starts 12 px under the image, and the fit and the check both count overflow above the box (`tooTall` in templates/carousel/index.html). Verified on news-test run 39024571806: the headline sits under the image one size smaller; other slides unchanged. A lesson stops the writer from adding "no information about Turkey".
- **Checked, no problem:** feed dates without a time zone, rejected news marked used, sources are company blogs only, price check covers every text field, editor and trial judge drop unchecked output, free-model routes only.
- **OpenAI reader route (user: "başka bir yolla almak olsun"):** when a page answers 401/403/429, src/article_capture.py takes the same page's HTML from the reader service r.jina.ai and shows it to the browser under the article's own address, so text, cover, date and the page screenshot come out as usual. Only the public URL is sent; the images still come from OpenAI's own server (images.ctfassets.net). Verified in news-test run 39022883644 (Itaú article: 9,247 characters, OpenAI's own cover, the real page on slide 2, date 16 Oct). That carousel was rejected for a separate template fault: a 4-line cover headline runs into the cover image.
- **Guarded by:** tests/test_daily.py, tests/test_decisions.py, tests/test_biz_denedik.py.

## D-29 · 2026-10-17 · Morning Reel at 07:30 (Turkey), produced first; smarter selection for every slot
- **User:** "bizim zaten belli konseptimiz değişiklik yapmayacağız ... sabah saatinde de bir reel ekleyelim bu da sabah saatlerinde Türkiye'deki AI teknolojik gelişmeler konulu olsun ... 7:30 olsun ... keskin hatlarla belli olsun ... ilk sadece sabah reel çıkarılmaya çalışılacak, hazırlandı planlamaya alındıktan sonra diğerleri için çalışma başlatılacak ... kaynaklar olarak kurumların kendi siteleri ve sektörün önde gelen alakalı siteleri ... kaynak siteden haberi gördük, sistem hemen ilgili kurumun sitesinden baksın, aynı görseller kullanılmışsa hemen alıp kullansın ... hangi haberin daha fazla kitleye hitap ettiği, ilgi çekici olması ... daha akıllı seçim yapılması için uğraşıyoruz".
- **Decided:**
  1. The four existing slots and their concepts stay as they are (11:45 tool Reel, 12:30 / 18:00 news carousels, 20:30 "Biz denedik" Reel).
  2. New slot 07:30 Reel, one concept only: AI and technology developments in Turkey.
  3. Order: the morning Reel is produced first; the other posts start after it is scheduled (one thing at a time in a crisis). If nobody starts them, they start on their own (planned: 08:00).
  4. Sources for the 07:30 Reel: institutions' own sites and the leading Turkish tech news sites. A story found on a news site is followed to the institution's own page, and images come from there (the institution's own images). This widens rule 9 for this slot only; press photos stay banned.
  5. The main work: in every slot, pick the candidate that reaches more people and is more interesting, inside the slot's concept.
- **Pictures for the 07:30 Reel (user, same day):** "görseli kaynağına bakılır, eğer kurumdan geliyorsa o görseli kullanır, eğer değilse kurumdan başka görsel kullanılır ... kurumun olduğunu anımsatması bile yeterli, birebir o konuyu anlatan görsel olması şart değil". Built: the institution's page about the story first; if there is none, an image from the institution's own site (home or newsroom); the news site's picture only when it matches an image on the institution's site (compared, not guessed). Facts come from the institution's page, or from the news article when there is none.
- **Waiting for the user:** voice quota for three Reels a day (~30,000 characters a month; one account left this month with 10,000).

## D-30 · 2026-10-18 · Voice only for the Reel the editor approved
- **User:** "ilk anahtarlı hesap zaten kredisi bitmiş ... her denemede ses kullanma önce reel doğru yaptıktan sonra editör onay verince ses kullan ya da tekrar baştan doğru haliyle sesi kullan".
- **Built:** every Reel attempt (tool, "Biz denedik", 07:30 Turkey) is rendered on a silent draft voice with word timings estimated at George's measured pace (`tts_engine.draft_voice` / `reel_voice`; daily.py sets `KAVAR_DRAFT_VOICE`). The editor reviews that draft. Only when it says "publish", `src/voice_final.py` voices the same script and pictures with George once and re-renders; the voiced Reel must pass the measured first-frame and 14-26 s checks before it is queued. A rejected draft spends no voice. If the voice fails, no Reel is made and no further attempt runs (§1.6). Hand fixes (rerender.yml) still voice directly.
- **Guarded by:** tests/test_voice_last.py.
- **Note:** ElevenLabs account 1 is out of credits (HTTP 401 on 2026-10-18); account 2 carries the voice.
- **Not merged (user, same night):** "sabah çalıştırmak için henüz temiz reel çıkaramıyoruz ... önce temiz reel çıkar ondan sonra sabah reel çalışmasını ekleriz". Clarified: "onaylanan reel üzerine ses direk eklenmeyecek" - the approved Reel is rebuilt from scratch with the voice (as built: voice_final re-runs the whole build on the real timings). Dry run 39074237044: draft 19.5 s, voiced rebuild 20.2 s.

## D-31 · 2026-10-18 · Guide concept at 07:30 (Reel) and 18:00 (carousel); Turkey Reel cancelled
- **User:** "türkiye gelişmesini yapmayalım ... bilinen AI modelleri veya AI kurumlarının özelliklerinin anlatıldığı veya doğru kullanımlarla ilgili şeyler yapsak çünkü insanların kafası çok karışık ... (örnek: animasyon için Claude terminal + render mı, tarayıcıda artifact/HTML mi, hangisi daha kullanışlı, eklentilerle güçlendirme önerileri)". "ücretli ya da ücretsiz olmasının bir önemi yok ... biz yol göstericisi olacağız, doğru kullanım, doğru amaçla kullanım ... henüz bilmedikleri özellikler ya da kullanım yerine göre farklı modlarda veya şekillerde kullanılıyor ... reel olmasını tercih ederim ... sabah 7.30 koyarız, bir post olarak da birinin yerine kullanırız". Approved the proposal "07:30 Rehber Reel + 18:00 Rehber carousel": "tamam öyle yapalım".
- **Decided:** 07:30 Reel = guide; 18:00 carousel = guide (12:30 stays the news carousel, with "Biz denedik" first; 11:45 tool Reel and 20:30 best Reel unchanged). D-29's Turkey concept is cancelled (src/tr_reel.py is not merged). Facts come from the companies' official docs / help pages and our own tries, never from memory; no prices, plans, free/paid (§1.1).
- **Order:** first a hand-made sample shown to the user, then the pipeline; `main` keeps the old 4 slots until a clean guide Reel exists.
- **Built (same night, user: "sabaha üretime hazır olması için çalışmaya başla"):** src/guide_reel.py takes the place of the Turkey Reel in the morning stage: candidates are the companies' own blog posts of the last 14 days, ranked by content_ranker in the "guide_reel" concept (a feature a Turkish viewer can use today; research, business news, enterprise/developer-only off concept); facts and pictures only from the company's page; silent draft -> editor -> voiced rebuild (D-30). The 18:00 guide carousel comes next; until it exists 18:00 stays a news carousel.
- **Guarded by:** tests/test_decisions.py (schedule: 07:30 concept "guide"), tests/test_daily.py (morning stage, guide candidates), tests/test_voice_last.py.

## D-32 · 2026-10-18 · Price rule: plans, beta and credit use may be named
- **User:** "beta olayı elbette sınırlı kullanıcı için veya başka özel durumlar olursa da uygundur hatta ücretsiz değil paket söylesen de uygundur örnek veriyorum pro pakette bu özellik kullanılıyor ya da ... fable mesela kredi istiyor hatta onun böyle olmasının sebebi de bir konu olabilir". Proposed boundary accepted ("fable bir örnekti sadece sen daha değerli şeyleri bul ... çalışmaya başla").
- **Decided:** §1.1 stays, with a boundary. Allowed when the source says so: the plan / package a feature comes in (Pro, Plus, Premium, a subscription), beta or limited access, "kredi harcıyor / kullanım hakkından düşüyor" without amounts, and why it works that way. Still banned: amounts, currencies, discounts, campaigns, trials, "bedava / ücretsiz" / free vs paid as a selling line. Reason: the 10-18 guide dry run had to hide that Gemini 4 Argon is for subscribers, which made the Reel misleading.
- **Built:** `PRICE_PATTERN` no longer flags abonelik / subscription / premium (credit amounts stay flagged); `NO_PRICE_RULE` (all writers and the editor) names what is allowed; the guide Reel says when a feature is beta, plan-only or uses credits.
- **Guarded by:** tests/test_policy.py (SAFE list: plan, beta, credit-use phrases), tests/test_decisions.py (credit amounts, paid, discount, trial still caught).

## D-33 · 2026-10-18 · A rejected Reel draft is fixed, not thrown away
- **User:** "bir reel ses olmadan yapılacak editör vs red derse sen devreye giriyorsun düzeltilecek bir yanı varsa düzelt hatta sen de hata yapıyorsun sorun var editör haklı deyip düzeltmeden sen de reel iptal edip başka reel aramıyorsun ... hep aynı yerde dönüp duruyoruz ... kalıcı çözüm yapmıyorsun". Earlier the same day: "her seferinde neden benim söylememi bekliyorsun red edilenleri sen uygun hale getir sende yapamıyorsan başka reel baktır".
- **Why:** on 10-18, five tool Reels in a row were rejected and thrown away (proof picture not showing the promise, cut text, subtitles over picture text, overstated claims, a non-AI tool); each time a new tool was tried and the same faults came back.
- **Built:** daily._reel_attempt: when the editor rejects the silent draft (D-30), `src/reel_fixer.py` runs (REEL_FIX_ROUNDS = 2). One Claude call reads the editor's problems, the script, the tool's source, the rejected frames and a numbered sheet of every picture we have (guide Reels: the page's figures / video stills / cover; tool Reels: proof-shaped windows over the site's full page; "Biz denedik": text only, our outputs stay). It either fixes everything (claims, hook, cards, caption, hashtags, picks the pictures that show the promise or rewrites the promise to match the best picture) or says the topic can't be fixed (no AI, off concept, nothing honest to say, no usable picture). The fix passes the normal script checks, is rendered again on the draft voice and goes back to the editor. Only an approved draft is voiced. Unfixable → the next tool, as before.
- **Claude's own part (morning "yükle"):** a rejection is never answered with "editör haklı" and an empty slot: fix it by hand or get another Reel made, without asking (memory: fix-rejections-without-asking).
- **First cloud tests (same day):** the fixer sees up to 12 windows over the whole page (it saw one and gave up on Inbox Zero); its word limit is the writers' 42 (a stricter 38 refused valid scripts). Inbox Zero was fixed twice (claim cut to the source, the product's real reply-draft screen chosen) and still rejected for one template fault: captions sat on the site picture's text, as in most rejections of 10-18. The template now hides the captions during the two site shots (the voice goes on). MeetPaw was rightly "not fixable" (no AI): tool Reel candidates are now ranked by content_ranker in the tool concept and tools with no AI are dropped before any capture (ai_tools_first, 8 candidates fetched).
- **Guarded by:** tests/test_voice_last.py (fix then publish, unfixable moves on, fixes stay silent, script rules kept, whole-page candidates, captions hidden during shots, non-AI tools dropped).

## D-34 · 2026-10-18 · George says product names the Turkish way
- **User:** "11:45 reel instagramdan sildim çünkü seslendirme hatası var ... gemini yazıldığı gibi okuyor sanırım önceki reellerde ismi geçen AI isimlerini de yazıyla nasıl yazıldıysa öyle okuyor bu çok kötü bunu düzeltmemiz gerekiyor".
- **Built:** `tts_engine.spoken_text` sends George each name as a Turkish reader says it, from `rules/pronunciation.json` ("Gemini" -> "Cemini", "ChatGPT" -> "Çetcipiti", "Google" -> "Gugıl"...), one word for one word with Turkish suffixes kept. `written_words` puts the script's own spelling back on the word timings, so captions still read "Gemini". The silent draft is unchanged (it shows the written text). Names are added to the JSON file; never two words for one. `say.yml` speaks one test sentence to check a pronunciation (spends only its characters).
- **Made permanent for every name (user, same day, after listening to the say.yml sample: "doğru söylüyor ama bunu sadece bu bilinen isimler için değil tanıtılan hangi isimde bir ürün olursa onun söylenişi de doğru söyleyecek, ekranda yazılışı nasıl yazılıyorsa ismi olduğu gibi yazılsın, ilerde unutup böyle sorunlar olmaması için sistemde kalıcı hale getir"):** before George speaks, `tts_engine.learn_names` asks Claude for the Turkish way to say every foreign name, English word or abbreviation in the voiceover that isn't known yet (new tools too: "Openbroca", "SpeechFast"). Answers must be one word of Turkish letters (parts joined) and appear in the text; they are kept in `state/pronunciations.json` (committed by the cloud run), so a name is said the same way every time. The hand-checked list always wins. Screens, cards and captions always show the written name.
- **Guarded by:** tests/test_voice_last.py (spoken text, whole words only, one-for-one, captions keep the spelling, new names learned and remembered, bad answers refused).

## D-35 · 2026-10-19 · No fresh news: use the unused news of the last 7 days
- **User:** asked during the morning "yükle" after the day produced 0 of 5 posts, whether to add the fallback: "Olur test et ekle".
- **Why:** on Monday 10-19 no company blog had posted anything unused in 72 h (weekend), so `fetch_news` returned 0 candidates and both carousel slots stayed empty. The same stories (15 Oct FLUX.3 Klein, 14 Oct Meta AI glasses) were then made by hand and passed the editor.
- **Built:** `src/news_fetcher.fetch_news` keeps the 72 h window (`max_age_hours`); when it holds fewer than `min_fresh` (6) unused items, the unused items of the last `fallback_age_hours` (168) are added after the fresh ones (news_sources.json), logged as "[news] N unused in 72 h; adding M unused from the last 168 h". A first version that fell back only on an empty pool would not have helped on 10-19: a live check found one fresh item, a Samsung SSD ad. Ranking (content_ranker, repeats flagged) and the editor gate are unchanged.
- **Guarded by:** tests/test_daily.py (72 h window kept when enough fresh news exists; a thin pool is topped up from 7 days, fresh first, used and older items stay out).

## D-36 · 2026-10-19 · A tool Reel's proof is the product's own screens
- **User:** after the 10-19 report (3 tool Reels rejected 3 x 3 times for slogan cards; the "Biz denedik" Reel step crashed without a trial output), Claude proposed both fixes; the user: "İki içinde onay veriyorum".
- **Why:** the proof box was always cut from the top 4 screens of the home page, where tool sites show slogans, prompt cards and logo walls; the product's interface is further down, on its feature pages or in its README.
- **Built:** `src/product_images.py` + `media_capturer` (after the captures it scrolls the whole page and reads PAGE_MEDIA_JS): big images anywhere on the page, the GitHub README's screenshots (also behind the site's own /github redirect), the og:image of up to 5 of the site's feature pages (pricing, login, blog... skipped); badges, logos, svg, tiny and flat images are dropped, at most 6. The tool pipeline adds them to `best_proof_crop` (shown whole, letterboxed, never cut) and the Reel fixer sees them first. The proof picker now also refuses a slogan or marketing headline on its own, a menu of feature cards, a template/prompt card and a wall of customer logos. Test runs on 10-19 (rerender draft=yes, George not spent): Krea 3 and Popcraft got real outputs as proof (a knight render, a dragon, an avatar video) instead of prompt / menu cards; the editor's remaining objections were the old scripts' text. Inbox Zero had no allowed picture and was skipped before a script was spent; its README (behind getinboxzero.com/github) was added after that run.
- **Also:** `rerender.yml -f draft=yes` renders on the silent draft voice (D-30) to test pictures / templates; `news-test.yml reel=yes` logs "no Biz denedik Reel" instead of crashing when the trial gave no output.
- **Guarded by:** tests/test_product_images.py (collected and filtered, README behind a redirect, offered to the picker whole, slogans / card menus / logo walls refused, the fixer sees them first).


## D-37 · 2026-10-22 · Unposted approved posts are a reserve for empty slots
- **User:** after 10-22 was filled with the unposted posts of 10-21: "Yarın veya başka gün red birşey çıkarsa bunkikanilmayanlari boş olan saatlere yerine kullanırız hem boşa gitmez hemde token harcanmaz busuna".
- **Why:** on 10-21 four editor-approved posts were made but the weekly Claude limit stopped the scheduling; on 10-22 the cloud made 0/5 and three of them filled the day. Approved posts thrown away cost tokens and voice that were already spent.
- **Built:** `state/reserve.json` lists editor-approved, never-published posts (kind, concept, title, local folder, date made). During the morning "yükle" (CLAUDE.md §2 step 2) an empty or rejected slot is filled first from the reserve when an item fits the slot's concept and is still current (company news ages in days, guide and tool Reels last longer; captions with "bugün/dün" are corrected); only then is a fix or a new cloud run started. A reserve item is removed once posted. Started with the 10-21 OpenAI-Orchestra Bio carousel.
- **Made automatic (user, same day):** "normal günlük sabah üretiminde editörden onay alıp yayınlamaya uygun fazlalık varsa onları da yedeklemeye alıp ... yedeklemedekilerde hazır üretilmiş halde yedeklensin". `src/reserve.py`: an item is kept READY, the files Business Suite needs (Reel: upload.mp4, cover.jpg, post.json, script.json, verdict; carousel: slides, story, caption, carousel.json) are copied into `reserve/<name>/` on this PC (gitignored; output/ is replaced every morning) and listed in `state/reserve.json`. `daily._produce_rest` names approved posts that found no slot in `output/reserve/<date>.json`; `daily.py fetch` copies them into the reserve. `daily.py reserve` lists (age, current or old: news 4 days, Reels 14), `reserve keep HH:MM` keeps an unposted ready item of today, `reserve used N` drops a posted one with its files. Note: today the run stops each slot at its first approved post, so cloud surplus is rare; most reserve items will be unposted ready posts.
- **Guarded by:** tests/test_reserve.py (kept files are the ones posting needs, listed once, posted items removed with their files, old news marked, surplus of the day goes to the reserve, no surplus no file).

## D-38 · 2026-10-22 · Stabilization: fewer slots, shorter chain, loud failures
- **User:** after three read-only audits: "neden sürekli hatalı veya eksik üretim yapamıyoruz sistem neyden takılı kalıyor ... sen sistemin gerçek çalışma haline göre düzeltme öneri çözüm getir Yeter artık". Claude proposed six changes (freeze; one carousel + one Reel until 7 clean days; Reels chosen by their material; shorter chain and loud failures; publish first; weekly numbers). User: "Evet".
- **Why (from the records):** 11 days, 158 commits, 36 decisions, 55 editor lessons; 15 of 39 slots filled; 9 of 32 Reels passed the editor (18 of 23 rejections: proof does not show the promise); 1 follow from 36 posts. Tool sites have no product screens, and each rejection got a new layer (proof picker, product screens, fixer) instead of a different source; the fixer itself cropped the proof (reel_fixer.apply_pictures used ImageOps.fit; cut text in 12 of 14 fix rounds; ToDo.is 10-21: the cut text appeared in the fix rounds). Seven Claude steps fail silently on one subscription; 10-22 made 0/5 and the run showed success.
- **Built:** schedule.json = 12:30 carousel + 20:30 Reel, `guide_reel: true`, `tool_reels: false`; the guide Reel is made every morning and fills 20:30 when there is no "Biz denedik" Reel, else it goes to the reserve (daily._build_queue, _produce_rest). REEL_FIX_ROUNDS = 0 (D-33 off). Proof pictures are shown whole in the fixer and the guide Reel (`_fit_whole`, D-36 applied everywhere). A live tool with no product screen is skipped before any script (main.produce_video; hand-written scripts exempt). carousel_writer, editor_review, the proof picker and the ranker log why Claude gave nothing. The produce command exits 1 when nothing is ready (`daily.empty_day`). CLAUDE.md: freeze rule (§0), D-38 notes in §1.2 and §1.7, morning order publish-first and Monday numbers (§2). RISKS.md: the 10-22 limit cause marked unproven.
- **Not changed:** the editor's rules and threshold, George, prices, "Biz denedik" (its Reel keeps 20:30), the reserve. Slots come back only after 7 days with both filled, with the user's approval.
- **Guarded by (D-38):** tests/test_decisions.py::test_schedule_slots; tests/test_daily.py (d38: guide Reel fills 20:30, no tool Reel, "Biz denedik" keeps 20:30 and the guide Reel goes to the reserve, empty day reported; guide proof letterboxed); tests/test_voice_last.py (no fixer run; the fixer never crops); tests/test_product_images.py (no product screens = skipped before any script).

## D-39 · 2026-10-22 · The system records its failures and reacts to repeats by itself
- **User:** "Benim istediğim sadece hatanın düzeltilmesi değil ... eksik olan tarafta kendini geliştirip hataları düzeltip kendiliğinden doğrusunu yapamadıktan sonra herşey boşuna bir çaba". Claude proposed four parts (failure ledger, automatic reactions, measuring each editor lesson, steering by results), the first two first; user: "Evet".
- **Why:** failures were free text in the day log; nothing counted them, so the same fault returned (no_proof in 11 and cut_text in 10 of the 14 rejected tool Reels of the last 7 days) and the only "learning" was 55 editor lessons whose effect was never measured.
- **Built (parts 1-2):** `src/failures.py`: `record()` / `ok()` keep every outcome as data in `state/failures.json` (date, stage, kind news/guide/trial/tool, item, host, categories from `classify()`: no_proof, cut_text, claude_empty, source_refused, off_concept, facts, price, voice, timeout, other; `rendered` false when nothing was made). `react()` runs at the start of every production (logged as "self-correct: ..."): a news host with 3 source failures in 7 days is skipped for 7 days; a Reel kind with 3 rejected drafts and no approval in 7 days is paused for 7 days, then tried again. Mornings with no candidate or no answer from Claude are counted but never pause a kind. daily.py records news failures / rejections / approvals and Reel pipeline failures / rejections / approvals, and honours pauses and blocked hosts. `python daily.py failures` prints the last 7 days. The ledger was started from state/metrics/reels.json (34 Reel outcomes, 10-13..10-21); today no rule fires (tool Reels: 7 approved, 14 rejected; guide: 2 approved, 1 rejected).
- **Next (parts 3-4, same approval):** each editor lesson's effect on its rejection category; weekly results by kind and hook pattern feeding the ranker.
- **Guarded by:** tests/test_failures.py (classification from real texts, host skipped then retried, kind paused then retried, a kind that also works never paused, empty mornings never pause, old failures leave the window, daily records a rejected Reel and honours a pause); tests/conftest.py keeps the real ledger out of tests.

## D-40 · 2026-10-22 · All five slots back; the recorded rejection causes fixed at their source
- **User:** "1 hafta bu düzenle devam etsek haftaya başka saat eklesek yine aynı sorunlar baş gösterecek ... çözümü bu 1 haftalıkta bulmayı uymuyorsan zaten geçmişteki haftaya bakıp halederdin saçma sapan zaman çalmaktan başka birşey bulmuyorsun". Claude proposed: five slots back now, every recorded cause fixed in code with a test on its real example. User: "Evet diyorum derin araştırma yap en iyi yolu bumu çözüm olarak riskleri ve en iyisini bulup öyle yap varsayım yapmadan".
- **Evidence (the rejected files, not guesses):**
  - Empty pictures: 11 of 119 captured figures / page shots score as empty (edge share < 0.025, or a 97 % flat background): OpenAI's page via the reader = a green gradient (10-20 slide 2 rejected), a blank figure, the "Rosalind" card, "This page couldn't load", a Gemini logo strip, robot-arm art, the abstract "4" (guide Reel rejected 10-19), VocabX's figure 5 = the empty first frame of an animation (10-22 rejected). No usable picture scored below (sparse FairStress illustration 0.027, a white Windows UI 0.040).
  - Wrong picture: FairStress (10-22) had good alt texts; the writer put figure 2 on the slide about figure 3 and 3 on 4 (off by one) and figure 1 twice. The writer never sees the pictures, only their alt texts.
  - Editor fix lost the post: YouTube (10-22) pasted the editor's cover (7 words, limit 6) and was thrown away; the editor itself said the story and caption couldn't be changed by slide fixes.
  - Play-button still: Copilot (10-20) figure is a video thumbnail with a play button and a real person; no reliable way to see that in code, the editor saw it.
  - Reel cut text: ToDo.is frame 0 measured (text touches both inner edges at zoom 1.0); proof windows cut at fixed steps (Composio's half buttons); the hook zoom 1.0->1.12 and the site-shot zoom 1.02->1.3 push the edges out (1.3 leaves 831 of 1080 px).
  - 07:30: the guide Reel was ready 06:28 (10-21) but the archive only came at 07:34, after the whole job.
- **Built:** schedule.json five slots, `tool_reels: true` (the product-screen gate of D-38 stays). `article_capture.informative()`: a figure that shows nothing is shot again after 2.5 s (animations), then dropped; an empty page shot sets `page_blank`, and the writer may not use "page". `news_writer`: each figure slide carries `visual_quote` (words copied from that figure's alt / caption); `_visual_problems` rejects a quote that doesn't match its figure (naming the figure it does match), a figure used twice and a blank page. The editor names `bad_visual_slides`; a "fix" verdict is now rewritten by the writer (`revise_for_editor`: slides, story and caption, inside every rule; wrong pictures dropped and kept out); pasting the editor's text is only the fallback. Reels: proof windows end in the quietest rows nearby (`_snap_window`), every proof is shown whole with a margin for the hook zoom (`_fit_whole`, HOOK_ZOOM), the first site shot zooms to 1.12 instead of 1.3; the guide Reel never uses an empty cover. produce.yml: the morning guide Reel is its own step and artifact (`kavar-morning`), then the rest; `daily.py produce morning|rest` skips a stage already made unless forced; `fetch` takes `kavar-morning` from a run still going (`gh run download`, else the artifacts API).
- **Not changed:** the editor's rules and threshold, the fixer stays off (D-38: 1 approval from 7 fixed Reels), George, prices, "Biz denedik", the reserve, the failure ledger.
- **Risks:** fewer pictures per carousel when figures are dropped (text-only slides); the writer may need an extra try to give matching quotes; letterboxed proofs are ~11 % smaller; untested in production until the first run (a dry run first). The play-button / real-person case is still left to the editor (now dropped as a bad visual instead of losing the post).
- **Guarded by:** tests/test_causes.py (real VocabX empty frame and FairStress illustration; blank / gradient / chart; the 10-22 FairStress slides caught with the right figure named, the right ones pass; blank page refused; the editor's fix goes to the writer and a bad picture stays out; proof windows end in a gap; proofs whole and clear of the zoom; shot zoom; two-step day never repeats a stage; fetch takes a running run's morning artifact; workflow order), tests/test_decisions.py::test_schedule_slots.

## D-41 · 2026-10-22 · The guide Reel also reads official feature announcements (Workspace Updates)
- **User:** asked to choose for the empty 07:30 slot between (a) official help / feature pages as a guide source and (b) filling it from the reserve or a tool Reel: "evet ve a".
- **Evidence:** on 10-22 three runs found 0 guide topics in 40 company posts. In the last 14 days the Gemini blog had 7 posts (every guide-worthy one already used), the Workspace product blog 0, Android 3; the news carousels use the same blogs. Probed feeds (10-22): Google Workspace Updates 22 posts in 14 days, each naming who can use it (e.g. "users with personal Google accounts"); Search 6, Windows 3, Apple Newsroom 11 (almost none about AI), Photos / Chrome / Maps / Microsoft 365 0; Copilot, Canva, Adobe, WhatsApp, Instagram, Anthropic had no readable feed. With Workspace Updates added, the same ranker found 9 guide topics in a pool of 55 (Docs Live by voice, customising Gemini, Meet live translation in 63 languages, Gemini in Sheets on iPhone, NotebookLM slides / video overviews...); paid-only features (Gmail Live) were left out.
- **Built:** news_sources.json `guide_feeds` (Google Workspace Updates), read by `guide_reel.fetch_guide` only, up to GUIDE_FEED_POSTS (15) of its posts, weekly recaps skipped. The news carousels never see it. Concept, ranker, editor and pictures are unchanged.
- **Guarded by:** tests/test_daily.py::test_guide_only_sources_feed_the_guide_reel_and_not_the_news.
