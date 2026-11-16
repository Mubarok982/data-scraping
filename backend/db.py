import os, sys
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
for _p in (ROOT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os
import json
import hashlib
from datetime import datetime
from email.utils import parsedate_to_datetime

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)

load_dotenv(os.path.join(BACKEND_DIR, ".env"))
load_dotenv(os.path.join(ROOT_DIR, ".env"))


def get_db_url() -> str:
    val = os.getenv("DATABASE_URL", "") or os.getenv("SUPABASE_DB_URL", "")
    return val.strip().strip('"').strip("'")


def get_conn():
    db_url = get_db_url()
    if not db_url:
        return None
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=15)


def parse_safe_timestamp(val) -> datetime:
    if not val:
        return datetime.now()
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return datetime.now()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:19], fmt)
        except Exception:
            continue
    return datetime.now()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def ensure_source(cur, code: str, name: str, source_type: str, platform: str) -> str:
    cur.execute(
        """
        INSERT INTO core.sources (name, code, source_type, platform, status)
        VALUES (%s, %s, %s, %s, 'active')
        ON CONFLICT (code) DO UPDATE SET updated_at = now()
        RETURNING id
        """,
        (name, code, source_type, platform)
    )
    return str(cur.fetchone()["id"])


def ingest_dataset_to_supabase(
    category: str,
    tool: str,
    job_name: str,
    parameters: dict,
    rows: list[dict]
) -> dict:
    if not rows:
        return {"synced": False, "reason": "empty_rows"}

    conn = get_conn()
    if not conn:
        return {"synced": False, "reason": "DATABASE_URL belum diatur"}

    source_code = f"{tool.lower()}_{category.lower()}"[:50]
    source_name = f"{tool.upper()} ({category.upper()})"
    data_type_map = {
        "berita": "news_article",
        "keyword": "keyword",
        "trending": "trend",
        "keyword_trending": "keyword",
        "facebook": "social_post",
        "instagram": "social_post",
        "tiktok": "social_post",
        "twitter": "social_post",
        "linkedin": "social_account"
    }
    data_type = data_type_map.get(category, "generic")

    processed_count = 0
    failed_count = 0

    try:
        with conn:
            with conn.cursor() as cur:
                source_id = ensure_source(cur, source_code, source_name, "api", category)

                cur.execute(
                    """
                    INSERT INTO scraper.jobs (source_id, job_type, job_name, parameters, status, priority)
                    VALUES (%s, %s, %s, %s, 'running', 5)
                    RETURNING id
                    """,
                    (source_id, category, job_name[:150], Json(parameters))
                )
                job_id = str(cur.fetchone()["id"])

                cur.execute(
                    """
                    INSERT INTO scraper.job_executions (job_id, status, attempt_number, items_found)
                    VALUES (%s, 'running', 1, %s)
                    RETURNING id
                    """,
                    (job_id, len(rows))
                )
                execution_id = str(cur.fetchone()["id"])

                for r in rows:
                    try:
                        raw_json_str = json.dumps(r, default=str, sort_keys=True)
                        p_hash = sha256_hex(raw_json_str)

                        ext_raw_id = str(
                            r.get("link") or r.get("Link") or r.get("url")
                            or r.get("Link_Profil") or r.get("Query") or p_hash[:32]
                        )[:250]

                        cur.execute(
                            """
                            INSERT INTO scraper.raw_data
                                (execution_id, source_id, external_id, data_type, payload, payload_hash, processing_status)
                            VALUES (%s, %s, %s, %s, %s, %s, 'processed')
                            RETURNING id
                            """,
                            (execution_id, source_id, ext_raw_id, data_type, Json(r), p_hash)
                        )
                        raw_data_id = str(cur.fetchone()["id"])

                        if category == "berita":
                            url = str(r.get("link") or r.get("Link") or "").strip()
                            title = str(r.get("judul") or r.get("Judul") or "Untitled").strip()
                            content = str(r.get("isi_berita") or r.get("Isi_Berita") or "").strip()
                            author = str(r.get("penulis") or r.get("Penulis berita") or r.get("Penulis") or "Redaksi")[:250]
                            pub_at = parse_safe_timestamp(r.get("tanggal") or r.get("Tanggal"))
                            ext_id = md5_hex(url or title)
                            c_hash = sha256_hex(content or title)

                            cur.execute(
                                """
                                INSERT INTO news.articles
                                    (source_id, external_id, raw_data_id, title, url, author, summary, language, content_hash, published_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, 'id', %s, %s)
                                ON CONFLICT (source_id, external_id) DO UPDATE
                                    SET title = EXCLUDED.title, updated_at = now()
                                RETURNING id
                                """,
                                (source_id, ext_id, raw_data_id, title, url or f"https://news.local/{ext_id}", author, content[:300], c_hash, pub_at)
                            )
                            article_id = str(cur.fetchone()["id"])

                            cur.execute(
                                """
                                INSERT INTO news.article_contents (article_id, content)
                                VALUES (%s, %s)
                                ON CONFLICT (article_id) DO UPDATE SET content = EXCLUDED.content
                                """,
                                (article_id, content)
                            )

                            sent_val = r.get("sentimen_diffbot")
                            if sent_val is not None and str(sent_val) != "":
                                try:
                                    s_num = float(sent_val)
                                    s_label = "positive" if s_num > 0.05 else ("negative" if s_num < -0.05 else "neutral")
                                    conf = min(abs(s_num), 1.0)
                                except Exception:
                                    s_str = str(sent_val).lower()
                                    s_label = s_str if s_str in ("positive", "negative", "neutral", "mixed") else "neutral"
                                    conf = 0.75

                                cur.execute(
                                    """
                                    INSERT INTO analytics.sentiment_results
                                        (entity_type, entity_id, model_name, sentiment, confidence)
                                    VALUES ('news_article', %s, %s, %s, %s)
                                    """,
                                    (article_id, tool, s_label, conf)
                                )

                        elif category in ("keyword", "trending", "keyword_trending"):
                            kw_text = str(r.get("Query") or r.get("keyword") or "").strip()
                            if kw_text:
                                norm_kw = kw_text.lower()
                                try:
                                    val_num = int(float(r.get("Values") or 0))
                                except Exception:
                                    val_num = 50
                                is_trending = "kategori" in r or category == "trending" or "rising" in job_name.lower()

                                cur.execute(
                                    """
                                    INSERT INTO keyword.keywords (keyword, normalized_keyword, language)
                                    VALUES (%s, %s, 'id')
                                    ON CONFLICT (normalized_keyword, language) DO UPDATE SET updated_at = now()
                                    RETURNING id
                                    """,
                                    (kw_text[:500], norm_kw[:500])
                                )
                                kw_id = str(cur.fetchone()["id"])

                                cur.execute(
                                    """
                                    INSERT INTO keyword.keyword_sources (keyword_id, source_id, external_id, source_metadata)
                                    VALUES (%s, %s, %s, %s)
                                    ON CONFLICT (keyword_id, source_id) DO NOTHING
                                    """,
                                    (kw_id, source_id, norm_kw[:250], Json(r))
                                )

                                cur.execute(
                                    """
                                    INSERT INTO keyword.keyword_metrics (keyword_id, source_id, search_volume, metric_date, metadata)
                                    VALUES (%s, %s, %s, CURRENT_DATE, %s)
                                    ON CONFLICT (keyword_id, source_id, metric_date) DO UPDATE
                                        SET search_volume = EXCLUDED.search_volume
                                    """,
                                    (kw_id, source_id, max(val_num, 0), Json(r))
                                )

                                if is_trending:
                                    cur.execute(
                                        """
                                        INSERT INTO trend.topics (name, normalized_name, description, language)
                                        VALUES (%s, %s, %s, 'id')
                                        ON CONFLICT (normalized_name) DO UPDATE SET updated_at = now()
                                        RETURNING id
                                        """,
                                        (kw_text[:500], norm_kw[:500], str(r.get("kategori", "trending")))
                                    )
                                    topic_id = str(cur.fetchone()["id"])

                                    cur.execute(
                                        """
                                        INSERT INTO trend.snapshots (topic_id, source_id, trend_score, popularity, metadata)
                                        VALUES (%s, %s, %s, %s, %s)
                                        """,
                                        (topic_id, source_id, val_num, max(val_num, 0), Json(r))
                                    )

                        elif category == "linkedin":
                            nama = str(r.get("Nama") or "Unknown").strip()
                            prof_url = str(r.get("Link_Profil") or "").strip()
                            ext_acc_id = md5_hex(prof_url or nama)
                            conn_raw = str(r.get("Koneksi") or "0")
                            conn_digits = "".join(ch for ch in conn_raw if ch.isdigit())
                            followers = int(conn_digits) if conn_digits else 0

                            cur.execute(
                                """
                                INSERT INTO social.accounts
                                    (source_id, external_id, username, display_name, profile_url, followers_count, account_metadata)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (source_id, external_id) DO UPDATE
                                    SET display_name = EXCLUDED.display_name,
                                        account_metadata = EXCLUDED.account_metadata,
                                        updated_at = now()
                                """,
                                (source_id, ext_acc_id, ext_acc_id[:50], nama[:250], prof_url, followers, Json(r))
                            )

                        else:
                            uname = str(
                                r.get("username") or r.get("Username") or r.get("pagename")
                                or r.get("owner full name") or f"{category}_user"
                            ).strip()[:250]
                            link = str(
                                r.get("link") or r.get("Link") or r.get("url") or r.get("input url") or ""
                            ).strip()
                            teks = str(
                                r.get("teks") or r.get("Teks") or r.get("text") or r.get("caption") or ""
                            ).strip()
                            pub_at = parse_safe_timestamp(
                                r.get("tanggal") or r.get("Tanggal") or r.get("time") or r.get("timestamp")
                            )

                            acc_ext_id = md5_hex(f"{category}:{uname}")
                            cur.execute(
                                """
                                INSERT INTO social.accounts (source_id, external_id, username, display_name, profile_url)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (source_id, external_id) DO UPDATE SET updated_at = now()
                                RETURNING id
                                """,
                                (source_id, acc_ext_id, uname, uname, link)
                            )
                            account_id = str(cur.fetchone()["id"])

                            post_ext_id = str(r.get("postid") or r.get("id") or r.get("shortcode") or md5_hex(link or teks))[:250]
                            c_hash = sha256_hex(teks or link)

                            cur.execute(
                                """
                                INSERT INTO social.posts
                                    (source_id, account_id, raw_data_id, external_id, post_type, content, permalink, content_hash, published_at, post_metadata)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (source_id, external_id) DO UPDATE
                                    SET content = EXCLUDED.content, updated_at = now()
                                RETURNING id
                                """,
                                (source_id, account_id, raw_data_id, post_ext_id, category, teks, link, c_hash, pub_at, Json(r))
                            )
                            post_id = str(cur.fetchone()["id"])

                            def to_nonneg_int(v) -> int:
                                try:
                                    return max(int(float(v or 0)), 0)
                                except Exception:
                                    return 0

                            likes = to_nonneg_int(r.get("likes") or r.get("Likes") or r.get("like") or r.get("likes count"))
                            comments = to_nonneg_int(r.get("komen") or r.get("Komen") or r.get("comment") or r.get("comments") or r.get("comments count"))
                            shares = to_nonneg_int(r.get("share") or r.get("Share") or r.get("shares"))
                            views = to_nonneg_int(r.get("views count") or r.get("video Post View Count"))

                            cur.execute(
                                """
                                INSERT INTO social.post_metrics
                                    (post_id, likes_count, comments_count, shares_count, views_count, metrics_metadata)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """,
                                (post_id, likes, comments, shares, views, Json(r))
                            )

                        processed_count += 1
                    except Exception as row_err:
                        failed_count += 1
                        cur.execute(
                            """
                            INSERT INTO scraper.job_logs (execution_id, log_level, message)
                            VALUES (%s, 'ERROR', %s)
                            """,
                            (execution_id, str(row_err)[:500])
                        )

                cur.execute(
                    """
                    UPDATE scraper.job_executions
                    SET status = 'completed', items_processed = %s, items_failed = %s, finished_at = now()
                    WHERE id = %s
                    """,
                    (processed_count, failed_count, execution_id)
                )
                cur.execute("UPDATE scraper.jobs SET status = 'completed', updated_at = now() WHERE id = %s", (job_id,))

                cur.execute(
                    """
                    INSERT INTO analytics.daily_summaries (summary_date, source_id, data_type, total_records)
                    VALUES (CURRENT_DATE, %s, %s, %s)
                    ON CONFLICT (summary_date, source_id, data_type) DO UPDATE
                        SET total_records = analytics.daily_summaries.total_records + EXCLUDED.total_records
                    """,
                    (source_id, data_type, processed_count)
                )

        conn.close()
        return {
            "synced": True,
            "job_id": job_id,
            "execution_id": execution_id,
            "items_processed": processed_count,
            "items_failed": failed_count
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"synced": False, "error": str(e)}


# Alias agar huruf besar/kecil tetap dikenali
ingest_Dataset_to_supabase = ingest_dataset_to_supabase


def get_warehouse_summary_stats() -> dict:
    conn = get_conn()
    if not conn:
        return {"connected": False, "message": "DATABASE_URL belum dikonfigurasi"}

    try:
        with conn:
            with conn.cursor() as cur:
                stats = {}
                tables = [
                    ("sources", "core.sources"),
                    ("jobs", "scraper.jobs"),
                    ("raw_data", "scraper.raw_data"),
                    ("news_articles", "news.articles"),
                    ("keywords", "keyword.keywords"),
                    ("trend_snapshots", "trend.snapshots"),
                    ("social_accounts", "social.accounts"),
                    ("social_posts", "social.posts"),
                    ("sentiment_results", "analytics.sentiment_results")
                ]
                for key, tbl in tables:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {tbl}")
                    stats[key] = cur.fetchone()["cnt"]
        conn.close()
        return {"connected": True, "counts": stats}
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"connected": False, "message": str(e)}


def query_warehouse_records(
    category: str = "berita",
    search_query: str = "",
    limit: int = 200
) -> list[dict]:
    conn = get_conn()
    if not conn:
        return []

    q_like = f"%{search_query.strip()}%" if search_query and search_query.strip() else None
    rows = []

    try:
        with conn:
            with conn.cursor() as cur:
                if category == "berita":
                    sql = """
                        SELECT s.code AS source, a.published_at AS tanggal, a.author AS penulis,
                               a.title AS judul, c.content AS isi_berita, a.url AS link,
                               sr.sentiment, sr.confidence
                        FROM news.articles a
                        JOIN core.sources s ON a.source_id = s.id
                        LEFT JOIN news.article_contents c ON c.article_id = a.id
                        LEFT JOIN LATERAL (
                            SELECT sentiment, confidence FROM analytics.sentiment_results
                            WHERE entity_type = 'news_article' AND entity_id = a.id
                            ORDER BY analyzed_at DESC LIMIT 1
                        ) sr ON true
                    """
                    if q_like:
                        sql += " WHERE a.title ILIKE %s OR c.content ILIKE %s"
                        cur.execute(sql + " ORDER BY a.published_at DESC NULLS LAST LIMIT %s", (q_like, q_like, limit))
                    else:
                        cur.execute(sql + " ORDER BY a.published_at DESC NULLS LAST LIMIT %s", (limit,))
                    rows = [dict(r) for r in cur.fetchall()]

                elif category in ("facebook", "instagram", "tiktok", "twitter"):
                    sql = """
                        SELECT s.code AS source, p.post_type AS platform, p.published_at AS tanggal,
                               acc.username, p.content AS teks, p.permalink AS link,
                                COALESCE(m.likes_count, 0) AS likes,
                               COALESCE(m.comments_count, 0) AS komen,
                               COALESCE(m.shares_count, 0) AS share
                        FROM social.posts p
                        JOIN core.sources s ON p.source_id = s.id
                        LEFT JOIN social.accounts acc ON p.account_id = acc.id
                        LEFT JOIN LATERAL (
                            SELECT likes_count, comments_count, shares_count
                            FROM social.post_metrics WHERE post_id = p.id
                            ORDER BY recorded_at DESC LIMIT 1
                        ) m ON true
                        WHERE p.post_type = %s
                    """
                    if q_like:
                        sql += " AND (p.content ILIKE %s OR acc.username ILIKE %s)"
                        cur.execute(sql + " ORDER BY p.published_at DESC NULLS LAST LIMIT %s", (category, q_like, q_like, limit))
                    else:
                        cur.execute(sql + " ORDER BY p.published_at DESC NULLS LAST LIMIT %s", (category, limit))
                    rows = [dict(r) for r in cur.fetchall()]

                elif category == "linkedin":
                    sql = """
                        SELECT display_name AS "Nama",
                               account_metadata->>'Pekerjaan_Saat_Ini' AS "Pekerjaan_Saat_Ini",
                               account_metadata->>'Tempat_Kerja' AS "Tempat_Kerja",
                               account_metadata->>'Pendidikan' AS "Pendidikan",
                               account_metadata->>'Skill' AS "Skill",
                               account_metadata->>'Lokasi' AS "Lokasi",
                               followers_count AS "Koneksi",
                               profile_url AS "Link_Profil"
                        FROM social.accounts a
                        JOIN core.sources s ON a.source_id = s.id
                        WHERE s.platform = 'linkedin'
                    """
                    if q_like:
                        sql += " AND (a.display_name ILIKE %s OR a.account_metadata::text ILIKE %s)"
                        cur.execute(sql + " ORDER BY a.updated_at DESC LIMIT %s", (q_like, q_like, limit))
                    else:
                        cur.execute(sql + " ORDER BY a.updated_at DESC LIMIT %s", (limit,))
                    rows = [dict(r) for r in cur.fetchall()]

                elif category in ("keyword", "trending", "keyword_trending"):
                    sql = """
                        SELECT k.keyword AS "Query", COALESCE(km.search_volume, 0) AS "Values",
                               k.language, km.metric_date AS tanggal
                        FROM keyword.keywords k
                        LEFT JOIN LATERAL (
                            SELECT search_volume, metric_date FROM keyword.keyword_metrics
                            WHERE keyword_id = k.id ORDER BY collected_at DESC LIMIT 1
                        ) km ON true
                    """
                    if q_like:
                        sql += " WHERE k.keyword ILIKE %s"
                        cur.execute(sql + " ORDER BY km.search_volume DESC NULLS LAST LIMIT %s", (q_like, limit))
                    else:
                        cur.execute(sql + " ORDER BY km.search_volume DESC NULLS LAST LIMIT %s", (limit,))
                    rows = [dict(r) for r in cur.fetchall()]
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
    return rows

import re
from collections import Counter, defaultdict

ID_LOCATIONS = {
    "DKI Jakarta": ["jakarta", "dki", "jakpus", "jaksel", "jakbar", "jaktim", "jakut", "monas", "istana"],
    "Riau & Kepri": ["riau", "pekanbaru", "dumai", "bengkalis", "siak", "batam", "kepri", "karhutla"],
    "Jawa Barat": ["jawa barat", "jabar", "bandung", "bogor", "bekasi", "depok", "cirebon", "garut"],
    "Jawa Tengah": ["jawa tengah", "jateng", "semarang", "solo", "surakarta", "magelang", "banyumas", "tegal"],
    "Jawa Timur": ["jawa timur", "jatim", "surabaya", "malang", "sidoarjo", "kediri", "banyuwangi"],
    "Kalimantan (IKN)": ["kalimantan", "ikn", "nusantara", "balikpapan", "samarinda", "pontianak", "banjarmasin", "palangkaraya", "kalbar", "kalteng", "kaltim", "kalsel"],
    "Sumatera Selatan": ["sumatera selatan", "sumsel", "palembang", "ogan", "musi", "lahat"],
    "Sumatera Utara": ["sumatera utara", "sumut", "medan", "deli serdang", "toba", "tapanuli"],
    "Sulawesi": ["sulawesi", "makassar", "manado", "palu", "kendari", "sulsel", "sulut", "morowali"],
    "Bali & Nusa Tenggara": ["bali", "denpasar", "ntt", "ntb", "lombok", "kupang", "flores", "manggarai"],
    "Banten": ["banten", "tangerang", "tangsel", "serang", "cilegon", "merak"],
    "Papua & Maluku": ["papua", "jayapura", "merauke", "timika", "maluku", "ambon", "ternate"]
}

KNOWN_FIGURES = {
    "Prabowo Subianto": ["prabowo", "subianto", "presiden prabowo"],
    "Joko Widodo (Jokowi)": ["jokowi", "joko widodo"],
    "Gibran Rakabuming": ["gibran", "rakabuming", "wapres gibran"],
    "Roy Suryo": ["roy suryo"],
    "Sri Mulyani": ["sri mulyani", "menkeu"],
    "Bahlil Lahadalia": ["bahlil", "lahadalia"],
    "Erick Thohir": ["erick thohir"],
    "Meutya Hafid": ["meutya", "menkomdigi"],
    "Anies Baswedan": ["anies", "baswedan"],
    "Ganjar Pranowo": ["ganjar", "pranowo"],
    "Luhut Pandjaitan": ["luhut", "pandjaitan"],
    "Sufmi Dasco": ["dasco", "sufmi dasco"],
    "Mahfud MD": ["mahfud"],
    "Agus Harimurti (AHY)": ["ahy", "agus harimurti"],
    "Purbaya / Ekonomi": ["purbaya", "gubernur bi", "perry warjiyo"]
}

NEG_CUES = ["kebakaran", "karhutla", "bencana", "gempa", "banjir", "korban", "kritik", "konflik", "darurat", "rugi", "demo", "kasus", "krisis", "turun", "gagal"]
POS_CUES = ["sukses", "berhasil", "naik", "tumbuh", "inovasi", "solusi", "positif", "dukungan", "prestasi", "investasi", "kerja sama", "optimis", "mbg"]


def _classify_text_sentiment(text: str) -> str:
    t = text.lower()
    p = sum(1 for w in POS_CUES if w in t)
    n = sum(1 for w in NEG_CUES if w in t)
    if p > n:
        return "positive"
    if n > p:
        return "negative"
    return "neutral"


def get_dashboard_analytics() -> dict:
    conn = get_conn()
    texts_with_meta = []
    top_keywords = []
    platform_counts = {"Berita": 0, "Keyword & Trend": 0, "Social Media": 0, "LinkedIn": 0}
    sentiment_totals = {"positive": 0, "neutral": 0, "negative": 0}
    timeline_buckets = defaultdict(lambda: {"berita": 0, "keyword": 0, "sosmed": 0})

    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    # 1. Ambil artikel berita + waktu + sentimen
                    cur.execute("""
                        SELECT a.title, COALESCE(c.content, a.summary, '') AS body,
                               TO_CHAR(COALESCE(a.published_at, a.created_at), 'YYYY-MM-DD HH24:00') AS t_bucket
                        FROM news.articles a
                        LEFT JOIN news.article_contents c ON c.article_id = a.id
                        ORDER BY a.created_at DESC LIMIT 1500
                    """)
                    for r in cur.fetchall():
                        full_t = f"{r['title']} {r['body']}"
                        tb = r["t_bucket"] or datetime.now().strftime("%Y-%m-%d %H:00")
                        texts_with_meta.append({"text": full_t, "source": "berita", "time": tb})
                        timeline_buckets[tb]["berita"] += 1
                        platform_counts["Berita"] += 1

                    # 2. Ambil Top Keywords & Metrics
                    cur.execute("""
                        SELECT k.keyword, COALESCE(MAX(km.search_volume), 50) AS vol,
                               TO_CHAR(MAX(k.updated_at), 'YYYY-MM-DD HH24:00') AS t_bucket
                        FROM keyword.keywords k
                        LEFT JOIN keyword.keyword_metrics km ON km.keyword_id = k.id
                        GROUP BY k.id, k.keyword
                        ORDER BY vol DESC, k.updated_at DESC
                        LIMIT 300
                    """)
                    kw_rows = cur.fetchall()
                    for idx, r in enumerate(kw_rows):
                        kw_str = r["keyword"]
                        vol = int(r["vol"] or 50)
                        tb = r["t_bucket"] or datetime.now().strftime("%Y-%m-%d %H:00")
                        texts_with_meta.append({"text": kw_str, "source": "keyword", "time": tb})
                        timeline_buckets[tb]["keyword"] += 1
                        platform_counts["Keyword & Trend"] += 1
                        if idx < 12:
                            top_keywords.append({"keyword": kw_str, "volume": vol})

                    # 3. Ambil Social Posts & Accounts
                    cur.execute("""
                        SELECT p.content, p.post_type, p.post_metadata::text AS meta_txt,
                               TO_CHAR(COALESCE(p.published_at, p.created_at), 'YYYY-MM-DD HH24:00') AS t_bucket
                        FROM social.posts p
                        ORDER BY p.created_at DESC LIMIT 1500
                    """)
                    for r in cur.fetchall():
                        full_t = f"{r['content'] or ''} {r['meta_txt'] or ''}"
                        tb = r["t_bucket"] or datetime.now().strftime("%Y-%m-%d %H:00")
                        texts_with_meta.append({"text": full_t, "source": "sosmed", "time": tb})
                        timeline_buckets[tb]["sosmed"] += 1
                        platform_counts["Social Media"] += 1

                    cur.execute("""
                        SELECT display_name, account_metadata::text AS meta_txt
                        FROM social.accounts
                        LIMIT 500
                    """)
                    for r in cur.fetchall():
                        texts_with_meta.append({
                            "text": f"{r['display_name'] or ''} {r['meta_txt'] or ''}",
                            "source": "linkedin",
                            "time": datetime.now().strftime("%Y-%m-%d %H:00")
                        })
                        platform_counts["LinkedIn"] += 1
            conn.close()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    # Hitung Polarisasi Lokasi & Tokoh Ter-trending
    loc_stats = {
        loc: {"name": loc, "total": 0, "positive": 0, "neutral": 0, "negative": 0, "top_issue": Counter()}
        for loc in ID_LOCATIONS
    }
    person_stats = {
        p: {"name": p, "mentions": 0, "positive": 0, "negative": 0, "neutral": 0}
        for p in KNOWN_FIGURES
    }

    for item in texts_with_meta:
        txt = item["text"]
        txt_lower = txt.lower()
        sent = _classify_text_sentiment(txt_lower)
        sentiment_totals[sent] += 1

        # Deteksi Lokasi
        matched_any_loc = False
        for loc_name, aliases in ID_LOCATIONS.items():
            if any(a in txt_lower for a in aliases):
                matched_any_loc = True
                loc_stats[loc_name]["total"] += 1
                loc_stats[loc_name][sent] += 1
                for issue_kw in ["karhutla", "prabowo", "teknologi", "ekonomi", "gempa", "mbg", "ikn", "banjir", "politik"]:
                    if issue_kw in txt_lower:
                        loc_stats[loc_name]["top_issue"][issue_kw] += 1

        # Jika teks umum nasional tanpa nama kota spesifik, masukkan sebagian ke DKI Jakarta (Pusat Berita Nasional)
        if not matched_any_loc and any(w in txt_lower for w in ["nasional", "indonesia", "pemerintah", "menteri", "dpr", "presiden"]):
            loc_stats["DKI Jakarta"]["total"] += 1
            loc_stats["DKI Jakarta"][sent] += 1

        # Deteksi Tokoh / Orang
        for person_name, aliases in KNOWN_FIGURES.items():
            if any(a in txt_lower for a in aliases):
                person_stats[person_name]["mentions"] += 1
                person_stats[person_name][sent] += 1

    # Urutkan Lokasi berdasarkan total kemunculan
    locations_list = []
    for loc_name, st in loc_stats.items():
        if st["total"] > 0:
            dom_issue = st["top_issue"].most_common(1)[0][0] if st["top_issue"] else "umum"
            pol_index = round(((st["positive"] - st["negative"]) / max(st["total"], 1)) * 100, 1)
            locations_list.append({
                "location": loc_name,
                "total": st["total"],
                "positive": st["positive"],
                "neutral": st["neutral"],
                "negative": st["negative"],
                "polarization_index": pol_index,
                "dominant_issue": dom_issue.upper()
            })
    locations_list.sort(key=lambda x: x["total"], reverse=True)

    # Urutkan Tokoh Ter-trending
    people_list = [v for v in person_stats.values() if v["mentions"] > 0]
    people_list.sort(key=lambda x: x["mentions"], reverse=True)

    # Susun Timeline (12 titik waktu terakhir)
    sorted_times = sorted(timeline_buckets.keys())[-12:]
    timeline_list = [
        {
            "time": t[-11:],
            "berita": timeline_buckets[t]["berita"],
            "keyword": timeline_buckets[t]["keyword"],
            "sosmed": timeline_buckets[t]["sosmed"],
            "total": timeline_buckets[t]["berita"] + timeline_buckets[t]["keyword"] + timeline_buckets[t]["sosmed"]
        }
        for t in sorted_times
    ]

    return {
        "locations": locations_list[:10],
        "top_people": people_list[:10],
        "top_keywords": top_keywords[:10],
        "timeline": timeline_list,
        "sentiment_summary": sentiment_totals,
        "platform_share": platform_counts
    }
