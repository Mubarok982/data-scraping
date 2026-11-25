import time
import threading
from collections import OrderedDict
from typing import Dict, Any, List, Tuple

TARGET_SCHEMAS = ("scraper", "news", "keyword", "trend", "social", "analytics")

TIME_COL_CANDIDATES = {
    "created_at", "updated_at", "published_at", "scraped_at", "fetched_at",
    "collected_at", "snapshot_at", "snapshot_date", "recorded_at", "executed_at",
    "started_at", "finished_at", "next_run_at", "last_run_at", "tanggal", "date"
}

FILTER_COL_CANDIDATES = {
    "platform", "category", "source", "status", "sentiment", "label",
    "language", "geo", "location", "region", "tool", "job_id", "raw_id",
    "article_id", "keyword_id", "account_id", "post_id", "run_id"
}

TEXT_SEARCH_CANDIDATES = {
    "title", "judul", "keyword", "query", "caption", "author", "penulis", "username"
}


class TTLLRUCache:
    """Thread-safe in-memory LRU cache dengan TTL untuk endpoint analitik & arsip."""

    def __init__(self, max_entries: int = 64, max_item_bytes: int = 15 * 1024 * 1024):
        self.max_entries = max_entries
        self.max_item_bytes = max_item_bytes
        self._store: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                self.misses += 1
                return None
            exp, payload, media_type = entry
            if now > exp:
                self._store.pop(key, None)
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
            return payload, media_type

    def set(self, key: str, payload: bytes, media_type: str, ttl_seconds: int):
        if len(payload) > self.max_item_bytes:
            return
        exp = time.time() + ttl_seconds
        with self._lock:
            self._store[key] = (exp, payload, media_type)
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    def clear(self) -> int:
        with self._lock:
            n = len(self._store)
            self._store.clear()
            return n

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            total_bytes = sum(len(v[1]) for v in self._store.values())
            return {
                "entries": len(self._store),
                "max_entries": self.max_entries,
                "memory_mb": round(total_bytes / (1024 * 1024), 2),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_pct": round((self.hits / total) * 100, 1) if total else 0.0,
            }


HTTP_CACHE = TTLLRUCache(max_entries=64, max_item_bytes=15 * 1024 * 1024)

CACHED_ROUTE_TTLS = {
    "/api/v1/warehouse/analytics": 180,
    "/api/v1/bank-data/catalog": 300,
    "/api/v1/warehouse/records": 60,
    "/api/v1/bank-data/records": 90,
    "/api/v1/scheduler/status": 30,
    "/api/v1/warehouse/stats": 60,
    "/api/v1/project/records": 30,
}


def get_ttl_for_path(path: str) -> int:
    return CACHED_ROUTE_TTLS.get(path, 0)


def clear_http_cache() -> int:
    return HTTP_CACHE.clear()



def _rval(row, key: str, idx: int):
    return row[key] if isinstance(row, dict) else row[idx]


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def get_fast_table_estimates(conn) -> List[Dict[str, Any]]:
    """Ambil estimasi jumlah baris O(1) dan ukuran disk dari pg_class tanpa COUNT(*)."""
    sql = """
        SELECT
            n.nspname AS schema_name,
            c.relname AS table_name,
            GREATEST(c.reltuples::bigint, 0) AS est_rows,
            pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
            (
                SELECT count(*)
                FROM pg_index i
                WHERE i.indrelid = c.oid
            ) AS index_count
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname = ANY(%s)
        ORDER BY pg_total_relation_size(c.oid) DESC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (list(TARGET_SCHEMAS),))
        rows = cur.fetchall()
    return [
        {
            "table": f"{_rval(r, 'schema_name', 0)}.{_rval(r, 'table_name', 1)}",
            "estimated_rows": int(_rval(r, 'est_rows', 2) or 0),
            "total_size": _rval(r, 'total_size', 3),
            "index_count": int(_rval(r, 'index_count', 4) or 0),
        }
        for r in rows
    ]


def apply_10m_db_optimizations(conn) -> Dict[str, Any]:
    """
    Memasang indeks B-Tree (waktu, filter, FK) dan GIN pg_trgm (pencarian teks)
    secara idempoten pada seluruh tabel di 6 skema DDC, lalu menjalankan ANALYZE.
    """
    prev_autocommit = conn.autocommit
    conn.autocommit = True
    report = {
        "pg_trgm_enabled": False,
        "indexes_ensured": [],
        "analyzed_tables": [],
        "warnings": [],
    }

    try:
        with conn.cursor() as cur:
            # 1. Aktifkan pg_trgm untuk mempercepat ILIKE '%keyword%' pada jutaan baris
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                report["pg_trgm_enabled"] = True
            except Exception as e:
                report["warnings"].append(f"pg_trgm dilewati: {e}")

            # 2. Baca seluruh tabel & kolom aktual di 6 skema target
            cur.execute(
                """
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = ANY(%s)
                ORDER BY table_schema, table_name, ordinal_position;
                """,
                (list(TARGET_SCHEMAS),),
            )
            cols_by_table: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
            for _r in cur.fetchall():
                sch, tbl, col, dtype = _rval(_r, 'table_schema', 0), _rval(_r, 'table_name', 1), _rval(_r, 'column_name', 2), _rval(_r, 'data_type', 3)
                cols_by_table.setdefault((sch, tbl), []).append((col, dtype))

            # Ambil daftar indeks yang sudah ada dalam 1 query agar tidak membuang round-trip WAN
            cur.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = ANY(%s);",
                (list(TARGET_SCHEMAS),),
            )
            existing_indexes = {_rval(_r, 'indexname', 0) for _r in cur.fetchall()}

            # 3. Buat indeks B-Tree & GIN secara aman (hanya jika belum ada)
            for (sch, tbl), cols in cols_by_table.items():
                q_tbl = f"{_quote_ident(sch)}.{_quote_ident(tbl)}"
                for col, dtype in cols:
                    col_l = col.lower()
                    q_col = _quote_ident(col)

                    # Indeks waktu (DESC NULLS LAST untuk ORDER BY terbaru & range query)
                    if col_l in TIME_COL_CANDIDATES or "timestamp" in dtype or dtype == "date":
                        idx_name = f"idx_{sch}_{tbl}_{col}_desc"[:60]
                        if idx_name not in existing_indexes:
                            sql = f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx_name)} ON {q_tbl} ({q_col} DESC NULLS LAST);"
                            try:
                                cur.execute(sql)
                                report["indexes_ensured"].append(f"{sch}.{tbl}.{col} (btree desc)")
                            except Exception as e:
                                report["warnings"].append(f"{idx_name}: {e}")

                    # Indeks kolom filter & foreign key
                    elif col_l in FILTER_COL_CANDIDATES or col_l.endswith("_id"):
                        idx_name = f"idx_{sch}_{tbl}_{col}_bt"[:60]
                        if idx_name not in existing_indexes:
                            sql = f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx_name)} ON {q_tbl} ({q_col});"
                            try:
                                cur.execute(sql)
                                report["indexes_ensured"].append(f"{sch}.{tbl}.{col} (btree)")
                            except Exception as e:
                                report["warnings"].append(f"{idx_name}: {e}")

                    # Indeks GIN Trigram untuk pencarian teks cepat (ILIKE)
                    if report["pg_trgm_enabled"] and col_l in TEXT_SEARCH_CANDIDATES and ("char" in dtype or dtype == "text"):
                        idx_name = f"idx_{sch}_{tbl}_{col}_trgm"[:60]
                        if idx_name not in existing_indexes:
                            sql = f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx_name)} ON {q_tbl} USING gin ({q_col} gin_trgm_ops);"
                            try:
                                cur.execute(sql)
                                report["indexes_ensured"].append(f"{sch}.{tbl}.{col} (gin_trgm)")
                            except Exception as e:
                                report["warnings"].append(f"{idx_name}: {e}")

            # 4. Indeks komposit & ekspresi khusus query analitik / warehouse
            extra_indexes = [
                (
                    "idx_social_pm_engagement_desc",
                    "CREATE INDEX IF NOT EXISTS idx_social_pm_engagement_desc ON social.post_metrics ((COALESCE(likes_count,0)+COALESCE(comments_count,0)+COALESCE(shares_count,0)+COALESCE(views_count,0)+COALESCE((engagement_rate*100)::bigint,0)) DESC);"
                ),
                (
                    "idx_social_posts_type_pub_desc",
                    "CREATE INDEX IF NOT EXISTS idx_social_posts_type_pub_desc ON social.posts (post_type, published_at DESC NULLS LAST);"
                ),
                (
                    "idx_analytics_sent_ent_time_desc",
                    "CREATE INDEX IF NOT EXISTS idx_analytics_sent_ent_time_desc ON analytics.sentiment_results (entity_type, entity_id, analyzed_at DESC);"
                ),
                (
                    "idx_keyword_metrics_kw_col_desc",
                    "CREATE INDEX IF NOT EXISTS idx_keyword_metrics_kw_col_desc ON keyword.keyword_metrics (keyword_id, collected_at DESC);"
                ),
                (
                    "idx_scraper_raw_job_type_col",
                    "CREATE INDEX IF NOT EXISTS idx_scraper_raw_job_type_col ON scraper.raw_data (collected_at DESC NULLS LAST) WHERE data_type IN ('job_search', 'project_hunter', '/api/v1/project/search');"
                ),
            ]
            for idx_name, sql in extra_indexes:
                if idx_name not in existing_indexes:
                    try:
                        cur.execute(sql)
                        report["indexes_ensured"].append(f"{idx_name} (custom)")
                    except Exception as e:
                        report["warnings"].append(f"{idx_name}: {e}")

            # 5. Perbarui statistik query planner PostgreSQL pada tabel utama
            for (sch, tbl) in cols_by_table:
                q_tbl = f"{_quote_ident(sch)}.{_quote_ident(tbl)}"
                try:
                    cur.execute(f"ANALYZE {q_tbl};")
                    report["analyzed_tables"].append(f"{sch}.{tbl}")
                except Exception as e:
                    report["warnings"].append(f"ANALYZE {sch}.{tbl}: {e}")
    finally:
        conn.autocommit = prev_autocommit

    return report
