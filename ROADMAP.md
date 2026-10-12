# saas-video-automation - Proje Takip Dosyası

## 📌 Durum
- FAZ 1: Ortam Kurulumu ve Bağımlılıklar [TAMAMLANDI]
- FAZ 2: Veri Çekici (fetcher.py) ve Senaryo Motoru (script_writer.py) [TAMAMLANDI]
- FAZ 3: Ücretsiz Ses Motoru (Edge-TTS) ve Web Ekran Kaydı (Playwright) [TAMAMLANDI]
- FAZ 4: FFmpeg Otonom Video Render Motoru (video_builder.py) [TAMAMLANDI]
- FAZ 5: Affiliate Link Yapılandırması ve Yükleme Hazırlığı [TAMAMLANDI]

**Çalıştırma:** `python main.py` (Product Hunt'tan güncel araç) · `python main.py --sample` (yerleşik örnek araçlar) · `python main.py --script output/temp/script.json` (hazır senaryo; API anahtarı gerekmez)

**API anahtarı olmadan gerçek senaryo:** Claude Code oturumunda senaryo yazdırılıp `output/temp/script.json` olarak kaydedilir (`source: "claude_code"`), ardından `--script` ile çalıştırılır. 2026-10-10: Kitbar için bu yolla 24,17 sn / 2,09 MB video üretildi (toplam 124 sn).

## ✅ FAZ 1 Kayıtları (2026-10-10)
- Klasör yapısı kuruldu: `src/`, `output/temp/`, `output/final/`, `templates/`
- `requirements.txt` paketleri yüklendi (Python 3.14.3, pip 25.3) — tüm paketler import testinden geçti
  - anthropic 1.13.0, playwright 1.63.0, moviepy 2.2.1, ffmpeg-python 0.2.0 (+ edge-tts, python-dotenv, requests, pydantic)
- Playwright Chromium kuruldu (153.0.8010.12) — 1080x1920 viewport ile açılış testi başarılı
- FFmpeg sistemde mevcut: 8.0.1 (gyan.dev essentials build), PATH üzerinden erişilebilir

## ✅ FAZ 2 Kayıtları (2026-10-10)
- [x] `src/fetcher.py` oluşturuldu
  - Kaynak: Product Hunt Atom akışı (`https://www.producthunt.com/feed`, token gerektirmez)
  - Product Hunt yönlendirme linki takip edilerek gerçek site URL'si bulunur; `description` sitenin meta açıklamasından alınır (yoksa tag_line kullanılır)
  - Akış erişilemezse 3 örnek araçla (Notion, Zapier, Grammarly) yedek veri döner
  - `fetch_latest_tools(limit, use_sample)` → dict listesi; `fetch_latest_tools_json()` → JSON metni
  - Alanlar: `tool_name`, `tag_line`, `website_url`, `description` (pydantic ile doğrulanır)
  - Test: `python src/fetcher.py` — canlı akış ve yedek veri için 3'er kayıt başarıyla doğrulandı
- [x] `fetcher.py` SaaS filtresi (`classify_tool`)
  - Donanım kelimeleri (laptop, tablet, keyboard, motorized, wheels…) ad, tagline ve açıklamanın ilk 300 karakterinde aranır → ürün elenir
  - Belirsiz kelimeler yalnızca kalıp olarak aranır ("screen protector", "standing desk", "phone case") — "full screen reminders", "help desk" gibi yazılımlar elenmez
  - Yazılım sinyali (ai, saas, app, platform, api, agent, extension, macos…) yoksa ürün elenir
  - Yeterli SaaS bulunamazsa eksik kalan yerler yedek listeyle (Notion, Zapier, Grammarly) doldurulur
  - Test: canlı akışta Surface Laptop, Alexa Tablets ve Moonwalkers elendi; seçilen 3 aracın tamamı SaaS/AI
- [x] `src/script_writer.py` (Senaryo Motoru) oluşturuldu
  - Girdi: fetcher'dan gelen `Tool` nesnesi, dict veya JSON metni
  - Claude (`claude-opus-5-5`) structured outputs ile `ScriptDraft` şemasına uygun çıktı üretir: `hook`, `voiceover`, `shots` (zaman kodlu ekran kaydı / screenshot / b-roll / yazı kartı direktifleri), `caption`, `hashtags`
  - Pydantic doğrulaması: voiceover ≤ 75 kelime (~30 sn; FAZ 3'te ölçülen hız: ~2,5 kelime/sn), sahneler 0–30 sn arası sıralı ve çakışmasız, 3–10 hashtag
  - Güvenlik reddinde sunucu tarafı yedek model (`fallbacks: "default"`) devreye girer
  - Mock fallback: kimlik bilgisi yoksa, ağ/API hatasında, ret veya geçersiz çıktıda şablon senaryo döner (`source: "mock"`)
  - Dil `config.json` → `language` alanından okunur
  - Test: `python src/script_writer.py` — fetcher entegrasyonu + mock yolu geçti; geçersiz anahtarla 401 → mock fallback doğrulandı
- [ ] **AÇIK:** Gerçek Claude çıktısının testi henüz yapılmadı (API anahtarı yok; şu an hep mock senaryo üretiliyor) — `.env` dosyasına `ANTHROPIC_API_KEY` eklenince `python src/script_writer.py` tekrar çalıştırılacak

## ✅ FAZ 3 Kayıtları (2026-10-10)
- [x] `src/tts_engine.py` (Ses Motoru) oluşturuldu
  - edge-tts 7.2.8, ses: `en-US-AriaNeural` (alternatif: `en-US-ChristopherNeural`)
  - Çıktılar (`output/temp/`): `voiceover.mp3`, `voiceover.srt`, `voiceover_words.json` (kelime bazlı başlangıç/bitiş süreleri — FAZ 4 altyazıları için)
  - Süre kontrolü: tahmin 30 sn'yi aşarsa ses en fazla %15 hızlandırılır; gerçek süre ffprobe ile ölçülür, aşım varsa bir kez daha hızlı render edilir; yine aşarsa `TTSError` verilir ve aşan dosya silinir
  - Hata yakalama: boş metin, servis hataları (403 handshake vb.) için 3 deneme + üstel bekleme; yarım dosya `.part` olarak yazılır, tamamlanınca yerine konur
  - `synthesize(text)` → `{audio_path, srt_path, words_path, voice, rate, duration_sec, word_count}`
  - Test: `python src/tts_engine.py` — 50 kelime → 20,09 sn MP3 (118 KB) üretildi; boş ve aşırı uzun metin `TTSError` verdi
  - Ölçüm: 84 kelime +15% hızda bile 31 sn → `script_writer` üst sınırı 85'ten 75 kelimeye düşürüldü
- [x] `src/media_capturer.py` (Web Görsel Yakalama) oluşturuldu
  - Site telefon olarak açılır: `config.json` boyutu / 3 → 360x640 CSS viewport @3x = tam 1080x1920 piksel, mobil yerleşim (okunur yazı boyutu)
  - Temizlik: çerez "Accept/Allow/Kabul et" butonuna tıklama (iframe'ler dahil) + bilinen consent/chat/reklam widget'larını CSS ile gizleme + ekranın %30'undan büyük ya da adı cookie/modal/newsletter/interstitial içeren sabit katmanları gizleme (site menüsü/header korunur); her ekran görüntüsünden hemen önce tekrar çalışır
  - Çıktılar (`output/temp/`): `screenshot.png` (1080x1920), `fullpage.png` (sayfanın ilk 4 ekranı, 1080x7680), `scroll.mp4` (FFmpeg ile yumuşak ease-in-out kaydırma, 1080x1920, 30 fps, 8 sn, H.264)
  - Lazy-load görseller için sayfa önce adım adım kaydırılır
  - Hata yakalama: bağlantı/DNS hatası ve HTTP ≥ 400 → `CaptureError`; yavaş siteler (`load`/`networkidle` gelmezse) beklenmeden devam edilir
  - `capture_site(url, scroll_seconds=8)` → `{screenshot_path, fullpage_path, scroll_video_path, title, final_url, cookie_accept_clicked, overlays_hidden}`
  - Test: `python src/media_capturer.py` — Notion ve GitHub: görsel boyutları ve video (1080x1920 @ 30 fps, 8 sn) doğrulandı, görseller gözle kontrol edildi (temiz); erişilemeyen alan adı `CaptureError` verdi. Ek manuel test: HubSpot'ta 1 katman gizlendi, temiz
- (Senaryo → ses → görsel → video zincirinin tek komutla çalıştırılması FAZ 4'e taşındı)

## ✅ FAZ 4 Kayıtları (2026-10-10)
- [x] `src/video_builder.py` (Video Render Motoru) oluşturuldu — doğrudan FFmpeg, tek filtre grafiği ve tek encode (MoviePy kullanılmadı: kare kare Python işlemesi çok daha yavaş)
  - Zaman çizelgesi (süre seslendirmeden hesaplanır, +0,6 sn sessiz kuyruk, en fazla 30 sn):
    - 0–3 sn: `screenshot.png`, 1,12x'ten 1:1'e yavaş zoom-out + hook başlığı (pop-in, fade-out)
    - 3 sn → son: `fullpage.png` üzerinde ease-in-out kaydırma; ilk karesi girişin son karesiyle aynı olduğu için geçiş dikişsiz
    - Baştan sona: `voiceover_words.json` kelime zamanlarından 3'er kelimelik altyazılar — opak siyah kutu, beyaz büyük harf, o an söylenen kelime sarı (Segoe UI Black)
  - Çıktı: `output/final/final_video.mp4` — H.264 (high, yuv420p, CRF 20) + AAC 192k, 1080x1920, 30 fps, faststart
  - `full page` yoksa tüm video boyunca ekran görüntüsü zoom'u kullanılır; eksik girdi/font/FFmpeg hatası → `BuildError`
  - `build_video(hook, audio_path, words_path, screenshot_path, fullpage_path)` → `{video_path, duration_sec, size_mb, render_seconds, background, caption_events}`
  - Test: `python src/video_builder.py` (FAZ 3 çıktılarıyla) — 20,69 sn video, 2,25 MB, render 41 sn; codec/boyut/fps ffprobe ile doğrulandı, kareler gözle kontrol edildi
  - İyileştirmeler: yarı saydam kutu → opak (arka plan sızıyordu, kelime aralarında dikiş vardı); crossfade → dikişsiz kesme (çift görüntü oluşuyordu); ayrı scroll encode'u kaldırıldı + görseller bir kez decode edilip bellekte tekrarlanıyor (render 107 sn → 41 sn)
- [x] `main.py` — uçtan uca orkestrasyon: fetcher → script_writer → tts_engine → media_capturer → video_builder
  - Her adım `▶ [n/5] … / ✔ … done (süre) / ✖ … failed` mesajlarıyla raporlanır
  - 3 aday araç çekilir; Product Hunt URL'si gelen (gerçek sitesi çözülemeyen) araçlar elenir; site yakalanamazsa (`CaptureError`) veya ses üretilemezse (`TTSError`) sıradaki adaya geçilir; hiçbiri olmazsa çıkış kodu 1
  - Ek çıktılar: `output/temp/script.json` (senaryo), `output/final/post.json` (araç, hook, caption, hashtag'ler, video yolu — FAZ 5 yükleme için)
  - Test: `python main.py` — Kitbar (kitbar.io) için 24,02 sn, 2,06 MB video üretildi, toplam 192 sn (çekme 10 sn, senaryo 1,5 sn, ses 5 sn, yakalama 123 sn, render 52 sn); kareler gözle kontrol edildi
  - Yakalama süresinin çoğu sitenin kendi yavaşlığı (kitbar.io: ilk yanıt 21,5 sn + yükleme 21 sn); kod tarafı < 10 sn

## ✅ FAZ 5 Kayıtları (2026-10-10)
- [x] `affiliates.json` — tek yapılandırma dosyası
  - `tools.<alan adı>.url`: araç bazında affiliate linki (`www.` farkı yok sayılır); şu an yalnızca `example-saas.com` şablon kaydı var
  - `default_params`: affiliate kaydı olmayan araçlarda gerçek site URL'sine eklenen izleme parametreleri (UTM; `{slug}` → araç adı); mevcut parametreler ezilmez
  - `disclosure`: affiliate link kullanıldığında tüm caption'lara eklenen beyan (`#ad · affiliate link`)
  - `platforms`: platform başına `caption_mode` (`link_in_bio` / `link`), hashtag ve karakter sınırı — varsayılan TikTok/Instagram: "Link in bio", YouTube Shorts: doğrudan link
- [x] `src/distribution.py` — `build_affiliate_link()`, `format_caption()`, `build_post()`; uzun caption kısaltılırken link, beyan ve hashtag'ler korunur
- [x] `main.py` → `post.json` artık şunları içerir: `affiliate_link`, `affiliate_link_source`, `is_affiliate`, `bio_link`, `platforms.{tiktok,instagram,youtube_shorts}.caption` (kopyala-yapıştır hazır), `youtube_shorts.title`
- Test: `python src/distribution.py` (UTM yolu, affiliate + beyan yolu, parametre korunumu, kısaltma) geçti; `python main.py --script output/temp/script.json` → Kitbar videosu + post.json (119 sn)

## ✅ Kalite güncellemesi (2026-10-10)
- **Akış:** adım sırası artık 1) araç çekme → 2) site kontrolü + yakalama → 3) senaryo → 4) ses → 5) render. Site yanıtsızsa senaryo (Claude çağrısı) ve ses hiç üretilmeden sıradaki araca geçilir
  - `precheck()`: tarayıcı açmadan ≤15 sn HTTP kontrolü (bağlantı hatası / zaman aşımı / 5xx → `CaptureError`; bot korumalı 403 geçer)
  - Boş/tek renk ekran görüntüsü → `CaptureError`
- **Görsel:** `src/scene_composer.py` (Pillow) + yeni `video_builder.py`
  - Sitenin 4 bölümüne kadar (tam sayfadan kesilir, boş bölümler atlanır), her biri tarayıcı mockup'ı içinde: trafik ışıkları, alan adlı URL çubuğu, yuvarlatılmış köşeler, gölge; arkada aynı bölümün bulanık + karartılmış kopyası
  - Her sahnede farklı Ken Burns hareketi (zoom in → pan down → zoom out → pan up, ease-in-out, %6), sahneler arası değişen geçişler (smoothup, slideleft, circleopen, smoothleft, fade)
  - Kapanış kartı: logo (header'daki logo elemanı, yoksa apple-touch-icon / en büyük favicon), araç adı, alan adı; açık renkli logoda kart otomatik koyu
  - Hook ilk sahnede, kelime kelime altyazılar baştan sona
- **İsim netliği:** senaryo talimatına kural eklendi — aracın adının geçtiği ilk cümlede ne tür ürün olduğu ve platformu söylenir (ör. "Buffer, a free macOS clipboard manager"); mock senaryo da adı ve tanımı aynı cümlede verir
- Test: `python main.py` → KernelAI (kernelai.app); açılış cümlesi: "KernelAI is a private, offline AI app for iOS and Android."; 28,97 sn, 5,8 MB, 4 bölüm + logolu kapanış; kareler gözle kontrol edildi
  - İlk denemede pan hareketi mockup'ın üst çubuğunu kadraj dışına itiyordu → mockup %84 → %80 genişlik, hareket %8 → %6; logo bulunamıyordu → site ikonu yedeği eklendi
  - Render süresi ~40–60 sn'den ~125 sn'ye çıktı (2x ölçekte Ken Burns); toplam akış ~6 dk

## 📌 Bilinen sınırlar / sonraki adımlar
- Gerçek affiliate ID'leri henüz girilmedi — şu an tüm linkler UTM'li site linki (komisyon getirmez); programa katıldıkça `affiliates.json` → `tools` doldurulmalı
- ~~Otomatik senaryo için API anahtarı yok~~ → `claude -p` entegrasyonu eklendi (aşağıda)

## ✅ Ek: `claude -p` ile otomatik senaryo (2026-10-10)
- `script_writer.py` senaryo kaynağı sırası: 1) Anthropic API (`.env` → `ANTHROPIC_API_KEY`) → 2) yerel Claude Code CLI `claude -p` → 3) mock
- `claude -p --output-format json --json-schema <ScriptDraft şeması> --system-prompt <senaryo talimatı> --tools "" --no-session-persistence`
  - API anahtarı gerekmez; Claude Code'un giriş yaptığı hesabı ve planının kullanım limitlerini kullanır
  - Araçlar kapalı (`--tools ""`): CLI yalnızca yanıt üretir, dosyalara dokunamaz
  - Çıktı aynı Pydantic kurallarıyla doğrulanır; kurala uymayan taslakta hatalar geri bildirilip 1 kez yeniden denenir; yine olmazsa mock
  - `source: "claude_code"`, `model`: CLI'ın kullandığı model
  - Kapatmak için: `SCRIPT_WRITER_NO_CLI=1`
- Not: çağrı başına ~30–40 sn (Claude Code açılış süresi dahil)
- Düzeltme: `.env`'deki şablon anahtar ortamdan `claude` alt sürecine geçip "Invalid API key" verdiriyordu → CLI çağrılırken `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` ortamdan çıkarılıyor
- Test: `python main.py` (seçeneksiz) → Maildun for Mac için `claude -p` (claude-opus-5-5) senaryosu yazdı (40 sn), 30,0 sn / 2,8 MB video, toplam 185 sn
- Ayar: 64 kelime normal hızda 32 sn sürdü (+%7 hızla sığdı) → Claude'a verilen hedef 60–70'ten 50–62 kelimeye indirildi (75 kelime üst sınırı aynı)
- Platformlara yükleme otomatik değil: video + `post.json` hazırlanır, yükleme elle yapılır

## ⚠️ Notlar
- Pop-up temizliği sezgiseldir: geç çıkan tam ekran reklamlar (ör. BBC'de bir kez görüldü) her zaman yakalanamayabilir; SaaS açılış sayfalarında sorun gözlenmedi.
- edge-tts, Microsoft'un resmi olmayan ücretsiz servisini kullanır; zaman zaman 403 handshake hatası verebilir (yeniden deneme bunu çözüyor) ve ileride kesintiye uğrayabilir.
- Python script klasörü PATH'te değil (`%APPDATA%\Python\Python314\Scripts`); `playwright` CLI'ı `python -m playwright` ile çalıştırılmalı.
