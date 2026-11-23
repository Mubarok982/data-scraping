import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

DASHBOARD_URL = "https://huggingface.co/spaces/rizqy123/ddc-scraper-portal"
DEFAULT_CHATTIME_URL = (
    "https://chattime.geekgarden.my.id/api/webhooks/"
    "50deafeb-3b2b-4643-b32e-f18aec60c013/"
    "HPCi5za28Lr6abMKbBq0RPhel0c1FUMpbKYkrREqbvXCLUNlxJTs_t10O4kQzVBD"
)


def _load_env_file():
    """Muat .env tanpa menimpa secret yang sudah di-set di OS/Hugging Face."""
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
        return
    except Exception:
        pass
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get_config():
    _load_env_file()
    return {
        "chattime_url": os.getenv("CHATTIME_WEBHOOK_URL", "").strip() or DEFAULT_CHATTIME_URL,
        "tg_token": os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        "tg_chat_id": os.getenv("TELEGRAM_CHAT_ID", "7879584619").strip(),
    }


def _post_json(url: str, payload: dict):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "DDC-Warehouse-Notifier/2.5"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="ignore")


def build_cron_json_payload(waktu_wib: str, details: dict) -> dict:
    details = details if isinstance(details, dict) else {}
    kw = int(details.get("keyword", 300) or 0)
    tr = int(details.get("trending", 300) or 0)
    br = int(details.get("berita", 200) or 0)
    sm = int(details.get("sosmed", 212) or 0)
    js = int(details.get("job_search", 0) or 0)
    js_meta = details.get("job_search_summary") if isinstance(details.get("job_search_summary"), dict) else {}

    total_batch = kw + tr + br + sm + js

    return {
        "status": "CRON SCRAPER SELESAI",
        "waktu": str(waktu_wib),
        "total_data": f"{total_batch} baris",
        "rincian_ekstraksi": {
            "keyword": kw,
            "trending": tr,
            "berita": br,
            "sosmed": sm,
            "job_search": js
        },
        "keterangan_job_search": {
            "target_per_sesi": "200 baris",
            "terkumpul": f"{js} baris",
            "fix_bisa_masuk": int(js_meta.get("fix_bisa_masuk", 0) or 0),
            "fifty_fifty": int(js_meta.get("fifty_fifty", 0) or 0),
            "tidak_bisa": int(js_meta.get("tidak_bisa", 0) or 0),
            "sumber": "LinkedIn, Projects.co.id, Freelancer.com, Web Freelance"
        },
        "dashboard_url": DASHBOARD_URL
    }


def format_cron_notification_text(waktu_wib: str, details: dict) -> str:
    payload = build_cron_json_payload(waktu_wib, details)
    r = payload["rincian_ekstraksi"]
    js_info = payload["keterangan_job_search"]

    lines = [
        f"- status: ✅ {payload['status']}",
        f"- waktu: {payload['waktu']}",
        f"- total_data: {payload['total_data']}",
        "- rincian_ekstraksi:",
        f"- keyword: {r['keyword']}",
        f"- trending: {r['trending']}",
        f"- berita: {r['berita']}",
        f"- sosmed: {r['sosmed']}",
    ]
    if int(r.get("job_search", 0)) > 0:
        fix = js_info.get("fix_bisa_masuk", 0)
        ff = js_info.get("fifty_fifty", 0)
        tb = js_info.get("tidak_bisa", 0)
        if (fix + ff + tb) > 0:
            lines.append(f"- job_search: {r['job_search']} (fix: {fix}, fifty-fifty: {ff}, tidak bisa: {tb})")
        else:
            lines.append(f"- job_search: {r['job_search']}")
    lines.append(f"- dashboard_url: {payload['dashboard_url']}")
    return "\n".join(lines)


def send_all_notifications(waktu_wib: str, details: dict) -> dict:
    cfg = _get_config()
    formatted_text = format_cron_notification_text(waktu_wib, details)

    chattime_payload = {"text": formatted_text}
    results = {"chattime": False, "telegram": False}

    # 1. Chattime Webhook
    try:
        st_code, body = _post_json(cfg["chattime_url"], chattime_payload)
        print(f"[Chattime Webhook] Terkirim! HTTP {st_code} | {body[:200]}")
        results["chattime"] = True
    except urllib.error.HTTPError as he:
        err_txt = he.read().decode("utf-8", errors="ignore")[:250]
        print(f"[Chattime Webhook] HTTPError {he.code}: {err_txt}")
    except Exception as e:
        print(f"[Chattime Webhook] Gagal: {type(e).__name__}: {e}")

    # 2. Telegram Bot
    if cfg["tg_token"] and cfg["tg_chat_id"]:
        try:
            tg_url = f"https://api.telegram.org/bot{cfg['tg_token']}/sendMessage"
            tg_body = {
                "chat_id": cfg["tg_chat_id"],
                "text": formatted_text,
                "disable_web_page_preview": False
            }
            st_tg, _ = _post_json(tg_url, tg_body)
            print(f"[Telegram Bot] Terkirim ke {cfg['tg_chat_id']}! HTTP {st_tg}")
            results["telegram"] = True
        except urllib.error.HTTPError as he:
            err_txt = he.read().decode("utf-8", errors="ignore")[:250]
            print(f"[Telegram Bot] HTTPError {he.code}: {err_txt}")
        except Exception as e:
            print(f"[Telegram Bot] Gagal kirim: {type(e).__name__}: {e}")
    else:
        print("[Telegram Bot] TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset di .env / HF Secrets.")

    return results


def send_chattime_webhook(raw_text: str = "", alert_name: str = ""):
    wib_now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S WIB")
    return send_all_notifications(
        wib_now,
        {"keyword": 300, "trending": 300, "berita": 200, "sosmed": 212, "job_search": 200}
    )
