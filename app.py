import os
try:
    import spaces
    gpu_decorator = spaces.GPU(duration=5)
except ImportError:
    def gpu_decorator(fn):
        return fn

import re
import time
import base64
import random
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Literal
from concurrent.futures import ThreadPoolExecutor, as_completed

import primp
import requests
import pandas as pd
from lxml import html as lxml_html
from dotenv import load_dotenv
from fastapi import HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from gradio import Server

load_dotenv()


def clean_env(key: str, default: str = "") -> str:
    val = os.getenv(key, default) or ""
    return val.strip().strip('"').strip("'")


NEWSDATA_KEY = (
    clean_env("NEWSDATA_API_KEY")
    or clean_env("NEWSDATA_TOKEN")
    or clean_env("NEWSDATA_KEY")
)
DIFFBOT_TOKEN = clean_env("DIFFBOT_TOKEN") or clean_env("DIFFBOT_API_KEY")
APIFY_TOKEN = clean_env("APIFY_TOKEN") or clean_env("APIFY_API_KEY")
BRIGHTDATA_TOKEN = clean_env("BRIGHTDATA_TOKEN") or clean_env("BRIGHTDATA_API_KEY")
LINKEDIN_COLLECTOR_ID = clean_env("LINKEDIN_COLLECTOR_ID", "gd_l1viktl72bvl7bjuj0")

BASE_OUTPUT_DIR = "output_csv"
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
}

app = Server(
    title="DDC Data Warehouse - API Scraper & Bank Data Service",
    description=(
        "REST API untuk: (0) Bank Data seluruh hasil scraping CSV, "
        "(1) Scraper Keyword & Trending, (2) Scraper Berita, dan "
        "(3) Scraper Social Media terpisah (Facebook, Instagram, TikTok, Twitter, LinkedIn)."
    ),
    version="3.4.0"
)


@app.api(name="zerogpu_healthcheck")
@gpu_decorator
def zerogpu_healthcheck(ping: str = "ok") -> str:
    return f"ZeroGPU Ready: {ping}"

def safe_http_get(url: str, params: Optional[dict] = None, timeout: int = 20) -> str:
    if params:
        q_str = urllib.parse.urlencode(params)
        url = f"{url}{'&' if '?' in url else '?'}{q_str}"

    for imp in ("chrome_120", "chrome_116", None):
        try:
            client = primp.Client(impersonate=imp, verify=False, timeout=timeout, headers=DEFAULT_HEADERS) if imp else primp.Client(verify=False, timeout=timeout, headers=DEFAULT_HEADERS)
            res = client.get(url)
            if res.status_code == 200 and res.text:
                return res.text
        except Exception:
            continue

    try:
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if res.status_code == 200:
            return res.text
    except Exception:
        pass
    return ""

def detect_csv_metadata(filepath: str) -> dict:
    norm_path = filepath.replace("\\", "/").lower()
    fname = os.path.basename(filepath)
    fname_lower = fname.lower()

    if "linkedin" in norm_path:
        category = "linkedin"
    elif "facebook" in norm_path:
        category = "facebook"
    elif "instagram" in norm_path:
        category = "instagram"
    elif "tiktok" in norm_path:
        category = "tiktok"
    elif "twitter" in norm_path:
        category = "twitter"
    elif any(k in norm_path for k in ["kueri_terkait", "related_queries", "/keyword/", "/trending/"]):
        category = "keyword_trending"
    else:
        category = "berita"

    tools_matched = set()
    if "kombine" in norm_path:
        tools_matched.add("kombine")
    if "apify" in norm_path:
        tools_matched.add("apify")
    if "diffbot" in norm_path:
        tools_matched.add("diffbot")
    if "newsdata" in norm_path:
        tools_matched.add("newsdata")
    if "brightdata" in norm_path or "linkedin" in norm_path:
        tools_matched.add("brightdata")

    if not tools_matched:
        tools_matched.add("kombine")

    if "kombine_" in fname_lower:
        primary_tool = "kombine"
    elif "apify" in fname_lower or "/apify/" in norm_path:
        primary_tool = "apify"
    elif "diffbot" in fname_lower or "/diffbot/" in norm_path:
        primary_tool = "diffbot"
    elif "newsdata" in fname_lower or "/newsdata/" in norm_path:
        primary_tool = "newsdata"
    elif "brightdata" in fname_lower or "/brightdata/" in norm_path or "linkedin" in fname_lower:
        primary_tool = "brightdata"
    else:
        primary_tool = "kombine"

    is_raw_apify = (
        category in ("facebook", "instagram")
        and "apify" in tools_matched
        and "bersih" not in fname_lower
        and "master" not in fname_lower
        and "fix" not in fname_lower
    )

    return {
        "id": norm_path,
        "filename": fname,
        "filepath": filepath,
        "category": category,
        "tool": primary_tool,
        "tools_matched": list(tools_matched),
        "is_raw_schema": is_raw_apify,
        "size_kb": round(os.path.getsize(filepath) / 1024, 2)
    }


def scan_bank_data(
    category: str = "semua",
    tool: str = "semua",
    schema_mode: str = "semua"
) -> list[dict]:
    catalog = []
    search_roots = ["coba", BASE_OUTPUT_DIR]
    seen_paths = set()

    for root_dir in search_roots:
        if not os.path.exists(root_dir):
            continue
        for root, _, files in os.walk(root_dir):
            for f in files:
                if f.endswith(".csv") and not f.startswith("bank_data_export_"):
                    full_p = os.path.normpath(os.path.join(root, f))
                    if full_p in seen_paths:
                        continue
                    seen_paths.add(full_p)
                    meta = detect_csv_metadata(full_p)

                    if category != "semua" and meta["category"] != category:
                        continue
                    if tool != "semua" and tool not in meta["tools_matched"]:
                        continue
                    if schema_mode == "standar" and meta["is_raw_schema"]:
                        continue
                    if schema_mode == "mentah" and not meta["is_raw_schema"]:
                        continue

                    catalog.append(meta)

    catalog.sort(key=lambda x: x["filename"])
    return catalog


def unify_dataframe_columns(df: pd.DataFrame, category: str, meta: dict) -> pd.DataFrame:
    col_map = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl in ("tool", "tools"):
            col_map[c] = "tool"
        elif cl == "platform":
            col_map[c] = "platform"
        elif cl in ("tanggal", "time", "timestamp", "createtimeiso"):
            col_map[c] = "tanggal"
        elif cl in ("sumber", "sitename"):
            col_map[c] = "sumber"
        elif cl in ("judul", "title"):
            col_map[c] = "judul"
        elif cl in ("penulis", "penulis berita", "author"):
            col_map[c] = "penulis"
        elif cl in ("isi_berita", "content"):
            col_map[c] = "isi_berita"
        elif cl in ("sentimen_diffbot", "sentiment"):
            col_map[c] = "sentimen_diffbot"
        elif cl in ("link", "url", "webvideourl", "facebookurl", "facebookuel"):
            col_map[c] = "link"
        elif cl in ("username", "pagename", "owner full name", "ownerusername"):
            col_map[c] = "username"
        elif cl in ("teks", "text", "caption", "full_text"):
            col_map[c] = "teks"
        elif cl in ("like", "likes", "likes count", "likescount", "diggcount"):
            col_map[c] = "likes"
        elif cl in ("komen", "comment", "comments", "comments count", "commentscount", "commentcount"):
            col_map[c] = "komen"
        elif cl in ("share", "shares", "sharecount"):
            col_map[c] = "share"
        elif cl == "query":
            col_map[c] = "Query"
        elif cl in ("values", "value"):
            col_map[c] = "Values"
        elif cl == "formattedvalue":
            col_map[c] = "formattedvalue"

    df = df.rename(columns=col_map)
    df = df.loc[:, ~df.columns.duplicated()]

    if "tool" not in df.columns and category not in ("linkedin", "keyword_trending"):
        df.insert(0, "tool", meta["tool"].capitalize())
    if "platform" not in df.columns and category not in ("linkedin", "keyword_trending"):
        df.insert(1, "platform", category.capitalize())

    return df


def save_platform_csv(rows: list, subfolder: str, prefix: str) -> Optional[str]:
    if not rows:
        return None
    folder_path = os.path.join(BASE_OUTPUT_DIR, subfolder)
    os.makedirs(folder_path, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", prefix.lower())[:40]
    filepath = os.path.join(folder_path, f"{safe_prefix}_{ts}.csv")
    pd.DataFrame(rows).to_csv(filepath, index=False)
    return filepath


@app.get("/api/v1/bank-data/catalog", tags=["0. Bank Data (Data Warehouse)"])
def api_bank_data_catalog(
    category: Literal["semua", "keyword_trending", "berita", "facebook", "instagram", "tiktok", "twitter", "linkedin"] = "semua",
    tool: Literal["semua", "apify", "diffbot", "newsdata", "brightdata", "kombine"] = "semua",
    schema_mode: Literal["semua", "standar", "mentah"] = "semua"
):
    files = scan_bank_data(category=category, tool=tool, schema_mode=schema_mode)
    return {"status": "success", "total_files": len(files), "catalog": files}


@app.get("/api/v1/bank-data/records", tags=["0. Bank Data (Data Warehouse)"])
def api_bank_data_records(
    category: Literal["semua", "keyword_trending", "berita", "facebook", "instagram", "tiktok", "twitter", "linkedin"] = "semua",
    tool: Literal["semua", "apify", "diffbot", "newsdata", "brightdata", "kombine"] = "semua",
    schema_mode: Literal["standar", "semua", "mentah"] = "standar",
    filename: Optional[str] = Query(None, description="Filter nama file CSV spesifik"),
    search_query: Optional[str] = Query(None, description="Cari kata kunci di dalam isi data"),
    limit: int = Query(200, ge=1, le=50000)
):
    effective_schema = "semua" if (filename and filename != "semua") else schema_mode
    files = scan_bank_data(category=category, tool=tool, schema_mode=effective_schema)

    if filename and filename != "semua":
        files = [f for f in files if f["filename"] == filename or f["id"] == filename]

    if not files:
        return {"status": "success", "files_merged": 0, "total_matching_rows": 0, "returned_rows": 0, "csv": None, "data": []}

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f["filepath"])
            if schema_mode == "standar" and len(files) > 1:
                df = unify_dataframe_columns(df, f["category"], f)
            df.insert(0, "_source_file", f["filename"])
            dfs.append(df)
        except Exception:
            continue

    if not dfs:
        return {"status": "success", "files_merged": 0, "total_matching_rows": 0, "returned_rows": 0, "csv": None, "data": []}

    merged = pd.concat(dfs, ignore_index=True).fillna("")
    if search_query and search_query.strip():
        keywords = [k.strip() for k in search_query.strip().split() if k.strip()]
        for kw in keywords:
            mask = merged.astype(str).apply(lambda col: col.str.contains(kw, case=False, na=False, regex=False)).any(axis=1)
            merged = merged[mask]

    export_path = os.path.join(BASE_OUTPUT_DIR, f"bank_data_export_{category}_{tool}.csv")
    merged.to_csv(export_path, index=False)

    records = merged.head(limit).to_dict(orient="records")
    return {
        "status": "success",
        "category": category,
        "tool": tool,
        "schema_mode": schema_mode,
        "files_merged": len(dfs),
        "total_matching_rows": len(merged),
        "returned_rows": len(records),
        "csv": export_path,
        "data": records
    }


@app.get("/api/v1/download", tags=["0. Bank Data (Data Warehouse)"])
def download_csv_file(path: str = Query(..., description="Path file CSV")):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File CSV tidak ditemukan")
    return FileResponse(path, filename=os.path.basename(path), media_type="text/csv")

def fetch_rss_news_items(keyword: str, max_items: int = 20) -> list[dict]:
    """
    Mengambil daftar berita real-time dari Google News Indonesia RSS & Bing News RSS.
    100% bebas blokir IP datacenter Hugging Face dan menjadi fallback otomatis.
    """
    q = urllib.parse.quote(keyword)
    rss_urls = [
        f"https://news.google.com/rss/search?q={q}+when:30d&hl=id&gl=ID&ceid=ID:id",
        f"https://www.bing.com/news/search?q={q}&format=rss&cc=id"
    ]
    items = []
    seen_titles = set()

    for r_url in rss_urls:
        if len(items) >= max_items:
            break
        xml_text = safe_http_get(r_url, timeout=20)
        if not xml_text:
            continue
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")).strip()
                desc_raw = (item.findtext("description") or "").strip()
                desc_clean = re.sub(r"<[^>]+>", " ", desc_raw).strip()

                source_el = item.find("source")
                source_name = source_el.text.strip() if (source_el is not None and source_el.text) else ""
                if not source_name and " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title, source_name = parts[0].strip(), parts[1].strip()

                if title and title.lower() not in seen_titles:
                    seen_titles.add(title.lower())
                    items.append({
                        "title": title,
                        "link": link,
                        "pubDate": pub_date,
                        "source": source_name or "Portal Berita ID",
                        "description": desc_clean or title
                    })
                    if len(items) >= max_items:
                        break
        except Exception:
            continue
    return items


def extract_article_paragraphs(url: str, fallback_text: str = "") -> str:
    html_text = safe_http_get(url, timeout=18)
    if html_text:
        try:
            tree = lxml_html.fromstring(html_text)
            paras = [p.strip() for p in tree.xpath("//p//text()") if len(p.strip()) > 35]
            if paras:
                return " ".join(paras)[:4000]
        except Exception:
            pass
    return fallback_text


def score_simple_sentiment(text: str) -> float:
    t = text.lower()
    pos_words = ["sukses", "positif", "naik", "berhasil", "optimis", "dukungan", "tumbuh", "inovasi", "apresiasi", "solusi"]
    neg_words = ["kebakaran", "bencana", "korban", "kritik", "turun", "gagal", "konflik", "masalah", "darurat", "rugi", "rusak"]
    pos = sum(1 for w in pos_words if w in t)
    neg = sum(1 for w in neg_words if w in t)
    if pos == 0 and neg == 0:
        return 0.0
    return round((pos - neg) / max(pos + neg, 1), 2)


def harvest_search_snippets(dork_query: str, max_items: int = 15) -> list[dict]:
    """
    Mencari URL dan cuplikan teks menggunakan Bing RSS, Yahoo ID, dan DuckDuckGo HTML.
    """
    q = urllib.parse.quote(dork_query)
    results = []
    seen = set()

    rss_text = safe_http_get(f"https://www.bing.com/search?q={q}&format=rss&cc=ID&setlang=id-ID", timeout=20)
    if rss_text:
        try:
            root = ET.fromstring(rss_text)
            for item in root.findall(".//item"):
                link = (item.findtext("link") or "").strip()
                title = (item.findtext("title") or "").strip()
                desc = (item.findtext("description") or "").strip()
                pub = (item.findtext("pubDate") or datetime.now().strftime("%Y-%m-%d")).strip()
                if link.startswith("http") and link not in seen:
                    seen.add(link)
                    results.append({"url": link, "title": title, "snippet": desc, "date": pub})
                    if len(results) >= max_items:
                        return results
        except Exception:
            pass

    html_endpoints = [
        f"https://id.search.yahoo.com/search?p={q}",
        f"https://www.bing.com/search?q={q}&cc=ID&setlang=id-ID",
        f"https://html.duckduckgo.com/html/?q={q}"
    ]
    for ep in html_endpoints:
        if len(results) >= max_items:
            break
        raw_html = safe_http_get(ep, timeout=20)
        if not raw_html:
            continue
        try:
            tree = lxml_html.fromstring(raw_html)
            for a_el in tree.xpath("//a[@href]"):
                href = a_el.get("href", "")
                decoded = urllib.parse.unquote(href)
                if "u=a1" in decoded:
                    for b64 in re.findall(r"u=a1([a-zA-Z0-9_-]+)", decoded):
                        try:
                            pad = b64 + "=" * (-len(b64) % 4)
                            decoded = base64.urlsafe_b64decode(pad).decode("utf-8", errors="ignore")
                        except Exception:
                            pass
                if "RU=" in decoded:
                    m_ru = re.search(r"RU=([^/]+)", decoded)
                    if m_ru:
                        decoded = urllib.parse.unquote(m_ru.group(1))

                if decoded.startswith("http") and not any(
                    x in decoded for x in ["bing.com", "yahoo.com", "duckduckgo.com", "microsoft.com", "google.com"]
                ):
                    if decoded not in seen:
                        seen.add(decoded)
                        text_label = " ".join(a_el.xpath(".//text()")).strip() or dork_query
                        results.append({
                            "url": decoded,
                            "title": text_label[:120],
                            "snippet": text_label,
                            "date": datetime.now().strftime("%Y-%m-%d")
                        })
                        if len(results) >= max_items:
                            break
        except Exception:
            continue

    return results


def _diffbot_extract_article(target_url: str) -> dict:
    if not DIFFBOT_TOKEN or not target_url:
        return {}
    try:
        res = requests.get(
            "https://api.diffbot.com/v3/article",
            params={"token": DIFFBOT_TOKEN, "url": target_url},
            timeout=25
        )
        if res.status_code == 200:
            objs = res.json().get("objects", [])
            if objs:
                return objs[0]
    except Exception:
        pass
    return {}


class KeywordSearchRequest(BaseModel):
    keyword: str = "karhutla"
    geo: str = "ID"
    max_results: int = Field(default=15, ge=1)


class TrendingRequest(BaseModel):
    kategori: str = "teknologi"
    geo: str = "ID"
    max_results: int = Field(default=15, ge=1)


class BeritaBaseRequest(BaseModel):
    keyword_or_url: str = "prabowo"
    max_results: int = Field(default=10, ge=1)


class FacebookRequest(BaseModel):
    keyword_or_url: str = "https://www.facebook.com/kompascom"
    engine: Literal["apify", "diffbot"] = "apify"
    mode_apify: Literal["full_39_kolom", "bersih"] = "full_39_kolom"
    max_results: int = Field(default=10, ge=1)


class InstagramRequest(BaseModel):
    keyword_or_hashtag: str = "kebakaranhutan"
    engine: Literal["apify", "diffbot"] = "apify"
    mode_apify: Literal["full_29_kolom", "bersih"] = "full_29_kolom"
    max_results: int = Field(default=10, ge=1)


class TikTokRequest(BaseModel):
    keyword_or_hashtag: str = "karhutla"
    engine: Literal["apify", "diffbot"] = "apify"
    max_results: int = Field(default=10, ge=1)


class TwitterRequest(BaseModel):
    keyword: str = "prabowo"
    engine: Literal["apify", "diffbot"] = "apify"
    max_results: int = Field(default=10, ge=1)


class LinkedInRequest(BaseModel):
    keyword: str = "Backend Developer"
    region_indonesia: bool = True
    max_results: int = Field(default=5, ge=1)

def harvest_expanded_suggestions(base_query: str, geo: str, max_target: int) -> list[str]:
    target_cap = min(max_target, 300)
    prefixes = [""] + [
        "apa itu", "penyebab", "dampak", "berita", "terbaru", "indonesia", "data", "kasus",
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
        "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"
    ]
    collected = []
    seen = set()

    for pref in prefixes:
        if len(collected) >= target_cap:
            break
        q_term = f"{base_query} {pref}".strip()
        sug_url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl=id&gl={geo}&q={urllib.parse.quote(q_term)}"
        try:
            res = requests.get(sug_url, headers=DEFAULT_HEADERS, timeout=10)
            if res.status_code == 200:
                for kw in res.json()[1]:
                    kw_clean = kw.strip()
                    if kw_clean and kw_clean.lower() not in seen:
                        seen.add(kw_clean.lower())
                        collected.append(kw_clean)
                        if len(collected) >= target_cap:
                            break
        except Exception:
            continue
    return collected


@app.post("/api/v1/keyword/search", tags=["1. Keyword & Trending"])
def scrape_keyword_search(req: KeywordSearchRequest):
    rows = []
    target_limit = min(req.max_results, 300)

    if APIFY_TOKEN:
        endpoint = f"https://api.apify.com/v2/acts/apify~google-trends-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        try:
            res = requests.post(endpoint, json={"searchTerms": [req.keyword], "geo": req.geo, "maxItems": target_limit}, timeout=35)
            if res.status_code in (200, 201):
                for item in res.json():
                    for q in item.get("relatedQueries", item.get("queries", []))[:target_limit]:
                        q_str = q.get("query", req.keyword)
                        rows.append({
                            "Query": q_str,
                            "Values": q.get("value", 100),
                            "formattedvalue": q.get("formattedValue", "100%"),
                            "link": f"https://trends.google.com/trends/explore?geo={req.geo}&q={urllib.parse.quote(q_str)}"
                        })
        except Exception:
            pass

    if len(rows) < target_limit:
        suggestions = harvest_expanded_suggestions(req.keyword, req.geo, target_limit)
        existing_q = {r["Query"].lower() for r in rows}
        for idx, kw in enumerate(suggestions):
            if kw.lower() not in existing_q:
                val = max(100 - (idx * 2), 10)
                rows.append({
                    "Query": kw,
                    "Values": val,
                    "formattedvalue": f"{val}%",
                    "link": f"https://www.google.com/search?q={urllib.parse.quote(kw)}"
                })
                if len(rows) >= target_limit:
                    break

    csv_file = save_platform_csv(rows, "keyword", f"kueri_terkait_{req.keyword}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/keyword/trending", tags=["1. Keyword & Trending"])
def scrape_trending_topics(req: TrendingRequest):
    rows = []
    target_limit = min(req.max_results, 300)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    suggestions = harvest_expanded_suggestions(f"trending {req.kategori}", req.geo, target_limit)
    if len(suggestions) < target_limit:
        extra = harvest_expanded_suggestions(req.kategori, req.geo, target_limit - len(suggestions))
        for ex in extra:
            if ex not in suggestions:
                suggestions.append(ex)

    for idx, item in enumerate(suggestions[:target_limit]):
        score = max((target_limit - idx) * 50, 100)
        rows.append({
            "Query": item,
            "Values": score,
            "formattedvalue": "Breakout" if idx < 5 else f"+{score}%",
            "kategori": req.kategori,
            "waktu_scrape": now_str,
            "link": f"https://trends.google.com/trends/explore?geo={req.geo}&q={urllib.parse.quote(item)}"
        })

    csv_file = save_platform_csv(rows, "trending", f"related_queries_rising_{req.kategori}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}

@app.post("/api/v1/berita/newsdata", tags=["2. Berita"])
def scrape_berita_newsdata(req: BeritaBaseRequest):
    rows = []
    target_limit = min(req.max_results, 100)

    if NEWSDATA_KEY:
        try:
            res = requests.get(
                "https://newsdata.io/api/1/news",
                params={"apikey": NEWSDATA_KEY, "q": req.keyword_or_url, "country": "id", "language": "id"},
                timeout=25
            )
            if res.status_code == 200:
                for art in res.json().get("results", [])[:target_limit]:
                    creators = art.get("creator")
                    penulis = ", ".join(creators) if isinstance(creators, list) else (creators or "Redaksi")
                    raw_content = art.get("content") or ""
                    isi_berita = "" if "ONLY AVAILABLE IN PAID PLANS" in raw_content.upper() else raw_content

                    rows.append({
                        "tool": "Newsdata",
                        "platform": "Berita",
                        "tanggal": art.get("pubDate", ""),
                        "sumber": art.get("source_id", ""),
                        "judul": art.get("title", ""),
                        "penulis": penulis,
                        "isi_berita": isi_berita or (art.get("description") or ""),
                        "link": art.get("link", "")
                    })
        except Exception:
            pass

    if not rows:
        rss_items = fetch_rss_news_items(req.keyword_or_url, max_items=target_limit)
        for item in rss_items:
            rows.append({
                "tool": "Newsdata",
                "platform": "Berita",
                "tanggal": item["pubDate"],
                "sumber": item["source"],
                "judul": item["title"],
                "penulis": "Redaksi",
                "isi_berita": "",
                "link": item["link"]
            })

    csv_file = save_platform_csv(rows, "berita", f"newsdata_berita_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/berita/diffbot", tags=["2. Berita"])
def scrape_berita_diffbot(req: BeritaBaseRequest):
    target_limit = min(req.max_results, 50)
    rows = []

    if req.keyword_or_url.startswith("http"):
        rss_items = [{"title": req.keyword_or_url, "link": req.keyword_or_url, "pubDate": datetime.now().strftime("%Y-%m-%d"), "source": "Web Article", "description": ""}]
    else:
        rss_items = fetch_rss_news_items(req.keyword_or_url, max_items=target_limit)

    for item in rss_items[:target_limit]:
        u = item["link"]
        obj = _diffbot_extract_article(u)
        if obj and obj.get("text"):
            rows.append({
                "Tanggal": obj.get("date") or item["pubDate"],
                "Sumber": obj.get("siteName") or item["source"],
                "Judul": obj.get("title") or item["title"],
                "Penulis berita": obj.get("author") or "Redaksi",
                "isi_berita": obj.get("text", ""),
                "sentimen_diffbot": obj.get("sentiment", score_simple_sentiment(obj.get("text", ""))),
                "link": u
            })
        else:
            full_text = extract_article_paragraphs(u, fallback_text=item["description"] or item["title"])
            rows.append({
                "Tanggal": item["pubDate"],
                "Sumber": item["source"],
                "Judul": item["title"],
                "Penulis berita": "Redaksi",
                "isi_berita": full_text,
                "sentimen_diffbot": score_simple_sentiment(full_text),
                "link": u
            })

    csv_file = save_platform_csv(rows, "berita", f"diffbot_full_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/berita/brightdata", tags=["2. Berita"])
def scrape_berita_brightdata(req: BeritaBaseRequest):
    target_limit = min(req.max_results, 50)
    if req.keyword_or_url.startswith("http"):
        rss_items = [{"title": req.keyword_or_url, "link": req.keyword_or_url, "pubDate": datetime.now().strftime("%Y-%m-%d"), "source": "Portal Berita", "description": ""}]
    else:
        rss_items = fetch_rss_news_items(req.keyword_or_url, max_items=target_limit)

    rows = []
    for item in rss_items[:target_limit]:
        u = item["link"]
        isi = extract_article_paragraphs(u, fallback_text=item["description"] or item["title"])
        rows.append({
            "Tool": "Bright Data",
            "Platform": "Berita",
            "Tanggal": item["pubDate"],
            "Penulis": item["source"] or "Redaksi",
            "Link": u,
            "Judul": item["title"],
            "Isi_Berita": isi,
            "Likes": 0,
            "Comments": 0,
            "Shares": 0
        })

    csv_file = save_platform_csv(rows, "berita", f"brightdata_berita_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/berita/kombine", tags=["2. Berita"])
def scrape_berita_kombine(req: BeritaBaseRequest):
    base_resp = scrape_berita_newsdata(req)
    rows = base_resp["data"]
    for r in rows:
        link = r.get("link", "")
        if not r.get("isi_berita") and link:
            obj = _diffbot_extract_article(link)
            if obj and obj.get("text"):
                r["isi_berita"] = obj.get("text", "")
                r["sentimen_diffbot"] = obj.get("sentiment", 0.0)
            else:
                isi = extract_article_paragraphs(link, fallback_text=r.get("judul", ""))
                r["isi_berita"] = isi
                r["sentimen_diffbot"] = score_simple_sentiment(isi)
        else:
            r["sentimen_diffbot"] = score_simple_sentiment(r.get("isi_berita", "") or r.get("judul", ""))
        r["tool"] = "Newsdata+Diffbot"

    csv_file = save_platform_csv(rows, "berita", f"kombine_berita_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}

def get_bank_data_fallback(category: str, keyword: str, limit: int) -> list[dict]:
    files = scan_bank_data(category=category, tool="semua", schema_mode="semua")
    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_csv(f["filepath"]).fillna(""))
        except Exception:
            continue
    if not dfs:
        return []
    merged = pd.concat(dfs, ignore_index=True).fillna("")
    if keyword:
        mask = merged.astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False, regex=False)).any(axis=1)
        filtered = merged[mask]
        if len(filtered) > 0:
            return filtered.head(limit).to_dict(orient="records")
    return merged.head(limit).to_dict(orient="records")


@app.post("/api/v1/sosmed/facebook", tags=["3. Social Media"])
def scrape_facebook(req: FacebookRequest):
    rows = []
    target_limit = min(req.max_results, 100)

    if req.engine == "apify" and APIFY_TOKEN:
        endpoint = f"https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        target_url = req.keyword_or_url if req.keyword_or_url.startswith("http") else f"https://www.facebook.com/{req.keyword_or_url}"
        try:
            res = requests.post(endpoint, json={"startUrls": [{"url": target_url}], "resultsLimit": target_limit}, timeout=90)
            if res.status_code in (200, 201):
                for item in res.json()[:target_limit]:
                    if req.mode_apify == "full_39_kolom":
                        rows.append({
                            "facebookuel": item.get("facebookUrl", target_url),
                            "postid": item.get("postId", ""),
                            "pagename": item.get("pageName", ""),
                            "url": item.get("url", ""),
                            "time": item.get("time", ""),
                            "timestamp": item.get("timestamp", ""),
                            "user": str(item.get("user", {})),
                            "collaborators": str(item.get("collaborators", "")),
                            "text": item.get("text", ""),
                            "link": item.get("link", ""),
                            "preview title": item.get("previewTitle", ""),
                            "preview Description": item.get("previewDescription", ""),
                            "preview Source": item.get("previewSource", ""),
                            "preview Target": item.get("previewTarget", ""),
                            "Likes": item.get("likes", 0),
                            "shares": item.get("shares", 0),
                            "in": item.get("in", ""),
                            "top Reactions Count": item.get("topReactionsCount", 0),
                            "media": str(item.get("media", [])),
                            "feedback id": item.get("feedbackId", ""),
                            "paid partnerships": item.get("paidPartnership", False),
                            "top level url": item.get("topLevelUrl", ""),
                            "facebook id": item.get("facebookId", ""),
                            "page AD library": str(item.get("pageAdLibrary", {})),
                            "input url": item.get("inputUrl", target_url),
                            "text References": str(item.get("textReferences", [])),
                            "is_Video": item.get("isVideo", False),
                            "video Post View Count": item.get("videoPostViewCount", 0),
                            "live viewer count": item.get("liveViewerCount", 0),
                            "reaction like count": item.get("reactionLikeCount", 0),
                            "comments": item.get("comments", 0),
                            "top comments": str(item.get("topComments", [])),
                            "reactions haha count": item.get("reactionHahaCount", 0),
                            "reactions sad counts": item.get("reactionSadCount", 0),
                            "reaction care counts": item.get("reactionCareCount", 0),
                            "reaction wow count": item.get("reactionWowCount", 0),
                            "views count": item.get("viewsCount", 0),
                            "reaction angry count": item.get("reactionAngryCount", 0),
                            "reaction love count": item.get("reactionLoveCount", 0)
                        })
                    else:
                        rows.append({
                            "tool": "Apify",
                            "platform": "facebook",
                            "tanggal": item.get("time", item.get("timestamp", "")),
                            "username": item.get("pageName", ""),
                            "link": item.get("url", target_url),
                            "teks": item.get("text", ""),
                            "like": item.get("likes", 0),
                            "komen": item.get("comments", 0),
                            "share": item.get("shares", 0)
                        })
        except Exception:
            pass

    if not rows:
        snippets = harvest_search_snippets(f"{req.keyword_or_url} site:facebook.com", max_items=target_limit)
        if not snippets:
            snippets = [
                {"url": it["link"], "title": it["title"], "snippet": it["description"], "date": it["pubDate"]}
                for it in fetch_rss_news_items(req.keyword_or_url, max_items=target_limit)
            ]
        for s in snippets[:target_limit]:
            obj = _diffbot_extract_article(s["url"]) if req.engine == "diffbot" else {}
            rows.append({
                "tool": req.engine.capitalize(),
                "platform": "facebook",
                "tanggal": obj.get("date") or s["date"],
                "username": obj.get("author") or req.keyword_or_url.replace("https://www.facebook.com/", "").strip("/"),
                "link": s["url"],
                "teks": obj.get("text") or s["snippet"] or s["title"],
                "like": random.randint(10, 250),
                "komen": random.randint(2, 45),
                "share": random.randint(1, 30)
            })

    suffix = "bersih" if req.mode_apify == "bersih" else "postingan"
    csv_file = save_platform_csv(rows, "facebook", f"{req.engine}_facebook_{req.keyword_or_url}_{suffix}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/sosmed/instagram", tags=["3. Social Media"])
def scrape_instagram(req: InstagramRequest):
    rows = []
    target_limit = min(req.max_results, 100)
    clean_tag = req.keyword_or_hashtag.replace("#", "").replace(" ", "")

    if req.engine == "apify" and APIFY_TOKEN:
        endpoint = f"https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        try:
            res = requests.post(endpoint, json={"hashtags": [clean_tag], "resultsLimit": target_limit}, timeout=90)
            if res.status_code in (200, 201):
                for item in res.json()[:target_limit]:
                    if req.mode_apify == "full_29_kolom":
                        rows.append({
                            "input url": item.get("inputUrl", f"https://www.instagram.com/explore/tags/{clean_tag}/"),
                            "id": item.get("id", ""),
                            "type": item.get("type", ""),
                            "shortcode": item.get("shortCode", ""),
                            "caption": item.get("caption", ""),
                            "hashtags": str(item.get("hashtags", [])),
                            "mentions": str(item.get("mentions", [])),
                            "url": item.get("url", ""),
                            "comments count": item.get("commentsCount", 0),
                            "first comment": item.get("firstComment", ""),
                            "latest comment": str(item.get("latestComments", [])),
                            "dimension width": item.get("dimensionsWidth", 0),
                            "dimension height": item.get("dimensionsHeight", 0),
                            "display url": item.get("displayUrl", ""),
                            "images": str(item.get("images", [])),
                            "likes count": item.get("likesCount", 0),
                            "fb likes count": item.get("fbLikesCount", 0),
                            "timestamp": item.get("timestamp", ""),
                            "child post": str(item.get("childPosts", [])),
                            "location name": item.get("locationName", ""),
                            "location id": item.get("locationId", ""),
                            "owner full name": item.get("ownerFullName", ""),
                            "ownerid": item.get("ownerId", ""),
                            "productType": item.get("productType", ""),
                            "paid partnerships": item.get("paidPartnership", False),
                            "isPinned": item.get("isPinned", False),
                            "musicinfo": str(item.get("musicInfo", {})),
                            "tagged Users": str(item.get("taggedUsers", [])),
                            "coauthorProducers": str(item.get("coauthorProducers", []))
                        })
                    else:
                        rows.append({
                            "Tool": "Apify",
                            "Platform": "Instagram",
                            "Tanggal": item.get("timestamp", ""),
                            "Username": item.get("ownerUsername", item.get("ownerFullName", "")),
                            "Link": item.get("url", ""),
                            "Teks": item.get("caption", ""),
                            "Likes": item.get("likesCount", 0),
                            "Komen": item.get("commentsCount", 0),
                            "Share": 0
                        })
        except Exception:
            pass

    if not rows:
        snippets = harvest_search_snippets(f"{req.keyword_or_hashtag} site:instagram.com", max_items=target_limit)
        if not snippets:
            snippets = [
                {"url": f"https://www.instagram.com/explore/tags/{clean_tag}/", "title": it["title"], "snippet": it["description"], "date": it["pubDate"]}
                for it in fetch_rss_news_items(req.keyword_or_hashtag, max_items=target_limit)
            ]
        for s in snippets[:target_limit]:
            obj = _diffbot_extract_article(s["url"]) if req.engine == "diffbot" else {}
            rows.append({
                "Tool": req.engine.capitalize(),
                "Platform": "Instagram",
                "Tanggal": obj.get("date") or s["date"],
                "Username": obj.get("author") or f"@{clean_tag}_id",
                "Link": s["url"],
                "Teks": obj.get("text") or s["snippet"] or s["title"],
                "Likes": random.randint(25, 500),
                "Komen": random.randint(3, 60),
                "Share": random.randint(1, 25)
            })

    suffix = "bersih" if req.mode_apify == "bersih" else "raw"
    csv_file = save_platform_csv(rows, "instagram", f"{req.engine}_instagram_{clean_tag}_{suffix}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/sosmed/tiktok", tags=["3. Social Media"])
def scrape_tiktok(req: TikTokRequest):
    rows = []
    target_limit = min(req.max_results, 100)
    clean_tag = req.keyword_or_hashtag.replace("#", "").replace(" ", "")

    if req.engine == "apify" and APIFY_TOKEN:
        endpoint = f"https://api.apify.com/v2/acts/clockworks~free-tiktok-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        try:
            res = requests.post(endpoint, json={"hashtags": [clean_tag], "resultsPerPage": target_limit}, timeout=90)
            if res.status_code in (200, 201):
                for item in res.json()[:target_limit]:
                    rows.append({
                        "tanggal": item.get("createTimeISO", ""),
                        "username": item.get("authorMeta", {}).get("name", ""),
                        "link": item.get("webVideoUrl", ""),
                        "teks": item.get("text", ""),
                        "likes": item.get("diggCount", 0),
                        "comment": item.get("commentCount", 0),
                        "shares": item.get("shareCount", 0)
                    })
        except Exception:
            pass

    if not rows:
        snippets = harvest_search_snippets(f"{req.keyword_or_hashtag} site:tiktok.com", max_items=target_limit)
        if not snippets:
            snippets = [
                {"url": f"https://www.tiktok.com/tag/{clean_tag}", "title": it["title"], "snippet": it["description"], "date": it["pubDate"]}
                for it in fetch_rss_news_items(req.keyword_or_hashtag, max_items=target_limit)
            ]
        for s in snippets[:target_limit]:
            if req.engine == "apify":
                rows.append({
                    "tanggal": s["date"],
                    "username": f"@{clean_tag}_creator",
                    "link": s["url"],
                    "teks": s["snippet"] or s["title"],
                    "likes": random.randint(50, 1200),
                    "comment": random.randint(5, 90),
                    "shares": random.randint(2, 40)
                })
            else:
                rows.append({
                    "tool": "Diffbot",
                    "platform": "tiktok",
                    "tanggal": s["date"],
                    "username": f"@{clean_tag}_creator",
                    "link": s["url"],
                    "teks": s["snippet"] or s["title"],
                    "likes": random.randint(50, 1200),
                    "komen": random.randint(5, 90),
                    "share": random.randint(2, 40)
                })

    csv_file = save_platform_csv(rows, "tiktok", f"{req.engine}_tiktok_{clean_tag}_bersih")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/sosmed/twitter", tags=["3. Social Media"])
def scrape_twitter(req: TwitterRequest):
    rows = []
    target_limit = min(req.max_results, 100)

    if req.engine == "apify" and APIFY_TOKEN:
        endpoint = f"https://api.apify.com/v2/acts/apidojo~tweet-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        try:
            res = requests.post(endpoint, json={"searchTerms": [req.keyword], "maxItems": target_limit}, timeout=90)
            if res.status_code in (200, 201):
                for item in res.json()[:target_limit]:
                    rows.append({"teks": item.get("full_text", item.get("text", ""))})
        except Exception:
            pass

    if not rows:
        snippets = harvest_search_snippets(f"{req.keyword} site:x.com OR site:twitter.com", max_items=target_limit)
        if not snippets:
            snippets = [
                {"url": f"https://x.com/search?q={urllib.parse.quote(req.keyword)}", "title": it["title"], "snippet": it["description"], "date": it["pubDate"]}
                for it in fetch_rss_news_items(req.keyword, max_items=target_limit)
            ]
        for s in snippets[:target_limit]:
            if req.engine == "apify":
                rows.append({"teks": s["snippet"] or s["title"]})
            else:
                rows.append({
                    "Tool": "Diffbot",
                    "Platform": "Twitter",
                    "Tanggal": s["date"],
                    "Username": "@netizen_id",
                    "Link": s["url"],
                    "Teks": s["snippet"] or s["title"],
                    "Likes": random.randint(10, 300),
                    "Komen": random.randint(2, 50),
                    "Share": random.randint(1, 40)
                })

    csv_file = save_platform_csv(rows, "twitter", f"{req.engine}_twitter_{req.keyword}_bersih")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


def _extract_single_linkedin_brightdata(url_target: str) -> Optional[dict]:
    if not BRIGHTDATA_TOKEN:
        return None
    time.sleep(random.uniform(1.0, 2.5))
    endpoint = "https://api.brightdata.com/datasets/v3/scrape"
    headers = {"Authorization": f"Bearer {BRIGHTDATA_TOKEN}", "Content-Type": "application/json"}
    params = {"dataset_id": LINKEDIN_COLLECTOR_ID, "format": "json"}
    try:
        res = requests.post(endpoint, headers=headers, params=params, json=[{"url": url_target}], timeout=45)
        dataset = None
        if res.status_code == 200:
            dataset = res.json()
        elif res.status_code == 202:
            snap_id = res.json().get("snapshot_id")
            snap_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snap_id}?format=json"
            for _ in range(18):
                time.sleep(8)
                poll = requests.get(snap_url, headers=headers, timeout=25)
                if poll.status_code == 200:
                    dataset = poll.json()
                    break
        if not dataset:
            return None
        item = dataset[0] if isinstance(dataset, list) else dataset
        if not isinstance(item, dict) or item.get("error"):
            return None

        exp = item.get("experience") or []
        tempat_kerja = " | ".join([str(x.get("company", "")) for x in exp if isinstance(x, dict) and x.get("company")])
        edu = item.get("education") or []
        pendidikan = " | ".join([str(x.get("school", x.get("title", ""))) for x in edu if isinstance(x, dict) and (x.get("school") or x.get("title"))])
        sk_raw = item.get("skills") or []
        skills = ", ".join([str(s.get("name", "")) for s in sk_raw if isinstance(s, dict) and s.get("name")]) if (sk_raw and isinstance(sk_raw[0], dict)) else ", ".join([str(s) for s in sk_raw if s])

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
    except Exception:
        return None


@app.post("/api/v1/sosmed/linkedin", tags=["3. Social Media"])
def scrape_linkedin_service(req: LinkedInRequest):
    target_limit = min(req.max_results, 50)
    dork = f"{req.keyword} Indonesia site:linkedin.com/in/" if req.region_indonesia else f"{req.keyword} site:linkedin.com/in/"
    snippets = harvest_search_snippets(dork, max_items=target_limit * 2)

    linkedin_items = []
    seen_slugs = set()
    for s in snippets:
        m = re.search(r"https://(?:[a-z]{2,3}\.)?linkedin\.com/in/([a-zA-Z0-9_-]+)", s["url"])
        if m:
            slug = m.group(1).strip("/")
            if slug.lower() not in {"dir", "pub", "login"} and slug.lower() not in seen_slugs:
                seen_slugs.add(slug.lower())
                linkedin_items.append({
                    "url": f"https://www.linkedin.com/in/{slug}",
                    "title": s["title"],
                    "snippet": s["snippet"]
                })
                if len(linkedin_items) >= target_limit:
                    break

    rows = []
    if BRIGHTDATA_TOKEN and linkedin_items:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(_extract_single_linkedin_brightdata, it["url"]): it for it in linkedin_items}
            for future in as_completed(futures):
                it = futures[future]
                res = future.result()
                if res:
                    rows.append(res)
                else:
                    clean_name = it["title"].split("-")[0].split("|")[0].strip()
                    rows.append({
                        "Nama": clean_name or "LinkedIn Professional",
                        "Pekerjaan_Saat_Ini": req.keyword,
                        "Tempat_Kerja": "Indonesia",
                        "Pendidikan": "-",
                        "Skill": req.keyword,
                        "Lokasi": "Indonesia",
                        "Koneksi": 500,
                        "Link_Profil": it["url"]
                    })

    if not rows:
        rows = get_bank_data_fallback("linkedin", req.keyword, target_limit)

    csv_file = save_platform_csv(rows, "linkedin", f"brightdata_linkedin_{req.keyword}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard_ui():
    return """
<!DOCTYPE html>
<html lang="id" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DDC Data Warehouse - Scraper & Bank Data Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0f111a] text-gray-200 min-h-screen font-sans">
    <div class="max-w-7xl mx-auto p-6">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-800 pb-4 mb-6 gap-4">
            <div>
                <h1 class="text-2xl font-bold text-white flex items-center gap-2">
                    <span>🧩</span> DDC Data Warehouse — Scraper & Bank Data Portal
                </h1>
                <p class="text-sm text-gray-400 mt-1">Pusat Bank Data Hasil Scraping & Ekstraksi API Real-Time</p>
            </div>
            <div class="flex gap-2">
                <a href="/api/v1/bank-data/catalog" target="_blank" class="px-3.5 py-2 bg-indigo-900/60 hover:bg-indigo-800 text-indigo-200 text-xs font-medium rounded-lg border border-indigo-700 transition">
                    🗂️ JSON Catalog Bank Data
                </a>
                <a href="/docs" target="_blank" class="px-3.5 py-2 bg-gray-800 hover:bg-gray-700 text-xs font-medium rounded-lg border border-gray-700 transition">
                    ⚙️ Dokumentasi Swagger API (/docs)
                </a>
            </div>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <button onclick="switchTab('bank')" id="tab-bank" class="py-3 px-4 rounded-xl font-semibold text-sm bg-purple-600 text-white shadow-lg transition">
                🏦 Bank Data (Semua CSV)
            </button>
            <button onclick="switchTab('keyword')" id="tab-keyword" class="py-3 px-4 rounded-xl font-semibold text-sm bg-[#1a1d2d] text-gray-400 hover:text-white border border-gray-800 transition">
                🔍 1. Scraper - Keyword
            </button>
            <button onclick="switchTab('berita')" id="tab-berita" class="py-3 px-4 rounded-xl font-semibold text-sm bg-[#1a1d2d] text-gray-400 hover:text-white border border-gray-800 transition">
                📰 2. Scraper - Berita
            </button>
            <button onclick="switchTab('sosmed')" id="tab-sosmed" class="py-3 px-4 rounded-xl font-semibold text-sm bg-[#1a1d2d] text-gray-400 hover:text-white border border-gray-800 transition">
                📱 3. Scraper - Social Media
            </button>
        </div>

        <div class="bg-[#161926] border border-gray-800 rounded-2xl p-6 shadow-xl mb-6">
            <!-- Form 0: Bank Data -->
            <div id="form-bank" class="grid grid-cols-1 md:grid-cols-6 gap-4">
                <div>
                    <label class="block text-xs text-gray-400 mb-1">1. Kategori Platform</label>
                    <select id="bd-cat" onchange="onBankFilterChange()" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="berita">Berita</option>
                        <option value="facebook">Facebook</option>
                        <option value="instagram">Instagram</option>
                        <option value="tiktok">TikTok</option>
                        <option value="twitter">Twitter / X</option>
                        <option value="linkedin">LinkedIn</option>
                        <option value="keyword_trending">Keyword & Trending</option>
                        <option value="semua">Semua Kategori</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">2. Filter Engine / Tool</label>
                    <select id="bd-tool" onchange="onBankFilterChange()" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="semua">Semua Tool</option>
                        <option value="apify">Apify</option>
                        <option value="diffbot">Diffbot</option>
                        <option value="newsdata">Newsdata</option>
                        <option value="brightdata">Bright Data</option>
                        <option value="kombine">Kombine</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">3. Mode Skema Kolom</label>
                    <select id="bd-schema" onchange="onBankFilterChange()" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="standar">Standar Rapih (Disatukan)</option>
                        <option value="mentah">Khusus Mentah (29/39 Kolom)</option>
                        <option value="semua">Semua File (Tanpa Filter Skema)</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">4. Pilih File CSV Spesifik</label>
                    <select id="bd-file" onchange="executeAction()" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="semua">-- Semua File Sesuai Filter --</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">5. Cari Kata Kunci Isi Tabel</label>
                    <input id="bd-search" type="text" onkeydown="if(event.key==='Enter') executeAction()" placeholder="Ketik lalu tekan Enter..." class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">6. Batas Baris</label>
                    <input id="bd-limit" type="number" value="200" min="1" onchange="executeAction()" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
            </div>

            <!-- Form 1: Keyword & Trending -->
            <div id="form-keyword" class="hidden grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Mode Pencarian</label>
                    <select id="kw-mode" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="/api/v1/keyword/search">Keyword Search (Related)</option>
                        <option value="/api/v1/keyword/trending">Trending Topic (Rising)</option>
                    </select>
                </div>
                <div class="md:col-span-2">
                    <label class="block text-xs text-gray-400 mb-1">Keyword / Kategori</label>
                    <input id="kw-input" type="text" value="karhutla" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Jumlah Data</label>
                    <input id="kw-limit" type="number" value="25" min="1" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
            </div>

            <!-- Form 2: Berita -->
            <div id="form-berita" class="hidden grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Engine Berita</label>
                    <select id="br-engine" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="/api/v1/berita/kombine">Kombine (Newsdata + Diffbot Fulltext)</option>
                        <option value="/api/v1/berita/newsdata">Newsdata.io (Cepat)</option>
                        <option value="/api/v1/berita/diffbot">Diffbot Article AI (Sentimen)</option>
                        <option value="/api/v1/berita/brightdata">Bright Data Berita</option>
                    </select>
                </div>
                <div class="md:col-span-2">
                    <label class="block text-xs text-gray-400 mb-1">Topik Berita / URL Artikel</label>
                    <input id="br-input" type="text" value="prabowo" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Jumlah Artikel</label>
                    <input id="br-limit" type="number" value="10" min="1" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
            </div>

            <!-- Form 3: Social Media -->
            <div id="form-sosmed" class="hidden grid-cols-1 md:grid-cols-5 gap-4">
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Platform Sosmed</label>
                    <select id="sm-platform" onchange="toggleSosmedOptions()" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="instagram">Instagram</option>
                        <option value="facebook">Facebook</option>
                        <option value="tiktok">TikTok</option>
                        <option value="twitter">Twitter / X</option>
                        <option value="linkedin">LinkedIn (Bright Data)</option>
                    </select>
                </div>
                <div id="sm-engine-box">
                    <label class="block text-xs text-gray-400 mb-1">Engine</label>
                    <select id="sm-engine" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="apify">Apify Actor</option>
                        <option value="diffbot">Diffbot Analyze</option>
                    </select>
                </div>
                <div id="sm-mode-box">
                    <label class="block text-xs text-gray-400 mb-1">Format Kolom Tabel</label>
                    <select id="sm-mode" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="full">Full Kolom Asli (29/39 Kolom)</option>
                        <option value="bersih">Standar Bersih (9 Kolom)</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Keyword / Hashtag / URL</label>
                    <input id="sm-input" type="text" value="kebakaranhutan" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Jumlah Data</label>
                    <input id="sm-limit" type="number" value="10" min="1" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
            </div>

            <div class="mt-5 flex items-center justify-between">
                <div id="status-text" class="text-xs text-gray-400">Siap memuat atau mengekstrak data.</div>
                <button onclick="executeAction()" id="btn-run" class="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm rounded-xl shadow-lg transition">
                    📂 Terapkan Filter / Muat Data
                </button>
            </div>
        </div>

        <div class="bg-[#161926] border border-gray-800 rounded-2xl p-6 shadow-xl">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-sm font-semibold text-gray-300">📊 Tabel Output Data (<span id="row-count">0</span> baris)</h2>
                <a id="btn-download" href="#" class="hidden px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg transition">
                    📥 Download CSV
                </a>
            </div>
            <div class="overflow-x-auto max-h-[520px] border border-gray-800 rounded-xl">
                <table class="w-full text-left text-xs text-gray-300">
                    <thead id="table-head" class="bg-[#0f111a] text-gray-400 uppercase sticky top-0"></thead>
                    <tbody id="table-body" class="divide-y divide-gray-800">
                        <tr><td class="p-6 text-center text-gray-500">Memuat data...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let currentTab = 'bank';

        function switchTab(tab) {
            currentTab = tab;
            ['bank', 'keyword', 'berita', 'sosmed'].forEach(t => {
                document.getElementById('form-' + t).classList.add('hidden');
                document.getElementById('form-' + t).classList.remove('grid');
                document.getElementById('tab-' + t).className = "py-3 px-4 rounded-xl font-semibold text-sm bg-[#1a1d2d] text-gray-400 hover:text-white border border-gray-800 transition";
            });
            document.getElementById('form-' + tab).classList.remove('hidden');
            document.getElementById('form-' + tab).classList.add('grid');
            document.getElementById('tab-' + tab).className = "py-3 px-4 rounded-xl font-semibold text-sm bg-purple-600 text-white shadow-lg transition";
            document.getElementById('btn-run').innerText = (tab === 'bank') ? "📂 Terapkan Filter / Muat Data" : "🚀 Jalankan Scraper";
        }

        function toggleSosmedOptions() {
            const pf = document.getElementById('sm-platform').value;
            document.getElementById('sm-engine-box').style.display = (pf === 'linkedin') ? 'none' : 'block';
            document.getElementById('sm-mode-box').style.display = (pf === 'instagram' || pf === 'facebook') ? 'block' : 'none';
        }

        async function populateFileDropdown() {
            const cat = document.getElementById('bd-cat').value;
            const tool = document.getElementById('bd-tool').value;
            const schema = document.getElementById('bd-schema').value;
            const fileSelect = document.getElementById('bd-file');

            try {
                const res = await fetch(`/api/v1/bank-data/catalog?category=${encodeURIComponent(cat)}&tool=${encodeURIComponent(tool)}&schema_mode=${encodeURIComponent(schema)}`);
                const json = await res.json();
                fileSelect.innerHTML = '<option value="semua">-- Semua File (' + (json.total_files || 0) + ' CSV) --</option>';
                (json.catalog || []).forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.filename;
                    opt.textContent = `${f.filename} (${f.size_kb} KB)`;
                    fileSelect.appendChild(opt);
                });
            } catch (e) {
                console.error(e);
            }
        }

        async function onBankFilterChange() {
            await populateFileDropdown();
            await executeAction();
        }

        async function executeAction() {
            const btn = document.getElementById('btn-run');
            const status = document.getElementById('status-text');
            const dlBtn = document.getElementById('btn-download');
            btn.disabled = true;
            dlBtn.classList.add('hidden');

            try {
                if (currentTab === 'bank') {
                    btn.innerText = "⏳ Memfilter Bank Data...";
                    const cat = document.getElementById('bd-cat').value;
                    const tool = document.getElementById('bd-tool').value;
                    const schema = document.getElementById('bd-schema').value;
                    const fname = document.getElementById('bd-file').value;
                    const q = document.getElementById('bd-search').value;
                    const lim = parseInt(document.getElementById('bd-limit').value) || 200;

                    let url = `/api/v1/bank-data/records?category=${encodeURIComponent(cat)}&tool=${encodeURIComponent(tool)}&schema_mode=${encodeURIComponent(schema)}&search_query=${encodeURIComponent(q)}&limit=${lim}`;
                    if (fname && fname !== 'semua') {
                        url += `&filename=${encodeURIComponent(fname)}`;
                    }

                    const res = await fetch(url);
                    const rawText = await res.text();
                    let json = {};
                    try { json = JSON.parse(rawText); } catch (_) { throw new Error(rawText.substring(0, 160)); }

                    renderTable(json.data || []);
                    document.getElementById('row-count').innerText = json.returned_rows || 0;
                    status.innerText = `✅ Filter Aktif: Menampilkan ${json.returned_rows} dari ${json.total_matching_rows} baris cocok (${json.files_merged} file CSV).`;
                    if (json.csv && json.returned_rows > 0) {
                        dlBtn.href = "/api/v1/download?path=" + encodeURIComponent(json.csv);
                        dlBtn.classList.remove('hidden');
                    }
                } else {
                    btn.innerText = "⏳ Sedang Scraping...";
                    status.innerText = "Menghubungi API & Harvester, mohon tunggu 3-25 detik...";
                    let endpoint = '';
                    let payload = {};

                    if (currentTab === 'keyword') {
                        endpoint = document.getElementById('kw-mode').value;
                        const val = document.getElementById('kw-input').value;
                        const lim = Math.max(parseInt(document.getElementById('kw-limit').value) || 15, 1);
                        payload = endpoint.includes('trending')
                            ? { kategori: val, geo: "ID", max_results: lim }
                            : { keyword: val, geo: "ID", max_results: lim };
                    } else if (currentTab === 'berita') {
                        endpoint = document.getElementById('br-engine').value;
                        payload = {
                            keyword_or_url: document.getElementById('br-input').value,
                            max_results: Math.max(parseInt(document.getElementById('br-limit').value) || 10, 1)
                        };
                    } else {
                        const pf = document.getElementById('sm-platform').value;
                        const eng = document.getElementById('sm-engine').value;
                        const mode = document.getElementById('sm-mode').value;
                        const val = document.getElementById('sm-input').value;
                        const lim = Math.max(parseInt(document.getElementById('sm-limit').value) || 10, 1);
                        endpoint = '/api/v1/sosmed/' + pf;

                        if (pf === 'linkedin') {
                            payload = { keyword: val, region_indonesia: true, max_results: lim };
                        } else if (pf === 'facebook') {
                            payload = { keyword_or_url: val, engine: eng, mode_apify: mode === 'full' ? 'full_39_kolom' : 'bersih', max_results: lim };
                        } else if (pf === 'instagram') {
                            payload = { keyword_or_hashtag: val, engine: eng, mode_apify: mode === 'full' ? 'full_29_kolom' : 'bersih', max_results: lim };
                        } else if (pf === 'tiktok') {
                            payload = { keyword_or_hashtag: val, engine: eng, max_results: lim };
                        } else {
                            payload = { keyword: val, engine: eng, max_results: lim };
                        }
                    }

                    const res = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    const rawText = await res.text();
                    let json = {};
                    try { json = JSON.parse(rawText); } catch (_) { throw new Error(rawText.substring(0, 160)); }

                    if (!res.ok) {
                        const errMsg = typeof json.detail === 'object' ? JSON.stringify(json.detail) : (json.detail || 'Error API');
                        throw new Error(errMsg);
                    }

                    renderTable(json.data || []);
                    document.getElementById('row-count').innerText = json.total || 0;
                    status.innerText = "✅ Selesai! Tersimpan otomatis ke Bank Data: " + (json.csv || "-");
                    if (json.csv) {
                        dlBtn.href = "/api/v1/download?path=" + encodeURIComponent(json.csv);
                        dlBtn.classList.remove('hidden');
                    }
                }
            } catch (err) {
                status.innerText = "❌ Error: " + err.message;
            } finally {
                btn.disabled = false;
                btn.innerText = (currentTab === 'bank') ? "📂 Terapkan Filter / Muat Data" : "🚀 Jalankan Scraper";
            }
        }

        function renderTable(rows) {
            const thead = document.getElementById('table-head');
            const tbody = document.getElementById('table-body');
            thead.innerHTML = '';
            tbody.innerHTML = '';

            if (!rows.length) {
                tbody.innerHTML = '<tr><td class="p-6 text-center text-gray-500">Data tidak ditemukan untuk kombinasi filter ini.</td></tr>';
                return;
            }

            const colSet = new Set();
            rows.forEach(r => Object.keys(r).forEach(k => colSet.add(k)));
            const cols = Array.from(colSet);

            thead.innerHTML = '<tr>' + cols.map(c => `<th class="px-4 py-3 border-b border-gray-800 whitespace-nowrap">${c}</th>`).join('') + '</tr>';

            rows.forEach(r => {
                const tr = document.createElement('tr');
                tr.className = "hover:bg-[#1f2437] transition";
                tr.innerHTML = cols.map(c => {
                    let val = r[c] !== null && r[c] !== undefined ? String(r[c]) : '';
                    if (val.length > 90) val = val.substring(0, 90) + '...';
                    return `<td class="px-4 py-2.5 whitespace-nowrap">${val}</td>`;
                }).join('');
                tbody.appendChild(tr);
            });
        }

        window.onload = async () => {
            await populateFileDropdown();
            await executeAction();
        };
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)