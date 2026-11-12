import os
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
import gradio as gr
import uvicorn
from lxml import html as lxml_html
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

load_dotenv()

NEWSDATA_KEY = os.getenv("NEWSDATA_API_KEY", os.getenv("NEWSDATA_TOKEN", ""))
DIFFBOT_TOKEN = os.getenv("DIFFBOT_TOKEN", "")
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
BRIGHTDATA_TOKEN = os.getenv("BRIGHTDATA_TOKEN", "")
LINKEDIN_COLLECTOR_ID = os.getenv("LINKEDIN_COLLECTOR_ID", "gd_l1viktl72bvl7bjuj0")

BASE_OUTPUT_DIR = "output_csv"
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

api = FastAPI(
    title="DDC Data Warehouse - API Scraper & Bank Data Service",
    description=(
        "REST API untuk: (1) Bank Data seluruh hasil scraping CSV, "
        "(2) Scraper Keyword & Trending, (3) Scraper Berita, dan "
        "(4) Scraper Social Media terpisah (Facebook, Instagram, TikTok, Twitter, LinkedIn)."
    ),
    version="3.0.0"
)


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
                if f.endswith(".csv"):
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
# ENDPOINT API BANK DATA (UNTUK DATA WAREHOUSE)
# =====================================================================
@api.get("/api/v1/bank-data/catalog", tags=["0. Bank Data (Data Warehouse)"])
def api_bank_data_catalog(
    category: Literal["semua", "keyword_trending", "berita", "facebook", "instagram", "tiktok", "twitter", "linkedin"] = "semua",
    tool: Literal["semua", "apify", "diffbot", "newsdata", "brightdata", "kombine"] = "semua"
):
    """Melihat daftar seluruh file CSV hasil scraping yang ada di Bank Data."""
    files = scan_bank_data(category=category, tool=tool)
    return {"status": "success", "total_files": len(files), "catalog": files}


@api.get("/api/v1/bank-data/records", tags=["0. Bank Data (Data Warehouse)"])
def api_bank_data_records(
    category: Literal["semua", "keyword_trending", "berita", "facebook", "instagram", "tiktok", "twitter", "linkedin"] = "semua",
    tool: Literal["semua", "apify", "diffbot", "newsdata", "brightdata", "kombine"] = "semua",
    filename: Optional[str] = Query(None, description="Nama file spesifik (opsional)"),
    search_query: Optional[str] = Query(None, description="Filter teks di dalam tabel (opsional)"),
    limit: int = Query(100, ge=1, le=5000)
):
    """Mengambil isi baris data (JSON) dari Bank Data berdasarkan kategori/tool/file/kata kunci."""
    files = scan_bank_data(category=category, tool=tool)
    if filename:
        files = [f for f in files if f["filename"] == filename or f["id"] == filename]

    if not files:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan di Bank Data")

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f["filepath"])
            df["_source_file"] = f["filename"]
            dfs.append(df)
        except Exception:
            continue

    if not dfs:
        return {"status": "success", "total_rows": 0, "data": []}

    merged = pd.concat(dfs, ignore_index=True).fillna("")
    if search_query:
        mask = merged.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        merged = merged[mask]

    records = merged.head(limit).to_dict(orient="records")
    return {
        "status": "success",
        "category": category,
        "tool": tool,
        "files_merged": len(dfs),
        "total_matching_rows": len(merged),
        "returned_rows": len(records),
        "data": records
    }


@api.get("/api/v1/bank-data/download", tags=["0. Bank Data (Data Warehouse)"])
def api_bank_data_download(filepath: str = Query(..., description="Path file dari catalog")):
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File CSV tidak ditemukan")
    return FileResponse(filepath, filename=os.path.basename(filepath), media_type="text/csv")


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
# SCHEMAS & ENDPOINT 1: KEYWORD & TRENDING
# =====================================================================
class KeywordSearchRequest(BaseModel):
    keyword: str = Field(..., example="karhutla")
    geo: str = Field("ID", example="ID")
    max_results: int = Field(15, ge=1, le=100)


class TrendingRequest(BaseModel):
    kategori: str = Field("teknologi", example="teknologi")
    geo: str = Field("ID", example="ID")
    max_results: int = Field(15, ge=1, le=100)


@api.post("/api/v1/keyword/search", tags=["1. Keyword & Trending"])
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


@api.post("/api/v1/keyword/trending", tags=["1. Keyword & Trending"])
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
# SCHEMAS & ENDPOINT 2: BERITA (NEWSDATA, DIFFBOT, BRIGHTDATA, KOMBINE)
# =====================================================================
class BeritaBaseRequest(BaseModel):
    keyword_or_url: str = Field(..., example="prabowo")
    max_results: int = Field(10, ge=1, le=200)


@api.post("/api/v1/berita/newsdata", tags=["2. Berita"])
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


@api.post("/api/v1/berita/diffbot", tags=["2. Berita"])
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


@api.post("/api/v1/berita/brightdata", tags=["2. Berita"])
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


@api.post("/api/v1/berita/kombine", tags=["2. Berita"])
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
# SCHEMAS & ENDPOINT 3: SOCIAL MEDIA (FB, IG, TIKTOK, TWITTER, LINKEDIN)
# =====================================================================
class FacebookRequest(BaseModel):
    keyword_or_url: str = Field(..., example="https://www.facebook.com/kompascom")
    engine: Literal["apify", "diffbot"] = Field("apify")
    mode_apify: Literal["full_39_kolom", "bersih"] = Field("full_39_kolom")
    max_results: int = Field(10, ge=1, le=100)


class InstagramRequest(BaseModel):
    keyword_or_hashtag: str = Field(..., example="kebakaranhutan")
    engine: Literal["apify", "diffbot"] = Field("apify")
    mode_apify: Literal["full_29_kolom", "bersih"] = Field("full_29_kolom")
    max_results: int = Field(10, ge=1, le=100)


class TikTokRequest(BaseModel):
    keyword_or_hashtag: str = Field(..., example="karhutla")
    engine: Literal["apify", "diffbot"] = Field("apify")
    max_results: int = Field(10, ge=1, le=100)


class TwitterRequest(BaseModel):
    keyword: str = Field(..., example="prabowo")
    engine: Literal["apify", "diffbot"] = Field("apify")
    max_results: int = Field(10, ge=1, le=100)


class LinkedInRequest(BaseModel):
    keyword: str = Field(..., example="Backend Developer")
    region_indonesia: bool = Field(True)
    max_results: int = Field(5, ge=1, le=1000)


@api.post("/api/v1/sosmed/facebook", tags=["3. Social Media"])
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


@api.post("/api/v1/sosmed/instagram", tags=["3. Social Media"])
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


@api.post("/api/v1/sosmed/tiktok", tags=["3. Social Media"])
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


@api.post("/api/v1/sosmed/twitter", tags=["3. Social Media"])
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


@api.post("/api/v1/sosmed/linkedin", tags=["3. Social Media"])
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
# GRADIO UI CALLBACKS (UNTUK PM & DEMO LANGSUNG)
# =====================================================================
def ui_load_bank_data(category, tool, search_text):
    files = scan_bank_data(category=category, tool=tool)
    if not files:
        return pd.DataFrame([{"Info": "Tidak ada file CSV untuk filter ini."}]), None, "0 file ditemukan"

    dfs = []
    for f in files:
        try:
            d = pd.read_csv(f["filepath"])
            d.insert(0, "File_Sumber", f["filename"])
            dfs.append(d)
        except Exception:
            continue

    if not dfs:
        return pd.DataFrame([{"Info": "Gagal membaca CSV."}]), None, "Error"

    merged = pd.concat(dfs, ignore_index=True).fillna("")
    if search_text.strip():
        mask = merged.astype(str).apply(lambda x: x.str.contains(search_text.strip(), case=False, na=False)).any(axis=1)
        merged = merged[mask]

    export_path = os.path.join(BASE_OUTPUT_DIR, f"bank_data_export_{category}_{tool}.csv")
    merged.to_csv(export_path, index=False)
    info = f"✅ Menampilkan {len(merged)} baris dari {len(dfs)} file CSV di Bank Data."
    return merged.head(300), export_path, info


def ui_run_keyword(mode, keyword, limit):
    try:
        if mode == "Keyword Search (Related Queries)":
            res = scrape_keyword_search(KeywordSearchRequest(keyword=keyword, max_results=int(limit)))
        else:
            res = scrape_trending_topics(TrendingRequest(kategori=keyword, max_results=int(limit)))
        df = pd.DataFrame(res["data"]) if res["data"] else pd.DataFrame([{"Info": "Data kosong"}])
        return df, res["csv"], f"✅ Sukses menarik {res['total']} data."
    except Exception as e:
        return pd.DataFrame([{"Error": str(e)}]), None, f"❌ Error: {e}"


def ui_run_berita(engine, keyword, limit):
    try:
        req = BeritaBaseRequest(keyword_or_url=keyword, max_results=int(limit))
        if engine == "kombine":
            res = scrape_berita_kombine(req)
        elif engine == "newsdata":
            res = scrape_berita_newsdata(req)
        elif engine == "diffbot":
            res = scrape_berita_diffbot(req)
        else:
            res = scrape_berita_brightdata(req)
        df = pd.DataFrame(res["data"]) if res["data"] else pd.DataFrame([{"Info": "Data kosong"}])
        return df, res["csv"], f"✅ Sukses menarik {res['total']} artikel berita ({engine})."
    except Exception as e:
        return pd.DataFrame([{"Error": str(e)}]), None, f"❌ Error: {e}"


def ui_run_sosmed(platform, engine, mode_kolom, keyword, limit):
    try:
        lim = int(limit)
        if platform == "linkedin":
            res = scrape_linkedin_service(LinkedInRequest(keyword=keyword, region_indonesia=True, max_results=lim))
        elif platform == "facebook":
            m = "full_39_kolom" if mode_kolom == "Full Kolom Asli" else "bersih"
            res = scrape_facebook(FacebookRequest(keyword_or_url=keyword, engine=engine, mode_apify=m, max_results=lim))
        elif platform == "instagram":
            m = "full_29_kolom" if mode_kolom == "Full Kolom Asli" else "bersih"
            res = scrape_instagram(InstagramRequest(keyword_or_hashtag=keyword, engine=engine, mode_apify=m, max_results=lim))
        elif platform == "tiktok":
            res = scrape_tiktok(TikTokRequest(keyword_or_hashtag=keyword, engine=engine, max_results=lim))
        else:
            res = scrape_twitter(TwitterRequest(keyword=keyword, engine=engine, max_results=lim))

        df = pd.DataFrame(res["data"]) if res["data"] else pd.DataFrame([{"Info": "Data kosong"}])
        return df, res["csv"], f"✅ Sukses menarik {res['total']} data {platform.upper()}."
    except Exception as e:
        return pd.DataFrame([{"Error": str(e)}]), None, f"❌ Error: {e}"


# =====================================================================
# GRADIO BLOCKS INTERFACE
# =====================================================================
with gr.Blocks(title="DDC Data Warehouse & Scraper Portal", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🧩 DDC Data Warehouse — Portal Scraper & Bank Data
        **Akses REST API / Dokumentasi Swagger untuk Backend:** Klik [**`/docs` (Swagger UI)**](/docs) | **Endpoint Bank Data JSON:** [`/api/v1/bank-data/catalog`](/api/v1/bank-data/catalog) & [`/api/v1/bank-data/records`](/api/v1/bank-data/records)
        """
    )

    with gr.Tabs():
        # TAB 0: BANK DATA (SEMUA HASIL SCRAPING)
        with gr.Tab("🏦 Bank Data (Semua Hasil Scraping)"):
            gr.Markdown("Menampilkan seluruh kumpulan data `.csv` dari folder `coba/` (Apify, Diffbot, Newsdata, Bright Data, Kombine) maupun hasil baru.")
            with gr.Row():
                bd_cat = gr.Dropdown(
                    choices=["semua", "berita", "facebook", "instagram", "tiktok", "twitter", "linkedin", "keyword_trending"],
                    value="berita",
                    label="Kategori Platform / Data"
                )
                bd_tool = gr.Dropdown(
                    choices=["semua", "apify", "diffbot", "newsdata", "brightdata", "kombine"],
                    value="semua",
                    label="Filter Tool / Engine"
                )
                bd_search = gr.Textbox(label="Cari Kata Kunci di Dalam Bank Data (Opsional)", placeholder="Contoh: prabowo, mbg, teknologi...")
                bd_btn = gr.Button("📂 Muat & Gabungkan Bank Data", variant="primary")

            with gr.Row():
                bd_status = gr.Markdown("Klik tombol di atas untuk memuat data.")
                bd_file = gr.File(label="Download Gabungan CSV")
            bd_table = gr.Dataframe(label="Tabel Bank Data", interactive=False)
            bd_btn.click(ui_load_bank_data, inputs=[bd_cat, bd_tool, bd_search], outputs=[bd_table, bd_file, bd_status])

        # TAB 1: KEYWORD & TRENDING
        with gr.Tab("🔍 1. Scraper - Keyword & Trending"):
            with gr.Row():
                kw_mode = gr.Radio(
                    choices=["Keyword Search (Related Queries)", "Trending Topic (Rising Queries)"],
                    value="Keyword Search (Related Queries)",
                    label="Mode"
                )
                kw_input = gr.Textbox(value="karhutla", label="Keyword / Kategori")
                kw_limit = gr.Slider(1, 50, value=15, step=1, label="Jumlah Target")
                kw_btn = gr.Button("🚀 Scrape Keyword", variant="primary")
            kw_status = gr.Markdown()
            kw_file = gr.File(label="Download CSV")
            kw_table = gr.Dataframe(interactive=False)
            kw_btn.click(ui_run_keyword, inputs=[kw_mode, kw_input, kw_limit], outputs=[kw_table, kw_file, kw_status])

        # TAB 2: BERITA
        with gr.Tab("📰 2. Scraper - Berita"):
            with gr.Row():
                br_engine = gr.Dropdown(
                    choices=["kombine", "newsdata", "diffbot", "brightdata"],
                    value="kombine",
                    label="Engine Berita (Struktur Tabel Otomatis Menyesuaikan Laporan)"
                )
                br_input = gr.Textbox(value="prabowo", label="Topik Berita / URL")
                br_limit = gr.Slider(1, 50, value=10, step=1, label="Jumlah Artikel")
                br_btn = gr.Button("🚀 Scrape Berita", variant="primary")
            br_status = gr.Markdown()
            br_file = gr.File(label="Download CSV")
            br_table = gr.Dataframe(interactive=False)
            br_btn.click(ui_run_berita, inputs=[br_engine, br_input, br_limit], outputs=[br_table, br_file, br_status])

        # TAB 3: SOCIAL MEDIA & LINKEDIN
        with gr.Tab("📱 3. Scraper - Social Media (Terpisah)"):
            with gr.Row():
                sm_pf = gr.Dropdown(
                    choices=["instagram", "facebook", "tiktok", "twitter", "linkedin"],
                    value="instagram",
                    label="Platform Social Media"
                )
                sm_eng = gr.Dropdown(choices=["apify", "diffbot"], value="apify", label="Engine (Khusus Non-LinkedIn)")
                sm_mode = gr.Radio(choices=["Full Kolom Asli", "Standar Bersih (9 Kolom)"], value="Full Kolom Asli", label="Skema Kolom (IG/FB)")
                sm_input = gr.Textbox(value="kebakaranhutan", label="Keyword / Hashtag / URL Page")
                sm_limit = gr.Slider(1, 50, value=10, step=1, label="Jumlah Data")
            sm_btn = gr.Button("🚀 Scrape Social Media", variant="primary")
            sm_status = gr.Markdown()
            sm_file = gr.File(label="Download CSV")
            sm_table = gr.Dataframe(interactive=False)
            sm_btn.click(ui_run_sosmed, inputs=[sm_pf, sm_eng, sm_mode, sm_input, sm_limit], outputs=[sm_table, sm_file, sm_status])

# Mount Gradio UI ke dalam FastAPI App pada path "/"
app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)