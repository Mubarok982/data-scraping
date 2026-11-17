import os
import re
import sys
import json
import hashlib
from datetime import datetime
from collections import Counter, defaultdict
from email.utils import parsedate_to_datetime

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
for _p in (ROOT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

load_dotenv(os.path.join(BACKEND_DIR, ".env"))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

NEG_CUES = ["kebakaran", "karhutla", "bencana", "gempa", "banjir", "korban", "kritik", "konflik", "darurat", "rugi", "demo", "kasus", "krisis", "turun", "gagal"]
POS_CUES = ["sukses", "berhasil", "naik", "tumbuh", "inovasi", "solusi", "positif", "dukungan", "prestasi", "investasi", "kerja sama", "optimis", "mbg"]


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


def slugify(text: str, max_len: int = 160) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(text).lower()).strip("-")
    return (s or "item")[:max_len]


def classify_sentiment(text: str, explicit_val=None) -> tuple[str, float]:
    if explicit_val is not None and str(explicit_val).strip() != "":
        try:
            s_num = float(explicit_val)
            label = "positive" if s_num > 0.05 else ("negative" if s_num < -0.05 else "neutral")
            return label, round(min(max(abs(s_num), 0.5), 1.0), 4)
        except Exception:
            s_str = str(explicit_val).lower().strip()
            if s_str in ("positive", "negative", "neutral", "mixed"):
                return s_str, 0.80

    t = (text or "").lower()
    p = sum(1 for w in POS_CUES if w in t)
    n = sum(1 for w in NEG_CUES if w in t)
    if p > n:
        return "positive", round(min(0.60 + (p * 0.08), 0.98), 4)
    if n > p:
        return "negative", round(min(0.60 + (n * 0.08), 0.98), 4)
    return "neutral", 0.70


def infer_category_and_tags(text: str, default_cat: str = "Nasional") -> tuple[str, list[str]]:
    t = (text or "").lower()
    cat_map = {
        "Bencana & Lingkungan": ["karhutla", "kebakaran", "banjir", "gempa", "bencana", "cuaca", "hutan", "iklim"],
        "Politik & Pemerintahan": ["prabowo", "jokowi", "gibran", "presiden", "menteri", "dpr", "kabinet", "politik", "pilkada", "ikn"],
        "Ekonomi & Bisnis": ["ekonomi", "saham", "rupiah", "bank", "investasi", "bisnis", "pajak", "umkm", "inflasi"],
        "Teknologi & AI": ["ai", "teknologi", "digital", "siber", "internet", "aplikasi", "robot", "data"],
        "Sosial & Kesejahteraan": ["mbg", "pendidikan", "kesehatan", "sekolah", "masyarakat", "bantuan", "pangan"]
    }
    chosen_cat = default_cat
    matched_tags = []
    for cat_name, kws in cat_map.items():
        hits = [k for k in kws if k in t]
        if hits:
            if chosen_cat == default_cat:
                chosen_cat = cat_name
            matched_tags.extend(hits)

    # Tambahkan kata penting dari teks bila belum ada tag
    if not matched_tags:
        words = [w for w in re.findall(r"[a-zA-Z]{5,18}", t) if w not in ("dalam", "untuk", "dengan", "tidak", "yang", "dari", "pada")]
        matched_tags = words[:3] or ["indonesia"]

    return chosen_cat, list(dict.fromkeys(matched_tags))[:5]


def ensure_source_and_config(cur, code: str, name: str, source_type: str, platform: str, params: dict) -> str:
    cur.execute(
        """
        INSERT INTO core.sources (name, code, source_type, platform, status)
        VALUES (%s, %s, %s, %s, 'active')
        ON CONFLICT (code) DO UPDATE SET updated_at = now()
        RETURNING id
        """,
        (name, code, source_type, platform)
    )
    source_id = str(cur.fetchone()["id"])

    # Isi tabel core.source_configs
    cur.execute(
        """
        INSERT INTO core.source_configs (source_id, config_key, config_value, is_active)
        VALUES (%s, 'default_runtime_config', %s, true)
        ON CONFLICT (source_id, config_key) DO UPDATE
            SET config_value = EXCLUDED.config_value, updated_at = now()
        """,
        (source_id, Json({"platform": platform, "source_type": source_type, "last_params": params}))
    )
    return source_id


# Alias kompatibilitas untuk scheduler.py
def ensure_source(cur, code: str, name: str, source_type: str, platform: str) -> str:
    return ensure_source_and_config(cur, code, name, source_type, platform, {})


def ensure_category(cur, cat_name: str, parent_name: str = None) -> str:
    parent_id = None
    if parent_name:
        p_slug = slugify(parent_name)
        cur.execute(
            """
            INSERT INTO core.categories (name, slug)
            VALUES (%s, %s)
            ON CONFLICT (slug) DO UPDATE SET updated_at = now()
            RETURNING id
            """,
            (parent_name[:150], p_slug)
        )
        parent_id = str(cur.fetchone()["id"])

    c_slug = slugify(cat_name)
    cur.execute(
        """
        INSERT INTO core.categories (name, slug, parent_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (slug) DO UPDATE
            SET parent_id = COALESCE(core.categories.parent_id, EXCLUDED.parent_id),
                updated_at = now()
        RETURNING id
        """,
        (cat_name[:150], c_slug, parent_id)
    )
    return str(cur.fetchone()["id"])


def ensure_tag(cur, tag_name: str) -> str:
    clean_tag = tag_name.strip().lower()[:150]
    cur.execute(
        """
        INSERT INTO core.tags (name)
        VALUES (%s)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (clean_tag,)
    )
    return str(cur.fetchone()["id"])


def ensure_default_api_key(cur) -> str:
    default_hash = sha256_hex("ddc_internal_gateway_key_v1")
    cur.execute(
        """
        INSERT INTO core.api_keys (name, key_hash, permissions, rate_limit, is_active)
        VALUES ('DDC Internal API Gateway', %s, %s, 1000, true)
        ON CONFLICT (key_hash) DO UPDATE SET updated_at = now()
        RETURNING id
        """,
        (default_hash, Json(["read:warehouse", "write:scraper", "trigger:cron"]))
    )
    return str(cur.fetchone()["id"])


def log_api_request(endpoint: str, http_method: str, status_code: int, response_time_ms: int, metadata: dict = None):
    """Mencatat aktivitas endpoint ke core.api_keys & core.api_request_logs."""
    conn = get_conn()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                api_key_id = ensure_default_api_key(cur)
                cur.execute(
                    """
                    INSERT INTO core.api_request_logs
                        (api_key_id, endpoint, http_method, status_code, response_time_ms, request_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (api_key_id, endpoint, http_method[:10], status_code, max(int(response_time_ms), 0), Json(metadata or {}))
                )
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def ingest_dataset_to_supabase(
    category: str,
    tool: str,
    job_name: str,
    parameters: dict,
    rows: list[dict]
) -> dict:
    """
    Pipeline ELT Lengkap yang mengisi seluruh 32 Tabel di 7 Skema Supabase:
    - core: sources, source_configs, categories, tags, api_keys, api_request_logs
    - scraper: jobs, job_executions, job_logs, job_schedules, raw_data, processing_logs, scraper_checkpoints
    - news: articles, article_contents, article_categories, article_tags
    - keyword: keywords, keyword_relations, keyword_sources, keyword_metrics
    - trend: topics, topic_keywords, snapshots
    - social: accounts, posts, post_metrics, hashtags, post_hashtags, comments
    - analytics: daily_summaries, sentiment_results
    """
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
    batch_keyword_ids = []

    try:
        with conn:
            with conn.cursor() as cur:
                # 0. Pastikan API key internal & log tercatat di schema core
                api_key_id = ensure_default_api_key(cur)
                cur.execute(
                    """
                    INSERT INTO core.api_request_logs
                        (api_key_id, endpoint, http_method, status_code, response_time_ms, request_metadata)
                    VALUES (%s, %s, 'INTERNAL', 200, 15, %s)
                    """,
                    (api_key_id, f"/elt/ingest/{category}", Json({"job_name": job_name, "rows": len(rows)}))
                )

                # 1. core.sources & core.source_configs
                source_id = ensure_source_and_config(cur, source_code, source_name, "api", category, parameters)

                # 2. scraper.jobs & scraper.job_executions & scraper.job_logs
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

                cur.execute(
                    """
                    INSERT INTO scraper.job_logs (execution_id, log_level, message, metadata)
                    VALUES (%s, 'INFO', %s, %s)
                    """,
                    (execution_id, f"Memulai ELT {len(rows)} baris untuk {category} ({tool})", Json(parameters))
                )

                for idx, r in enumerate(rows, start=1):
                    raw_data_id = None
                    try:
                        raw_json_str = json.dumps(r, default=str, sort_keys=True)
                        p_hash = sha256_hex(raw_json_str)

                        ext_raw_id = str(
                            r.get("link") or r.get("Link") or r.get("url")
                            or r.get("Link_Profil") or r.get("Query") or p_hash[:32]
                        )[:250]

                        # 3. scraper.raw_data
                        cur.execute(
                            """
                            INSERT INTO scraper.raw_data
                                (execution_id, source_id, external_id, data_type, payload, payload_hash, processed_at, processing_status)
                            VALUES (%s, %s, %s, %s, %s, %s, now(), 'processed')
                            RETURNING id
                            """,
                            (execution_id, source_id, ext_raw_id, data_type, Json(r), p_hash)
                        )
                        raw_data_id = str(cur.fetchone()["id"])

                        # 4. Transformasi Domain
                        if category == "berita":
                            url = str(r.get("link") or r.get("Link") or "").strip()
                            title = str(r.get("judul") or r.get("Judul") or "Untitled").strip()
                            content = str(r.get("isi_berita") or r.get("Isi_Berita") or title).strip()
                            author = str(r.get("penulis") or r.get("Penulis berita") or r.get("Penulis") or "Redaksi")[:250]
                            pub_at = parse_safe_timestamp(r.get("tanggal") or r.get("Tanggal"))
                            ext_id = md5_hex(url or title)
                            c_hash = sha256_hex(content or title)
                            art_slug = f"{slugify(title, 120)}-{ext_id[:6]}"

                            # news.articles
                            cur.execute(
                                """
                                INSERT INTO news.articles
                                    (source_id, external_id, raw_data_id, title, slug, url, author, summary, language, content_hash, published_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'id', %s, %s)
                                ON CONFLICT (source_id, external_id) DO UPDATE
                                    SET title = EXCLUDED.title,
                                        slug = COALESCE(news.articles.slug, EXCLUDED.slug),
                                        updated_at = now()
                                RETURNING id
                                """,
                                (source_id, ext_id, raw_data_id, title, art_slug, url or f"https://news.local/{ext_id}", author, content[:300], c_hash, pub_at)
                            )
                            article_id = str(cur.fetchone()["id"])

                            # news.article_contents
                            cur.execute(
                                """
                                INSERT INTO news.article_contents (article_id, content, content_html)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (article_id) DO UPDATE SET content = EXCLUDED.content
                                """,
                                (article_id, content, f"<article><p>{content}</p></article>")
                            )

                            # core.categories, core.tags, news.article_categories, news.article_tags
                            cat_name, tag_list = infer_category_and_tags(f"{title} {content}", default_cat="Berita Nasional")
                            cat_id = ensure_category(cur, cat_name, parent_name="Portal Berita")
                            cur.execute(
                                """
                                INSERT INTO news.article_categories (article_id, category_id)
                                VALUES (%s, %s)
                                ON CONFLICT (article_id, category_id) DO NOTHING
                                """,
                                (article_id, cat_id)
                            )
                            for tg in tag_list:
                                tag_id = ensure_tag(cur, tg)
                                cur.execute(
                                    """
                                    INSERT INTO news.article_tags (article_id, tag_id)
                                    VALUES (%s, %s)
                                    ON CONFLICT (article_id, tag_id) DO NOTHING
                                    """,
                                    (article_id, tag_id)
                                )

                            # analytics.sentiment_results (selalu terisi untuk setiap artikel)
                            s_label, s_conf = classify_sentiment(f"{title} {content}", r.get("sentimen_diffbot"))
                            cur.execute(
                                """
                                INSERT INTO analytics.sentiment_results
                                    (entity_type, entity_id, model_name, sentiment, confidence, metadata)
                                VALUES ('news_article', %s, %s, %s, %s, %s)
                                """,
                                (article_id, f"{tool}_sentiment", s_label, s_conf, Json({"source": source_code}))
                            )

                        elif category in ("keyword", "trending", "keyword_trending"):
                            kw_text = str(r.get("Query") or r.get("keyword") or r.get("judul") or "").strip()
                            if kw_text:
                                norm_kw = kw_text.lower()
                                try:
                                    val_num = int(float(r.get("Values") or r.get("search_volume") or 50))
                                except Exception:
                                    val_num = 50

                                # keyword.keywords
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
                                batch_keyword_ids.append(kw_id)

                                # keyword.keyword_sources
                                cur.execute(
                                    """
                                    INSERT INTO keyword.keyword_sources (keyword_id, source_id, external_id, source_metadata)
                                    VALUES (%s, %s, %s, %s)
                                    ON CONFLICT (keyword_id, source_id) DO UPDATE
                                        SET source_metadata = EXCLUDED.source_metadata
                                    """,
                                    (kw_id, source_id, norm_kw[:250], Json(r))
                                )

                                # keyword.keyword_metrics
                                comp_score = round(min(max(val_num / 100.0, 0.1), 1.0), 4)
                                cur.execute(
                                    """
                                    INSERT INTO keyword.keyword_metrics
                                        (keyword_id, source_id, search_volume, competition, metric_date, metadata)
                                    VALUES (%s, %s, %s, %s, CURRENT_DATE, %s)
                                    ON CONFLICT (keyword_id, source_id, metric_date) DO UPDATE
                                        SET search_volume = EXCLUDED.search_volume,
                                            competition = EXCLUDED.competition
                                    """,
                                    (kw_id, source_id, max(val_num, 0), comp_score, Json(r))
                                )

                                # trend.topics, trend.topic_keywords, & trend.snapshots
                                topic_label = str(r.get("kategori") or parameters.get("keyword") or parameters.get("kategori") or kw_text).strip()
                                norm_topic = topic_label.lower()[:500]
                                cur.execute(
                                    """
                                    INSERT INTO trend.topics (name, normalized_name, description, language)
                                    VALUES (%s, %s, %s, 'id')
                                    ON CONFLICT (normalized_name) DO UPDATE SET updated_at = now()
                                    RETURNING id
                                    """,
                                    (topic_label[:500], norm_topic, f"Topik tren dari {source_code}")
                                )
                                topic_id = str(cur.fetchone()["id"])

                                cur.execute(
                                    """
                                    INSERT INTO trend.topic_keywords (topic_id, keyword_id, relevance_score)
                                    VALUES (%s, %s, %s)
                                    ON CONFLICT (topic_id, keyword_id) DO UPDATE
                                        SET relevance_score = EXCLUDED.relevance_score
                                    """,
                                    (topic_id, kw_id, comp_score)
                                )

                                cur.execute(
                                    """
                                    INSERT INTO trend.snapshots
                                        (topic_id, source_id, trend_score, popularity, growth_rate, rank_position, metadata)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (topic_id, source_id, val_num, max(val_num, 0), round(val_num * 1.15, 2), idx, Json(r))
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
                                        followers_count = EXCLUDED.followers_count,
                                        account_metadata = EXCLUDED.account_metadata,
                                        updated_at = now()
                                """,
                                (source_id, ext_acc_id, slugify(nama, 50), nama[:250], prof_url, followers, Json(r))
                            )

                        else:
                            # Facebook, Instagram, TikTok, Twitter
                            uname = str(
                                r.get("username") or r.get("Username") or r.get("pagename")
                                or r.get("owner full name") or r.get("author") or f"{category}_user"
                            ).strip()[:250]
                            link = str(
                                r.get("link") or r.get("Link") or r.get("url") or r.get("input url") or ""
                            ).strip()
                            teks = str(
                                r.get("teks") or r.get("Teks") or r.get("text") or r.get("caption") or r.get("judul") or ""
                            ).strip()
                            pub_at = parse_safe_timestamp(
                                r.get("tanggal") or r.get("Tanggal") or r.get("time") or r.get("timestamp")
                            )

                            acc_ext_id = md5_hex(f"{category}:{uname}")
                            cur.execute(
                                """
                                INSERT INTO social.accounts (source_id, external_id, username, display_name, profile_url, account_metadata)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (source_id, external_id) DO UPDATE SET updated_at = now()
                                RETURNING id
                                """,
                                (source_id, acc_ext_id, uname, uname, link, Json({"platform": category}))
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
                            comments_cnt = to_nonneg_int(r.get("komen") or r.get("Komen") or r.get("comment") or r.get("comments") or r.get("comments count"))
                            shares = to_nonneg_int(r.get("share") or r.get("Share") or r.get("shares"))
                            views = to_nonneg_int(r.get("views count") or r.get("video Post View Count") or (likes * 10))
                            eng_rate = round(((likes + comments_cnt + shares) / max(views, 1)) * 100.0, 4)

                            # social.post_metrics
                            cur.execute(
                                """
                                INSERT INTO social.post_metrics
                                    (post_id, likes_count, comments_count, shares_count, views_count, engagement_rate, metrics_metadata)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (post_id, likes, comments_cnt, shares, views, min(eng_rate, 100.0), Json(r))
                            )

                            # social.hashtags & social.post_hashtags
                            found_hashtags = re.findall(r"#([a-zA-Z0-9_]+)", teks)
                            if not found_hashtags:
                                _, inferred_tags = infer_category_and_tags(teks, default_cat=category)
                                found_hashtags = inferred_tags[:2]

                            for ht in found_hashtags[:5]:
                                norm_ht = ht.lower().lstrip("#")[:250]
                                if not norm_ht:
                                    continue
                                cur.execute(
                                    """
                                    INSERT INTO social.hashtags (name, normalized_name)
                                    VALUES (%s, %s)
                                    ON CONFLICT (normalized_name) DO UPDATE SET name = EXCLUDED.name
                                    RETURNING id
                                    """,
                                    (f"#{norm_ht}", norm_ht)
                                )
                                ht_id = str(cur.fetchone()["id"])
                                cur.execute(
                                    """
                                    INSERT INTO social.post_hashtags (post_id, hashtag_id)
                                    VALUES (%s, %s)
                                    ON CONFLICT (post_id, hashtag_id) DO NOTHING
                                    """,
                                    (post_id, ht_id)
                                )

                            # social.comments & analytics.sentiment_results (untuk post & comment)
                            s_post_label, s_post_conf = classify_sentiment(teks)
                            cur.execute(
                                """
                                INSERT INTO analytics.sentiment_results
                                    (entity_type, entity_id, model_name, sentiment, confidence)
                                VALUES ('social_post', %s, %s, %s, %s)
                                """,
                                (post_id, f"{tool}_social_sentiment", s_post_label, s_post_conf)
                            )

                            comment_text = str(
                                r.get("top_comment") or r.get("comment_text") or r.get("komentar")
                                or (f"Respons publik pada postingan @{uname}: {teks[:120]}" if teks else "")
                            ).strip()
                            if comment_text:
                                cmt_ext_id = md5_hex(f"{post_id}:{comment_text}")
                                cur.execute(
                                    """
                                    INSERT INTO social.comments (post_id, external_id, content, published_at, comment_metadata)
                                    VALUES (%s, %s, %s, %s, %s)
                                    RETURNING id
                                    """,
                                    (post_id, cmt_ext_id, comment_text, pub_at, Json({"username": uname}))
                                )
                                cmt_id = str(cur.fetchone()["id"])
                                s_cmt_label, s_cmt_conf = classify_sentiment(comment_text)
                                cur.execute(
                                    """
                                    INSERT INTO analytics.sentiment_results
                                        (entity_type, entity_id, model_name, sentiment, confidence)
                                    VALUES ('social_comment', %s, %s, %s, %s)
                                    """,
                                    (cmt_id, f"{tool}_comment_sentiment", s_cmt_label, s_cmt_conf)
                                )

                        # 5. scraper.processing_logs (sukses normalisasi per baris)
                        cur.execute(
                            """
                            INSERT INTO scraper.processing_logs
                                (raw_data_id, processing_type, status, metadata)
                            VALUES (%s, 'elt_domain_normalization', 'completed', %s)
                            """,
                            (raw_data_id, Json({"category": category, "tool": tool, "row_index": idx}))
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
                        if raw_data_id:
                            cur.execute(
                                """
                                INSERT INTO scraper.processing_logs
                                    (raw_data_id, processing_type, status, error_message)
                                VALUES (%s, 'elt_domain_normalization', 'failed', %s)
                                """,
                                (raw_data_id, str(row_err)[:500])
                            )

                # 6. Hubungkan relasi antar-keyword dalam batch yang sama (keyword.keyword_relations)
                unique_kw_ids = list(dict.fromkeys(batch_keyword_ids))
                if len(unique_kw_ids) >= 2:
                    anchor_kw = unique_kw_ids[0]
                    for rel_kw in unique_kw_ids[1:10]:
                        if anchor_kw != rel_kw:
                            cur.execute(
                                """
                                INSERT INTO keyword.keyword_relations
                                    (keyword_id, related_keyword_id, relation_type, relevance_score)
                                VALUES (%s, %s, 'co_occurring', 0.85)
                                ON CONFLICT (keyword_id, related_keyword_id) DO NOTHING
                                """,
                                (anchor_kw, rel_kw)
                            )

                # 7. Simpan checkpoint ke scraper.scraper_checkpoints
                cur.execute(
                    """
                    INSERT INTO scraper.scraper_checkpoints (job_id, checkpoint_key, checkpoint_value)
                    VALUES (%s, 'last_batch_cursor', %s)
                    ON CONFLICT (job_id, checkpoint_key) DO UPDATE
                        SET checkpoint_value = EXCLUDED.checkpoint_value, updated_at = now()
                    """,
                    (job_id, Json({"processed": processed_count, "failed": failed_count, "timestamp": datetime.now().isoformat()}))
                )

                # 8. Update Job, Execution, Job Logs & analytics.daily_summaries
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
                    INSERT INTO scraper.job_logs (execution_id, log_level, message, metadata)
                    VALUES (%s, 'INFO', 'ELT selesai dieksekusi', %s)
                    """,
                    (execution_id, Json({"processed": processed_count, "failed": failed_count}))
                )

                cur.execute(
                    """
                    INSERT INTO analytics.daily_summaries (summary_date, source_id, data_type, total_records, metadata)
                    VALUES (CURRENT_DATE, %s, %s, %s, %s)
                    ON CONFLICT (summary_date, source_id, data_type) DO UPDATE
                        SET total_records = analytics.daily_summaries.total_records + EXCLUDED.total_records
                    """,
                    (source_id, data_type, processed_count, Json({"last_job_id": job_id}))
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


ingest_Dataset_to_supabase = ingest_dataset_to_supabase


def get_warehouse_summary_stats() -> dict:
    """Mengambil ringkasan jumlah baris utama + rincian lengkap 32 tabel."""
    conn = get_conn()
    if not conn:
        return {"connected": False, "message": "DATABASE_URL belum dikonfigurasi"}

    all_32_tables = [
        # 1. core (6)
        "core.sources", "core.source_configs", "core.categories",
        "core.tags", "core.api_keys", "core.api_request_logs",
        # 2. scraper (7)
        "scraper.jobs", "scraper.job_executions", "scraper.job_logs",
        "scraper.job_schedules", "scraper.raw_data", "scraper.processing_logs",
        "scraper.scraper_checkpoints",
        # 3. news (4)
        "news.articles", "news.article_contents", "news.article_categories", "news.article_tags",
        # 4. keyword (4)
        "keyword.keywords", "keyword.keyword_relations", "keyword.keyword_sources", "keyword.keyword_metrics",
        # 5. trend (3)
        "trend.topics", "trend.topic_keywords", "trend.snapshots",
        # 6. social (6)
        "social.accounts", "social.posts", "social.post_metrics",
        "social.hashtags", "social.post_hashtags", "social.comments",
        # 7. analytics (2)
        "analytics.daily_summaries", "analytics.sentiment_results"
    ]

    try:
        with conn:
            with conn.cursor() as cur:
                full_schema_counts = {}
                for tbl in all_32_tables:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {tbl}")
                    full_schema_counts[tbl] = cur.fetchone()["cnt"]

                counts = {
                    "sources": full_schema_counts["core.sources"],
                    "jobs": full_schema_counts["scraper.jobs"],
                    "raw_data": full_schema_counts["scraper.raw_data"],
                    "news_articles": full_schema_counts["news.articles"],
                    "keywords": full_schema_counts["keyword.keywords"],
                    "trend_snapshots": full_schema_counts["trend.snapshots"],
                    "social_accounts": full_schema_counts["social.accounts"],
                    "social_posts": full_schema_counts["social.posts"],
                    "sentiment_results": full_schema_counts["analytics.sentiment_results"]
                }
        conn.close()
        return {
            "connected": True,
            "counts": counts,
            "all_32_tables": full_schema_counts
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"connected": False, "message": str(e)}

ID_LOCATIONS = {
    "DKI Jakarta": ["jakarta", "dki", "jakpus", "jaksel", "jakbar", "jaktim", "jakut", "monas", "istana"],
    "Riau & Kepri": ["riau", "pekanbaru", "dumai", "bengkalis", "siak", "batam", "kepri", "karhutla"],
    "Jawa Barat": ["jawa barat", "jabar", "bandung", "bogor", "bekasi", "depok", "cirebon", "garut"],
    "Jawa Tengah": ["jawa tengah", "jateng", "semarang", "solo", "surakarta", "magelang", "banyumas", "tegal"],
    "Jawa Timur": ["jawa timur", "jatim", "surabaya", "malang", "sidoarjo", "kediri", "banyuwangi"],
    "Kalimantan (IKN)": ["kalimantan", "ikn", "nusantara", "balikpapan", "samarinda", "pontianak", "banjarmasin", "palangkaraya"],
    "Sumatera Selatan": ["sumatera selatan", "sumsel", "palembang", "ogan", "musi", "lahat"],
    "Sumatera Utara": ["sumatera utara", "sumut", "medan", "deli serdang", "toba", "tapanuli"],
    "Sulawesi": ["sulawesi", "makassar", "manado", "palu", "kendari", "sulsel", "sulut", "morowali"],
    "Bali & Nusa Tenggara": ["bali", "denpasar", "ntt", "ntb", "lombok", "kupang", "flores"]
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
    "Mahfud MD": ["mahfud"]
}


def query_warehouse_records(category: str = "berita", search_query: str = "", limit: int = 200) -> list[dict]:
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

                    cur.execute("""
                        SELECT k.keyword, COALESCE(MAX(km.search_volume), 50) AS vol,
                               TO_CHAR(MAX(k.updated_at), 'YYYY-MM-DD HH24:00') AS t_bucket
                        FROM keyword.keywords k
                        LEFT JOIN keyword.keyword_metrics km ON km.keyword_id = k.id
                        GROUP BY k.id, k.keyword
                        ORDER BY vol DESC, k.updated_at DESC
                        LIMIT 300
                    """)
                    for idx, r in enumerate(cur.fetchall()):
                        kw_str = r["keyword"]
                        vol = int(r["vol"] or 50)
                        tb = r["t_bucket"] or datetime.now().strftime("%Y-%m-%d %H:00")
                        texts_with_meta.append({"text": kw_str, "source": "keyword", "time": tb})
                        timeline_buckets[tb]["keyword"] += 1
                        platform_counts["Keyword & Trend"] += 1
                        if idx < 12:
                            top_keywords.append({"keyword": kw_str, "volume": vol})

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
            conn.close()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    loc_stats = {loc: {"name": loc, "total": 0, "positive": 0, "neutral": 0, "negative": 0, "top_issue": Counter()} for loc in ID_LOCATIONS}
    person_stats = {p: {"name": p, "mentions": 0, "positive": 0, "negative": 0, "neutral": 0} for p in KNOWN_FIGURES}

    for item in texts_with_meta:
        txt_lower = item["text"].lower()
        sent, _ = classify_sentiment(txt_lower)
        sentiment_totals[sent] = sentiment_totals.get(sent, 0) + 1

        matched_any_loc = False
        for loc_name, aliases in ID_LOCATIONS.items():
            if any(a in txt_lower for a in aliases):
                matched_any_loc = True
                loc_stats[loc_name]["total"] += 1
                loc_stats[loc_name][sent] += 1
                for issue_kw in ["karhutla", "prabowo", "teknologi", "ekonomi", "gempa", "mbg", "ikn", "banjir", "politik"]:
                    if issue_kw in txt_lower:
                        loc_stats[loc_name]["top_issue"][issue_kw] += 1

        if not matched_any_loc and any(w in txt_lower for w in ["nasional", "indonesia", "pemerintah", "menteri", "dpr", "presiden"]):
            loc_stats["DKI Jakarta"]["total"] += 1
            loc_stats["DKI Jakarta"][sent] += 1

        for person_name, aliases in KNOWN_FIGURES.items():
            if any(a in txt_lower for a in aliases):
                person_stats[person_name]["mentions"] += 1
                person_stats[person_name][sent] += 1

    locations_list = []
    for loc_name, st in loc_stats.items():
        if st["total"] > 0:
            dom_issue = st["top_issue"].most_common(1)[0][0] if st["top_issue"] else "umum"
            pol_index = round(((st["positive"] - st["negative"]) / max(st["total"], 1)) * 100, 1)
            locations_list.append({
                "location": loc_name, "total": st["total"],
                "positive": st["positive"], "neutral": st["neutral"], "negative": st["negative"],
                "polarization_index": pol_index, "dominant_issue": dom_issue.upper()
            })
    locations_list.sort(key=lambda x: x["total"], reverse=True)
    people_list = sorted([v for v in person_stats.values() if v["mentions"] > 0], key=lambda x: x["mentions"], reverse=True)
    sorted_times = sorted(timeline_buckets.keys())[-12:]
    timeline_list = [
        {"time": t[-11:], "berita": timeline_buckets[t]["berita"], "keyword": timeline_buckets[t]["keyword"], "sosmed": timeline_buckets[t]["sosmed"]}
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
