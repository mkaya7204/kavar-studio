# Instagram Reels Recommendation Algorithm 2025-2026: What It Rewards and Penalizes (for @thekavar.ai)

Research date: 2026-10-12. Labels used below: **[OFFICIAL]** means Instagram or Meta said it directly, or a reputable outlet quotes Instagram or Meta. **[SECONDARY]** means a marketer or vendor claim. **[OLD]** means from before 2025.

## 1. Official ranking signals and what Mosseri said in 2025-2026

### Takeaway
Instagram has named three top signals in 2025: watch time, likes per reach and sends per reach. Sends (sharing by DM) count slightly more for reach to non-followers. Meta's Reels ranking card (updated Nov 2025) also lists these predictions:
- watching less than 3 seconds, which is a negative
- watching more than 95% of the people who watched Reels of the same length
- reshares, off-platform shares, comments, follows and audio reuse

So a Reel is ranked on hook (not being skipped), retention relative to its length, and shareability.

### Cited Findings
- **[OFFICIAL]** Jan 2025: Mosseri named the top three signals as watch time, likes and sends. He said to "pay close attention to average watch time, likes per reach, and sends per reach." He added: "Likes are slightly more important for connected content, and sends are slightly more important for unconnected content." His overview did not mention comments — [Social Media Today, 22 Jan 2025](https://www.socialmediatoday.com/news/instagram-shares-algorithm-insights-2025/738034/)
- **[OFFICIAL, quoted secondhand]** Mosseri: "One of the most important signals we use in ranking is sends per reach." Sends per reach is the share of viewers who sent the post to someone by DM — [Search Engine Journal](https://searchenginejournal.com/instagram-algorithm-shift-why-sends-matter-more-than-ever/521389); [Inro guide](https://www.inro.social/guides/instagram-algorithm-guide)
- **[SECONDARY, disputed]** Sources disagree on whether watch time or sends ranks first. Mosseri's Jan 2025 statement does not rank them — [Dataslayer](https://www.dataslayer.ai/blog/instagram-algorithm-2025-complete-guide-for-marketers). One claim says sends weigh 3-5x likes for non-follower reach (attributed to "CreatorFlow"). It is not verified.
- **[OFFICIAL]** Meta Transparency Center, Instagram Reels ranking card (updated 11 Nov 2025). The ranking predicts how likely a viewer is to do each of these:
  - use the Reel's audio in their own Reel
  - **watch less than three seconds**
  - tap "Interested"
  - comment
  - **watch more than 95% of users who watched reels of the same length**
  - open a tall Explore Reel full screen
  - reshare the Reel
  - share the Reel off Instagram
  - follow the Reel's author

  — [Meta Transparency: Instagram Reels](https://transparency.meta.com/features/explaining-ranking/ig-reels-chaining/)
- **[OFFICIAL]** Input signals for the "less than 3 seconds" prediction include 3+ second views, dismissals, sound-on views and **skips within two seconds**. Input signals for the ">95%" prediction are reel length and viewing time. Before scoring, integrity filters remove "non-recommendable" content — [Meta Transparency](https://transparency.meta.com/features/explaining-ranking/ig-reels-chaining/)
- **[OFFICIAL, secondhand]** Mosseri said the system weighs both relative watch time (% watched) and absolute watch time (seconds watched) — [Fanpage Karma](https://www.fanpagekarma.com/insights/?p=9293); [Onestream](https://onestream.live/blog/how-long-can-instagram-reels-be/)
- **[OFFICIAL]** Aug 2025: Instagram added a per-Reel **retention chart** and a **skip rate** metric to Insights. Skip rate is the share of viewers who leave within the first 3 seconds. It replaced the older view-rate metric — [exchange4media](https://www.exchange4media.com/influence-zone-news/instagram-introduces-skip-rate-new-metric-to-make-brandcreator-conversations-tougher-146829.html); [marketing4ecommerce](https://marketing4ecommerce.net/en/retention-and-skip-rate-reels/)

### Inferences
- For a new account, almost all reach is "unconnected," so **sends per reach is the key lever**. Practical, useful AI-tool content ("send this to a friend who...") fits this.
- The ">95% of users at the same length" prediction means completion is judged **relative to Reels of similar length**. A short Reel is not automatically favored if it does not out-retain its peers.
- The first 2-3 seconds are an explicit model input (skip prediction). The opening frame or hook is directly scored.

### Gaps
- Instagram has published no official numeric weights, and there are no primary-source thresholds for "good" sends or likes per reach.
- I found no primary Mosseri video transcript (only press reports of it).

## 2. How new or small accounts are tested: trial reels, timing, scheduling

### Takeaway
Trial Reels show a Reel only to non-followers first. Instagram can then share it with followers automatically, within about 24-72 hours, if it performs well. Mosseri warned that Trial Reels usually underperform normal Reels and should only be compared with other Trial Reels. Mosseri reportedly said scheduling or API posting does not change reach. That is the official answer, but it is only reported secondhand and by vendors who have an interest in it.

### Cited Findings
- **[OFFICIAL, secondhand]** Mosseri: Trial Reels tend to perform worse than regular Reels because they always go to a new audience, so compare them only with other trials — [Fanpage Karma](https://www.fanpagekarma.com/insights/?p=9293)
- **[SECONDARY]** Trial Reels are hidden from your profile grid and Reels tab and from followers' feeds. Non-followers see them in Reels and Explore. They sit in "Drafts and trial reels." Metrics arrive after about 24 hours. Auto-share to followers happens if the Reel performs well within about 72 hours — [Storrito](https://storrito.com/resources/how-instagram-trial-reels-work-72-hours/); [Inro](https://www.inro.social/blog/what-is-a-reel-trial); [Outfy](https://outfy.com/blog/instagram-trial-reels)
- **[SECONDARY, unverified]** Eligibility thresholds are reported as professional accounts with 200+ followers and personal accounts with 1,000+. Instagram has not confirmed these — [Outfy](https://outfy.com/blog/instagram-trial-reels)
- **[SECONDARY]** Trial content can still spread through shares or DMs — [Fliki](https://fliki.ai/blog/trial-reels-instagram)
- **[OFFICIAL, secondhand, vendor-reported]** Mosseri said in a Q&A that scheduled posts "will not affect reach either way" — [Planoly, Apr 2025](https://planoly.com/blog/does-scheduling-your-posts-affect-your-post-reach); [Metricool](https://metricool.com/does-scheduling-social-media-posts-affect-reach/)
- **[SECONDARY]** The scheduling penalty myth comes from 2016-2018, when unofficial password-based auto-posters really were penalized. Today's API-based publishing (including the Instagram Graph API and Meta Business Suite) is a different thing — [SocialBu](https://socialbu.com/blog/does-scheduling-hurt-reach); [Poster.ly](https://www.poster.ly/blog/does-scheduling-hurt-reach-research)

### Inferences
- Publishing through the Instagram API (as daily.py does) should not be penalized in itself. The risk factors are originality and quality, not the posting method.
- Trial Reels are a low-risk way to A/B test hooks or covers with cold audiences without cluttering the grid. Compare trial-to-trial only.

### Gaps
- There is no official spec for the size of the initial test audience or the exact window before Instagram decides on wider distribution. Figures like "first 30-60 minutes" are folklore. I found no primary source for them.
- I found no primary Instagram documentation of trial eligibility thresholds or the auto-share window.

## 3. Ideal length, the 3-minute limit, completion and loops

### Takeaway
Since Jan 2025, Reels can be up to 3 minutes long, and Instagram's own guidance says recommendable Reels must be 3 minutes or shorter. Length studies conflict because they measure different things:
- For completion and shares, roughly 7-15 seconds does best.
- For engagement rate and median views on business accounts, roughly 45-60 seconds does best.

Because ranking compares retention against Reels of the same length, the right length is the shortest one that delivers the payoff.

### Cited Findings
- **[OFFICIAL, secondhand]** Jan 2025: Mosseri raised the Reels limit from 90 seconds to 3 minutes — [Brandsynario](https://www.brandsynario.com/news/instagram-users-can-now-post-three-minute-long-reels/); [Onestream](https://onestream.live/blog/how-long-can-instagram-reels-be/)
- **[OFFICIAL]** Instagram's creator guidance says recommendable Reels must be **3 minutes or shorter**. It also asks for full-screen vertical 9:16, high resolution, no borders, text that does not cover most of the screen, and to "grab attention in the first 3 seconds" — [Instagram Creators: recommendations eligibility](https://creators.instagram.com/blog/instagram-recommendations-eligibility-tips-creators). The page was first published Aug 2022 and updated Apr 2023, and the 3-minute figure shows it was revised after Jan 2025.
- **[SECONDARY]** Earlier guidance (before 2025) said Reels over 90 seconds could hurt distribution. **[OLD]** — [Onestream](https://onestream.live/blog/how-long-can-instagram-reels-be/)
- **[SECONDARY]** A 2026 Socialinsider analysis of about 140k business Reels (reported secondhand) found the **45-60 second** band had the highest engagement rate (0.35%) and median views (10,374). Reels over 3 minutes dropped to 0.15% — [Klap](https://klap.app/blog/how-long-should-reels-be)
- **[SECONDARY]** A CreatorsJet analysis of 500 viral Reels (Oct 2024-Mar 2025) found **7-15 seconds** gave the highest completion and shareability, with 60-80% retention. Another analysis of 315 Reels found 15-30 seconds best for engagement per view (9.4%) — [Klap](https://klap.app/blog/how-long-should-reels-be); [Shortimize](https://www.shortimize.com/blog/video-length-sweet-spots-tiktok-reels-shorts)

### Inferences
- For a 30-second news Reel, the target is a high average % watched plus some rewatches. Seamless loops raise viewing time per viewer, which is a direct input to the ">95%" prediction. (This is inferred. Instagram has not said loops are counted specially.)
- Going over 60 seconds only pays if retention holds. The 3-minute cap is a hard eligibility limit for recommendations.

### Gaps
- I could not access the original Socialinsider, Metricool or Emplifi reports. The figures above are secondhand.
- There is no official statement on how rewatches or loops are counted.

## 4. Originality rules, aggregators, watermarks and recommendation eligibility

### Takeaway
On **30 April 2026**, Instagram extended its 2024 Reels originality rule to photos and carousels. Accounts that mostly repost others' content become **ineligible for all recommendations**. They can recover once most of their recent posts are original over a rolling **30-day** window. Watermarks, speed changes, borders, captions, credits or screenshots of others' posts do not make content original. Unique text or context, graphics that add information, commentary or remixing do.

### Cited Findings
- **[OFFICIAL]** 30 Apr 2026, Instagram Creators blog. Accounts that mostly share non-original photos, carousels or Reels are not recommended.
  - **75% of US recommendations now come from original posts.**
  - Accounts become eligible again when most recently shared posts are judged original over a 30-day period, calculated continuously.
  - Status can be checked in **Account Status**, where you can remove posts or appeal.
  - Adding a border, watermark, caption or credit does not count as original.
  - Significant edits do count, such as unique text that adds context, graphics that add new information, or a remix.
  - Credit others through Collabs, remix, Stories shares or reposts.
  - Followers still see the account's posts.

  — [Instagram Creators: Rewarding original creators](https://creators.instagram.com/blog/rewarding-original-creators-on-instagram)
- **[OFFICIAL, via press]** Same change: watermarks or speed changes are not original. A screenshot of another person's post is not original even with their username shown. "An original meme transforms another creator's photo or video" — [TechCrunch, 30 Apr 2026](https://techcrunch.com/2026/04/30/instagram-restricts-reach-of-content-aggregators-in-new-crackdown/); [Tubefilter](https://tubefilter.com/2026/04/30/instagram-removes-algorithm-recommendations-repost-content-aggregator); [PetaPixel](https://petapixel.com/2026/04/30/new-instagram-policies-target-reposted-content/)
- **[OFFICIAL]** Eligibility guidance:
  - Avoid watermarked, blurry or low-quality Reels, and do not re-upload Reels already on Instagram.
  - Repeatedly posting non-recommendable content, or having violating content in your profile photo or bio, can make the **whole account** ineligible for a period.
  - Account Status (Settings > Account > Account Status) shows whether you can be recommended to non-followers.

  — [Instagram Creators: recommendations eligibility](https://creators.instagram.com/blog/instagram-recommendations-eligibility-tips-creators)
- **[OFFICIAL]** Recommendation Guidelines set a higher bar than Community Guidelines and define five categories of content that is allowed but may not be recommended. Coverage lists "unoriginal content that is largely repurposed from another source without adding material value" and "low-quality publishing" among them — [Instagram Help: Recommendation Guidelines](https://help.instagram.com/313829416281232); [Social Media Today](https://www.socialmediatoday.com/news/facebook-provides-an-overview-of-content-that-it-looks-to-exclude-from-its/584442)
- **[OFFICIAL, OLD 2021]** Reels visibly recycled from other apps (for example with a TikTok logo) are less discoverable in the Reels tab but still shown to followers — [The Next Web, Feb 2021](https://thenextweb.com/plugged/2021/02/10/instagram-wont-recommend-reels-with-a-tiktok-logo-and-its-unfair/)

### Inferences
- **Highly relevant to @thekavar.ai:** AI news Reels built from company demo clips, screen recordings of other people's posts, or reposted launch videos with only a voiceover or credit are at risk if they make up most of the output. Each Reel should add clear transformation: original Turkish narration that gives context or analysis, our own graphics and on-screen text, our own design system and our own demos. Also avoid other platforms' watermarks (TikTok or CapCut end cards).
- Check Account Status regularly. One period of mostly repurposed posts can switch off non-follower reach for the whole account until the 30-day mix recovers.

### Gaps
- I could not fetch the full current text of the Help Center Recommendation Guidelines (the page did not render).
- There is no official numeric threshold for "mostly" (for example, what share of a 30-day window has to be original).

## 5. Ads and branded content, AI-generated content and synthetic voice

### Takeaway
I found no official rule that demotes organic content because it looks promotional. The official non-recommendable categories target regulated products, low quality and unoriginal content, not promotion as such.

On AI: as of Aug-Sep 2026, Instagram penalizes only **unlabeled AI-persona profiles** (accounts featuring an AI-generated person), which become non-recommendable. Using AI tools for graphics, edits or captions does not require the profile label. Mosseri's Dec 2025 memo signals that Instagram favors authentic, human-made content, but this is a direction, not a stated ranking rule.

### Cited Findings
- **[OFFICIAL, via press]** 31 Aug 2026: the "AI creator" label was renamed "AI-generated profile." It is required only for accounts that feature an AI-generated person.
  - Unlabeled profiles that Instagram detects become **ineligible for recommendations**, which also limits monetization.
  - Labeled AI personas keep recommendation reach.
  - Creators who use AI tools but appear as their real selves do not need the label.
  - Enforcement and detection were described as rolling out "in coming weeks."

  — [MediaPost](https://mediapost.com/publications/article/417580/instagram-limits-reach-for-creator-profiles-withou.html); [Implicator](https://www.implicator.ai/instagram-will-cut-the-reach-of-ai-personas-that-skip-its-new-label/); [Khaleej Times](https://www.khaleejtimes.com/business/tech/instagram-ai-generated-profile-label-reach-restrictions?amp=1)
- **[OFFICIAL, via press]** In May 2026, Instagram said labeling an AI creator profile would not affect recommendations — [MediaPost](https://mediapost.com/publications/article/417580/instagram-limits-reach-for-creator-profiles-withou.html)
- **[OFFICIAL, summarized by commentators]** Mosseri's year-end memo, posted 31 Dec 2025 as a 20-slide carousel, included these points:
  - "authenticity is becoming infinitely reproducible"
  - raw, less polished content works as a signal of human origin
  - Instagram plans to label AI content, show more context about accounts, and support credibility signals and verification

  — [Om Malik](https://om.co/2026/01/01/what-is-instagrams-adam-mosseri-really-saying-in-his-year-end-memo/); [Tubefilter, Jan 2026](https://www.tubefilter.com/2026/01/06/adam-mosseri-instagram-warning-generative-ai-deepfakes/)
- **[SECONDARY]** Claims that Instagram will "prioritize raw human content over AI in 2026" with specific reach-weighting percentages come from newsletters with unclear sourcing — [Creator Growth Weekly](https://creatorgrowthweekly.beehiiv.com/p/instagram-algorithm-2026-what-gets-reach)
- **[OFFICIAL]** Content promoting regulated products (tobacco, e-cigarettes) is an example of non-recommendable content. Branded content should use the paid partnership label — [Instagram Creators](https://creators.instagram.com/blog/instagram-recommendations-eligibility-tips-creators); [Instagram Creators, Apr 2026](https://creators.instagram.com/blog/rewarding-original-creators-on-instagram)
- **[SECONDARY]** A Kantar 2025 report (via exchange4media) found influencer content holds viewers longer before they skip than branded assets: 17.8s vs 7.9s average time before skipping — [exchange4media](https://www.exchange4media.com/influence-zone-news/instagram-introduces-skip-rate-new-metric-to-make-brandcreator-conversations-tougher-146829.html)

### Inferences
- @thekavar.ai shows no AI-generated person, so the AI-generated profile rule should not apply. If an AI avatar presenter is ever used, label the profile.
- An ElevenLabs synthetic voice has no documented reach penalty. The indirect risk is behavioral: content that feels ad-like or synthetic may get skipped faster (Kantar's branded-vs-creator gap), and a high skip rate is a direct negative prediction.

### Gaps
- There is no official source on whether the post-level "AI info" label reduces reach, or on any treatment of synthetic voiceovers.
- There is no official source on organic demotion of content that looks like an ad. Only folklore exists.

## 6. Hashtags, captions and keywords, cover and first frame, posting times

### Takeaway
Since Dec 2025, Instagram limits posts to **5 hashtags**. Mosseri says hashtags help categorize content and search but do not increase reach. Officially, keywords in the caption, username, name and bio help Search. Best posting times depend on how a study measures success: Buffer (9.6M posts) favors weekday mornings and midday, while Later favors early morning.

### Cited Findings
- **[OFFICIAL, via press]** Instagram capped hashtags at 5 per post (previously 30). Mosseri said a few specific tags work better than many generic ones, and that hashtags help with search and with signaling what a post is about but "don't increase your reach." Reports differ on enforcement — [Social Media Today](https://www.socialmediatoday.com/news/instagrams-implementing-new-limits-on-hashtag-use/808309/); [Blog du Modérateur](https://www.blogdumoderateur.com/instagram-limite-hashtags-5-par-publication/)
- **[OFFICIAL]** For Search, put keywords in your username, name, bio and captions, and keep keywords and hashtags in the caption rather than the comments — [Instagram Creators](https://creators.instagram.com/blog/instagram-recommendations-eligibility-tips-creators)
- **[SECONDARY]** Buffer's 2026 study of 9.6M Instagram posts (Jan 2024-Dec 2025) found these top slots: Thu 9am, Wed 12pm, Wed 6pm. Wednesday was the best day. Later's study of 6M+ posts, measured by engagement rate, favors about 5am local time. SocialPilot recommends 8am-12pm Mon-Thu for Reels. The differences come from methodology: total engagement versus reach-normalized engagement — [Buffer](https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram); [Fliki summary](https://fliki.ai/blog/best-time-to-post-reels-on-instagram); [SocialPilot](https://www.socialpilot.co/insights/best-time-to-post-reels-on-instagram)
- **[OFFICIAL]** Explore/Reels predictions include "open a tall Explore reel full screen." The Explore grid shows a tile (the cover or first frame), so how clickable the tile is feeds a ranking prediction — [Meta Transparency](https://transparency.meta.com/features/explaining-ranking/ig-reels-chaining/)

### Inferences
- The cover matters mostly for Explore grid tiles and the profile grid. In the Reels feed, the **first frame plus the first 2 seconds** is what gets judged, through the skip prediction. Design the opening frame to work both as a cover and as a hook.
- Use 3-5 precise Turkish and English keyword hashtags (for example #yapayzeka #aiaraçları) plus keyword-rich Turkish captions for search. Do not expect hashtags to bring reach.
- Posting times from US-heavy studies may not apply to a Turkish audience (UTC+3). Use your own Insights.

### Gaps
- There is no official statement on whether a custom cover versus the first frame affects ranking.
- There is no Turkey-specific posting-time data from a credible firm.

## 7. Benchmarks: hold rate, skip rate, retention

### Takeaway
Instagram publishes no official benchmarks for skip rate or retention. The available numbers are vendor or blog rules of thumb, and they disagree: healthy skip rate is put somewhere between under about 30-40% and the low teens. Engagement benchmarks are small: about 0.35% engagement rate for the best length band in Socialinsider's 2026 business-Reels data.

### Cited Findings
- **[SECONDARY]** Skip rate under about 30-40% is called healthy and over 50% signals a weak hook (trackers cited by a blog). Shortimize: a great hook gets skip rate into the low teens or single digits, and a poor one loses 30%+ — [Async](https://async.com/blog/reel-retention-tips/); [Shortimize](https://www.shortimize.com/blog/compare-watch-time-tiktok-vs-reels-vs-shorts)
- **[OFFICIAL]** Skip rate means the share of viewers who leave within the first 3 seconds. Insights also shows a retention curve per Reel (since Aug 2025) — [Metricool](https://metricool.com/instagram-reel-analytics/); [Website Builder Expert](https://www.websitebuilderexpert.com/news/instagram-reel-retention-chart/)
- **[SECONDARY]** Socialinsider 2026 (secondhand): best length band engagement rate 0.35%, median views 10,374 for business Reels — [Klap](https://klap.app/blog/how-long-should-reels-be)
- **[SECONDARY]** The 7-15 second band showed 60-80% retention in a sample of 500 viral Reels — [Klap](https://klap.app/blog/how-long-should-reels-be)
- **[SECONDARY]** Kantar 2025: average time before skipping was 17.8s for influencer content and 7.9s for brand assets — [exchange4media](https://www.exchange4media.com/influence-zone-news/instagram-introduces-skip-rate-new-metric-to-make-brandcreator-conversations-tougher-146829.html)

### Inferences
- Practical internal targets: skip rate under about 30% and average watch time of 60% or more for 20-30 second Reels. Track sends per reach as the main growth KPI and compare Reel against Reel. These are working heuristics, not official thresholds.

### Gaps
- I found no credible large-sample published benchmark (Later, Buffer, Hootsuite, Dash Hudson, Metricool, Socialinsider) for 3-second hold rate or skip rate. Metricool mentions an "Instagram Study 2026" (25M posts), but I did not find retention figures from it.
