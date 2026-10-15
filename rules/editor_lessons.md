# Editor lessons

Agreed workflow (user, 2026-10-14, made permanent 2026-10-16): when the editor rejects a post,
Claude reviews it during the morning "yükle", decides whether the rejection was right, fixes the
post by hand (in the cloud), shows it to the user before scheduling, and then writes the lesson
here. `src/skill_rules.py editor_lessons()` feeds this file to the editor (src/editor_review.py)
and the writers (src/news_writer.py, src/script_writer.py), so the same mistake is not made, or
wrongly rejected, again.

Format: one `## <date> - <short title>` section per lesson, with:
- **What happened:** the post, what the editor said, and whether it was right.
- **Fix:** what was changed by hand.
- **Rule:** one or two sentences the writers and the editor must follow from now on.
Add new lessons at the bottom. Never delete a lesson without the user's approval.

## 2026-10-15 - Cover overstated the news
- **What happened:** NVIDIA Europe carousel. The cover said "35 süper bilgisayar geliştiriyor", which the editor flagged as stronger than the article. Even after the fix round the cover still said it, because the fix did not reach every field.
- **Fix:** not fixed by hand at the time; it was logged as open item 15.
- **Rule:** The cover, story and caption must use the article's own verb and actor ("kullanılıyor", "destekliyor", "şirkete göre"), never a stronger one. An editor fix applies to every place the sentence appears: cover, slides, story and caption.

## 2026-10-16 - Our test image carried an invented price
- **What happened:** "Biz denedik" FLUX.3 test. The model wrote "Sıcak Simit 50 Kr" on a sign in its simit image, and the editor rejected the carousel. The rejection was right: the page never shows prices.
- **Fix:** the image prompts now ask for no text, prices or logos. The test judge marks outputs with prices, other brands' logos, real people or unsafe content as unusable, and they are dropped.
- **Rule:** Any image we show, ours or the source's, must not contain a price or currency, even a small invented one. The editor rejects it, and the writer never describes a price seen in an image.

## 2026-10-16 - Reel caption stronger than the test
- **What happened:** the first "Biz denedik" Reel (FLUX.3). The voiceover said "Her harf doğru çıktı", but the caption said the neon sign was written "kusursuz", while the test note mentioned a small unreadable note in the window. The editor rejected it, and it was right: the caption claimed more than the test showed. Reels have no fix round, so one word cost the Reel.
- **Fix:** the Reel writer rule now says the caption uses the same verdicts and verbs as the voiceover, with no superlatives.
- **Rule:** Caption, story and on-screen text never claim more than the test or article shows. No "kusursuz", "mükemmel", "harika" or "inanılmaz" unless the source says exactly that. Use the same verb in every field.
