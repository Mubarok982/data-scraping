import os
import sys
import pandas as pd
from apify_client import ApifyClient
import datetime
import re

# 1. Inisialisasi client
client = ApifyClient("APIFY_TOKEN")

# 2. Siapkan direktori output
base_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(base_dir, "output_csv")
os.makedirs(output_dir, exist_ok=True)

# 3. Definisikan daftar antrean scraping (Sumber, Actor ID, Topik untuk nama file, dan Parameter Input)
scraping_tasks = [
    # FACEBOOK 
    # {
    #     "sumber": "facebook",
    #     "actor": "apify/facebook-posts-scraper",
    #     "topik": "kompascom_postingan",
    #     "input": {
    #         "startUrls": [{"url": "https://www.facebook.com/kompascom"}],
    #         "resultsLimit": 50,
    #         "maxPosts": 50,
    #         "viewOption": "POSTS",
    #         "commentsMode": "NONE"
    #     }
    # },
    
    # INSTAGRAM 
    # {
    #     "sumber": "instagram",
    #     "actor": "apify/instagram-hashtag-scraper", 
    #     "topik": "kebakaran_hutan",
    #     "input": {
    #         "hashtags": ["kebakaranhutan"], 
    #         "resultsLimit": 20
    #     }
    # },
    
    # TWITTER / X (Satu-satunya yang aktif)
    {
        "sumber": "twitter",
        "actor": "api-ninja/x-twitter-advanced-search", 
        "topik": "prabowo",
        "input": {
            "searchTerms": ["prabowo"],
            "maxItems": 50,
            "tweetLanguage": "id"
        }
    }
    
    # TIKTOK 
    # ,{
    #     "sumber": "tiktok",
    #     "actor": "clockworks/tiktok-comments-scraper", 
    #     "topik": "karhutla",
    #     "input": {
    #         "hashtags": ["karhutla"],
    #         "resultsPerPage": 30,
    #         "excludePinnedPosts": True
    #     }
    # }
]

# 4. Eksekusi setiap task secara berurutan
for task in scraping_tasks:
    sumber = task["sumber"]
    topik = task["topik"]
    actor_id = task["actor"]
    run_input = task["input"]
    
    print(f"\n[{sumber.upper()}] Memulai scraping untuk topik: {topik}...")
    
    try:
        # Jalankan scraper
        run = client.actor(actor_id).call(run_input=run_input)
        
        # Ambil dataset ID dengan aman
        dataset_id = None
        if isinstance(run, dict):
            dataset_id = run.get("defaultDatasetId")
        elif hasattr(run, "defaultDatasetId"):
            dataset_id = run.defaultDatasetId
        elif hasattr(run, "default_dataset_id"):
            dataset_id = run.default_dataset_id
            
        if not dataset_id:
            print(f"[{sumber.upper()}] Error: Dataset ID tidak ditemukan.")
            continue # Lanjut ke platform berikutnya jika gagal

        # Tarik data hasil scraping
        dataset_items = client.dataset(dataset_id).list_items().items
        
# 5. Pemrosesan Data, Filtering Kolom, dan Export ke CSV
        if dataset_items:
            df = pd.DataFrame(dataset_items)
            
            if sumber == "facebook":
                kolom_map = {'url': 'Link', 'time': 'Tanggal', 'pageName': 'Username', 'text': 'Teks', 'likes': 'Likes', 'comments': 'Comments', 'shares': 'Shares'}
                df_bersih = df.rename(columns=kolom_map)
                
            elif sumber == "instagram":
                kolom_map = {'url': 'Link', 'timestamp': 'Tanggal', 'ownerUsername': 'Username', 'caption': 'Teks', 'likesCount': 'Likes', 'commentsCount': 'Comments'}
                df_bersih = df.rename(columns=kolom_map)
                df_bersih['Shares'] = 0 # IG API jarang mengembalikan share count publik
                
            elif sumber == "twitter":
                kolom_map = {'twitterUrl': 'Link', 'createdAt': 'Tanggal', 'author': 'Username', 'fullText': 'Teks', 'text': 'Teks', 'likeCount': 'Likes', 'replyCount': 'Comments', 'retweetCount': 'Shares'}
                df_bersih = df.rename(columns=kolom_map)
                
                # Ekstrak username dari JSON string jika diperlukan
                if 'Username' in df_bersih.columns:
                    df_bersih['Username'] = df_bersih['Username'].apply(lambda x: x.get('userName', '') if isinstance(x, dict) else x)
                
            elif sumber == "tiktok":
                kolom_map = {'videoWebUrl': 'Link', 'createTimeISO': 'Tanggal', 'uniqueId': 'Username', 'text': 'Teks', 'diggCount': 'Likes', 'replyCommentTotal': 'Comments', 'shareCount': 'Shares'}
                df_bersih = df.rename(columns=kolom_map)
                if 'Shares' not in df_bersih.columns:
                    df_bersih['Shares'] = 0
            
            # Buang kolom-kolom sampah (metadata mentah) yang tidak ada di daftar mapping kita
            kolom_target = ['Tanggal', 'Username', 'Link', 'Teks', 'Likes', 'Comments', 'Shares']
            kolom_tersedia = [k for k in kolom_target if k in df_bersih.columns]
            df_bersih = df_bersih[kolom_tersedia]
            
            # Bersihkan teks dari Enter (\n) agar file CSV tidak rusak barisnya
            if 'Teks' in df_bersih.columns:
                df_bersih['Teks'] = df_bersih['Teks'].astype(str).str.replace('\n', ' ', regex=False)
            
            # Isi nilai NaN (kosong) dengan 0 untuk kolom angka
            for col in ['Likes', 'Comments', 'Shares']:
                if col in df_bersih.columns:
                    df_bersih[col] = pd.to_numeric(df_bersih[col], errors='coerce').fillna(0).astype(int)


            # Buat stempel waktu dan simpan
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nama_file = f"{sumber}_{topik}_bersih_{timestamp}.csv"
            
            file_path = os.path.join(output_dir, nama_file)
            df_bersih.to_csv(file_path, index=False)
            
            print(f"[{sumber.upper()}]  Selesai! Data ditarik: {len(df_bersih)} baris.")
            print(f"[{sumber.upper()}]  Tersimpan di: {nama_file} (Format Rapi)")
        else:
            print(f"[{sumber.upper()}]  Data kosong dari Apify.")

    except Exception as e:
        print(f"[{sumber.upper()}] Terjadi kesalahan eksekusi: {e}")

print("\nSeluruh antrean scraping telah selesai diproses.")