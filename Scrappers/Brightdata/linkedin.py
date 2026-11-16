import os
import re
import time
import base64
import random
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import primp
import requests
import pandas as pd
from lxml import html as lxml_html
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
BRIGHTDATA_TOKEN = os.getenv("BRIGHTDATA_TOKEN")
COLLECTOR_ID = "gd_l1viktl72bvl7bjuj0"


class HybridHarvester:
    def __init__(self, seen_urls=None):
        self.seen_urls = set(seen_urls) if seen_urls else set()

    def _new_client(self):
        try:
            return primp.Client(
                impersonate="chrome_131",
                verify=False,
                timeout=20,
                headers={"Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8"}
            )
        except Exception:
            return primp.Client(verify=False, timeout=20)

    def _clean_and_register(self, candidates):
        valid = []
        for raw in candidates:
            decoded = urllib.parse.unquote(raw)
            if "u=a1" in decoded:
                for b64 in re.findall(r"u=a1([a-zA-Z0-9_-]+)", decoded):
                    try:
                        pad = b64 + "=" * (-len(b64) % 4)
                        decoded += " " + base64.urlsafe_b64decode(pad).decode("utf-8", errors="ignore")
                    except Exception:
                        pass

            for match in re.findall(r"https://(?:[a-z]{2,3}\.)?linkedin\.com/in/[a-zA-Z0-9_-]+", decoded):
                slug = match.split("/in/")[-1].strip("/")
                if len(slug) > 2 and slug.lower() not in {"dir", "pub", "login", "signup", "company", "jobs"}:
                    url = f"https://www.linkedin.com/in/{slug}"
                    if url not in self.seen_urls:
                        self.seen_urls.add(url)
                        valid.append(url)
        return valid

    def _parse_dom(self, raw_html):
        candidates = [raw_html]
        try:
            tree = lxml_html.fromstring(raw_html)
            hrefs = tree.xpath("//a/@href")
            candidates.extend(hrefs)
        except Exception:
            pass
        return self._clean_and_register(candidates)

    def fetch_via_primp(self, keyword, page_num):
        q = urllib.parse.quote(f'{keyword} Indonesia site:id.linkedin.com/in/')
        endpoints = [
            f"https://www.bing.com/search?q={q}&cc=ID&setlang=id-ID&first={page_num * 10 + 1}",
            f"https://id.search.yahoo.com/search?p={q}&b={page_num * 10 + 1}",
            f"https://search.brave.com/search?q={q}&country=id&offset={page_num}",
            f"https://html.duckduckgo.com/html/?q={q}&kl=id-id&s={page_num * 30}"
        ]

        collected_batch = []
        for url in endpoints:
            try:
                client = self._new_client()
                res = client.get(url)
                if res.status_code == 200 and res.text:
                    found = self._parse_dom(res.text)
                    if found:
                        collected_batch.extend(found)
                        if len(collected_batch) >= 10:
                            break
            except Exception:
                continue
            time.sleep(1.5)
        return collected_batch

    def fetch_via_playwright(self, keyword, page_num):
        q = urllib.parse.quote(f'{keyword} Indonesia site:id.linkedin.com/in/')
        target_url = f"https://www.bing.com/search?q={q}&cc=ID&setlang=id-ID&first={page_num * 10 + 1}"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                context = browser.new_context(
                    locale="id-ID",
                    timezone_id="Asia/Jakarta",
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.goto(target_url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                content = page.content()
                browser.close()
                return self._clean_and_register(hrefs + [content])
        except Exception:
            return []

    def get_next_batch(self, keyword, page_num):
        urls = self.fetch_via_primp(keyword, page_num)
        if urls:
            print(f"[PRIMP+LXML ID] Halaman {page_num + 1} -> +{len(urls)} URL Indonesia ditemukan")
            return urls

        urls = self.fetch_via_playwright(keyword, page_num)
        if urls:
            print(f"[PLAYWRIGHT ID] Halaman {page_num + 1} -> +{len(urls)} URL Indonesia ditemukan")
            return urls

        return []


class BrightDataScraper:
    def __init__(self, token, collector_id):
        self.endpoint = "https://api.brightdata.com/datasets/v3/scrape"
        self.collector_id = collector_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _format_record(self, item, url_target):
        if not isinstance(item, dict) or item.get("error"):
            return None

        exp = item.get("experience") or []
        tempat_kerja = " | ".join([
            str(x.get("company", "")) for x in exp
            if isinstance(x, dict) and x.get("company")
        ])

        edu = item.get("education") or []
        pendidikan = " | ".join([
            str(x.get("school", x.get("title", ""))) for x in edu
            if isinstance(x, dict) and (x.get("school") or x.get("title"))
        ])

        sk_raw = item.get("skills") or []
        if sk_raw and isinstance(sk_raw[0], dict):
            skills = ", ".join([str(s.get("name", "")) for s in sk_raw if s.get("name")])
        else:
            skills = ", ".join([str(s) for s in sk_raw if s])

        return {
            "Nama": item.get("name") or item.get("full_name") or "Unknown",
            "Pekerjaan_Saat_Ini": item.get("headline") or item.get("position") or item.get("title") or "",
            "Tempat_Kerja": tempat_kerja or str(item.get("current_company_name", "")),
            "Pendidikan": pendidikan or str(item.get("educations_details", "")),
            "Skill": skills,
            "Lokasi": item.get("location") or item.get("city") or "Indonesia",
            "Koneksi": item.get("connections") or item.get("followers") or 0,
            "Link_Profil": item.get("url") or item.get("input_url") or url_target
        }

    def extract(self, url_target):
        time.sleep(random.uniform(2.0, 5.0))
        params = {"dataset_id": self.collector_id, "format": "json"}
        payload = [{"url": url_target}]

        try:
            res = requests.post(self.endpoint, headers=self.headers, params=params, json=payload, timeout=50)
            if res.status_code == 200:
                data = res.json()
                item = data[0] if isinstance(data, list) and data else data
                return self._format_record(item, url_target)

            if res.status_code == 202:
                snap_id = res.json().get("snapshot_id")
                snap_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snap_id}?format=json"
                for _ in range(25):
                    time.sleep(10)
                    poll = requests.get(snap_url, headers=self.headers, timeout=30)
                    if poll.status_code == 200:
                        data = poll.json()
                        item = data[0] if isinstance(data, list) and data else data
                        return self._format_record(item, url_target)
        except Exception:
            pass
        return None


def main():
    if not BRIGHTDATA_TOKEN:
        print("[ERROR] BRIGHTDATA_TOKEN belum diatur di .env")
        return

    kw = input("Masukkan keyword target: ").strip()
    try:
        max_target = int(input("Masukkan target jumlah data (Contoh: 100): ").strip())
    except ValueError:
        max_target = 100

    csv_file = f"linkedin_{kw.replace(' ', '_').lower()}_id.csv"
    done_urls = set()

    if os.path.exists(csv_file):
        try:
            old_df = pd.read_csv(csv_file)
            if "Link_Profil" in old_df.columns:
                done_urls = set(old_df["Link_Profil"].dropna().tolist())
                print(f"[RESUME] Ditemukan {len(done_urls)} data lama di {csv_file}")
        except Exception:
            pass

    harvester = HybridHarvester(seen_urls=done_urls)
    scraper = BrightDataScraper(BRIGHTDATA_TOKEN, COLLECTOR_ID)

    saved_count = 0
    page_num = 0
    empty_streak = 0

    while saved_count < max_target and empty_streak < 4:
        batch_urls = harvester.get_next_batch(kw, page_num)
        if not batch_urls:
            empty_streak += 1
            page_num += 1
            time.sleep(4)
            continue

        empty_streak = 0
        needed = max_target - saved_count
        target_slice = batch_urls[:needed]

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_url = {executor.submit(scraper.extract, u): u for u in target_slice}
            for future in as_completed(future_to_url):
                u = future_to_url[future]
                result = future.result()
                if result:
                    pd.DataFrame([result]).to_csv(
                        csv_file, mode="a", header=not os.path.exists(csv_file), index=False
                    )
                    saved_count += 1
                    print(f"[{saved_count}/{max_target}] SUKSES: {result['Nama']} - {result['Lokasi']} ({u})")
                else:
                    print(f"[SKIP] Gagal/Privat: {u}")

        page_num += 1
        if saved_count < max_target:
            time.sleep(random.randint(5, 10))

    print(f"\n[SELESAI] Total {saved_count} profil Indonesia tersimpan di {csv_file}")


if __name__ == "__main__":
    main()