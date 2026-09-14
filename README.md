# POOPY NANO 3 — Sütlaç logbook

Tuya kumluğunun olaylarını toplar, ziyaret/temizlik/tartım türetir, telefondan
açılan bir web arayüzünde gösterir. Mac'e bağımlı değil: veriyi GitHub Actions
Tuya Cloud'dan çekiyor, arayüzü Cloudflare Pages servis ediyor.

## Nasıl çalışıyor

    GitHub Actions (15 dk'da bir)  ->  poll.py  ->  events.jsonl + api/data.json
                                                          |
                                                    git push
                                                          |
                                            Cloudflare Pages  ->  telefon

`poll.py` Tuya Cloud'un ~4 günlük kayan penceresini okuyup `events.jsonl`'e
birleştirir. Pencere 4 gün, cron 15 dakika — Actions birkaç çalıştırmayı atlasa
bile veri kaybı olmaz.

## Kurulum

1. **Repo:** bu klasörü GitHub'a push et. `config.json` / `cloud.json`
   gitignore'da, gitmeyecek.
2. **Actions secrets** (Settings → Secrets → Actions), `cloud.json` ve
   `config.json` içindeki değerler:
   `TUYA_REGION`, `TUYA_KEY`, `TUYA_SECRET`, `TUYA_DEVICE`
3. **Cloudflare Pages:** Workers & Pages → Create → Pages → repoyu bağla.
   Build command boş, output directory `/`. URL: `<proje>.pages.dev`
4. **Telefon:** URL'yi aç → Paylaş → Ana Ekrana Ekle. Tam ekran açılır, offline'da
   son veriyi gösterir.

Actions cron'u ilk push'tan sonra kendi başlar; `workflow_dispatch` ile elle de
tetiklenir.

## Yerel çalıştırma

    ./venv/bin/python poll.py            # bulutu çek, api/data.json üret
    ./venv/bin/python logbook.py         # http://localhost:8420
    ./venv/bin/python watch.py           # OPSİYONEL, LAN dinleyici

`watch.py` sadece bulutta olmayan iki DP için (`101 cleaning`, `124 clean_count`).
Mac'te açık olursa `events.jsonl`'e onları da yazar; olmazsa arayüzde temizlik
sayacı eskide kalır, gerisi çalışır.

## Dosyalar

| dosya | ne |
|---|---|
| `poll.py` | Tuya Cloud → `events.jsonl` → `api/data.json` |
| `logbook.py` | türetme kuralları + olay deposu + yerel önizleme sunucusu |
| `watch.py` | opsiyonel LAN dinleyici (üretici DP'leri için) |
| `events.jsonl` | ham olay logu, tek veri kaynağı |
| `api/data.json` | arayüzün okuduğu türetilmiş çıktı |
| `index.html`, `sw.js`, `manifest.json` | arayüz (PWA) |
| `cutout.py` | `sutlac.jpeg` → fonu şeffaf `sutlac.png` + `favicon.png`; fotoğraf değişirse tekrar çalıştır |
| `config.json`, `cloud.json` | cihaz ve bulut anahtarları — gitignore'da |

## Türetme kuralları

| ne | nereden |
|---|---|
| ziyaret | `7` (excretion_times_day) her arttığında |
| **birleşik ziyaret** | `MERGE_GAP` (120 sn) içindeki ardışık girişler tek ziyaret; süreler toplanır, giriş sayısı `parts` alanında |
| kalma süresi | o andaki `8` (excretion_time_day) |
| tartım | o andaki `6` (cat_weight) |
| temizlik | `24` (status) `clean`'e girip çıktığında |

Arayüzdeki her sayı **birleşik ziyaret** üzerinden. Sütlaç girip çıkıp giriyor;
cihazın kendi sayacı bunları ayrı sayıyor (bugün 4), birleştirince gerçek ziyaret
sayısı çıkıyor (2). Süre grafiğinde **içi boş halka = girdili çıktılı ziyaret**.

## Bilinen sınırlar

- **Bulut sadece 5 DP logluyor** (6/7/8/22/24). Türetme için hepsi yeterli;
  `101`/`124` yalnızca `watch.py` açıkken gelir.
- **Ağırlık gürültülü.** Aynı kedi için 1.0–3.2 kg okumalar geliyor. Arayüz
  medyan gösteriyor. Kalibrasyon: `logbook.py` içindeki `W_SCALE` / `W_OFFSET`.
- **Kum ağırlığı yok.** Cihazda kumu tartan DP yok; gram ölçümü için harici
  kantar (ESP32 + HX711) gerekir.
- **Site açık.** URL'yi bilen görür. Kapatmak istersen Cloudflare Access
  (Zero Trust free tier) ile iki e-postaya kilitlenir.
