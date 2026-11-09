import os
import datetime
import requests
import pandas as pd
import time  
from gnews import GNews

# 1. Masukkan API Token Diffbot Anda
DIFFBOT_TOKEN = 'DIFFBOT_TOKEN'

google_news = GNews(language='id', country='ID', max_results=100) 

topik = input("Masukkan topik berita yang dicari (misal: mbg): ")
print(f"\nMencari daftar berita terbaru untuk topik '{topik}' via GNews...")

hasil_pencarian = google_news.get_news(topik)
hasil_berita = []

if hasil_pencarian:
    print(f"Ditemukan {len(hasil_pencarian)} tautan berita. Memulai ekstraksi *Full-Text* dengan Diffbot...\n")
    
    for idx, artikel in enumerate(hasil_pencarian):
        url_target = artikel.get('url')
        sumber = artikel.get('publisher', {}).get('title', 'Unknown')
        print(f"[{idx+1}/{len(hasil_pencarian)}] Mengekstrak dari {sumber}...")
        
        diffbot_url = f"https://api.diffbot.com/v3/article?token={DIFFBOT_TOKEN}&url={url_target}"
        
        try:
            response = requests.get(diffbot_url, timeout=30)
            
            # PENANGANAN ERROR 429: Jika terkena limit, tunggu 10 detik lalu coba lagi
            if response.status_code == 429:
                print("  limit API Diffbot. Jeda 10 detik ")
                time.sleep(10)
                response = requests.get(diffbot_url, timeout=30)
                
            if response.status_code == 200:
                data = response.json()
                
                if 'objects' in data and len(data['objects']) > 0:
                    ekstraksi = data['objects'][0]
                    
                    hasil_berita.append({
                        "Tanggal": ekstraksi.get('date', artikel.get('published date', '')),
                        "Sumber": sumber,
                        "Judul": ekstraksi.get('title', artikel.get('title', '')),
                        "Penulis": ekstraksi.get('author', 'Tidak diketahui'),
                        "Isi_Berita": ekstraksi.get('text', ''),
                        "Sentimen_Diffbot": ekstraksi.get('sentiment', 'N/A'), 
                        "Link": url_target
                    })
                    print("  Berhasil diekstrak!")
                else:
                    print("  Gagal: Diffbot tidak menemukan struktur teks.")
            else:
                print(f"   Gagal. HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"  Error koneksi: {e}")
            
        # JEDA REGULER: Berhenti 2 detik sebelum pindah ke URL berita selanjutnya
        time.sleep(2)
            
    # 5. Export Hasil ke CSV
    if hasil_berita:
        df = pd.DataFrame(hasil_berita)
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "output_csv")
        os.makedirs(output_dir, exist_ok=True)
        
        topik_aman = topik.replace(" ", "_").lower()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nama_file = f"diffbot_full_{topik_aman}_{timestamp}.csv"
        
        file_path = os.path.join(output_dir, nama_file)
        
        df['Isi_Berita'] = df['Isi_Berita'].astype(str).str.replace('\n', ' ', regex=False)
        df.to_csv(file_path, index=False)
        
        print(f"\n[DIFFBOT]  Proses Selesai! {len(df)} artikel utuh berhasil disimpan.")
        print(f"[DIFFBOT]  Tersimpan di: output_csv/{nama_file}")

else:
    print(f"Tidak ada berita yang ditemukan di Google News untuk topik '{topik}'.")