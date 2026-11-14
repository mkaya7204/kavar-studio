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
| 7 | D-69: the crow's sign-off at the end of every Reel (the crow the user saw on the logo page) | KODDA | user approved 11-13 ("Hepsine izin veriyorum"), merged; done when the first production Reel ends with the crow |
| 8 | C: 1 of 3 daily Reels is a 10-12 s single-point Reel, marked "KISA", named in every report, compared after a week | BAŞLAMADI | user approved 11-12 |
| 9 | D: 18:00 = a saveable guide carousel (a known AI product's feature, step by step), not news | BAŞLAMADI | user approved 11-12 (D-31's never-built guide carousel) |
| 10 | Plan 1: the writer gets the page text + what the proof picture shows + a required "angle" | BAŞLAMADI | plan https://claude.ai/artifact/8nuzgbgVwnEzCJ1t1cTnMN |
| 11 | Plan 2: new hook types (risk, counter-view, comparison, number); judge scores surprise first | BAŞLAMADI | same plan |
| 12 | Plan 3: editor gives a "would it stop the scroll" score; low score goes back to fixing | BAŞLAMADI | same plan |
| 13 | Plan 4: results feed the writer and the ranker (D-39 parts 3-4); closing line rotates save / send / comment | BAŞLAMADI | same plan |
| 14 | Plan 5: rank tools before the site search (only the top 3 are searched); usage labels fixed | BAŞLAMADI | same plan |
| 15 | A: tools with a free open demo are really tried in the cloud and the Reel says "denedik" | BAŞLAMADI | user approved 11-12: "A için evet". Free routes only (§1.5), no sign-ups; tools that need an account keep today's Reel |
| 16 | A brief for an illustrator to draw the crow (story, 5-8 poses, small-size version, vector files, rights) | BAŞLAMADI | Claude writes it; the drawing itself is KULLANICIDA |
| 17 | New post look, decided together with the crow drawing | KULLANICIDA | waits for the drawing |
| 18 | Instagram API token (posting and metrics without this PC) | KULLANICIDA | Meta phone verification |
| 19 | cron-job.org token expiry date | KULLANICIDA | the user looks it up |
| 20 | Reserve Skillbox + ElevenLabs Reels can be voiced only until 2026-11-14 | KODDA | artifact of run 43158731682 expires |
| 25 | D-77: the product's name + its company's logo as the LAST RESORT for a Reel's picture: screens first, the fixer edits weak pictures, the next tool, only then name / logo (user 11-14 "en son çare") | YAPILIYOR | branch logo-yeter b6e2f51; Reel dry run 43593954177; merge to main only with the user's OK |

What Claude cannot promise: reach, follows or any result on Instagram. Claude can promise that each line above is
built, tested in the cloud, shown to the user and reported honestly, and that a usage limit only pauses the list.
