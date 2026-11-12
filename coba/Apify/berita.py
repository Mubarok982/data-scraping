import os
import sys
import pandas as pd
from apify_client import ApifyClient
import datetime
import re

# 1. Inisialisasi client
client = ApifyClient("APIFY_TOKEN")

# 2. Parameter untuk Google Trends Scraper
run_input = {
    "searchTerms": ["gempa ntt"],  
    "timeRange": "today 3-m",    
    "geo": "ID",                 
}

print("Memulai proses scraping di server Apify...")

try:
    run = client.actor("apify/google-trends-scraper").call(run_input=run_input)
    
    dataset_id = None
    if isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")
    elif hasattr(run, "defaultDatasetId"):
        dataset_id = run.defaultDatasetId
    elif hasattr(run, "default_dataset_id"):
        dataset_id = run.default_dataset_id
    
    if not dataset_id:
        print("Error: Tidak dapat menemukan Dataset ID dari respon Apify.")
        sys.exit(1)

    dataset_items = client.dataset(dataset_id).list_items().items

# 6. Pemrosesan Data dan Export ke CSV dengan Nama Dinamis
    if dataset_items:
        df = pd.DataFrame(dataset_items)
        
        keyword_asli = run_input.get("searchTerms", ["unknown"])[0]
        keyword_aman = re.sub(r'[^a-zA-Z0-9]', '_', keyword_asli)
        
        # Buat stempel waktu (contoh: 20261109_143000)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "output_csv")
        os.makedirs(output_dir, exist_ok=True)
        
        # Ekstrak Interest Over Time
        if 'interestOverTime' in df.columns:
            try:
                iot_data = df['interestOverTime'].iloc[0]
                if isinstance(iot_data, list) and len(iot_data) > 0:
                    nama_file_iot = f"tren_waktu_{keyword_aman}_{timestamp}.csv"
                    pd.DataFrame(iot_data).to_csv(os.path.join(output_dir, nama_file_iot), index=False)
                    print(f" Tersimpan: {nama_file_iot}")
            except Exception as e:
                print(f" Gagal memproses interestOverTime: {e}")
                
        # Ekstrak Related Queries
        if 'relatedQueries_rising' in df.columns:
            try:
                rising_data = df['relatedQueries_rising'].iloc[0]
                if isinstance(rising_data, list) and len(rising_data) > 0:
                    nama_file_rising = f"kueri_terkait_{keyword_aman}_{timestamp}.csv"
                    pd.DataFrame(rising_data).to_csv(os.path.join(output_dir, nama_file_rising), index=False)
                    print(f" Tersimpan: {nama_file_rising}")
            except Exception as e:
                 print(f"Gagal memproses relatedQueries: {e}")
                 
        # Ekstrak Related Topics
        if 'relatedTopics_top' in df.columns:
            try:
                 topics_data = df['relatedTopics_top'].iloc[0]
                 if isinstance(topics_data, list) and len(topics_data) > 0:
                     nama_file_topics = f"topik_teratas_{keyword_aman}_{timestamp}.csv"
                     pd.DataFrame(topics_data).to_csv(os.path.join(output_dir, nama_file_topics), index=False)
                     print(f" Tersimpan: {nama_file_topics}")
            except Exception as e:
                  print(f" Gagal memproses relatedTopics: {e}")

    else:
        print("Data kosong dari Apify.")

except Exception as e:
    print(f"\nTerjadi kesalahan eksekusi: {e}")