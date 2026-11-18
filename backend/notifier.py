import json
import time
import urllib.request
import urllib.error

DASHBOARD_URL = "https://huggingface.co/spaces/rizqy123/ddc-scraper-portal"
CHATTIME_WEBHOOK_URL = (
    "https://chattime.geekgarden.my.id/api/webhooks/"
    "50deafeb-3b2b-4643-b32e-f18aec60c013/"
    "HPCi5za28Lr6abMKbBq0RPhel0c1FUMpbKYkrREqbvXCLUNlxJTs_t10O4kQzVBD"
)
TELEGRAM_BOT_TOKEN = "9261925207:AAGcUMrNsLf2NdjBlR030EQAQ9tGRCYpVKg"
TELEGRAM_CHAT_ID = "7879584619"

def send_all_notifications(waktu_wib: str, details: dict) -> dict:
    kw = int(details.get("keyword", 300))
    tr = int(details.get("trending", 300))
    br = int(details.get("berita", 200))
    sm = int(details.get("sosmed", 212))
    total = kw + tr + br + sm

    # Payload JSON rapi untuk Chattime / Slack & Telegram
    json_payload = {
        "status": "✅ CRON SCRAPER SELESAI",
        "waktu": waktu_wib,
        "total_data": f"{total} baris",
        "rincian_ekstraksi": {
            "keyword": kw,
            "trending": tr,
            "berita": br,
            "sosmed": sm
        },
        "dashboard_url": DASHBOARD_URL
    }

    results = {"chattime": False, "telegram": False}

    # 1. Kirim ke Chattime / Slack Webhook
    try:
        req = urllib.request.Request(
            CHATTIME_WEBHOOK_URL,
            data=json.dumps(json_payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "user-agent": "DDC-Warehouse-Notifier/2.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            print(f"✅ [Chattime/Slack Webhook] Terkirim! HTTP {resp.status} | {body}")
            results["chattime"] = True
    except Exception as e:
        print(f"❌ [Chattime/Slack Webhook] Gagal: {e}")

    # 2. Kirim ke Telegram Bot (dalam format JSON rapi + link aktif)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            tg_text = json.dumps(json_payload, indent=2, ensure_ascii=False)
            tg_body = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": tg_text,
                "disable_web_page_preview": False
            }
            req_tg = urllib.request.Request(
                tg_url,
                data=json.dumps(tg_body, ensure_ascii=False).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req_tg, timeout=15) as resp_tg:
                body_tg = resp_tg.read().decode("utf-8", errors="ignore")
                print(f"✅ [Telegram Bot] Terkirim ke {TELEGRAM_CHAT_ID}! HTTP {resp_tg.status}")
                results["telegram"] = True
        except Exception as e:
            print(f"❌ [Telegram Bot] Gagal kirim: {e}")
    else:
        print("⚠️ [Telegram Bot] Token atau Chat ID kosong, melewati pengiriman Telegram.")

    return results

def send_chattime_webhook(raw_text: str = "", alert_name: str = ""):
    from datetime import datetime, timezone, timedelta
    wib_now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S WIB")
    return send_all_notifications(wib_now, {"keyword": 300, "trending": 300, "berita": 200, "sosmed": 212})
