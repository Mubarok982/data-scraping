import os
import datetime
import requests
import pandas as pd
import time
import random
import warnings
import threading
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=RuntimeWarning)
load_dotenv()

# Kredensial API dari file .env
BRIGHTDATA_TOKEN = os.getenv('BRIGHTDATA_TOKEN')

# Konfigurasi ID (tanpa tulisan &notify di dalam value-nya karena sudah ditangani di URL)
BRIGHTDATA_COLLECTORS = {
    "instagram": "gd_ltppn085pokosxh13", 
    "facebook": "gd_lkay758p1eanlolqw8",
    "tiktok": "gd_lkf2st302ap89utw5k",
    "berita": "gd_mcswdt6z2elth3zqr2" 
    # Twitter dihapus
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
    
    nama_file = f"{output_dir}/{tool_name}_{platform}_{tipe_pencarian}_{query_aman}_master.csv"
    
    if os.path.isfile(nama_file):
        df.to_csv(nama_file, mode='a', header=False, index=False)
        print(f"[{tool_name.upper()} UPDATE] Menambahkan {len(df)} baris ke {nama_file}")
    else:
        df.to_csv(nama_file, index=False)
        print(f"[{tool_name.upper()} SUKSES] Membuat {nama_file} baru dengan {len(df)} baris")


def jalankan_brightdata(tipe_pencarian, query, platform):
    print(f"[BRIGHTDATA] Memulai siklus ekstraksi '{query}' di {platform}...")
    if not BRIGHTDATA_TOKEN:
        print(f"[BRIGHTDATA ERROR] Token tidak ditemukan untuk {platform}.")
        return
        
    collector_id = BRIGHTDATA_COLLECTORS.get(platform)
    if not collector_id or collector_id.startswith("c_id_"):
        print(f"[BRIGHTDATA WARNING] ID Collector belum dikonfigurasi untuk {platform}.")
        return

    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Format query aman agar bisa diubah menjadi URL tanpa validasi error
    query_aman = query.replace(" ", "")
    
    if platform == "berita":
        payload = [{"keyword": query, "num_results": 50}]
    elif platform in ["tiktok", "instagram"]:
        payload = [{"hashtag": query_aman, "limit": 50}]
    else: 
        payload = [{"search": query, "limit": 50}]

    try:
        if collector_id.startswith("gd_"):
            trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={collector_id}&include_errors=true&notify=false"
        else:
            trigger_url = f"https://api.brightdata.com/dca/trigger?collector={collector_id}"
            
        trigger_req = requests.post(trigger_url, headers=headers, json=payload, timeout=30)
        
        if trigger_req.status_code != 200:
            print(f"[BRIGHTDATA ERROR] Gagal trigger {platform}: {trigger_req.text}")
            return
            
        response_data = trigger_req.json()
        collection_id = response_data.get("collection_id") or response_data.get("snapshot_id")
        
        if not collection_id:
             print(f"[BRIGHTDATA ERROR] Tidak mendapat Snapshot/Collection ID dari {platform}.")
             return

        print(f"[BRIGHTDATA] Pekerjaan dimulai. Menunggu data dari {platform}...")
        
        if collector_id.startswith("gd_"):
            data_url = f"https://api.brightdata.com/datasets/v3/snapshot/{collection_id}?format=json"
        else:
            data_url = f"https://api.brightdata.com/dca/dataset?id={collection_id}"
            
        dataset = None
        retries = 12
        while retries > 0:
            time.sleep(10)
            data_req = requests.get(data_url, headers=headers)
            if data_req.status_code == 200:
                dataset = data_req.json()
                break
            elif data_req.status_code == 202:
                pass 
            retries -= 1
            
        if not dataset:
            print(f"[BRIGHTDATA WARNING] Waktu tunggu habis atau data kosong dari {platform}.")
            return
            
        hasil_brd = []
        for item in dataset:
            # Pengecekan isi data, buang jika teks kosong
            teks = item.get('text', item.get('title', item.get('description', '')))
            if not teks:
                continue

            hasil_brd.append({
                "Tool": "BrightData",
                "Platform": platform,
                "Tanggal": item.get('date', item.get('timestamp', item.get('posted_at', ''))),
                "Username": item.get('username', item.get('author', item.get('owner_username', 'Unknown'))),
                "Link": item.get('url', item.get('link', item.get('post_url', ''))),
                "Teks": teks,
                "Likes": item.get('likes', item.get('like_count', 0)),
                "Comments": item.get('comments', item.get('comment_count', 0)),
                "Shares": item.get('shares', item.get('share_count', 0))
            })
            
        if hasil_brd:
            df = pd.DataFrame(hasil_brd)
            if platform == "berita":
                df = df.rename(columns={"Teks": "Judul", "Username": "Penulis"})
                df["Isi_Berita"] = df["Judul"]
                
            simpan_csv(df, "brightdata", platform, tipe_pencarian, query)
        else:
            print(f"[BRIGHTDATA WARNING] Data berhasil ditarik dari {platform} namun isinya kosong (tidak ada teks).")
            
    except Exception as e:
        print(f"[BRIGHTDATA ERROR] Gagal scrape di {platform}: {e}")


def cari_trending_indonesia():
    print("[TRENDING] Sedang mengambil data trending via RSS Google Trends...")
    try:
        import xml.etree.ElementTree as ET
        
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=ID"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall('.//item'):
                topik = item.find('title').text
                print(f"[TRENDING] Topik trending saat ini: '{topik}'")
                return topik
    except Exception as e:
        print(f"[ERROR] Gagal mengambil data trending: {e}")
        
    print("[TRENDING] Menggunakan fallback keyword default: 'teknologi'")
    return "teknologi"


def jalankan_scheduler(tipe_pencarian, query):
    siklus = 1
    maksimal_siklus = 24  
    
    while siklus <= maksimal_siklus:
        print(f"\n==============================================")
        print(f"MEMULAI SIKLUS KE-{siklus} DARI {maksimal_siklus} UNTUK '{query}'")
        print(f"Waktu: {datetime.datetime.now().strftime('%H:%M:%S')}")
        print(f"==============================================\n")
        
        threads = []
        # Twitter dihapus dari eksekusi agar tidak bentrok dengan keterbatasan akun Bright Data
        platforms = ["berita", "facebook", "instagram", "tiktok"]
        
        for plat in platforms:
            t_brd = threading.Thread(target=jalankan_brightdata, args=(tipe_pencarian, query, plat))
            threads.append(t_brd)
            
        for t in threads:
            t.start()
            
        for t in threads:
            t.join()
            
        print(f"\n[SISTEM] Siklus ke-{siklus} selesai.")
        
        if siklus < maksimal_siklus:
            jeda_menit = random.randint(15, 30) 
            print(f"[SISTEM] Tidur selama {jeda_menit} menit untuk menghindari pemblokiran Anti-Bot...")
            time.sleep(jeda_menit * 60)
            
        siklus += 1


def main():
    print("Pilih tipe request:\n1. Keyword\n2. Topik\n3. Trending")
    
    pilihan = input("Masukkan angka pilihan (1/2/3): ")
    tipe_dict = {"1": "keyword", "2": "topik", "3": "trending"}
    tipe_pencarian = tipe_dict.get(pilihan, "keyword")
    
    query = ""
    if tipe_pencarian == "trending":
        query = cari_trending_indonesia()
    else:
        query = input(f"Masukkan {tipe_pencarian} pencarian: ")
        
    print(f"\nMemulai Auto-Scheduler Bright Data untuk: '{query}'\n")
    jalankan_scheduler(tipe_pencarian, query)


if __name__ == '__main__':
    main()