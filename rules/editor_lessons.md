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

## 2026-10-16 - Answer cut in the Reel's proof box
- **What happened:** the first language-model "Biz denedik" Reel (NVIDIA Nemotron 3.5). The proof box under the hook cropped the model's answer card from the top, so the answer stopped mid-sentence ("büyük bir başarıya"). The editor rejected it, and it was right: viewers saw half an answer while the hook said the model explained the proverb.
- **Fix:** the Reel now scales an answer card into the proof box whole instead of cropping it (`_proof` in src/trial_reel). The hand-made second version was rejected too, because the hook's slow zoom (to 1.12) cut the last line at 2.5 s. The card now sits inside the part that stays visible at full zoom (`PROOF_SAFE`). The same morning the test itself had cut answers with a 600-token limit; answers that hit our limit are now never shown.
- **Rule:** A quoted answer or text from a test is always shown whole, in every image and frame. If any part is cut off, at an edge or mid-sentence, reject it. Never let a cut of ours look like the model's mistake.

## 2026-10-16 - Headline subject unclear
- **What happened:** the Nemotron "Biz denedik" Reel passed the editor with the headline "Yapay zekâya atasözünü çocuğa açıklattık". The user read it as if something had been done to a child. The editor missed it.
- **Fix:** the headline and the spoken hook were changed by hand to "Yapay zekâ atasözünü iki cümlede açıkladı" (rerender/2026-10-16_nemotron-3-5.json).
- **Rule:** In every headline and hook, who did what must be unmistakable. The model or tool is the subject. A causative with two objects that can be read the wrong way is a problem.

## 2026-10-17 - Wrong publish date from the page
- **What happened:** two Hugging Face carousels (IBM Granite Switch 4.1, NVIDIA Indic pretraining). The slides and footers said "2 Ekim" and "7 Eylül", but the posts were published on 15 and 16 Oct, as the screenshot on slide 2 showed. The editor rejected both, and it was right. Our capture took the first `<time>` on the page, which on Hugging Face is not the post date.
- **Fix:** the date now comes from the news feed (`feed_published` in carousel.py, `feed_item` in src/news_fetcher.py). Both posts were made again in the cloud.
- **Rule:** A date in the text or footer must match the date the source page shows. If they differ, or the source shows no date, reject it. The writer only names a date the article text or the feed gives.
