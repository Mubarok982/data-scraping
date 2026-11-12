---
title: DDC Scraper Portal
emoji: 🧩
colorFrom: purple
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
---

# 🧩 DDC Data Warehouse — API Scraper Service & Bank Data Portal

Layanan **REST API** dan **Web Dashboard Portal** terpusat untuk kebutuhan ekstraksi data (*scraping*) otomatis serta pengelolaan **Bank Data (Data Warehouse)** pada proyek **DDC**.

Sistem ini mencakup penyelesaian 3 modul utama **Data Warehouse**:
1. **Bank Data Service (Data Warehouse)** — Katalog dan kueri JSON/CSV dari seluruh arsip hasil *scraping* historis maupun *real-time*.
2. **API Scraper Service - Keyword & Trending** — Ekstraksi kueri terkait (*Related Queries*) dan topik naik daun (*Rising Queries*).
3. **API Scraper Service - Berita** — Ekstraksi artikel berita multi-engine (**Newsdata.io**, **Diffbot**, **Bright Data**, dan **Kombine**).
4. **API Scraper Service - Social Media** — Ekstraksi data terpisah sesuai skema masing-masing platform (**Facebook**, **Instagram**, **TikTok**, **Twitter/X**, dan **LinkedIn**).

---

## 🌐 Cara Akses Cepat (Untuk PM, QA, & Frontend/Backend)

| Target Pengguna | Jalur Akses | URL / Path | Fungsi Utama |
| :--- | :--- | :--- | :--- |
| **Project Manager (PM) / QA** | **Web Dashboard UI** | `/` *(Halaman Utama)* | Memilih tab modul, melihat tabel Bank Data, menjalankan *live scraping* tanpa koding, dan mengunduh file `.csv`. |
| **Backend / Data Engineer** | **Swagger UI (OpenAPI)** | `/docs` | Dokumentasi interaktif seluruh *endpoint* REST API beserta fitur uji coba langsung (*Try it out*). |
| **Sistem Eksternal** | **Katalog Bank Data JSON** | `/api/v1/bank-data/catalog` | Mengambil daftar seluruh file `.csv` hasil *scraping* yang tersimpan di server. |

---

## 🏦 0. Modul Bank Data (Data Warehouse API)

Digunakan untuk mengakses seluruh kumpulan data hasil *scraping* yang sudah tersimpan di server tanpa perlu melakukan *scraping* ulang.

### A. Lihat Katalog Semua File CSV
* **Endpoint:** `GET /api/v1/bank-data/catalog`
* **Query Parameters:**
  * `category`: `semua` | `berita` | `facebook` | `instagram` | `tiktok` | `twitter` | `linkedin` | `keyword_trending`
  * `tool`: `semua` | `apify` | `diffbot` | `newsdata` | `brightdata` | `kombine`

**Contoh Request:**
```bash
curl -X GET "[https://NAMA-SPACE-ANDA.hf.space/api/v1/bank-data/catalog?category=semua&tool=semua](https://NAMA-SPACE-ANDA.hf.space/api/v1/bank-data/catalog?category=semua&tool=semua)"
```

### B. Ambil Isi Data (JSON) & Filter Kata Kunci dari Bank Data
* **Endpoint:** `GET /api/v1/bank-data/records`
* **Query Parameters:**
  * `category`: Kategori platform (`berita`, `facebook`, `instagram`, `tiktok`, `twitter`, `linkedin`, `keyword_trending`, `semua`)
  * `tool`: Filter *engine* (`apify`, `diffbot`, `newsdata`, `brightdata`, `kombine`, `semua`)
  * `search_query`: Kata kunci pencarian di dalam baris tabel *(opsional, contoh: `prabowo`, `mbg`, `teknologi`)*
  * `limit`: Jumlah maksimum baris yang dikembalikan *(default: `200`, maks: `5000`)*

**Contoh Request:**
```bash
curl -X GET "[https://NAMA-SPACE-ANDA.hf.space/api/v1/bank-data/records?category=berita&search_query=teknologi&limit=50](https://NAMA-SPACE-ANDA.hf.space/api/v1/bank-data/records?category=berita&search_query=teknologi&limit=50)"
```

### C. Download File CSV Spesifik dari Bank Data
* **Endpoint:** `GET /api/v1/download?path={filepath}`

---

## 🔍 1. Task: Build API Scraper Service - Keyword & Trending

Menyediakan 2 *endpoint* terpisah untuk mencari kata kunci terkait dan tren yang sedang naik.

### A. Keyword Search (Related Queries)
* **Endpoint:** `POST /api/v1/keyword/search`
* **Output Kolom Tabel:** `Query`, `Values`, `formattedvalue`, `link`
* **Contoh Payload JSON:**
```json
{
  "keyword": "karhutla",
  "geo": "ID",
  "max_results": 15
}
```

### B. Trending Topics (Rising Queries)
* **Endpoint:** `POST /api/v1/keyword/trending`
* **Output Kolom Tabel:** `Query`, `Values`, `formattedvalue`, `kategori`, `waktu_scrape`, `link`
* **Contoh Payload JSON:**
```json
{
  "kategori": "teknologi",
  "geo": "ID",
  "max_results": 15
}
```

---

## 📰 2. Task: Build API Scraper Service - Berita

Setiap *engine* berita dipisahkan agar menghasilkan skema tabel yang presisi sesuai karakteristik masing-masing *tool*:

| Endpoint | Engine | Struktur Kolom Output | Karakteristik Utama |
| :--- | :--- | :--- | :--- |
| `POST /api/v1/berita/newsdata` | **Newsdata.io** | `tool`, `platform`, `tanggal`, `sumber`, `judul`, `penulis`, `isi_berita`, `link` | Sangat cepat & bebas blokir bot (kuota ~200 req/hari). |
| `POST /api/v1/berita/diffbot` | **Diffbot AI** | `Tanggal`, `Sumber`, `Judul`, `Penulis berita`, `isi_berita`, `sentimen_diffbot`, `link` | Mengekstrak isi berita secara penuh disertai skor analisis sentimen AI. |
| `POST /api/v1/berita/brightdata` | **Bright Data** | `Tool`, `Platform`, `Tanggal`, `Penulis`, `Link`, `Judul`, `Isi_Berita`, `Likes`, `Comments`, `Shares` | Dilengkapi *Web Unlocker* untuk menembus proteksi anti-bot portal berita. |
| `POST /api/v1/berita/kombine` | **Newsdata + Diffbot** | `tool`, `platform`, `tanggal`, `sumber`, `judul`, `penulis`, `isi_berita`, `sentimen_diffbot`, `link` | **Rekomendasi Utama:** Mencari daftar berita cepat via Newsdata lalu menambal `isi_berita` penuh secara otomatis via Diffbot. |

**Contoh Payload JSON (Berlaku untuk ke-4 Endpoint Berita):**
```json
{
  "keyword_or_url": "prabowo",
  "max_results": 10
}
```

---

## 📱 3. Task: Build API Scraper Service - Social Media (Terpisah per Platform)

Karena setiap platform media sosial memiliki struktur metrik dan metadata yang berbeda, layanan ini dibagi menjadi **5 endpoint spesifik**:

### A. Facebook Scraper
* **Endpoint:** `POST /api/v1/sosmed/facebook`
* **Pilihan Skema Output:**
  * `mode_apify: "full_39_kolom"` (Apify): Menghasilkan 39 kolom lengkap (`facebookuel`, `postid`, `pagename`, `url`, `time`, `timestamp`, `user`, `collaborators`, `text`, `link`, `preview title`, `preview Description`, `preview Source`, `preview Target`, `Likes`, `shares`, `in`, `top Reactions Count`, `media`, `feedback id`, `paid partnerships`, `top level url`, `facebook id`, `page AD library`, `input url`, `text References`, `is_Video`, `video Post View Count`, `live viewer count`, `reaction like count`, `comments`, `top comments`, `reactions haha count`, `reactions sad counts`, `reaction care counts`, `reaction wow count`, `views count`, `reaction angry count`, `reaction love count`).
  * `mode_apify: "bersih"` / `engine: "diffbot"`: Menghasilkan 9 kolom standar (`tool`, `platform`, `tanggal`, `username`, `link`, `teks`, `like`, `komen`, `share`).
* **Contoh Payload JSON:**
```json
{
  "keyword_or_url": "[https://www.facebook.com/kompascom](https://www.facebook.com/kompascom)",
  "engine": "apify",
  "mode_apify": "bersih",
  "max_results": 10
}
```

### B. Instagram Scraper
* **Endpoint:** `POST /api/v1/sosmed/instagram`
* **Pilihan Skema Output:**
  * `mode_apify: "full_29_kolom"` (Apify): Menghasilkan 29 kolom lengkap (`input url`, `id`, `type`, `shortcode`, `caption`, `hashtags`, `mentions`, `url`, `comments count`, `first comment`, `latest comment`, `dimension width`, `dimension height`, `display url`, `images`, `likes count`, `fb likes count`, `timestamp`, `child post`, `location name`, `location id`, `owner full name`, `ownerid`, `productType`, `paid partnerships`, `isPinned`, `musicinfo`, `tagged Users`, `coauthorProducers`).
  * `mode_apify: "bersih"` / `engine: "diffbot"`: Menghasilkan 9 kolom standar (`Tool`, `Platform`, `Tanggal`, `Username`, `Link`, `Teks`, `Likes`, `Komen`, `Share`).
* **Contoh Payload JSON:**
```json
{
  "keyword_or_hashtag": "kebakaranhutan",
  "engine": "apify",
  "mode_apify": "bersih",
  "max_results": 10
}
```

### C. TikTok Scraper
* **Endpoint:** `POST /api/v1/sosmed/tiktok`
* **Skema Output:**
  * `engine: "apify"` (7 kolom): `tanggal`, `username`, `link`, `teks`, `likes`, `comment`, `shares`
  * `engine: "diffbot"` (9 kolom): `tool`, `platform`, `tanggal`, `username`, `link`, `teks`, `likes`, `komen`, `share`
* **Contoh Payload JSON:**
```json
{
  "keyword_or_hashtag": "karhutla",
  "engine": "apify",
  "max_results": 10
}
```

### D. Twitter / X Scraper
* **Endpoint:** `POST /api/v1/sosmed/twitter`
* **Skema Output:**
  * `engine: "apify"` (1 kolom): `teks`
  * `engine: "diffbot"` (9 kolom): `Tool`, `Platform`, `Tanggal`, `Username`, `Link`, `Teks`, `Likes`, `Komen`, `Share`
* **Contoh Payload JSON:**
```json
{
  "keyword": "prabowo",
  "engine": "apify",
  "max_results": 10
}
```

### E. LinkedIn Profile Scraper (Hybrid Harvester + Bright Data Datasets v3)
* **Endpoint:** `POST /api/v1/sosmed/linkedin`
* **Skema Output (8 Kolom Profesional):**
  `Nama`, `Pekerjaan_Saat_Ini`, `Tempat_Kerja`, `Pendidikan`, `Skill`, `Lokasi`, `Koneksi`, `Link_Profil`
* **Contoh Payload JSON:**
```json
{
  "keyword": "Backend Developer",
  "region_indonesia": true,
  "max_results": 5
}
```

---

## ⚙️ Konfigurasi Environment Variables (Secrets)

Pastikan variabel berikut sudah diatur pada file `.env` (untuk penggunaan lokal) atau pada menu **Settings -> Variables and secrets** di Hugging Face Spaces:

```env
NEWSDATA_API_KEY=your_newsdata_api_key
DIFFBOT_TOKEN=your_diffbot_token
APIFY_TOKEN=your_apify_token
BRIGHTDATA_TOKEN=your_brightdata_token
LINKEDIN_COLLECTOR_ID=gd_l1viktl72bvl7bjuj0
```

---

## 🚀 Cara Menjalankan di Lokal (Ubuntu / Linux)

```bash
# 1. Instal dependensi
pip install -r requirements.txt

# 2. Jalankan server aplikasi
python app.py
```
* **Web Dashboard UI:** `http://localhost:7860/`
* **Swagger API Docs:** `http://localhost:7860/docs`