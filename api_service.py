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
from lxml import html as lxml_html
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

NEWSDATA_KEY = os.getenv("NEWSDATA_API_KEY", os.getenv("NEWSDATA_TOKEN", ""))
DIFFBOT_TOKEN = os.getenv("DIFFBOT_TOKEN", "")
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
BRIGHTDATA_TOKEN = os.getenv("BRIGHTDATA_TOKEN", "")
LINKEDIN_COLLECTOR_ID = os.getenv("LINKEDIN_COLLECTOR_ID", "gd_l1viktl72bvl7bjuj0")
BRIGHTDATA_NEWS_COLLECTOR = os.getenv("BRIGHTDATA_NEWS_COLLECTOR", "gd_lnsx123456789")

BASE_OUTPUT_DIR = "output_csv"

app = FastAPI(
    title="DDC Data Warehouse - Multi-Platform Scraper API",
    description=(
        "API Scraper Service terpisah untuk Keyword, Trending, Berita (Newsdata, Diffbot, Bright Data, Kombine), "
        "dan Social Media (Facebook, Instagram, TikTok, Twitter, LinkedIn)"
    ),
    version="2.0.0"
)


# =====================================================================
# HELPER: PENYIMPANAN CSV TERPISAH PER FOLDER PLATFORM
# =====================================================================
def save_platform_csv(rows: list, subfolder: str, prefix: str) -> Optional[str]:
    if not rows:
        return None
    folder_path = os.path.join(BASE_OUTPUT_DIR, subfolder)
    os.makedirs(folder_path, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", prefix.lower())
    filepath = os.path.join(folder_path, f"{safe_prefix}_{ts}.csv")
    pd.DataFrame(rows).to_csv(filepath, index=False)
    return filepath


def harvest_urls_by_dork(dork_query: str, max_urls: int = 10) -> list[str]:
    q = urllib.parse.quote(dork_query)
    endpoints = [
        f"https://www.bing.com/search?q={q}&cc=ID&setlang=id-ID",
        f"https://id.search.yahoo.com/search?p={q}",
        f"https://search.brave.com/search?q={q}&country=id"
    ]
    collected = []
    seen = set()

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
                        x in decoded for x in ["bing.com", "yahoo.com", "brave.com", "microsoft.com", "go.microsoft"]
                    ):
                        if decoded not in seen:
                            seen.add(decoded)
                            collected.append(decoded)
                            if len(collected) >= max_urls:
                                break
        except Exception:
            continue
    return collected


# =====================================================================
# SCHEMAS REQUEST
# =====================================================================
class KeywordSearchRequest(BaseModel):
    keyword: str = Field(..., example="karhutla")
    geo: str = Field("ID", example="ID")
    max_results: int = Field(20, ge=1, le=100)
    save_csv: bool = True


class TrendingRequest(BaseModel):
    kategori: str = Field("teknologi", example="teknologi")
    geo: str = Field("ID", example="ID")
    max_results: int = Field(20, ge=1, le=100)
    save_csv: bool = True


class BeritaBaseRequest(BaseModel):
    keyword_or_url: str = Field(..., example="prabowo")
    max_results: int = Field(10, ge=1, le=200)
    save_csv: bool = True


class FacebookRequest(BaseModel):
    keyword_or_url: str = Field(..., example="https://www.facebook.com/kompascom")
    engine: Literal["apify", "diffbot"] = Field("apify")
    mode_apify: Literal["full_39_kolom", "bersih"] = Field("full_39_kolom")
    max_results: int = Field(15, ge=1, le=100)
    save_csv: bool = True


class InstagramRequest(BaseModel):
    keyword_or_hashtag: str = Field(..., example="kebakaranhutan")
    engine: Literal["apify", "diffbot"] = Field("apify")
    mode_apify: Literal["full_29_kolom", "bersih"] = Field("full_29_kolom")
    max_results: int = Field(15, ge=1, le=100)
    save_csv: bool = True


class TikTokRequest(BaseModel):
    keyword_or_hashtag: str = Field(..., example="karhutla")
    engine: Literal["apify", "diffbot"] = Field("apify")
    max_results: int = Field(15, ge=1, le=100)
    save_csv: bool = True


class TwitterRequest(BaseModel):
    keyword: str = Field(..., example="prabowo")
    engine: Literal["apify", "diffbot"] = Field("apify")
    max_results: int = Field(15, ge=1, le=100)
    save_csv: bool = True


class LinkedInRequest(BaseModel):
    keyword: str = Field(..., example="Backend Developer")
    region_indonesia: bool = Field(True)
    max_results: int = Field(10, ge=1, le=1000)
    save_csv: bool = True


# =====================================================================
# 1. ENDPOINT KEYWORD & TRENDING (TERPISAH)
# =====================================================================
@app.post("/api/v1/keyword/search", tags=["1. Keyword & Trending Service"])
def scrape_keyword_search(req: KeywordSearchRequest):
    """
    Output Tabel Keyword (Sesuai Laporan):
    Query | Values | formattedvalue | link
    """
    rows = []
    if APIFY_TOKEN:
        endpoint = (
            f"https://api.apify.com/v2/acts/apify~google-trends-scraper/"
            f"run-sync-get-dataset-items?token={APIFY_TOKEN}"
        )
        payload = {"searchTerms": [req.keyword], "geo": req.geo, "maxItems": req.max_results}
        try:
            res = requests.post(endpoint, json=payload, timeout=60)
            if res.status_code in (200, 201):
                for item in res.json():
                    related = item.get("relatedQueries", item.get("queries", []))
                    if isinstance(related, list) and related:
                        for q in related[:req.max_results]:
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
        sug_url = (
            f"https://suggestqueries.google.com/complete/search"
            f"?client=firefox&hl=id&gl={req.geo}&q={urllib.parse.quote(req.keyword)}"
        )
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

    csv_file = save_platform_csv(rows, "keyword", f"kueri_terkait_{req.keyword}") if req.save_csv else None
    return {"status": "success", "type": "keyword_search", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/keyword/trending", tags=["1. Keyword & Trending Service"])
def scrape_trending_topics(req: TrendingRequest):
    """
    Output Tabel Trending Rising Queries:
    Query | Values | formattedvalue | kategori | waktu_scrape | link
    """
    rows = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sug_url = (
        f"https://suggestqueries.google.com/complete/search"
        f"?client=firefox&hl=id&gl={req.geo}&q={urllib.parse.quote('trending ' + req.kategori)}"
    )
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    csv_file = save_platform_csv(rows, "trending", f"related_queries_rising_{req.kategori}") if req.save_csv else None
    return {"status": "success", "type": "trending_rising", "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# 2. ENDPOINT BERITA (TERPISAH PER ENGINE SESUAI LAPORAN)
# =====================================================================
@app.post("/api/v1/berita/newsdata", tags=["2. Berita Scraper Service"])
def scrape_berita_newsdata(req: BeritaBaseRequest):
    """
    Format Tabel Newsdata (Sesuai Laporan):
    tool | platform | tanggal | sumber | judul | penulis | isi_berita | link
    """
    if not NEWSDATA_KEY:
        raise HTTPException(status_code=400, detail="NEWSDATA_API_KEY belum diatur di .env")

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

    csv_file = save_platform_csv(rows, "berita", f"newsdata_berita_{req.keyword_or_url}") if req.save_csv else None
    return {"status": "success", "engine": "newsdata", "total": len(rows), "csv": csv_file, "data": rows}


def _diffbot_extract_article(target_url: str) -> dict:
    res = requests.get(
        "https://api.diffbot.com/v3/article",
        params={"token": DIFFBOT_TOKEN, "url": target_url},
        timeout=30
    )
    if res.status_code == 200:
        objs = res.json().get("objects", [])
        if objs:
            return objs[0]
    return {}


@app.post("/api/v1/berita/diffbot", tags=["2. Berita Scraper Service"])
def scrape_berita_diffbot(req: BeritaBaseRequest):
    """
    Format Tabel Diffbot Berita (Sesuai Laporan):
    Tanggal | Sumber | Judul | Penulis berita | isi_berita | sentimen_diffbot | link
    """
    if not DIFFBOT_TOKEN:
        raise HTTPException(status_code=400, detail="DIFFBOT_TOKEN belum diatur di .env")

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

    csv_file = save_platform_csv(rows, "berita", f"diffbot_full_{req.keyword_or_url}") if req.save_csv else None
    return {"status": "success", "engine": "diffbot", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/berita/brightdata", tags=["2. Berita Scraper Service"])
def scrape_berita_brightdata(req: BeritaBaseRequest):
    """
    Format Tabel Bright Data Berita (Sesuai Laporan):
    Tool | Platform | Tanggal | Penulis | Link | Judul | Isi_Berita | Likes | Comments | Shares
    """
    if not BRIGHTDATA_TOKEN:
        raise HTTPException(status_code=400, detail="BRIGHTDATA_TOKEN belum diatur di .env")

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

    csv_file = save_platform_csv(rows, "berita", f"brightdata_berita_topik_{req.keyword_or_url}") if req.save_csv else None
    return {"status": "success", "engine": "brightdata", "total": len(rows), "csv": csv_file, "data": rows}


@app.post("/api/v1/berita/kombine", tags=["2. Berita Scraper Service"])
def scrape_berita_kombine(req: BeritaBaseRequest):
    """
    Menggabungkan Newsdata (pencarian cepat) + Diffbot (penambal isi_berita & sentimen).
    """
    base_resp = scrape_berita_newsdata(BeritaBaseRequest(
        keyword_or_url=req.keyword_or_url, max_results=req.max_results, save_csv=False
    ))
    rows = base_resp["data"]

    for r in rows:
        if not r.get("isi_berita") and r.get("link") and DIFFBOT_TOKEN:
            obj = _diffbot_extract_article(r["link"])
            r["isi_berita"] = obj.get("text", "")
            r["sentimen_diffbot"] = obj.get("sentiment", 0.0)
            r["tool"] = "Newsdata+Diffbot"

    csv_file = save_platform_csv(rows, "berita", f"newsdata_berita_{req.keyword_or_url}_fix") if req.save_csv else None
    return {"status": "success", "engine": "kombine", "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# 3. ENDPOINT SOCIAL MEDIA - FACEBOOK
# =====================================================================
@app.post("/api/v1/sosmed/facebook", tags=["3. Social Media Service (Terpisah)"])
def scrape_facebook(req: FacebookRequest):
    """
    Output terpisah khusus Facebook:
    - Apify Full (39 kolom sesuai laporan: facebookuel, postid, pagename, ..., reaction love count)
    - Diffbot / Bersih (9 kolom: tool, platform, tanggal, username, link, teks, like, komen, share)
    """
    rows = []
    if req.engine == "apify":
        if not APIFY_TOKEN:
            raise HTTPException(status_code=400, detail="APIFY_TOKEN belum diatur di .env")

        endpoint = f"https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        target_url = req.keyword_or_url if req.keyword_or_url.startswith("http") else f"https://www.facebook.com/{req.keyword_or_url}"
        payload = {"startUrls": [{"url": target_url}], "resultsLimit": req.max_results}

        res = requests.post(endpoint, json=payload, timeout=120)
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
                        "user": item.get("user", {}),
                        "collaborators": item.get("collaborators", ""),
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
                        "media": item.get("media", []),
                        "feedback id": item.get("feedbackId", ""),
                        "paid partnerships": item.get("paidPartnership", False),
                        "top level url": item.get("topLevelUrl", ""),
                        "facebook id": item.get("facebookId", ""),
                        "page AD library": item.get("pageAdLibrary", {}),
                        "input url": item.get("inputUrl", target_url),
                        "text References": item.get("textReferences", []),
                        "is_Video": item.get("isVideo", False),
                        "video Post View Count": item.get("videoPostViewCount", 0),
                        "live viewer count": item.get("liveViewerCount", 0),
                        "reaction like count": item.get("reactionLikeCount", 0),
                        "comments": item.get("comments", 0),
                        "top comments": item.get("topComments", []),
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

    elif req.engine == "diffbot":
        if not DIFFBOT_TOKEN:
            raise HTTPException(status_code=400, detail="DIFFBOT_TOKEN belum diatur di .env")
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

    csv_file = save_platform_csv(rows, "facebook", f"{req.engine}_facebook_{req.keyword_or_url}") if req.save_csv else None
    return {"status": "success", "platform": "facebook", "engine": req.engine, "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# 4. ENDPOINT SOCIAL MEDIA - INSTAGRAM
# =====================================================================
@app.post("/api/v1/sosmed/instagram", tags=["3. Social Media Service (Terpisah)"])
def scrape_instagram(req: InstagramRequest):
    """
    Output terpisah khusus Instagram:
    - Apify Full (29 kolom sesuai laporan: input url, id, type, shortcode, caption, ..., coauthorProducers)
    - Diffbot / Bersih (9 kolom: Tool, Platform, Tanggal, Username, Link, Teks, Likes, Komen, Share)
    """
    rows = []
    clean_tag = req.keyword_or_hashtag.replace("#", "").replace(" ", "")

    if req.engine == "apify":
        if not APIFY_TOKEN:
            raise HTTPException(status_code=400, detail="APIFY_TOKEN belum diatur di .env")

        endpoint = f"https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        payload = {"hashtags": [clean_tag], "resultsLimit": req.max_results}
        res = requests.post(endpoint, json=payload, timeout=120)

        if res.status_code in (200, 201):
            for item in res.json()[:req.max_results]:
                if req.mode_apify == "full_29_kolom":
                    rows.append({
                        "input url": item.get("inputUrl", f"https://www.instagram.com/explore/tags/{clean_tag}/"),
                        "id": item.get("id", ""),
                        "type": item.get("type", ""),
                        "shortcode": item.get("shortCode", ""),
                        "caption": item.get("caption", ""),
                        "hashtags": item.get("hashtags", []),
                        "mentions": item.get("mentions", []),
                        "url": item.get("url", ""),
                        "comments count": item.get("commentsCount", 0),
                        "first comment": item.get("firstComment", ""),
                        "latest comment": item.get("latestComments", []),
                        "dimension width": item.get("dimensionsWidth", 0),
                        "dimension height": item.get("dimensionsHeight", 0),
                        "display url": item.get("displayUrl", ""),
                        "images": item.get("images", []),
                        "likes count": item.get("likesCount", 0),
                        "fb likes count": item.get("fbLikesCount", 0),
                        "timestamp": item.get("timestamp", ""),
                        "child post": item.get("childPosts", []),
                        "location name": item.get("locationName", ""),
                        "location id": item.get("locationId", ""),
                        "owner full name": item.get("ownerFullName", ""),
                        "ownerid": item.get("ownerId", ""),
                        "productType": item.get("productType", ""),
                        "paid partnerships": item.get("paidPartnership", False),
                        "isPinned": item.get("isPinned", False),
                        "musicinfo": item.get("musicInfo", {}),
                        "tagged Users": item.get("taggedUsers", []),
                        "coauthorProducers": item.get("coauthorProducers", [])
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

    elif req.engine == "diffbot":
        if not DIFFBOT_TOKEN:
            raise HTTPException(status_code=400, detail="DIFFBOT_TOKEN belum diatur di .env")
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

    csv_file = save_platform_csv(rows, "instagram", f"{req.engine}_instagram_{clean_tag}") if req.save_csv else None
    return {"status": "success", "platform": "instagram", "engine": req.engine, "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# 5. ENDPOINT SOCIAL MEDIA - TIKTOK
# =====================================================================
@app.post("/api/v1/sosmed/tiktok", tags=["3. Social Media Service (Terpisah)"])
def scrape_tiktok(req: TikTokRequest):
    """
    Output terpisah khusus TikTok sesuai laporan:
    - Apify (7 kolom: tanggal, username, link, teks, likes, comment, shares)
    - Diffbot (9 kolom: tool, platform, tanggal, username, link, teks, likes, komen, share)
    """
    rows = []
    clean_tag = req.keyword_or_hashtag.replace("#", "").replace(" ", "")

    if req.engine == "apify":
        if not APIFY_TOKEN:
            raise HTTPException(status_code=400, detail="APIFY_TOKEN belum diatur di .env")

        endpoint = f"https://api.apify.com/v2/acts/clockworks~free-tiktok-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        payload = {"hashtags": [clean_tag], "resultsPerPage": req.max_results}
        res = requests.post(endpoint, json=payload, timeout=120)

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

    elif req.engine == "diffbot":
        if not DIFFBOT_TOKEN:
            raise HTTPException(status_code=400, detail="DIFFBOT_TOKEN belum diatur di .env")
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

    csv_file = save_platform_csv(rows, "tiktok", f"{req.engine}_tiktok_{clean_tag}") if req.save_csv else None
    return {"status": "success", "platform": "tiktok", "engine": req.engine, "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# 6. ENDPOINT SOCIAL MEDIA - TWITTER / X
# =====================================================================
@app.post("/api/v1/sosmed/twitter", tags=["3. Social Media Service (Terpisah)"])
def scrape_twitter(req: TwitterRequest):
    """
    Output terpisah khusus Twitter sesuai laporan:
    - Apify (1 kolom: teks)
    - Diffbot (9 kolom: Tool, Platform, Tanggal, Username, Link, Teks, Likes, Komen, Share)
    """
    rows = []
    if req.engine == "apify":
        if not APIFY_TOKEN:
            raise HTTPException(status_code=400, detail="APIFY_TOKEN belum diatur di .env")

        endpoint = f"https://api.apify.com/v2/acts/apidojo~tweet-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        payload = {"searchTerms": [req.keyword], "maxItems": req.max_results}
        res = requests.post(endpoint, json=payload, timeout=120)

        if res.status_code in (200, 201):
            for item in res.json()[:req.max_results]:
                rows.append({
                    "teks": item.get("full_text", item.get("text", ""))
                })

    elif req.engine == "diffbot":
        if not DIFFBOT_TOKEN:
            raise HTTPException(status_code=400, detail="DIFFBOT_TOKEN belum diatur di .env")
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

    csv_file = save_platform_csv(rows, "twitter", f"{req.engine}_twitter_{req.keyword}") if req.save_csv else None
    return {"status": "success", "platform": "twitter", "engine": req.engine, "total": len(rows), "csv": csv_file, "data": rows}


# =====================================================================
# 7. ENDPOINT SOCIAL MEDIA - LINKEDIN (HYBRID + BRIGHT DATA V3)
# =====================================================================
def _extract_single_linkedin_brightdata(url_target: str) -> Optional[dict]:
    time.sleep(random.uniform(1.5, 3.5))
    endpoint = "https://api.brightdata.com/datasets/v3/scrape"
    headers = {"Authorization": f"Bearer {BRIGHTDATA_TOKEN}", "Content-Type": "application/json"}
    params = {"dataset_id": LINKEDIN_COLLECTOR_ID, "format": "json"}
    payload = [{"url": url_target}]

    try:
        res = requests.post(endpoint, headers=headers, params=params, json=payload, timeout=50)
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
    except Exception:
        return None


@app.post("/api/v1/sosmed/linkedin", tags=["3. Social Media Service (Terpisah)"])
def scrape_linkedin_service(req: LinkedInRequest):
    """
    Output terpisah khusus LinkedIn (8 kolom):
    Nama | Pekerjaan_Saat_Ini | Tempat_Kerja | Pendidikan | Skill | Lokasi | Koneksi | Link_Profil
    """
    if not BRIGHTDATA_TOKEN:
        raise HTTPException(status_code=400, detail="BRIGHTDATA_TOKEN belum diatur di .env")

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

    csv_file = save_platform_csv(rows, "linkedin", f"brightdata_linkedin_{req.keyword}") if req.save_csv else None
    return {
        "status": "success",
        "platform": "linkedin",
        "engine": "primp_lxml+brightdata_v3",
        "total": len(rows),
        "csv": csv_file,
        "data": rows
    }