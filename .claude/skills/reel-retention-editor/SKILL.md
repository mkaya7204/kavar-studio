---
name: reel-retention-editor
description: Review a rendered KAVAR (@thekavar.ai) Reel like a retention editor before it is published - first frame, hook, pacing, ad cues, length, captions, safe zones, facts and policy - and read Reel metrics (skip rate, watch %, sends) to decide what to change. Use when reviewing a Reel, when the user asks why a Reel did badly, or when recording / analysing Reel results. src/editor_review.py loads the RULES section below for the automatic review.
---

# Reel retention editor

Role: the editor who decides if a Reel holds attention, and who learns from the numbers.
Research: `reports/Reels kapak hook ve izlenme.md`. Hook rules: `reel-hook-writer` skill.
First frame / cover rules: `reel-cover-designer` skill.

<!-- RULES:START -->
REEL RETENTION REVIEW (reject anything that fails a MUST)

MUST
- Frame 0 (and the cover) is fully composed: the headline readable, a proof image visible.
  A blank, blurred, single-colour or half-revealed frame 0 = reject.
- No ad look in the first 3 seconds: no tool logo / tool-name pill at the top, no "YENİ ARAÇ" /
  "NEW" badge, no CTA button shape, no prices. The tool name is not in the headline or the first
  spoken sentence (famous-brand news is the exception).
- Triple hook: the on-screen headline and the first spoken sentence say the same thing.
- The promise of the hook is proven within the first ~6 seconds (shown and said).
- Length 14-26 s; no dead air longer than ~0.6 s; the closing card is short (≈2 s).
- Text never sits in the top ~270 px band or the bottom ~35 %, never cut off or overlapping.
- Facts only from the tool data / source; page policy: no prices, payment models, free/paid,
  trials or discounts anywhere (screen, voice, caption).
- Natural Turkish, correct İ/ı casing.
SHOULD (list as problems, don't reject for these alone)
- Something changes on screen every 2-3 seconds.
- The closing line gives a reason to send or save to a specific person.
- Captions are short (≤3 words) and follow the voice.
<!-- RULES:END -->

## Reading the numbers (Instagram Insights / Meta Business Suite)

Record every Reel's results in `output/metrics/reels.json` with
`python -m reel_metrics update <id> --views N --skip-rate P --avg-watch-pct P --sends N` (run from
`src/`), or let Claude fill them from Business Suite. Starting targets (vendor rules of thumb, not
official): skip rate under 30-40 %, average watch ≥ 50-60 %, sends > 0 per 100 views.
Compare only Reels of similar length. Change one thing at a time (hook pattern first), and keep
80 % of the format fixed. `python -m reel_metrics summary` shows results per hook pattern; the
script writer reads the same summary.
