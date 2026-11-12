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

BRIGHTDATA_TOKEN = os.getenv('BRIGHTDATA_TOKEN')
BRIGHTDATA_COLLECTORS = {
    "berita": "gd_mcswdt6z2elth3zqr2" 
}

def simpan_csv(df, tool_name, platform, tipe_pencarian, query):
    if df.empty:
        return
        
    if 'Teks' in df.columns:
        df['Teks'] = df['Teks'].astype(str).str.replace('\n', ' ', regex=False)
    if 'Isi_Berita' in df.columns:
        df['Isi_Berita'] = df['Isi_Berita'].astype(str).str.replace('\n', ' ', regex=False)
        
    query_aman = query.replace(" ", "_").lower()
    output_dir = "output_csv/berita"
    os.makedirs(output_dir, exist_ok=True)
    
    nama_file = f"{output_dir}/{tool_name}_{platform}_{tipe_pencarian}_{query_aman}_master.csv"
    
    if os.path.isfile(nama_file):
        df.to_csv(nama_file, mode='a', header=False, index=False)
        print(f"[{tool_name.upper()} UPDATE] Menambahkan {len(df)} baris ke {nama_file}")
    else:
        df.to_csv(nama_file, index=False)
        print(f"[{tool_name.upper()} SUKSES] Membuat {nama_file} baru dengan {len(df)} baris")

def jalankan_brightdata_berita(tipe_pencarian, query):
    platform = "berita"
    print(f"[BRIGHTDATA] Memulai siklus ekstraksi berita untuk '{query}'...")
    if not BRIGHTDATA_TOKEN:
        print("[BRIGHTDATA ERROR] Token tidak ditemukan.")
        return
        
    collector_id = BRIGHTDATA_COLLECTORS.get(platform)
    if not collector_id or collector_id.startswith("c_id_"):
        print("[BRIGHTDATA WARNING] ID Collector Berita belum dikonfigurasi.")
        return

    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    query_url_encode = query.replace(" ", "%20")
    
    payload = [{
        "url": f"https://news.google.com/search?q={query_url_encode}&hl=id&gl=ID&ceid=ID%3Aid",
        "prompt": query 
    }]

    try:
        if collector_id.startswith("gd_"):
            trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={collector_id}&include_errors=true&notify=false"
        else:
            trigger_url = f"https://api.brightdata.com/dca/trigger?collector={collector_id}"
            
        trigger_req = requests.post(trigger_url, headers=headers, json=payload, timeout=30)
        
        if trigger_req.status_code != 200:
            print(f"[BRIGHTDATA ERROR] Gagal trigger berita: {trigger_req.text}")
            return
            
        response_data = trigger_req.json()
        collection_id = response_data.get("collection_id") or response_data.get("snapshot_id")
        
        if not collection_id:
             print("[BRIGHTDATA ERROR] Tidak mendapat Snapshot/Collection ID.")
             return

        print(f"[BRIGHTDATA] ID Pekerjaan (Snapshot ID): {collection_id}")
        print("[BRIGHTDATA] Menunggu robot Bright Data bekerja di cloud...")
        
        if collector_id.startswith("gd_"):
            data_url = f"https://api.brightdata.com/datasets/v3/snapshot/{collection_id}?format=json"
        else:
            data_url = f"https://api.brightdata.com/dca/dataset?id={collection_id}"
            
        dataset = None
        
        # =========================================================================
        # PERBAIKAN: Limit dinaikkan jadi 30 (5 Menit) + Radar Live Tracking
        # =========================================================================
        retries = 30 
        while retries > 0:
            print(f"  -> Mengecek status server Bright Data... (Sisa batas waktu: {retries * 10} detik)")
            time.sleep(10)
            data_req = requests.get(data_url, headers=headers)
            
            if data_req.status_code == 200:
                print("  -> [HTTP 200 OK] Data selesai diproses!")
                dataset = data_req.json()
                break
            elif data_req.status_code == 202:
                print("  -> [HTTP 202] Robot masih mengekstrak data di latar belakang. Sabar ya...")
            else:
                print(f"  -> [HTTP {data_req.status_code}] Respon server: {data_req.text}")
                
            retries -= 1
            
        if not dataset:
            print("\n[BRIGHTDATA WARNING] SKRIP BERHENTI KARENA WAKTU HABIS ATAU DATA BENAR-BENAR KOSONG.")
            print(f"[DEBUG Terakhir] HTTP Status: {data_req.status_code}")
            print(f"[DEBUG Terakhir] RAW Text: {data_req.text[:500]}")
            return
            
        hasil_brd = []
        data_list = dataset if isinstance(dataset, list) else [dataset]
        
        for item in data_list:
            if not isinstance(item, dict):
                continue
                
            berita_items = []
            for k, v in item.items():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    if any(key in v[0] for key in ['title', 'link', 'url', 'snippet', 'text']):
                        berita_items.extend(v)
                        print(f"  -> Berhasil menemukan {len(v)} baris berita di dalam key JSON: '{k}'")
            
            if not berita_items:
                berita_items = [item]
                
            for berita in berita_items:
                if not isinstance(berita, dict):
                    continue
                    
                teks = berita.get('title', berita.get('text', berita.get('description', berita.get('snippet', ''))))
                penulis = "Unknown"
                if isinstance(berita.get('source'), dict):
                    penulis = berita['source'].get('title', berita['source'].get('name', 'Unknown'))
                else:
                    penulis = berita.get('source', berita.get('author', berita.get('publisher', 'Unknown')))

                if not teks:
                    continue

                hasil_brd.append({
                    "Tool": "BrightData",
                    "Platform": platform,
                    "Tanggal": berita.get('date', berita.get('timestamp', berita.get('pub_date', ''))),
                    "Penulis": penulis,
                    "Link": berita.get('link', berita.get('url', '')),
                    "Judul": teks,
                    "Isi_Berita": berita.get('snippet', berita.get('description', teks)), 
                    "Likes": 0, "Comments": 0, "Shares": 0
                })
            
        if hasil_brd:
            df = pd.DataFrame(hasil_brd)
            simpan_csv(df, "brightdata", platform, tipe_pencarian, query)
        else:
            print("\n[BRIGHTDATA WARNING] Data berita kosong. Struktur API mungkin berbeda.")
            print("[DEBUG] Mencetak struktur Keys (Kamar) yang ada di dalam data:")
            for i, item in enumerate(data_list):
                if isinstance(item, dict):
                    print(f"-> Item {i} memiliki keys: {list(item.keys())}")
            print(f">>> RAW Data 500 karakter:\n{str(dataset)[:500]}\n")
            
    except Exception as e:
        print(f"[BRIGHTDATA ERROR] Gagal scrape berita: {e}")

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
        
        t_brd = threading.Thread(target=jalankan_brightdata_berita, args=(tipe_pencarian, query))
        t_brd.start()
        t_brd.join()
            
        print(f"\n[SISTEM] Siklus ke-{siklus} selesai.")
        
        if siklus < maksimal_siklus:
            jeda_menit = random.randint(15, 30) 
            print(f"[SISTEM] Tidur selama {jeda_menit} menit untuk menghindari pemblokiran Anti-Bot...")
            time.sleep(jeda_menit * 60)
            
        siklus += 1

def main():
    print("=== PIPELINE SCRAPING BRIGHT DATA (KHUSUS BERITA) ===")
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