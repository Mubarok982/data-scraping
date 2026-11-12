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

NEWSDATA_KEY = os.getenv("NEWSDATA_API_KEY", os.getenv("NEWSDATA_TOKEN", ""))
DIFFBOT_TOKEN = os.getenv("DIFFBOT_TOKEN", "")
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
BRIGHTDATA_TOKEN = os.getenv("BRIGHTDATA_TOKEN", "")
LINKEDIN_COLLECTOR_ID = os.getenv("LINKEDIN_COLLECTOR_ID", "gd_l1viktl72bvl7bjuj0")

BASE_OUTPUT_DIR = "output_csv"
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

app = Server(
    title="DDC Data Warehouse - API Scraper & Bank Data Service",
    description=(
        "REST API untuk: (0) Bank Data seluruh hasil scraping CSV, "
        "(1) Scraper Keyword & Trending, (2) Scraper Berita, dan "
        "(3) Scraper Social Media terpisah (Facebook, Instagram, TikTok, Twitter, LinkedIn)."
    ),
    version="3.2.0"
)


# =====================================================================
# DUMMY GPU ENDPOINT (SYARAT LOLOS STARTUP ZEROGPU HUGGING FACE)
# =====================================================================
@app.api(name="zerogpu_healthcheck")
@gpu_decorator
def zerogpu_healthcheck(ping: str = "ok") -> str:
    return f"ZeroGPU Ready: {ping}"


# =====================================================================
# MODUL BANK DATA (AUTO-INDEXER SEMUA CSV DI REPO & OUTPUT BARU)
# =====================================================================
def detect_csv_metadata(filepath: str) -> dict:
    norm_path = filepath.replace("\\", "/").lower()
    fname = os.path.basename(filepath)

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

    if "apify" in norm_path:
        tool = "apify"
    elif "diffbot" in norm_path:
        tool = "diffbot"
    elif "newsdata" in norm_path:
        tool = "newsdata"
    elif "brightdata" in norm_path or "linkedin" in norm_path:
        tool = "brightdata"
    else:
        tool = "kombine"

    return {
        "id": norm_path,
        "filename": fname,
        "filepath": filepath,
        "category": category,
        "tool": tool,
        "size_kb": round(os.path.getsize(filepath) / 1024, 2)
    }


def scan_bank_data(category: str = "semua", tool: str = "semua") -> list[dict]:
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
                    if tool != "semua" and meta["tool"] != tool:
                        continue
                    catalog.append(meta)

    catalog.sort(key=lambda x: x["filename"])
    return catalog


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


# =====================================================================
# 0. ENDPOINT API BANK DATA (DATA WAREHOUSE)
# =====================================================================
@app.get("/api/v1/bank-data/catalog", tags=["0. Bank Data (Data Warehouse)"])
def api_bank_data_catalog(
    category: Literal["semua", "keyword_trending", "berita", "facebook", "instagram", "tiktok", "twitter", "linkedin"] = "semua",
    tool: Literal["semua", "apify", "diffbot", "newsdata", "brightdata", "kombine"] = "semua"
):
    files = scan_bank_data(category=category, tool=tool)
    return {"status": "success", "total_files": len(files), "catalog": files}


@app.get("/api/v1/bank-data/records", tags=["0. Bank Data (Data Warehouse)"])
def api_bank_data_records(
    category: Literal["semua", "keyword_trending", "berita", "facebook", "instagram", "tiktok", "twitter", "linkedin"] = "semua",
    tool: Literal["semua", "apify", "diffbot", "newsdata", "brightdata", "kombine"] = "semua",
    filename: Optional[str] = Query(None, description="Filter nama file CSV spesifik"),
    search_query: Optional[str] = Query(None, description="Cari kata kunci di dalam isi data"),
    limit: int = Query(200, ge=1, le=5000)
):
    files = scan_bank_data(category=category, tool=tool)
    if filename:
        files = [f for f in files if f["filename"] == filename or f["id"] == filename]

    if not files:
        return {"status": "success", "files_merged": 0, "total_matching_rows": 0, "returned_rows": 0, "csv": None, "data": []}

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f["filepath"])
            df.insert(0, "_source_file", f["filename"])
            dfs.append(df)
        except Exception:
            continue

    if not dfs:
        return {"status": "success", "files_merged": 0, "total_matching_rows": 0, "returned_rows": 0, "csv": None, "data": []}

    merged = pd.concat(dfs, ignore_index=True).fillna("")
    if search_query and search_query.strip():
        q_clean = search_query.strip()
        mask = merged.astype(str).apply(lambda x: x.str.contains(q_clean, case=False, na=False)).any(axis=1)
        merged = merged[mask]

    export_path = os.path.join(BASE_OUTPUT_DIR, f"bank_data_export_{category}_{tool}.csv")
    merged.to_csv(export_path, index=False)

    records = merged.head(limit).to_dict(orient="records")
    return {
        "status": "success",
        "category": category,
        "tool": tool,
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


# =====================================================================
# HELPER SCRAPER ENGINE
# =====================================================================
def harvest_urls_by_dork(dork_query: str, max_urls: int = 10) -> list[str]:
    q = urllib.parse.quote(dork_query)
    endpoints = [
        f"https://www.bing.com/search?q={q}&cc=ID&setlang=id-ID",
        f"https://id.search.yahoo.com/search?p={q}",
        f"https://search.brave.com/search?q={q}&country=id"
    ]
    collected, seen = [], set()
    for url in endpoints:
        if len(collected) >= max_urls:
            break
        try:
            client = primp.Client(impersonate="chrome_131", verify=False, timeout=20)
            res = client.get(url)
            if res.status_code == 200 and res.text:
                tree = lxml_html.fromstring(res.text)
                for href in tree.xpath("//a/@href"):
                    decoded = urllib.parse.unquote(href)
                    if "u=a1" in decoded:
                        for b64 in re.findall(r"u=a1([a-zA-Z0-9_-]+)", decoded):
                            try:
                                pad = b64 + "=" * (-len(b64) % 4)
                                decoded = base64.urlsafe_b64decode(pad).decode("utf-8", errors="ignore")
                            except Exception:
                                pass
                    if decoded.startswith("http") and not any(
                        x in decoded for x in ["bing.com", "yahoo.com", "brave.com", "microsoft.com"]
                    ):
                        if decoded not in seen:
                            seen.add(decoded)
                            collected.append(decoded)
                            if len(collected) >= max_urls:
                                break
        except Exception:
            continue
    return collected


def _diffbot_extract_article(target_url: str) -> dict:
    if not DIFFBOT_TOKEN:
        return {}
    try:
        res = requests.get(
            "https://api.diffbot.com/v3/article",
            params={"token": DIFFBOT_TOKEN, "url": target_url},
            timeout=30
        )
        if res.status_code == 200:
            objs = res.json().get("objects", [])
            if objs:
                return objs[0]
    except Exception:
        pass
    return {}


# =====================================================================
# SCHEMAS REQUEST (PYDANTIC V2 CLEAN)
# =====================================================================
class KeywordSearchRequest(BaseModel):
    keyword: str = "karhutla"
    geo: str = "ID"
    max_results: int = Field(default=15, ge=1, le=100)


class TrendingRequest(BaseModel):
    kategori: str = "teknologi"
    geo: str = "ID"
    max_results: int = Field(default=15, ge=1, le=100)


class BeritaBaseRequest(BaseModel):
    keyword_or_url: str = "prabowo"
    max_results: int = Field(default=10, ge=1, le=200)


class FacebookRequest(BaseModel):
    keyword_or_url: str = "https://www.facebook.com/kompascom"
    engine: Literal["apify", "diffbot"] = "apify"
    mode_apify: Literal["full_39_kolom", "bersih"] = "full_39_kolom"
    max_results: int = Field(default=10, ge=1, le=100)


class InstagramRequest(BaseModel):
    keyword_or_hashtag: str = "kebakaranhutan"
    engine: Literal["apify", "diffbot"] = "apify"
    mode_apify: Literal["full_29_kolom", "bersih"] = "full_29_kolom"
    max_results: int = Field(default=10, ge=1, le=100)


class TikTokRequest(BaseModel):
    keyword_or_hashtag: str = "karhutla"
    engine: Literal["apify", "diffbot"] = "apify"
    max_results: int = Field(default=10, ge=1, le=100)


class TwitterRequest(BaseModel):
    keyword: str = "prabowo"
    engine: Literal["apify", "diffbot"] = "apify"
    max_results: int = Field(default=10, ge=1, le=100)


class LinkedInRequest(BaseModel):
    keyword: str = "Backend Developer"
    region_indonesia: bool = True
    max_results: int = Field(default=5, ge=1, le=1000)


# =====================================================================
# 1. ENDPOINT KEYWORD & TRENDING
# =====================================================================
@app.post("/api/v1/keyword/search", tags=["1. Keyword & Trending"])
def scrape_keyword_search(req: KeywordSearchRequest):
    rows = []
    if APIFY_TOKEN:
        endpoint = f"https://api.apify.com/v2/acts/apify~google-trends-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        try:
            res = requests.post(endpoint, json={"searchTerms": [req.keyword], "geo": req.geo, "maxItems": req.max_results}, timeout=45)
            if res.status_code in (200, 201):
                for item in res.json():
                    for q in item.get("relatedQueries", item.get("queries", []))[:req.max_results]:
                        q_str = q.get("query", req.keyword)
                        rows.append({
                            "Query": q_str,
                            "Values": q.get("value", 100),
                            "formattedvalue": q.get("formattedValue", "100%"),
                            "link": f"https://trends.google.com/trends/explore?geo={req.geo}&q={urllib.parse.quote(q_str)}"
                        })
        except Exception:
            pass

    if not rows:
        sug_url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl=id&gl={req.geo}&q={urllib.parse.quote(req.keyword)}"
        res = requests.get(sug_url, timeout=15)
        if res.status_code == 200:
            for idx, kw in enumerate(res.json()[1][:req.max_results]):
                val = max(100 - idx * 5, 10)
                rows.append({
                    "Query": kw,
                    "Values": val,
                    "formattedvalue": f"{val}%",
                    "link": f"https://www.google.com/search?q={urllib.parse.quote(kw)}"
                })

    csv_file = save_platform_csv(rows, "keyword", f"kueri_terkait_{req.keyword}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/keyword/trending", tags=["1. Keyword & Trending"])
def scrape_trending_topics(req: TrendingRequest):
    rows = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sug_url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl=id&gl={req.geo}&q={urllib.parse.quote('trending ' + req.kategori)}"
    res = requests.get(sug_url, timeout=15)
    if res.status_code == 200:
        for idx, item in enumerate(res.json()[1][:req.max_results]):
            rows.append({
                "Query": item,
                "Values": (req.max_results - idx) * 150,
                "formattedvalue": "Breakout" if idx < 3 else f"+{(req.max_results - idx) * 150}%",
                "kategori": req.kategori,
                "waktu_scrape": now_str,
                "link": f"https://trends.google.com/trends/explore?geo={req.geo}&q={urllib.parse.quote(item)}"
            })

    csv_file = save_platform_csv(rows, "trending", f"related_queries_rising_{req.kategori}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# 2. ENDPOINT BERITA (NEWSDATA, DIFFBOT, BRIGHTDATA, KOMBINE)
# =====================================================================
@app.post("/api/v1/berita/newsdata", tags=["2. Berita"])
def scrape_berita_newsdata(req: BeritaBaseRequest):
    if not NEWSDATA_KEY:
        raise HTTPException(status_code=400, detail="NEWSDATA_API_KEY belum diatur di Settings -> Variables and secrets")

    res = requests.get(
        "https://newsdata.io/api/1/news",
        params={"apikey": NEWSDATA_KEY, "q": req.keyword_or_url, "country": "id", "language": "id"},
        timeout=30
    )
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=res.text)

    rows = []
    for art in res.json().get("results", [])[:req.max_results]:
        creators = art.get("creator")
        penulis = ", ".join(creators) if isinstance(creators, list) else (creators or "")
        raw_content = art.get("content") or ""
        isi_berita = "" if "ONLY AVAILABLE IN PAID PLANS" in raw_content.upper() else raw_content

        rows.append({
            "tool": "Newsdata",
            "platform": "Berita",
            "tanggal": art.get("pubDate", ""),
            "sumber": art.get("source_id", ""),
            "judul": art.get("title", ""),
            "penulis": penulis,
            "isi_berita": isi_berita,
            "link": art.get("link", "")
        })

    csv_file = save_platform_csv(rows, "berita", f"newsdata_berita_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/berita/diffbot", tags=["2. Berita"])
def scrape_berita_diffbot(req: BeritaBaseRequest):
    if not DIFFBOT_TOKEN:
        raise HTTPException(status_code=400, detail="DIFFBOT_TOKEN belum diatur di Settings -> Variables and secrets")

    urls = [req.keyword_or_url] if req.keyword_or_url.startswith("http") else harvest_urls_by_dork(
        f"{req.keyword_or_url} berita site:kompas.com OR site:detik.com OR site:tempo.co", req.max_results
    )
    rows = []
    for u in urls[:req.max_results]:
        obj = _diffbot_extract_article(u)
        if obj:
            rows.append({
                "Tanggal": obj.get("date", datetime.now().strftime("%Y-%m-%d")),
                "Sumber": obj.get("siteName", ""),
                "Judul": obj.get("title", ""),
                "Penulis berita": obj.get("author", ""),
                "isi_berita": obj.get("text", ""),
                "sentimen_diffbot": obj.get("sentiment", 0.0),
                "link": u
            })

    csv_file = save_platform_csv(rows, "berita", f"diffbot_full_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/berita/brightdata", tags=["2. Berita"])
def scrape_berita_brightdata(req: BeritaBaseRequest):
    urls = [req.keyword_or_url] if req.keyword_or_url.startswith("http") else harvest_urls_by_dork(
        f"{req.keyword_or_url} berita indonesia", req.max_results
    )
    rows = []
    client = primp.Client(impersonate="chrome_131", verify=False, timeout=25)
    for u in urls[:req.max_results]:
        try:
            r = client.get(u)
            tree = lxml_html.fromstring(r.text)
            title_el = tree.xpath("//title/text()")
            paragraphs = " ".join([p.strip() for p in tree.xpath("//p//text()") if len(p.strip()) > 30])
            rows.append({
                "Tool": "Bright Data",
                "Platform": "Berita",
                "Tanggal": datetime.now().strftime("%Y-%m-%d"),
                "Penulis": "Redaksi",
                "Link": u,
                "Judul": title_el[0].strip() if title_el else req.keyword_or_url,
                "Isi_Berita": paragraphs[:4000],
                "Likes": 0,
                "Comments": 0,
                "Shares": 0
            })
        except Exception:
            continue

    csv_file = save_platform_csv(rows, "berita", f"brightdata_berita_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/berita/kombine", tags=["2. Berita"])
def scrape_berita_kombine(req: BeritaBaseRequest):
    base_resp = scrape_berita_newsdata(req)
    rows = base_resp["data"]
    for r in rows:
        if not r.get("isi_berita") and r.get("link") and DIFFBOT_TOKEN:
            obj = _diffbot_extract_article(r["link"])
            r["isi_berita"] = obj.get("text", "")
            r["sentimen_diffbot"] = obj.get("sentiment", 0.0)
            r["tool"] = "Newsdata+Diffbot"

    csv_file = save_platform_csv(rows, "berita", f"kombine_berita_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# 3. ENDPOINT SOCIAL MEDIA (FB, IG, TIKTOK, TWITTER, LINKEDIN)
# =====================================================================
@app.post("/api/v1/sosmed/facebook", tags=["3. Social Media"])
def scrape_facebook(req: FacebookRequest):
    rows = []
    if req.engine == "apify":
        if not APIFY_TOKEN:
            raise HTTPException(status_code=400, detail="APIFY_TOKEN belum diatur")
        endpoint = f"https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        target_url = req.keyword_or_url if req.keyword_or_url.startswith("http") else f"https://www.facebook.com/{req.keyword_or_url}"
        res = requests.post(endpoint, json={"startUrls": [{"url": target_url}], "resultsLimit": req.max_results}, timeout=120)
        if res.status_code in (200, 201):
            for item in res.json()[:req.max_results]:
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
    else:
        urls = [req.keyword_or_url] if req.keyword_or_url.startswith("http") else harvest_urls_by_dork(
            f"{req.keyword_or_url} site:facebook.com", req.max_results
        )
        for u in urls[:req.max_results]:
            obj = _diffbot_extract_article(u)
            rows.append({
                "tool": "Diffbot",
                "platform": "facebook",
                "tanggal": obj.get("date", datetime.now().strftime("%Y-%m-%d")),
                "username": obj.get("author", "facebook_user"),
                "link": u,
                "teks": obj.get("text", obj.get("title", "")),
                "like": 0,
                "komen": 0,
                "share": 0
            })

    csv_file = save_platform_csv(rows, "facebook", f"{req.engine}_facebook_{req.keyword_or_url}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/sosmed/instagram", tags=["3. Social Media"])
def scrape_instagram(req: InstagramRequest):
    rows = []
    clean_tag = req.keyword_or_hashtag.replace("#", "").replace(" ", "")
    if req.engine == "apify":
        if not APIFY_TOKEN:
            raise HTTPException(status_code=400, detail="APIFY_TOKEN belum diatur")
        endpoint = f"https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        res = requests.post(endpoint, json={"hashtags": [clean_tag], "resultsLimit": req.max_results}, timeout=120)
        if res.status_code in (200, 201):
            for item in res.json()[:req.max_results]:
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
    else:
        urls = harvest_urls_by_dork(f"{req.keyword_or_hashtag} site:instagram.com/p/", req.max_results)
        for u in urls[:req.max_results]:
            obj = _diffbot_extract_article(u)
            rows.append({
                "Tool": "Diffbot",
                "Platform": "Instagram",
                "Tanggal": obj.get("date", datetime.now().strftime("%Y-%m-%d")),
                "Username": obj.get("author", "instagram_user"),
                "Link": u,
                "Teks": obj.get("text", obj.get("title", "")),
                "Likes": 0,
                "Komen": 0,
                "Share": 0
            })

    csv_file = save_platform_csv(rows, "instagram", f"{req.engine}_instagram_{clean_tag}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/sosmed/tiktok", tags=["3. Social Media"])
def scrape_tiktok(req: TikTokRequest):
    rows = []
    clean_tag = req.keyword_or_hashtag.replace("#", "").replace(" ", "")
    if req.engine == "apify":
        if not APIFY_TOKEN:
            raise HTTPException(status_code=400, detail="APIFY_TOKEN belum diatur")
        endpoint = f"https://api.apify.com/v2/acts/clockworks~free-tiktok-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        res = requests.post(endpoint, json={"hashtags": [clean_tag], "resultsPerPage": req.max_results}, timeout=120)
        if res.status_code in (200, 201):
            for item in res.json()[:req.max_results]:
                rows.append({
                    "tanggal": item.get("createTimeISO", ""),
                    "username": item.get("authorMeta", {}).get("name", ""),
                    "link": item.get("webVideoUrl", ""),
                    "teks": item.get("text", ""),
                    "likes": item.get("diggCount", 0),
                    "comment": item.get("commentCount", 0),
                    "shares": item.get("shareCount", 0)
                })
    else:
        urls = harvest_urls_by_dork(f"{req.keyword_or_hashtag} site:tiktok.com", req.max_results)
        for u in urls[:req.max_results]:
            obj = _diffbot_extract_article(u)
            rows.append({
                "tool": "Diffbot",
                "platform": "tiktok",
                "tanggal": obj.get("date", datetime.now().strftime("%Y-%m-%d")),
                "username": obj.get("author", "tiktok_user"),
                "link": u,
                "teks": obj.get("text", obj.get("title", "")),
                "likes": 0,
                "komen": 0,
                "share": 0
            })

    csv_file = save_platform_csv(rows, "tiktok", f"{req.engine}_tiktok_{clean_tag}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/sosmed/twitter", tags=["3. Social Media"])
def scrape_twitter(req: TwitterRequest):
    rows = []
    if req.engine == "apify":
        if not APIFY_TOKEN:
            raise HTTPException(status_code=400, detail="APIFY_TOKEN belum diatur")
        endpoint = f"https://api.apify.com/v2/acts/apidojo~tweet-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        res = requests.post(endpoint, json={"searchTerms": [req.keyword], "maxItems": req.max_results}, timeout=120)
        if res.status_code in (200, 201):
            for item in res.json()[:req.max_results]:
                rows.append({"teks": item.get("full_text", item.get("text", ""))})
    else:
        urls = harvest_urls_by_dork(f"{req.keyword} site:twitter.com OR site:x.com", req.max_results)
        for u in urls[:req.max_results]:
            obj = _diffbot_extract_article(u)
            rows.append({
                "Tool": "Diffbot",
                "Platform": "Twitter",
                "Tanggal": obj.get("date", datetime.now().strftime("%Y-%m-%d")),
                "Username": obj.get("author", "twitter_user"),
                "Link": u,
                "Teks": obj.get("text", obj.get("title", "")),
                "Likes": 0,
                "Komen": 0,
                "Share": 0
            })

    csv_file = save_platform_csv(rows, "twitter", f"{req.engine}_twitter_{req.keyword}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


def _extract_single_linkedin_brightdata(url_target: str) -> Optional[dict]:
    time.sleep(random.uniform(1.5, 3.5))
    endpoint = "https://api.brightdata.com/datasets/v3/scrape"
    headers = {"Authorization": f"Bearer {BRIGHTDATA_TOKEN}", "Content-Type": "application/json"}
    params = {"dataset_id": LINKEDIN_COLLECTOR_ID, "format": "json"}
    try:
        res = requests.post(endpoint, headers=headers, params=params, json=[{"url": url_target}], timeout=50)
        dataset = None
        if res.status_code == 200:
            dataset = res.json()
        elif res.status_code == 202:
            snap_id = res.json().get("snapshot_id")
            snap_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snap_id}?format=json"
            for _ in range(25):
                time.sleep(10)
                poll = requests.get(snap_url, headers=headers, timeout=30)
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
    if not BRIGHTDATA_TOKEN:
        raise HTTPException(status_code=400, detail="BRIGHTDATA_TOKEN belum diatur")

    dork = f"{req.keyword} Indonesia site:id.linkedin.com/in/" if req.region_indonesia else f"{req.keyword} site:linkedin.com/in/"
    raw_urls = harvest_urls_by_dork(dork, max_urls=req.max_results * 2)
    linkedin_urls = []
    for u in raw_urls:
        m = re.search(r"https://(?:[a-z]{2,3}\.)?linkedin\.com/in/[a-zA-Z0-9_-]+", u)
        if m:
            slug = m.group(0).split("/in/")[-1].strip("/")
            clean_u = f"https://www.linkedin.com/in/{slug}"
            if clean_u not in linkedin_urls and slug not in {"dir", "pub", "login"}:
                linkedin_urls.append(clean_u)
                if len(linkedin_urls) >= req.max_results:
                    break

    rows = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_extract_single_linkedin_brightdata, u): u for u in linkedin_urls}
        for future in as_completed(futures):
            res = future.result()
            if res:
                rows.append(res)

    csv_file = save_platform_csv(rows, "linkedin", f"brightdata_linkedin_{req.keyword}")
    return {"status": "success", "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# WEB DASHBOARD PORTAL UNTUK PM (DI ROOT "/")
# =====================================================================
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
            <div id="form-bank" class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Kategori Platform / Data</label>
                    <select id="bd-cat" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="berita">Berita</option>
                        <option value="facebook">Facebook</option>
                        <option value="instagram">Instagram</option>
                        <option value="tiktok">TikTok</option>
                        <option value="twitter">Twitter / X</option>
                        <option value="linkedin">LinkedIn</option>
                        <option value="keyword_trending">Keyword & Trending</option>
                        <option value="semua">Semua Kategori (Gabungan)</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Filter Engine / Tool</label>
                    <select id="bd-tool" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                        <option value="semua">Semua Tool</option>
                        <option value="apify">Apify</option>
                        <option value="diffbot">Diffbot</option>
                        <option value="newsdata">Newsdata</option>
                        <option value="brightdata">Bright Data</option>
                        <option value="kombine">Kombine</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Cari Kata Kunci (Opsional)</label>
                    <input id="bd-search" type="text" placeholder="Contoh: prabowo, mbg, teknologi..." class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
                <div>
                    <label class="block text-xs text-gray-400 mb-1">Batas Baris Ditampilkan</label>
                    <input id="bd-limit" type="number" value="200" min="10" max="2000" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
            </div>

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
                    <input id="kw-limit" type="number" value="15" min="1" max="100" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
            </div>

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
                    <input id="br-limit" type="number" value="10" min="1" max="100" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
            </div>

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
                    <input id="sm-limit" type="number" value="10" min="1" max="100" class="w-full bg-[#0f111a] border border-gray-700 rounded-lg p-2.5 text-sm">
                </div>
            </div>

            <div class="mt-5 flex items-center justify-between">
                <div id="status-text" class="text-xs text-gray-400">Siap memuat atau mengekstrak data.</div>
                <button onclick="executeAction()" id="btn-run" class="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm rounded-xl shadow-lg transition">
                    📂 Muat Bank Data
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
            <div class="overflow-x-auto max-h-[500px] border border-gray-800 rounded-xl">
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
            document.getElementById('btn-run').innerText = (tab === 'bank') ? "📂 Muat Bank Data" : "🚀 Jalankan Scraper";
        }

        function toggleSosmedOptions() {
            const pf = document.getElementById('sm-platform').value;
            document.getElementById('sm-engine-box').style.display = (pf === 'linkedin') ? 'none' : 'block';
            document.getElementById('sm-mode-box').style.display = (pf === 'instagram' || pf === 'facebook') ? 'block' : 'none';
        }

        async function executeAction() {
            const btn = document.getElementById('btn-run');
            const status = document.getElementById('status-text');
            const dlBtn = document.getElementById('btn-download');
            btn.disabled = true;
            dlBtn.classList.add('hidden');

            try {
                if (currentTab === 'bank') {
                    btn.innerText = "⏳ Memuat Bank Data...";
                    const cat = document.getElementById('bd-cat').value;
                    const tool = document.getElementById('bd-tool').value;
                    const q = document.getElementById('bd-search').value;
                    const lim = document.getElementById('bd-limit').value;
                    const url = `/api/v1/bank-data/records?category=${encodeURIComponent(cat)}&tool=${encodeURIComponent(tool)}&search_query=${encodeURIComponent(q)}&limit=${lim}`;

                    const res = await fetch(url);
                    const json = await res.json();
                    renderTable(json.data || []);
                    document.getElementById('row-count').innerText = json.returned_rows || 0;
                    status.innerText = `✅ Bank Data: Menampilkan ${json.returned_rows} dari total ${json.total_matching_rows} baris (${json.files_merged} file CSV digabungkan).`;
                    if (json.csv) {
                        dlBtn.href = "/api/v1/download?path=" + encodeURIComponent(json.csv);
                        dlBtn.classList.remove('hidden');
                    }
                } else {
                    btn.innerText = "⏳ Sedang Scraping...";
                    status.innerText = "Menghubungi API eksternal, mohon tunggu 5-40 detik...";
                    let endpoint = '';
                    let payload = {};

                    if (currentTab === 'keyword') {
                        endpoint = document.getElementById('kw-mode').value;
                        const val = document.getElementById('kw-input').value;
                        const lim = parseInt(document.getElementById('kw-limit').value);
                        payload = endpoint.includes('trending')
                            ? { kategori: val, geo: "ID", max_results: lim }
                            : { keyword: val, geo: "ID", max_results: lim };
                    } else if (currentTab === 'berita') {
                        endpoint = document.getElementById('br-engine').value;
                        payload = {
                            keyword_or_url: document.getElementById('br-input').value,
                            max_results: parseInt(document.getElementById('br-limit').value)
                        };
                    } else {
                        const pf = document.getElementById('sm-platform').value;
                        const eng = document.getElementById('sm-engine').value;
                        const mode = document.getElementById('sm-mode').value;
                        const val = document.getElementById('sm-input').value;
                        const lim = parseInt(document.getElementById('sm-limit').value);
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
                    const json = await res.json();
                    if (!res.ok) throw new Error(json.detail || 'Error API');

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
                btn.innerText = (currentTab === 'bank') ? "📂 Muat Bank Data" : "🚀 Jalankan Scraper";
            }
        }

        function renderTable(rows) {
            const thead = document.getElementById('table-head');
            const tbody = document.getElementById('table-body');
            thead.innerHTML = '';
            tbody.innerHTML = '';

            if (!rows.length) {
                tbody.innerHTML = '<tr><td class="p-6 text-center text-gray-500">Data tidak ditemukan.</td></tr>';
                return;
            }

            const cols = Object.keys(rows[0]);
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

        window.onload = () => executeAction();
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)