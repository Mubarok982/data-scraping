import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import requests
from datetime import datetime, timezone, timedelta

DASHBOARD_URL = "https://huggingface.co/spaces/rizqy123/ddc-scraper-portal"
CHATTIME_WEBHOOK_URL = (
    "https://chattime.geekgarden.my.id/api/webhooks/"
    "50deafeb-3b2b-4643-b32e-f18aec60c013/"
    "HPCi5za28Lr6abMKbBq0RPhel0c1FUMpbKYkrREqbvXCLUNlxJTs_t10O4kQzVBD"
)

_LAST_WEBHOOK_TS = 0.0

def parse_report_to_json(raw_text: str) -> dict:
    clean = re.sub(r"<[^>]+>", "", raw_text or "").strip()
    wib_now = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S WIB")

    waktu_m = re.search(r"Waktu:\s*([^\n\r]+)", clean)
    total_m = re.search(r"Total Data:\s*(\d+)", clean)
    kw_m = re.search(r"Keyword:\s*(\d+)", clean)
    tr_m = re.search(r"Trending:\s*(\d+)", clean)
    br_m = re.search(r"Berita:\s*(\d+)", clean)
    sm_m = re.search(r"Sosmed:\s*(\d+)", clean)

    waktu = waktu_m.group(1).strip() if waktu_m else wib_now
    kw = int(kw_m.group(1)) if kw_m else 0
    tr = int(tr_m.group(1)) if tr_m else 0
    br = int(br_m.group(1)) if br_m else 0
    sm = int(sm_m.group(1)) if sm_m else 0
    total = int(total_m.group(1)) if total_m else (kw + tr + br + sm)

    return {
        "status": "✅ CRON SCRAPER SELESAI",
        "waktu": waktu,
        "total_data": f"{total} baris",
        "rincian_ekstraksi": {
            "keyword": kw,
            "trending": tr,
            "berita": br,
            "sosmed": sm
        },
        "dashboard_url": DASHBOARD_URL
    }

def append_dashboard_link(text: str) -> str:
    text = (text or "").strip()
    if DASHBOARD_URL not in text:
        text += f"\n\n🌐 Web Dashboard:\n{DASHBOARD_URL}"
    return text

def send_chattime_webhook(raw_text: str) -> bool:
    global _LAST_WEBHOOK_TS
    now = time.time()
    if now - _LAST_WEBHOOK_TS < 3.0:
        return True
    _LAST_WEBHOOK_TS = now

    payload = parse_report_to_json(raw_text)

    try:
        t0 = time.time()
        req = urllib.request.Request(
            CHATTIME_WEBHOOK_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "user-agent": "DDC-Warehouse-Notifier/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = (time.time() - t0) * 1000
            body = resp.read().decode("utf-8", errors="ignore")
            print(f"✅ [Chattime Webhook] HTTP {resp.status} ({elapsed:.0f} ms) | Response: {body}")
            return True
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        print(f"⚠️ [Chattime Webhook] HTTP Error {he.code}: {err_body}")
        return False
    except Exception as e:
        print(f"❌ [Chattime Webhook] Gagal terhubung: {e}")
        return False

# --- INTERCEPTOR OTOMATIS UNTUK TELEGRAM & WEBHOOK ---
_orig_requests_request = requests.Session.request

def _patched_requests_request(self, method, url, *args, **kwargs):
    if url and "api.telegram.org" in str(url) and "sendMessage" in str(url):
        msg_captured = None
        if "json" in kwargs and isinstance(kwargs["json"], dict) and "text" in kwargs["json"]:
            msg_captured = str(kwargs["json"]["text"])
            kwargs["json"]["text"] = append_dashboard_link(msg_captured)
        elif "data" in kwargs and isinstance(kwargs["data"], dict) and "text" in kwargs["data"]:
            msg_captured = str(kwargs["data"]["text"])
            kwargs["data"]["text"] = append_dashboard_link(msg_captured)
        elif "params" in kwargs and isinstance(kwargs["params"], dict) and "text" in kwargs["params"]:
            msg_captured = str(kwargs["params"]["text"])
            kwargs["params"]["text"] = append_dashboard_link(msg_captured)

        if msg_captured:
            send_chattime_webhook(msg_captured)

    return _orig_requests_request(self, method, url, *args, **kwargs)

requests.Session.request = _patched_requests_request

_orig_urlopen = urllib.request.urlopen

def _patched_urlopen(url_or_req, data=None, *args, **kwargs):
    target_url = url_or_req.full_url if hasattr(url_or_req, "full_url") else str(url_or_req)
    if "api.telegram.org" in target_url and "sendMessage" in target_url:
        try:
            raw_bytes = url_or_req.data if hasattr(url_or_req, "data") and url_or_req.data else data
            if raw_bytes:
                body_str = raw_bytes.decode("utf-8", errors="ignore")
                try:
                    parsed = json.loads(body_str)
                    if isinstance(parsed, dict) and "text" in parsed:
                        orig_text = str(parsed["text"])
                        parsed["text"] = append_dashboard_link(orig_text)
                        new_bytes = json.dumps(parsed).encode("utf-8")
                        if hasattr(url_or_req, "data"):
                            url_or_req.data = new_bytes
                        else:
                            data = new_bytes
                        send_chattime_webhook(orig_text)
                except Exception:
                    qs = urllib.parse.parse_qs(body_str)
                    if "text" in qs and qs["text"]:
                        orig_text = qs["text"][0]
                        qs["text"] = [append_dashboard_link(orig_text)]
                        new_bytes = urllib.parse.urlencode(qs, doseq=True).encode("utf-8")
                        if hasattr(url_or_req, "data"):
                            url_or_req.data = new_bytes
                        else:
                            data = new_bytes
                        send_chattime_webhook(orig_text)
        except Exception as e:
            print("⚠️ Urllib hook warning:", e)

    return _orig_urlopen(url_or_req, data=data, *args, **kwargs)

urllib.request.urlopen = _patched_urlopen
