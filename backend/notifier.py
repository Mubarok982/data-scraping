import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

DASHBOARD_URL = "https://huggingface.co/spaces/rizqy123/ddc-scraper-portal"
CHATTIME_WEBHOOK_URL = (
    "https://chattime.geekgarden.my.id/api/webhooks/"
    "50deafeb-3b2b-4643-b32e-f18aec60c013/"
    "HPCi5za28Lr6abMKbBq0RPhel0c1FUMpbKYkrREqbvXCLUNlxJTs_t10O4kQzVBD"
)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9261925207:AAGcUMrNsLf2NdjBlR030EQAQ9tGRCYpVKg")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7879584619")


def _post_json(url: str, payload: dict):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "DDC-Warehouse-Notifier/2.2"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="ignore")


def send_all_notifications(waktu_wib: str, details: dict) -> dict:
    kw = int(details.get("keyword", 300))
    tr = int(details.get("trending", 300))
    br = int(details.get("berita", 200))
    sm = int(details.get("sosmed", 212))
    total_batch = kw + tr + br + sm

    json_payload = {
        "status": "CRON SCRAPER SELESAI",
        "waktu": str(waktu_wib),
        "total_data": f"{total_batch} baris",
        "rincian_ekstraksi": {
            "keyword": kw,
            "trending": tr,
            "berita": br,
            "sosmed": sm
        },
        "dashboard_url": DASHBOARD_URL
    }

    pretty_json = json.dumps(json_payload, indent=2, ensure_ascii=False)
    chattime_payload = {
        "text": f"CRON SCRAPER SELESAI ({waktu_wib})\n```json\n{pretty_json}\n```",
        **json_payload
    }

    results = {"chattime": False, "telegram": False}

    try:
        st_code, body = _post_json(CHATTIME_WEBHOOK_URL, chattime_payload)
        print(f"[Chattime Webhook] Terkirim! HTTP {st_code} | {body[:200]}")
        results["chattime"] = True
    except urllib.error.HTTPError as he:
        err_txt = he.read().decode("utf-8", errors="ignore")[:250]
        print(f"[Chattime Webhook] HTTPError {he.code}: {err_txt}")
    except Exception as e:
        print(f"[Chattime Webhook] Gagal: {type(e).__name__}: {e}")

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            tg_body = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": pretty_json,
                "disable_web_page_preview": False
            }
            st_tg, _ = _post_json(tg_url, tg_body)
            print(f"[Telegram Bot] Terkirim ke {TELEGRAM_CHAT_ID}! HTTP {st_tg}")
            results["telegram"] = True
        except Exception as e:
            print(f"[Telegram Bot] Gagal kirim: {type(e).__name__}: {e}")
    else:
        print("[Telegram Bot] Token atau Chat ID kosong.")

    return results


def send_chattime_webhook(raw_text: str = "", alert_name: str = ""):
    wib_now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S WIB")
    return send_all_notifications(wib_now, {"keyword": 300, "trending": 300, "berita": 200, "sosmed": 212})
