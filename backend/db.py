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
