import os, sys
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
for _p in (ROOT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os
import threading
from datetime import datetime
import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from psycopg2.extras import Json

from backend.db import get_conn, ensure_source, ingest_dataset_to_supabase

WIB = pytz.timezone("Asia/Jakarta")
CRON_EXPR = "0 0,8,16 * * *"
TARGET_ROWS_PER_RUN = 1000

_scheduler = None
_lock = threading.Lock()
_last_run_info = {
    "status": "idle",
    "last_run_wib": None,
    "total_rows_collected": 0,
    "breakdown": {}
}


def sync_schedule_record_in_db(next_run_dt=None, last_run_dt=None):
    """Mencatat jadwal cron 8 jam ke tabel scraper.job_schedules di Supabase."""
    conn = get_conn()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                source_id = ensure_source(
                    cur,
                    code="cron_auto_engine",
                    name="HuggingFace 8-Hour Auto Cron",
                    source_type="scheduler",
                    platform="multi"
                )
                cur.execute(
                    """
                    SELECT id FROM scraper.jobs
                    WHERE job_name = 'auto_cron_8h_1000_rows'
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if row:
                    job_id = str(row["id"])
                else:
                    cur.execute(
                        """
                        INSERT INTO scraper.jobs (source_id, job_type, job_name, parameters, status, priority)
                        VALUES (%s, 'scheduled_batch', 'auto_cron_8h_1000_rows', %s, 'queued', 1)
                        RETURNING id
                        """,
                        (source_id, Json({"cron": CRON_EXPR, "target_rows": TARGET_ROWS_PER_RUN, "tz": "Asia/Jakarta"}))
                    )
                    job_id = str(cur.fetchone()["id"])

                cur.execute("SELECT id FROM scraper.job_schedules WHERE job_id = %s LIMIT 1", (job_id,))
                sched = cur.fetchone()
                if sched:
                    cur.execute(
                        """
                        UPDATE scraper.job_schedules
                        SET cron_expression = %s,
                            timezone = 'Asia/Jakarta',
                            is_active = true,
                            next_run_at = COALESCE(%s, next_run_at),
                            last_run_at = COALESCE(%s, last_run_at),
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (CRON_EXPR, next_run_dt, last_run_dt, sched["id"])
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO scraper.job_schedules
                            (job_id, cron_expression, timezone, is_active, next_run_at, last_run_at)
                        VALUES (%s, %s, 'Asia/Jakarta', true, %s, %s)
                        """,
                        (job_id, CRON_EXPR, next_run_dt, last_run_dt)
                    )
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def run_batch_1000_rows(trigger_source: str = "cron_8h") -> dict:
    """
    Menjalankan engine untuk mengambil 1.000 baris data lintas kategori
    (Keyword, Trending, Berita, dan Social Media) lalu menyimpannya ke CSV & Supabase.
    """
    if not _lock.acquire(blocking=False):
        return {"status": "skipped", "reason": "Job cron sedang berjalan"}

    # Import fungsi scraper dari backend/app.py
    from backend.app import (
        scrape_keyword_search,
        scrape_trending_topics,
        scrape_berita_kombine,
        scrape_instagram,
        scrape_tiktok,
        scrape_twitter,
        scrape_facebook,
        KeywordSearchRequest,
        TrendingRequest,
        BeritaBaseRequest,
        InstagramRequest,
        TikTokRequest,
        TwitterRequest,
        FacebookRequest
    )

    now_wib = datetime.now(WIB)
    _last_run_info["status"] = "running"
    _last_run_info["last_run_wib"] = now_wib.strftime("%Y-%m-%d %H:%M:%S WIB")

    total_collected = 0
    breakdown = {"keyword": 0, "trending": 0, "berita": 0, "sosmed": 0}

    try:
        # 1. Keyword Search (~350 baris dari berbagai topik utama Indonesia)
        kw_seeds = ["karhutla", "prabowo", "ekonomi indonesia", "ai teknologi", "mbg", "energi hijau"]
        for kw in kw_seeds:
            if total_collected >= TARGET_ROWS_PER_RUN:
                break
            res = scrape_keyword_search(KeywordSearchRequest(keyword=kw, geo="ID", max_results=50))
            cnt = res.get("total", 0)
            breakdown["keyword"] += cnt
            total_collected += cnt

        # 2. Trending Topics (~350 baris dari berbagai kategori)
        trend_cats = ["teknologi", "bisnis", "politik", "olahraga", "kesehatan", "hiburan"]
        for cat in trend_cats:
            if total_collected >= TARGET_ROWS_PER_RUN:
                break
            res = scrape_trending_topics(TrendingRequest(kategori=cat, geo="ID", max_results=50))
            cnt = res.get("total", 0)
            breakdown["trending"] += cnt
            total_collected += cnt

        # 3. Berita Kombine (~200 baris)
        news_topics = ["prabowo", "teknologi", "ekonomi", "kebijakan pemerintah", "ikn", "pendidikan"]
        for top in news_topics:
            if breakdown['berita'] >= 200 or total_collected >= TARGET_ROWS_PER_RUN:
                break
            res = scrape_berita_kombine(BeritaBaseRequest(keyword_or_url=top, max_results=40))
            cnt = res.get("total", 0)
            breakdown["berita"] += cnt
            total_collected += cnt

        # 4. Social Media (~150+ baris penggenap hingga tepat/minimal 1.000 baris)
        sosmed_topics = ["indonesia", "teknologi", "prabowo", "karhutla", "ekonomi"]
        for st in sosmed_topics:
            if total_collected >= TARGET_ROWS_PER_RUN:
                break
            need = max(min(TARGET_ROWS_PER_RUN - total_collected, 40), 15)
            r_ig = scrape_instagram(InstagramRequest(keyword_or_hashtag=st, engine="diffbot", mode_apify="bersih", max_results=need))
            r_tt = scrape_tiktok(TikTokRequest(keyword_or_hashtag=st, engine="diffbot", max_results=need))
            r_tw = scrape_twitter(TwitterRequest(keyword=st, engine="diffbot", max_results=need))
            r_fb = scrape_facebook(FacebookRequest(keyword_or_url=st, engine="diffbot", mode_apify="bersih", max_results=need))
            added = r_ig.get("total", 0) + r_tt.get("total", 0) + r_tw.get("total", 0) + r_fb.get("total", 0)
            breakdown["sosmed"] += added
            total_collected += added

        finished_wib = datetime.now(WIB)
        next_run = get_next_run_wib()
        sync_schedule_record_in_db(next_run_dt=next_run, last_run_dt=finished_wib)

        _last_run_info.update({
            "status": "completed",
            "last_run_wib": finished_wib.strftime("%Y-%m-%d %H:%M:%S WIB"),
            "trigger_source": trigger_source,
            "total_rows_collected": total_collected,
            "breakdown": breakdown
        })
        send_telegram_notif(_last_run_info)
        return _last_run_info
    except Exception as e:
        _last_run_info.update({
            "status": "failed",
            "error": str(e),
            "total_rows_collected": total_collected,
            "breakdown": breakdown
        })
        send_telegram_notif(_last_run_info)
        return _last_run_info
    finally:
        _lock.release()



def send_telegram_notif(run_info: dict):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    
    status = run_info.get('status', 'unknown')
    collected = run_info.get('total_rows_collected', 0)
    bd = run_info.get('breakdown', {})
    waktu = run_info.get('last_run_wib', 'N/A')
    
    if status == 'completed':
        msg = f"✅ <b>CRON SCRAPER SELESAI</b>\n\n"
    else:
        msg = f"❌ <b>CRON SCRAPER GAGAL</b>\n\n"
        
    msg += f"⏱ <b>Waktu:</b> {waktu}\n"
    msg += f"📦 <b>Total Data:</b> {collected} baris\n\n"
    msg += f"📊 <b>Rincian Ekstraksi:</b>\n"
    msg += f" 🔍 Keyword: {bd.get('keyword', 0)}\n"
    msg += f" 🔥 Trending: {bd.get('trending', 0)}\n"
    msg += f" 📰 Berita: {bd.get('berita', 0)}\n"
    msg += f" 📱 Sosmed: {bd.get('sosmed', 0)}\n\n"
    
    if 'error' in run_info:
        msg += f"⚠️ <b>Error:</b> {run_info['error'][:200]}"
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception:
        pass


def get_next_run_wib():
    if _scheduler:
        job = _scheduler.get_job("ddc_cron_8h")
        if job and job.next_run_time:
            return job.next_run_time.astimezone(WIB)
    return None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone=WIB)
    trigger = CronTrigger(hour="0,8,16", minute=0, second=0, timezone=WIB)
    _scheduler.add_job(
        run_batch_1000_rows,
        trigger=trigger,
        id="ddc_cron_8h",
        name="Scraper 1000 Rows Every 8 Hours (08:00, 16:00, 00:00 WIB)",
        replace_existing=True,
        kwargs={"trigger_source": "apscheduler_cron_8h"}
    )
    _scheduler.start()
    sync_schedule_record_in_db(next_run_dt=get_next_run_wib())
    return _scheduler


def get_scheduler_status() -> dict:
    nxt = get_next_run_wib()
    return {
        "scheduler_active": bool(_scheduler and _scheduler.running),
        "cron_expression": CRON_EXPR,
        "schedule_hours_wib": ["08:00 WIB", "16:00 WIB", "00:00 WIB"],
        "target_rows_per_run": TARGET_ROWS_PER_RUN,
        "next_run_wib": nxt.strftime("%Y-%m-%d %H:%M:%S WIB") if nxt else None,
        "last_execution": _last_run_info
    }
