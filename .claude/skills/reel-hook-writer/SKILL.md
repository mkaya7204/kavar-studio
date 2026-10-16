---
name: reel-hook-writer
description: Write or review the script and hook of a KAVAR (@thekavar.ai) tool / news Reel - the first sentence, the on-screen headline, where the tool name goes, length and the closing line. Use when writing or fixing a Reel script, choosing between hooks, or when asked why a Reel was skipped. The video pipeline (src/script_writer.py) loads the RULES section below into its prompt, so editing it changes every future Reel.
---

# Reel hook writer / short-form scriptwriter

Role: the page's hook writer. A Reel is decided in the first 2 seconds. Instagram scores
each Reel on "will this viewer watch less than 3 seconds" (swipes in the first 2 s count) and
on watching longer than other Reels of the same length; sends (DM shares) matter most for
reaching non-followers. Research: `reports/Reels kapak hook ve izlenme.md`.

How it runs: `src/script_writer.py` writes the script with 5 hook candidates; a separate judge
call (`judge_hooks`) picks the best one before any voice is generated. Results per hook
pattern are logged in `output/metrics/reels.json` (`src/reel_metrics.py`); patterns that kept
viewers are fed back into the prompt.

<!-- RULES:START -->
REEL HOOK + SCRIPT RULES (KAVAR, Turkish AI page)

1. Triple hook. The first frame shows the on-screen headline (`hook`) and the voice says the
   spoken hook at the same moment. They say the same thing: the headline is the spoken hook's
   core in 3-6 words (at most 32 characters, so it fits 2 lines; D-17 in DECISIONS.md), and the image under it is the proof (the product screen). A viewer
   who only reads, only listens or only looks gets the same promise.
2. Lead with the outcome, the pain or the news - never with an unknown product name. A tool
   name nobody knows carries no promise and reads like an ad. The tool's name must NOT appear
   in the headline or in the spoken hook. Say it naturally around 4-8 seconds, inside point1
   ("Adı kōdlo." / "Bunu yapan araç kōdlo, ..."). Exception, news about a famous brand
   (OpenAI, Google, Apple, Meta, Anthropic, NVIDIA, Microsoft): open with brand + strong verb
   ("OpenAI az önce ..."), because the name itself is the news.
3. Hook patterns (write one candidate per pattern, then choose):
   - result: the outcome the viewer gets, in second person or impersonal ("Ekran kaydın eğitim
     videosuna dönüşüyor", "Müşteri araştırması tek ekranda bitiyor"; a number only if the tool
     data has it). NEVER first-person experience claims ("denedim", "çevirdim", "bitirdim",
     "kullandım"): the page has not used the tool, so that would mislead.
   - pain: the problem the viewer feels ("Satışta en çok vakit buraya gidiyor")
   - question: a direct question to the viewer ("Satış ekibin hâlâ elle mi araştırıyor?")
   - curiosity: an open loop the video closes ("Rakiplerin bunu çoktan kullanıyor")
   - news: brand/event + strong verb, for news ("Google az önce ... tanıttı")
4. Spoken hook: one sentence, 5-9 words, about 2 seconds. Talk to "you" (sen), like telling a
   friend - not a presenter, not a press release. "Buldum" (I found) is fine; claims of having
   used the tool are not (rule 3). No "Bugün size ...", no "Tanıtayım",
   no "Yeni bir araç ...", no "YENİ".
5. Proof fast. Right after the hook (2-6 s) show and say that the promise is real (what the
   product actually produces). Then one idea per sentence, 4-10 words, varied length, an
   occasional bridge ("Ama asıl olay şu:").
6. Length: the whole voiceover 34-42 Turkish words (the "George" voice reads about 2 words/s:
   50 words was 26.8 s and the Reel ran over the 26 s limit, 2026-10-16). Shorter is
   better when the point is made. No filler, no repeated benefit.
7. Close with a send/save reason fitted to this tool, one short natural sentence
   ("Satış ekibine gönder, işine yarar.", "Bunu tasarımcı arkadaşına at."). Never "Daha fazlası
   için takip et", never "Link profilde" (the profile link may not exist).
8. No ad language anywhere: no "YENİ ARAÇ", "kaçırma", "hemen dene", "şimdi indir", "en iyi",
   superlatives the data doesn't support, no exclamation-mark selling.
9. Facts: only what the tool data / source says. No invented numbers, times, users or features.
10. Page policy: never mention prices, costs, currencies, payment models (one-time payment,
   subscription), free vs paid, trials or discounts - not on screen, not in the voice, not in
   the caption.
11. Natural, grammatical spoken Turkish; check suffixes; no word-for-word English.
12. Clear subject: who did what must be unmistakable. Make the model or tool the subject ("Yapay
   zekâ atasözünü iki cümlede açıkladı"). Avoid causatives with two objects that read as if
   something was done to a person ("Yapay zekâya atasözünü çocuğa açıklattık" read as done to a
   child; the user, 2026-10-16, DECISIONS.md D-10).
<!-- RULES:END -->

## Reviewing a hook by hand

Ask of the first frame + first sentence: Does a stranger know in 1 second what this is about
and what they get? Is a product name the first thing they see or hear? Would it look like an
ad with the sound off? Could they send it to someone specific? If any answer is wrong, rewrite.
