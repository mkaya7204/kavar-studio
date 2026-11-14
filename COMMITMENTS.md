# Commitments to the user (Sözler)

The user, 2026-11-12: "bütün burda söylediklerini yapman için garantiye al ... söylediklerini gerçekten
yapabilir misin yoksa hepsi varsayım mı". Every promise Claude makes to the user goes here in the same turn
(CLAUDE.md §0). Every morning "yükle" report starts with this list's changes. A line moves to DONE only with a
cloud run's log or files as evidence (D-49); "kodda" alone is not done. Nothing is deleted without the user's OK.

Status: `DONE` (seen in a run) · `KODDA` (built and tested, not yet seen in production) · `YAPILIYOR` (being built)
· `BAŞLAMADI` (promised, not started) · `KULLANICIDA` (needs the user or an outside person; Claude cannot do it)
· `CEVAP BEKLİYOR` (waiting for the user's answer).

| # | Söz (promise) | Status | Evidence / next check |
|---|---|---|---|
| 1 | D-66: the same news from a second blog and test-run / reserve tools never come back | KODDA | 11-13 production log: no repeat of a used title or tool |
| 2 | D-67: a story the editor never answered stays unused; `fetch` warns when cron-job.org didn't start the day | KODDA | first unanswered editor / first late morning in a log |
| 3 | D-67: cloud packages pinned (constraints.txt) | DONE | 11-13 production run 43357936647 installed on the pins and succeeded |
| 4 | D-68: a tool's site is searched once (cache) | DONE | site searches 34 (11-12) -> 16 (11-13 run 43357936647) in state/claude_usage.jsonl; fewer `tool_site_search` rows in state/claude_usage.jsonl after 11-13 |
| 5 | D-68: voice.yml learns a new name instead of stopping | KODDA | the next voice.yml run with a new name |
| 6 | D-68: every metrics row carries its post's folder | YAPILIYOR | from the 11-13 "yükle" on, by hand each morning |
| 7 | D-69: the crow's sign-off at the end of every Reel (the crow the user saw on the logo page) | DONE | production run 43550831577 (11-14): the 07:30 guide Reel's review sheet ends with the crow, "YARIN YENİSİNİ GETİRİRİM." |
| 8 | C: 1 of 3 daily Reels is a 10-12 s single-point Reel, marked "KISA", named in every report, compared after a week | YAPILIYOR | D-71 dry run 43534664742: KISA Reel Expo Simulators 11.9 s, editor publish; 43537245307: KISA Burnstate approved. Waits for the user's OK to merge |
| 9 | D: 18:00 = a saveable guide carousel (a known AI product's feature, step by step), not news | YAPILIYOR | D-72 dry run 43536406394: guide carousel (Workspace skills, 9 slides, steps, Kaydet) editor publish, queued 18:00; first page (Gemini in Chrome) rejected for invented steps. Waits for the user's OK |
| 10 | Plan 1: the writer gets the page text + what the proof picture shows + a required "angle" | BAŞLAMADI | plan https://claude.ai/artifact/8nuzgbgVwnEzCJ1t1cTnMN |
| 11 | Plan 2: new hook types (risk, counter-view, comparison, number); judge scores surprise first | BAŞLAMADI | same plan |
| 12 | Plan 3: editor gives a "would it stop the scroll" score; low score goes back to fixing | BAŞLAMADI | same plan |
| 13 | Plan 4: results feed the writer and the ranker (D-39 parts 3-4); closing line rotates save / send / comment | BAŞLAMADI | same plan |
| 14 | Plan 5: rank tools before the site search (only the top 3 are searched); usage labels fixed | BAŞLAMADI | same plan |
| 15 | A (changed by the user 11-14): a tool Reel carries what real users / reviewers found when they tried it (their words summarised, source named, never their images; never "denedik") | YAPILIYOR | user 11-12 "A için evet", changed 11-14. D-73: search works (Granola: 3 real reports found locally 11-14); dry run 43537245307: 0 reports for Trainn MCP / Burnstate (launched this week, nobody has written yet). Waits for the user's OK |
| 16 | A brief for an illustrator to draw the crow (story, 5-8 poses, small-size version, vector files, rights) | BAŞLAMADI | Claude writes it; the drawing itself is KULLANICIDA |
| 17 | New post look, decided together with the crow drawing | KULLANICIDA | waits for the drawing |
| 18 | Instagram API token (posting and metrics without this PC) | KULLANICIDA | Meta phone verification |
| 19 | cron-job.org token expiry date | KULLANICIDA | the user looks it up |
| 20 | Reserve Skillbox + ElevenLabs Reels can be voiced only until 2026-11-14 | KAÇTI | 11-14 07:30 UTC: run 43158731682 has 0 artifacts and no release; they can no longer be voiced. Empty Reel slots of 11-15 go to the dry run 43571295790's approved Reels, with the user's OK |
| 21 | A, more sources (user 11-14 "başka kaynaklardan da baksan"): tool candidates also from Hacker News Show HN with their discussion | YAPILIYOR | D-74 on branch deneyenler (tests pass); next: dry run after the 11-14 production, show the user |
| 22 | More sources for every slot, no story twice (any blog, any wording), not always the same brand (user 11-14 "hep Gemini olması") | YAPILIYOR | D-75 on branch deneyenler (tests pass); next: dry run after the 11-14 production, then a week of queues showing the brand mix |
| 23 | Many news channels (press, Turkish sites, Reddit, Google News) find stories; text and pictures from the company's own page, else the same company's own pictures (user 11-14 "bir çok haber kanalı takip edilecek") | YAPILIYOR | D-76 on branch deneyenler (tests pass); next: full dry run after the 11-14 production, show the user |
| 24 | Test runs never take the Claude usage that production needs (11-14: three night dry runs + this session hit the limit at 06:30 TRT, the 11-15 day got 1 of 5 posts); the morning guide Reel alone no longer marks the rest done | YAPILIYOR | marker fix on branch deneyenler; production rest re-run 43568521370; rule: no dry run between 00:00 UTC and the end of production |

What Claude cannot promise: reach, follows or any result on Instagram. Claude can promise that each line above is
built, tested in the cloud, shown to the user and reported honestly, and that a usage limit only pauses the list.
