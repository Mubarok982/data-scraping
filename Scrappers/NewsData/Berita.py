import os
import datetime
import requests
import pandas as pd
import time

# 1. Masukkan API Key NewsData.io Anda
NEWSDATA_API_KEY = 'NEWSDATA_API_KEY'

# 2. Atur target jumlah berita 
TARGET_JUMLAH = 200 

topik = input("Masukkan topik berita yang dicari (misal: prabowo): ")
print(f"\nMencari target {TARGET_JUMLAH} berita terbaru untuk topik '{topik}' via NewsData.io...")

hasil_berita = []
next_page = None
halaman_ke = 1

# 3. Looping Pagination
while len(hasil_berita) < TARGET_JUMLAH:
    print(f"[SEARCH] Mengambil halaman {halaman_ke}...")
    
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q={topik}&language=id"
    if next_page:
        url += f"&page={next_page}"
        
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                print("[INFO] Tidak ada lagi berita lanjutan untuk topik ini.")
                break
                
            for artikel in results:
                judul = artikel.get('title', '')
                link = artikel.get('link', '')
                sumber = artikel.get('source_id', 'Unknown')
                tanggal = artikel.get('pubDate', '')
                
                penulis_raw = artikel.get('creator', None)
                penulis = ', '.join(penulis_raw) if isinstance(penulis_raw, list) else 'Tidak diketahui'
                
                isi_berita = artikel.get('content', '')
                if not isi_berita:
                    isi_berita = artikel.get('description', '')
                    
                hasil_berita.append({
                    "Tanggal": tanggal,
                    "Sumber": sumber,
                    "Judul": judul,
                    "Penulis": penulis,
                    "Isi_Berita": isi_berita,
                    "Link": link
                })
                
                # Berhenti jika sudah mencapai target di pertengahan halaman
                if len(hasil_berita) >= TARGET_JUMLAH:
                    break 
            
            # Cek apakah ada halaman selanjutnya
            next_page = data.get('nextPage')
            if not next_page:
                print("[INFO] Ini adalah halaman terakhir dari server NewsData.")
                break
            
            halaman_ke += 1
            time.sleep(2) # Jeda aman agar tidak diblokir server
            
        elif response.status_code == 429:
            print("[LIMIT] Terkena batas request. Menunggu 15 detik sebelum mencoba lagi...")
            time.sleep(15)
        else:
            print(f"[ERROR] HTTP {response.status_code}: {response.text}")
            break
            
    except Exception as e:
        print(f"[ERROR] Koneksi bermasalah: {e}")
        break

# 4. Pembersihan dan Export ke CSV
if hasil_berita:
    df = pd.DataFrame(hasil_berita)
    df['Isi_Berita'] = df['Isi_Berita'].astype(str).str.replace('\n', ' ', regex=False)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output_csv")
    os.makedirs(output_dir, exist_ok=True)
    
    topik_aman = topik.replace(" ", "_").lower()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nama_file = f"newsdata_{TARGET_JUMLAH}_{topik_aman}_{timestamp}.csv"
    file_path = os.path.join(output_dir, nama_file)
    
    df.to_csv(file_path, index=False)
    
    print(f"\n[SUKSES] {len(df)} artikel berhasil ditarik dan disimpan.")
    print(f"[INFO] Tersimpan di: output_csv/{nama_file}")
else:
    print("[INFO] Tidak ada data yang berhasil diekstrak.")