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

## 2026-10-17 - Shrunken headline under the proof box (template)
- **What happened:** three of four tool Reels. At ~2.5 s the headline shrinks into a label and the proof box moves up. The box always moved up 150 px, so a two-line headline's second line ended up under the box's top edge (Train with Pasta "ANTRENMANDA ELLER SERBEST Mİ?", Craft Agents "YÖNETİYORSUN?"; Earnote was tight). The domain stamp also sat on the proof's own text (Craft Agents: "agents.craft.do" on "OpenRouter, local models"). The editor rejected both, and it was right: overlapping, cut text is never allowed.
- **Fix:** the template now lifts the box only into the room the shrinking headline frees (`LIFT` in templates/hyperframes_news), and the stamp sits under the box, not on it. Train with Pasta rendered again by hand (rerender/2026-10-17_train-with-pasta.json): at 2.5 s the label sits clear above the box and the stamp under it; the editor passed it.
- **Rule:** Check the ~2.5 s frame: the small headline, the bar and the proof box never touch or overlap, and no stamp or label covers the proof's text. If they do, reject and name the frame. A writer never works around this by shortening a good headline; it is a template fault, so say "template" in the reason.

## 2026-10-17 - A card caught while it enters is not an empty card
- **What happened:** Ultracite v8. The editor said the card at 12.1 s was an empty glass box, twice (the hand-made second render had the same timing). A frame-by-frame sheet (frames.yml) showed card 02 enters at 12.0 s, its title arrives at 12.25-12.5 s and its detail at 12.75 s. The editor only sees one middle frame (half the length, 12.05 s here), which fell on the entrance. The editor was wrong on this point; its proof reasons were right (next lesson).
- **Fix:** the editor now also gets the frame 1 s after the middle one (src/editor_review.py `review_reel`).
- **Rule:** A card whose box is on screen and whose text arrives within 1 s is an entrance, not dead air. Before calling a card empty, look at the frame 1 s later; call it empty only if it is still empty there.

## 2026-10-17 - Proof that does not prove the hook
- **What happened:** Craft Agents' proof was the site's English slogan card ("Work with most powerful agents..."), and Ultracite v8's proof was a random changelog bullet ("Fixing all 11: typing the users...") with red capture edges and an empty lower half. Neither shows the promise the hook makes. The editor rejected both, and it was right.
- **Fix:** both were rendered again by hand. Craft Agents: the fresh capture found no clean proof on the site, so it was dropped. Ultracite v8: the same changelog bullet came back (it also filled the 13-15 s site shot) and the editor rejected it again, so it was dropped. A tool whose site shows no proof of the promise is skipped.
- **Rule:** The proof under the hook shows the product doing what the hook promises: its interface, its output, or a result. A slogan, a feature list, a changelog line, a pricing box or a cut-off block is not proof. Reject it, and the writer chooses a hook the proof can show, or the tool is skipped.

## 2026-10-17 - Misspelled hashtag
- **What happened:** Train with Pasta. The hashtags had "#applentelligence" instead of "#appleintelligence". Reels have no fix round, so the editor rejected it, and it was right.
- **Fix:** corrected by hand in rerender/2026-10-17_train-with-pasta.json.
- **Rule:** Every hashtag is a real, correctly spelled word or name, all lower case, without Turkish characters when the brand has none (#appleintelligence, #opensource). The writer checks each brand name letter by letter against the source.

## 2026-10-17 - Card says one thing, the voice another
- **What happened:** Ultracite v8. Card 02 read "Ayar yapmadan hazır preset" while the voice and captions said "Ajanın yazdığı kod tutarlı kalıyor"; card 03 read "Tutarlı ve tip güvenli kod" under "Tip güvenliği de korunuyor". The writer had put two benefits into point1, so every later card ran one step ahead of the voice. Neither the writer's checks nor the editor caught it.
- **Fix:** the writer now measures it (`card_voice_mismatch` in src/script_writer.py): each card must share words with the part spoken under it, more than with any other part, or the draft is written again.
- **Rule:** Card N is on screen while pointN is spoken, so key_points[N-1] and pointN say the same benefit, one benefit per point, in the same order. The editor compares each card with the words spoken under it and rejects a Reel whose cards and voice disagree.
