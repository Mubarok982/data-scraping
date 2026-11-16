import os
import sys
import datetime
import requests
import pandas as pd
import time
import warnings
from duckduckgo_search import DDGS
from apify_client import ApifyClient
from dotenv import load_dotenv
import threading
import random

warnings.filterwarnings("ignore", category=RuntimeWarning)
load_dotenv()

NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
DIFFBOT_TOKEN = os.getenv('DIFFBOT_TOKEN')
APIFY_TOKEN = os.getenv('APIFY_TOKEN')

APIFY_ACTORS = {
    "instagram": "apify/instagram-scraper", 
    "twitter": "apify/twitter-scraper-lite",
    "facebook": "apify/facebook-pages-scraper",
    "tiktok": "clockworks/tiktok-scraper" 
}

def simpan_csv(df, tool_name, platform, tipe_pencarian, query):
    if df.empty:
        return
        
    if 'Teks' in df.columns:
        df['Teks'] = df['Teks'].astype(str).str.replace('\n', ' ', regex=False)
    if 'Isi_Berita' in df.columns:
        df['Isi_Berita'] = df['Isi_Berita'].astype(str).str.replace('\n', ' ', regex=False)
        
    query_aman = query.replace(" ", "_").lower()
    
    output_dir = f"output_csv/{platform}" if platform else "output_csv/berita"
    os.makedirs(output_dir, exist_ok=True)
    
    # PERUBAHAN: Nama file distandarkan agar append bisa dilakukan (tidak menggunakan timestamp di nama file)
    nama_file = f"{output_dir}/{tool_name}_{platform}_{tipe_pencarian}_{query_aman}_master.csv"
    
    # PERUBAHAN: Mode append. Jika file sudah ada, tambahkan barisnya tanpa header.
    if os.path.isfile(nama_file):
        df.to_csv(nama_file, mode='a', header=False, index=False)
        print(f"[{tool_name.upper()} UPDATE] Menambahkan {len(df)} baris ke {nama_file}")
    else:
        df.to_csv(nama_file, index=False)
        print(f"[{tool_name.upper()} SUKSES] Membuat {nama_file} baru dengan {len(df)} baris")


def jalankan_newsdata(tipe_pencarian, query):
    print(f"[NEWSDATA] Memulai siklus pencarian berita '{query}'...")
    if not NEWSDATA_API_KEY:
        print("[NEWSDATA ERROR] API Key tidak ditemukan.")
        return

    # Turunkan load per request ke 50. Loop besar yang mengatur pengulangan ada di fungsi jalankan_scheduler
    target_jumlah = 50 
    hasil_berita = []
    next_page = None
    
    while len(hasil_berita) < target_jumlah:
        url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q={query}&language=id"
        if next_page:
            url += f"&page={next_page}"
            
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if not results:
                    break
                    
                for artikel in results:
                    hasil_berita.append({
                        "Tool": "NewsData",
                        "Platform": "portal_berita",
                        "Tanggal": artikel.get('pubDate', ''),
                        "Sumber": artikel.get('source_id', 'Unknown'),
                        "Judul": artikel.get('title', ''),
                        "Penulis": ', '.join(artikel.get('creator', [])) if isinstance(artikel.get('creator', []), list) else 'Tidak diketahui',
                        "Isi_Berita": artikel.get('content', artikel.get('description', '')),
                        "Link": artikel.get('link', '')
                    })
                    if len(hasil_berita) >= target_jumlah:
                        break 
                
                next_page = data.get('nextPage')
                if not next_page:
                    break
                time.sleep(2) 
            elif response.status_code == 429:
                print("[NEWSDATA] Rate limit tersentuh. Jeda perlindungan aktif.")
                break # Jangan menekan server. Berhenti dan biarkan scheduler yang mengulang nanti.
            else:
                break
        except Exception as e:
            print(f"[NEWSDATA ERROR] {e}")
            break

    if hasil_berita:
        df = pd.DataFrame(hasil_berita)
        simpan_csv(df, "newsdata", "berita", tipe_pencarian, query)


def jalankan_diffbot_sosmed(tipe_pencarian, query, platform):
    print(f"[DIFFBOT] Memulai siklus pencarian '{query}' di {platform}...")
    if not DIFFBOT_TOKEN:
        print(f"[DIFFBOT ERROR] Token tidak ditemukan untuk {platform}.")
        return

    daftar_url = []
    domain = f"{platform}.com"
    
    with DDGS() as ddgs:
        dork_query = f"site:{domain} {query}"
        try:
            # Kembali ke max 50 untuk menghindari pemblokiran DuckDuckGo
            results = ddgs.text(dork_query, region='id-id', max_results=50) 
            if results:
                for r in results:
                    daftar_url.append(r['href'])
        except Exception as e:
            print(f"[DIFFBOT ERROR] DDGS gagal di {platform}: {e}")
            
    if not daftar_url:
        return

    hasil_sosmed = []
    for url_target in daftar_url:
        diffbot_url = f"https://api.diffbot.com/v3/analyze?token={DIFFBOT_TOKEN}&url={url_target}"
        try:
            response = requests.get(diffbot_url, timeout=30)
            if response.status_code == 429:
                print(f"[DIFFBOT] Limit API Diffbot tercapai. Melompat ke URL berikutnya...")
                time.sleep(10)
                continue
                
            if response.status_code == 200:
                data = response.json()
                if 'objects' in data and len(data['objects']) > 0:
                    obj = data['objects'][0]
                    tipe_halaman = obj.get('type', '')
                    
                    if tipe_halaman == 'discussion' and 'posts' in obj and len(obj['posts']) > 0:
                        post_utama = obj['posts'][0]
                        hasil_sosmed.append({
                            "Tool": "Diffbot",
                            "Platform": platform,
                            "Tanggal": post_utama.get('date', ''),
                            "Username": post_utama.get('author', ''),
                            "Link": url_target,
                            "Teks": post_utama.get('text', ''),
                            "Likes": post_utama.get('votes', 0),
                            "Comments": 0, "Shares": 0
                        })
                    else:
                        hasil_sosmed.append({
                            "Tool": "Diffbot",
                            "Platform": platform,
                            "Tanggal": obj.get('date', ''),
                            "Username": obj.get('author', ''),
                            "Link": url_target,
                            "Teks": obj.get('text', obj.get('title', '')),
                            "Likes": 0, "Comments": 0, "Shares": 0
                        })
        except Exception as e:
            pass
        time.sleep(5) # Jeda antar request

    if hasil_sosmed:
        df = pd.DataFrame(hasil_sosmed)
        simpan_csv(df, "diffbot", platform, tipe_pencarian, query)


def jalankan_apify_sosmed(tipe_pencarian, query, platform):
    print(f"[APIFY] Memulai siklus ekstraksi '{query}' di {platform}...")
    if not APIFY_TOKEN:
        return

    try:
        client = ApifyClient(APIFY_TOKEN)
        actor_id = APIFY_ACTORS.get(platform)
        
        if not actor_id:
            return
            
        # Target mikrodosis (limit 20-50 per jalan).
        if platform == "tiktok":
            run_input = {"searchQueries": [query], "resultsPerPage": 20, "maxItems": 20}
        elif platform == "instagram":
            run_input = {"search": query, "searchType": "hashtag", "resultsLimit": 20}
        elif platform == "facebook":
            run_input = {"startUrls": [{"url": f"https://www.facebook.com/search/top/?q={query}"}], "resultsLimit": 20}
        else: # Twitter
            run_input = {"searchTerms": [query], "maxItems": 20}

        run = client.actor(actor_id).call(run_input=run_input)
        
        dataset_id = None
        if isinstance(run, dict):
            dataset_id = run.get("defaultDatasetId", run.get("default_dataset_id"))
        else:
            dataset_id = getattr(run, "defaultDatasetId", getattr(run, "default_dataset_id", None))

        if not dataset_id:
             dataset_id = run.get("id") if isinstance(run, dict) else getattr(run, "id", None)

        if not dataset_id:
            return
            
        dataset_items = client.dataset(dataset_id).list_items().items
        
        if not dataset_items:
            print(f"[APIFY WARNING] Data kosong dari {platform}.")
            return
            
        hasil_apify = []
        for item in dataset_items:
            teks = item.get('text', item.get('fullText', item.get('caption', '')))
            tanggal = item.get('createdAt', item.get('timestamp', item.get('date', '')))
            username = item.get('authorMeta', {}).get('name', item.get('ownerUsername', item.get('username', '')))
            link = item.get('url', item.get('postUrl', ''))
            
            likes = item.get('likesCount', item.get('diggCount', item.get('reactionLikeCount', 0)))
            comments = item.get('commentsCount', item.get('commentCount', 0))
            shares = item.get('sharesCount', item.get('shareCount', 0))

            hasil_apify.append({
                "Tool": "Apify",
                "Platform": platform,
                "Tanggal": tanggal,
                "Username": username,
                "Link": link,
                "Teks": teks,
                "Likes": likes,
                "Comments": comments,
                "Shares": shares
            })
            
        if hasil_apify:
            df = pd.DataFrame(hasil_apify)
            simpan_csv(df, "apify", platform, tipe_pencarian, query)
            
    except Exception as e:
        print(f"[APIFY ERROR] Gagal scrape di {platform}: {e}")

def cari_trending_indonesia():
    try:
        from pytrends.request import TrendReq
        pytrend = TrendReq(hl='id-ID', tz=420)
        trending_searches = pytrend.trending_searches(pn='indonesia')
        top_trend = trending_searches.iloc[0, 0] 
        print(f"[TRENDING] Topik trending saat ini: '{top_trend}'")
        return top_trend
    except Exception as e:
        print(f"[ERROR] Gagal mengambil data trending: {e}")
        return "teknologi"


def jalankan_scheduler(tipe_pencarian, query):
    siklus = 1
    maksimal_siklus = 24  # Berjalan 24 kali (misal: sepanjang hari)
    
    while siklus <= maksimal_siklus:
        print(f"\n==============================================")
        print(f"MEMULAI SIKLUS KE-{siklus} DARI {maksimal_siklus} UNTUK '{query}'")
        print(f"Waktu: {datetime.datetime.now().strftime('%H:%M:%S')}")
        print(f"==============================================\n")
        
        threads = []
        
        # Eksekusi NewsData
        t_news = threading.Thread(target=jalankan_newsdata, args=(tipe_pencarian, query))
        threads.append(t_news)
        
        platforms_sosmed = ["twitter", "facebook", "instagram", "tiktok"]
        
        # Eksekusi Diffbot
        for plat in platforms_sosmed:
            t_diff = threading.Thread(target=jalankan_diffbot_sosmed, args=(tipe_pencarian, query, plat))
            threads.append(t_diff)
            
        # Eksekusi Apify
        for plat in platforms_sosmed:
            t_apify = threading.Thread(target=jalankan_apify_sosmed, args=(tipe_pencarian, query, plat))
            threads.append(t_apify)
            
        for t in threads:
            t.start()
            
        for t in threads:
            t.join()
            
        print(f"\n[SISTEM] Siklus ke-{siklus} selesai.")
        
        if siklus < maksimal_siklus:
            jeda_menit = random.randint(15, 30) # Menggunakan delay acak (15-30 menit) agar tidak terlihat seperti bot terjadwal
            print(f"[SISTEM] Tidur selama {jeda_menit} menit untuk menghindari pemblokiran Anti-Bot...")
            time.sleep(jeda_menit * 60)
            
        siklus += 1
        
    print("\n[SISTEM] TARGET SIKLUS TERCAPAI. SELURUH PIPELINE SELESAI!")


def main():
    print("=== MULTI-THREAD DATA SCRAPING PIPELINE (AUTO-APPEND) ===")
    print("Pilih tipe request:\n1. Keyword\n2. Topik\n3. Trending")
    
    pilihan = input("Masukkan angka pilihan (1/2/3): ")
    tipe_dict = {"1": "keyword", "2": "topik", "3": "trending"}
    tipe_pencarian = tipe_dict.get(pilihan, "keyword")
    
    query = ""
    if tipe_pencarian == "trending":
        print("\nSedang mengambil data trending...")
        query = cari_trending_indonesia()
    else:
        query = input(f"Masukkan {tipe_pencarian} pencarian: ")
        
    print(f"\nMemulai Auto-Scheduler untuk: '{query}'\n")
    
    # Alihkan eksekusi utama ke scheduler
    jalankan_scheduler(tipe_pencarian, query)


if __name__ == '__main__':
    main()