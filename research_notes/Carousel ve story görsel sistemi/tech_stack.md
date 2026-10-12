# Tech stack for automatically rendering and publishing Instagram carousels and Stories

Research date: 2026-10-11. Pipeline context: Python on Windows 10 with 4 GB RAM, Claude writes the scripts, Playwright takes the screenshots, and HyperFrames (HTML) renders the video.

## 1. Rendering HTML/CSS templates to PNG/JPEG with Playwright (Python)

### Takeaway
Playwright's `page.screenshot()` can export PNG, JPEG or WebP with a quality setting and with animations disabled. That is enough to turn the existing HTML templates into carousel slides and Stories with almost no new dependencies. Fonts and images do need an explicit wait (`document.fonts.ready` plus `img.decode()`) before each capture. JPEG is the only image format the Instagram API accepts, so the final file must be a JPEG.

### Cited Findings
- `page.screenshot()` options:
  - `type`: `"png"` (default), `"jpeg"` or `"webp"`.
  - `quality`: 0–100, ignored for PNG. JPEG defaults to 80.
  - `scale`: `"css"` gives 1 px per CSS px. `"device"` (default) gives 1 px per device px.
  - `animations: "disabled"` fast-forwards finite animations to completion and resets infinite ones.
  - `caret: "hide"` (default).
  - `omit_background`: transparency, not applicable to JPEG.
  - `style`: CSS injected during the capture (v1.41+).
  - `clip`, `full_page`, `mask`, `mask_color`.
  - `timeout`: default 30000 ms.
  — [Playwright Python Page API](https://playwright.dev/python/docs/api/class-page)
- `set_viewport_size` should be called before navigation. To control both screen and viewport, pass `viewport`/`screen` to `browser.new_context()` (the same is true of `device_scale_factor`). — [Playwright Python Page API](https://playwright.dev/python/docs/api/class-page)
- The screenshot section of the docs says nothing about waiting for fonts, so do not assume that `screenshot()` waits for web fonts. — [Playwright Python Page API](https://playwright.dev/python/docs/api/class-page)
- `document.fonts.ready` resolves once the document has finished loading fonts, layout is complete and no further font loads are needed. A font that has not been requested yet (for example one added later by a class change) may not be covered, so use `document.fonts.load("700 64px Inter")` for explicit loads. — [MDN FontFaceSet.ready](https://developer.mozilla.org/en-US/docs/Web/API/FontFaceSet/ready)
- The Instagram API accepts JPEG only for images, with a maximum size of 8 MB. Images in other color spaces are converted to sRGB. Width must be 320–1440 px: smaller images are scaled up and larger ones scaled down. — [IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)

### Inferences
- **Recommended setup**
  - Create a context with `viewport={"width":1080,"height":1350}` (or 1920 for a Story) and `device_scale_factor=1`.
  - Output files should be exactly 1080 px wide. Going to 1440 px wide (dsf≈1.333) is technically accepted by the API, but there is no proof it improves quality.
  - Capture order: `goto(file://...)` → `page.evaluate("document.fonts.ready")` → `page.evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>{})))")` → `screenshot(type="png", animations="disabled")`.
- **JPEG conversion**
  - Take a PNG master, then convert it to a single JPEG with Pillow at `quality=90–95`, `subsampling=0` (4:4:4, keeps colored text sharp) and an embedded sRGB ICC profile.
  - Playwright's own JPEG encoder does not expose chroma subsampling, so this two-step conversion gives more control. This is inference, not a measured result.
- **Fonts and color**
  - Store fonts locally (woff2/ttf) and reference them with `@font-face` using `font-display: block`. Avoid depending on Google Fonts at render time.
  - Check that the fonts include the Turkish characters (ğ, ş, ı, İ).
  - Chromium renders to sRGB by default. Keep CSS colors in sRGB too, and avoid `display-p3` colors.
- **Memory on 4 GB RAM**
  - Launch one Chromium process and reuse a single page for every slide (re-`goto` or `set_content`).
  - Run renders sequentially, never in parallel.
  - Close the context after each batch.
  - Never run the HyperFrames render and the carousel render at the same time.
  - These recommendations follow from Chromium's known memory profile. No source was found that measured them.

### Gaps
- No primary source was found on whether Playwright's own screenshot waits for web fonts. There are anecdotal claims that it does since v1.2x, but they are unverified.
- No benchmark measuring Playwright memory per page on a 4 GB machine was found.

## 2. Alternatives: Satori, Pillow, Skia, Bannerbear, Placid, Templated.io, APITemplate, Canva Connect

### Takeaway
For this pipeline, the Playwright + HTML approach already covers the job and has no per-image cost. SaaS template APIs cost $29–$149/month for roughly 1k–10k images, and Canva Autofill requires Canva Enterprise on both the developer side and the end-user side. Satori now supports Grid but is Node-only, does not support WOFF2, and handles RTL only in a limited way, so it adds nothing over the current stack.

### Cited Findings
- **Satori**
  - Layout uses Taffy: "Flexbox, Grid and block layouts" are supported, except for `subgrid` (which throws) and `masonry`.
  - Fonts: TTF, OTF and WOFF are supported. WOFF2 is not.
  - `calc()` with percentages is partial. 3D perspective is approximated with affine transforms (an exact version is in `satori/experimental`).
  - Mixed LTR/RTL bidirectional layout is not fully supported.
  - Output is an SVG string. Sharp is recommended to convert it to PNG.
  - This is an update: older guides say Satori is flexbox-only, which is now outdated.
  — [vercel/satori README](https://github.com/vercel/satori)
- **Bannerbear**
  - Plans: Automate $49/month (1,000 API credits), Scale $149/month (10k–40k tiers), Enterprise $299/month (50k+).
  - REST API with Python, Node, Ruby and PHP libraries, plus MCP.
  - 1 render = 1 credit, multiplied by the number of formats and by scale (JPG+PNG at scale 2 = 4 credits).
  - Free trial: 30 credits, no card required.
  — [Bannerbear pricing](https://www.bannerbear.com/pricing/)
- **Placid**
  - Basic 500, Pro 2,500, Business 25k and VIP 100k credits per month.
  - 1 image = 1 credit. Previews are free.
  - The page did not show prices. A third-party, Templated-authored source cites Pro at $39/month for 2,500 credits and a $19 plan for 500 credits. Not verified.
  — [Placid pricing](https://placid.app/pricing); [Templated blog (vendor comparison)](https://templated.io/blog/top-placid-alternatives-for-image-generation/)
- **APITemplate.io**
  - Plans: Free (50 images/PDFs per month, 3 templates), Starter $35/month (1,500), Standard $89/month (9,000), Enterprise $179/month (20,000).
  - Annual billing saves up to 20%.
  — [APITemplate pricing](https://apitemplate.io/pricing/)
- **Templated.io** — Starter is reported at $29/month for 1,000 credits, with a 50-credit trial. This comes from a vendor's own blog. — [Templated blog](https://templated.io/blog/best-bannerbear-alternatives/)
- **Canva Connect Autofill**
  - The developer must be a member of a Canva Enterprise organization, and so must every user of the app. The developer's subscription does not extend to users.
  - While the app is in development, users on paid plans get a limited trial.
  - Brand template IDs are moving to a new format, with a 6-month migration period.
  — [Canva Autofill guide](https://canva.dev/docs/connect/autofill-guide); [Canva Autofill API reference](https://www.canva.dev/docs/connect/api-reference/autofills)

### Inferences
- **Pillow (PIL)**: good for simple compositions (background + screenshot + text), but Turkish typography, line wrapping, kerning and shadows have to be written by hand. Use it only for the post-processing step (JPEG/ICC conversion).
- **Skia (skia-python)**: a powerful 2D API, but it repeats the work HTML/CSS already does, so it has a low return for this project.
- **SaaS template APIs** make sense when a non-developer needs to edit templates in a visual editor. For a solo, code-driven pipeline, they add a monthly cost plus a dependency on public URLs.
- **Canva Autofill** is effectively closed to a single Turkish creator without an Enterprise plan.

### Gaps
- The Placid and Templated.io prices could not be confirmed on the vendors' own pages.
- No primary source was consulted for skia-python or Pillow.

## 3. Placing product screenshots into device/browser mockups programmatically

### Takeaway
The simplest and most consistent approach is a browser "chrome" frame made in pure CSS (three dots, an address bar, rounded corners, a shadow), with the Playwright screenshot inside it as an `<img>`. CSS 3D `perspective` + `rotateY/rotateX` gives angled shots, and it renders correctly in Chromium. For phone and laptop frames there are MIT-licensed CSS libraries.

### Cited Findings
- **css-device-frames** (npm, MIT, v1.0.6): single-element, CSS-only application and device frames, customizable through CSS custom properties. Keywords include iPhone, iPad, MacBook and browser. — [jsDelivr css-device-frames](https://www.jsdelivr.com/package/npm/css-device-frames)
- **react-mockframe** (MIT): iPhone, iPad and MacBook Pro mockups for React, with modular CSS. — [react-mockframe README](https://cdn.jsdelivr.net/npm/react-mockframe@1.1.0/README.md)
- **Flowbite**: Tailwind-based phone and laptop mockup components. Its sample screen images are hosted on external S3. — [Flowbite device mockups (mirror)](https://glama.ai/mcp/servers/@zoltanszogyenyi/flowbite-mcp/blob/a5a834e5de673c01e55043b1a82f3d36de437ecb/data/components/device-mockups.md)
- **Satori**: approximates perspective, so it is weak for 3D mockups. — [vercel/satori](https://github.com/vercel/satori)

### Inferences
- **Steps**
  1. Take the screenshot at 1440×900 with `device_scale_factor=2`, so the image stays sharp when shrunk inside the frame.
  2. Write a frame component in HyperFrames/HTML.
  3. Reuse the same component in both the video and the carousel.
- **Photorealistic device photos**: Apple and other vendors' official marketing images have licensing and trademark issues, so a stylized CSS frame is safer.
- **Perspective**: use `transform: perspective(1600px) rotateY(-14deg) rotateX(6deg)` together with `image-rendering: auto` and `backface-visibility: hidden`. This is enough in Chromium, and no separate mockup engine is needed.

### Gaps
- The GitHub repo, license and maintenance status of css-device-frames were not verified directly.

## 4. AI image generation (2025–2026): cost, API access, when to use it

### Takeaway
As of October 2026, the cheapest options are Google's "Nano Banana" family, at about $0.034–0.067 per 1K image, with the Batch tier at half price. Gemini 2.5 Flash Image (the original Nano Banana) was scheduled to shut down on 2 Oct 2026, so it should not be used. OpenAI gpt-image-2 / 2.5 is token-priced. FLUX 1.1 pro costs $0.04 per image, and Recraft V3 costs $0.04 (raster) or $0.08 (vector). AI images should be limited to backgrounds and illustrations. Text, the logo and product screenshots must be overlaid in HTML.

### Cited Findings
- **Gemini API image prices (standard / batch per image)**
  - Gemini 3.1 Flash Image ("Nano Banana 2"): $0.045 (0.5K), $0.067 (1K), $0.101 (2K), $0.151 (4K). Batch is about half.
  - Gemini 3.1 Flash Lite Image ("Nano Banana 2 Lite"): $0.0336 (1K), batch $0.0168.
  - "Nano Banana 2.1": $0.0336 (1K), $0.0504 (2K), $0.113 (4K).
  - Gemini 3 Pro Image ("Nano Banana Pro"): $0.134 (1K/2K), $0.24 (4K).
  - Gemini 2.5 Flash Image: $0.039. **Deprecated, shutdown Oct 2, 2026.**
  — [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- **OpenAI image models (per 1M tokens, image output)**
  - gpt-image-2 / gpt-image-2.5 (sunburst/flare variants): $30.
  - gpt-image-1.5 and chatgpt-image-latest: $32.
  - gpt-image-1: $40.
  - gpt-image-1-mini: $8.
  - Batch is half price.
  - The pricing page does not list per-image prices and points to the calculator in the image generation guide.
  - Regional processing endpoints carry a 10% uplift.
  — [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
- **FLUX 1.1 [pro]**: $0.04 per image. — [BFL docs](https://docs.bfl.ai/flux_models/flux_1_1_pro)
- **Recraft V3**: raster $0.04, vector (SVG) $0.08 per image. API units are bought in prepaid packages that cannot be refunded. — [Recraft API pricing](https://www.recraft.ai/docs/api-reference/pricing)
- **Ideogram**: no official API price list was found. Third-party trackers give $0.025–0.10 per image and disagree with each other. — [pricepertoken Ideogram](https://pricepertoken.com/ideogram-pricing); [apiscout comparison](https://apiscout.dev/guides/flux-vs-ideogram-vs-recraft-image-gen-api-2026)
- On carousels that contain AI images, the Instagram API's `is_ai_generated=true` parameter is set only on the parent carousel container. Setting it on the children causes an error. — [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)

### Inferences
- **Cost example**: one carousel with 8 slides needs 1–2 backgrounds. At ~$0.034–0.067 each, generation costs pennies per post, so cost does not decide the choice. Consistency does.
- **When to use AI**
  - Abstract or illustrated backgrounds, hero images and concept scenes.
  - Never for Turkish text, prices, product UI or the logo. Text rendering has improved but is still unreliable for Turkish diacritics.
- **Consistency**
  - Keep a fixed brand style prompt plus reference images (Gemini/OpenAI edit and reference input).
  - Recraft's vector output can be used for a brand-style icon set.
- **Pure design** (HTML gradients, shapes and typography) is the safer default for a news or product carousel. AI images can be added as an optional "visual layer".

### Gaps
- Imagen 4 prices were not shown on the fetched page.
- Per-image dollar figures for gpt-image-2 could not be extracted.
- No independent benchmark of Turkish text-rendering quality was found.

## 5. Instagram Graph API content publishing (carousel, Story, requirements, limits)

### Takeaway
Through the API, a carousel can hold **at most 10** items, even though the app allows 20 since August 2024. A Story can be published with `media_type=STORIES`, but link, poll and location stickers are not supported. Images must be JPEG, at most 8 MB, with an aspect ratio between 4:5 and 1.91:1, so **the 3:4 (1080×1440) format falls outside the API's documented range**. Publishing requires a professional account (Business or Creator), the media must be on a public URL, and the limit is 100 posts per 24 hours (one carousel counts as one post). The examples use v25.0.

### Cited Findings
- **Flow**
  1. Create a container for each child with `POST /<IG_ID>/media` (`image_url`, `is_carousel_item=true`).
  2. Create the parent with `media_type=CAROUSEL` and `children` (comma-separated container IDs).
  3. Publish with `POST /<IG_ID>/media_publish`.
  - Container statuses: `EXPIRED`, `ERROR`, `FINISHED`, `IN_PROGRESS`, `PUBLISHED`. Poll once per minute for no more than 5 minutes.
  — [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- **Carousel limit**: "Carousels are limited to 10 images, videos, or a mix", and `children` takes "up to 10 container IDs". Images are cropped based on the first image, default 1:1. — [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/); [IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)
  - The 20-item carousel is an in-app feature that rolled out in August 2024. The API docs do not mention it. — [Metricool](https://metricool.com/instagram-increases-carousel-content-limit/); [TechRadar](https://www.techradar.com/computing/instagram/instagram-will-now-let-you-post-up-to-20-photos-or-videos-in-a-gallery-your-friends-should-be-thrilled)
- **Image specs**
  - Feed images: JPEG, max 8 MB, aspect ratio 4:5 to 1.91:1, width 320–1440, sRGB.
  - Stories: JPEG, max 8 MB, 9:16 recommended (not required), sRGB.
  - MPO and JPS are not supported.
  — [IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media); [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- **3:4 in the app vs. the API**: third-party guides say the app added native 3:4 (1080×1440) photos in 2025, and that the profile grid switched to 3:4 thumbnails. These are not official sources and they disagree on details. — [Oktopost](https://www.oktopost.com/blog/instagram-grid-size-guide/); [RouteNote](https://routenote.com/blog/instagram-introduces-a-new-aspect-ratio-for-photos/)
- **Story limitations**
  - Link, poll and location stickers are not supported. Mentioning users without a sticker is supported.
  - Music tagging is available only for original audio.
  - `alt_text` and `collaborators` are not supported on Stories.
  - `user_tags` x/y coordinates are optional on Stories.
  — [IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)
- **Fields**
  - `alt_text`: added 24 March 2025, up to 1000 characters, image posts and carousel images only.
  - `collaborators`: up to 3 usernames (feed, Reels and carousel).
  - `user_tags`: x/y coordinates from 0.0 to 1.0.
  - `location_id`: a Page ID with location data, not supported on carousel items.
  - `audio_name`, `cover_url`, `share_to_feed` and `trial_params`: Reels only.
  - `branded_content_sponsor_ids` (max 2) and `is_paid_partnership`: Facebook Login only.
  — [IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media); [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- **Rate limit**
  - "100 API-published posts within a 24-hour moving period". A carousel counts as one post.
  - Usage can be checked with `GET /<IG_ID>/content_publishing_limit`.
  - The carousel section of the same page still says "50 published posts". This contradiction is in Meta's own docs.
  — [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- **Login types and permissions**
  - *Instagram API with Instagram Login*: Instagram User token, with `instagram_business_basic` and `instagram_business_content_publish`.
  - *Instagram API with Facebook Login*: Page token, with `instagram_basic`, `instagram_content_publish` and `pages_read_engagement`. If the user has a Business Manager role on the Page, `ads_management` and `ads_read` are also needed.
  - Both require Advanced or Standard Access.
  - If the connected Page requires Page Publishing Authorization (PPA), publishing is blocked until PPA is complete.
  - Resumable uploads (local file for large videos) are Facebook Login only.
  — [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- **Public URL**: "the media must be hosted on a publicly accessible server at the time of the attempt", because Meta fetches the URL with cURL. — [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- **API version**: the examples use `v25.0`, and the docs recommend the latest version. The page was updated on 30 June 2026. — [IG Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- **Deprecated**: the old "Instagram Basic Display API" was shut down on 4 Dec 2024. This comes from my own knowledge and was not verified in this session, so check it.

### Inferences
- **Recommended format**
  - Carousel: **1080×1350 (4:5)**. Every slide should be the same size, since all slides are cropped to the first one's ratio.
  - 1080×1440 (3:4) sits outside the API's documented range (0.75 < 0.8). It may be rejected or cropped, so test it with a single post before using it.
  - Story: 1080×1920.
- **For a single account you own**: "Instagram API with Instagram Login" is the simplest route, with no Facebook Page needed.
  - If the app stays in development mode and is used only by accounts with app roles (admin, developer or tester), App Review is usually not needed. This is based on Meta's general Standard Access model and was not separately verified.
- **Public URL options**
  - A temporary public URL: Cloudflare R2, S3 or GitHub raw.
  - Or an ngrok/cloudflared tunnel on the Windows machine.
  - Delete the file once the container reaches `FINISHED`.
- **Stories**: adding a link sticker requires a manual step (a mobile reminder notification). Automate the visuals only.

### Gaps
- Whether the API's carousel limit will rise to 20 is not documented.
- The official Meta changelog for 2025–2026 was not read in this session.
- The exact App Review conditions for a single-owner app were not checked.

## 6. Scheduling alternatives (Meta Business Suite, Buffer, Later, Ayrshare, Postiz)

### Takeaway
For a single account, calling the API directly is cheapest. Postiz is a free, open-source, self-hostable alternative, but Docker needs at least 4 GB of RAM, which is a problem on this machine. Ayrshare starts at $149/month. Buffer's new GraphQL API is in beta and uses a personal API key, which suits personal automation.

### Cited Findings
- **Ayrshare** (official page): Premium $149/month, Launch $299/month, Business $599/month, billed per profile. A third-party tracker lists different prices ($129/$249). — [Ayrshare pricing](https://www.ayrshare.com/pricing); [PricingSaaS](https://pricingsaas.com/companies/ayrshare)
- **Postiz**: AGPL-3.0, self-hostable. The hosted and self-hosted versions are the same. Supports Instagram. Docker needs at least 4 GB RAM (8 GB recommended). — [Postiz README](https://cdn.jsdelivr.net/gh/gitroomhq/postiz-app@main/README.md); [Postiz self-hosting docs](https://www.mintlify.com/gitroomhq/postiz-app/self-hosting/overview)
- **Buffer**
  - The old REST API has been closed to new apps since 2019.
  - The new GraphQL API (api.buffer.com) is in public beta, uses a personal API key, and does not yet support third-party OAuth.
  - It covers post creation and scheduling. Instagram first-comment support was added in February 2026.
  - Status history shows Meta-caused Instagram publishing incidents in May and July 2026.
  — [Buffer best social media APIs](https://buffer.com/resources/best-social-media-apis/); [Zernio on Buffer API](https://zernio.com/blog/buffer-api); [Pulsetic Buffer status](https://pulsetic.com/status/buffer/incidents/3969/)

### Inferences
- **Recommended**: call the API directly from Python and schedule it with Windows Task Scheduler.
  - Fallback 1: the Buffer GraphQL beta, if it supports the carousel or Story case.
  - Fallback 2: Meta Business Suite manual scheduling, used to schedule ready-made JPEGs by hand.
- **Postiz** would compete for RAM with Chromium and HyperFrames on a 4 GB machine. Run it on another server or a VPS.

### Gaps
- Later's API pricing and availability was not researched.
- Meta Business Suite has no public scheduling API, but no source was found confirming this.
- Whether Buffer's Story support works through its API was not verified.

## 7. Instagram's compression behavior and export settings

### Takeaway
Instagram has no official compression spec. Its documented inputs are a width limit of 320–1440 px and conversion of other color spaces to sRGB. Practical rule: a JPEG exactly 1080 px wide (1080×1350 or 1080×1920), in sRGB, at quality ~90, with 4:4:4 subsampling. Avoid fine, high-frequency noise and small text.

### Cited Findings
- Images must be 320–1440 px wide; anything outside is scaled. Images that are not sRGB are converted. JPEG only, max 8 MB. — [IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)
- Third-party advice:
  - Exporting with a long edge of ~1080 px avoids softening from rescaling.
  - JPEG quality around 70% is a "common practice".
  - Embed the sRGB profile.
  - These sources are low-quality mirror sites and Instagram has not confirmed any of it.
  — [example mirror article](https://erpstaging.fha.gov.ng/?p=26213)

### Inferences
- Instagram re-compresses every upload, so a quality of 95 or more only makes the file bigger. Quality 88–92 is a good balance, well under 8 MB (a typical carousel slide is around 300–900 KB).
- With 4:2:0 subsampling, red and blue text and thin lines blur. Saving with Pillow at `subsampling=0` reduces this.
- **Design rules**
  - Body text at least ~32 px.
  - Avoid very thin (hairline) fonts and dense gradient noise or grain, since they produce banding and artifacts.
  - Put a light dither on large flat gradients.
- **Story**: keep text clear of the top ~250 px and bottom ~250 px, where the UI overlays sit. This is common practice and has no official source.
- Run your own A/B test: upload the same slide as PNG→JPEG at q80, q90 and q95 to a private test account, then download and compare.

### Gaps
- No official Meta document or independent measurement of Instagram's re-compression (target bitrate or quality) was found.
