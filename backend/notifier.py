import json
import re
import time
import urllib.request
import requests

DASHBOARD_URL = "https://huggingface.co/spaces/rizqy123/ddc-scraper-portal"
CHATTIME_WEBHOOK_URL = (
    "https://chattime.geekgarden.my.id/api/webhooks/"
    "50deafeb-3b2b-4643-b32e-f18aec60c013/"
    "HPCi5za28Lr6abMKbBq0RPhel0c1FUMpbKYkrREqbvXCLUNlxJTs_t10O4kQzVBD"
)

_LAST_WEBHOOK_TS = 0.0

def append_dashboard_link(text: str) -> str:
    text = (text or "").strip()
    if DASHBOARD_URL not in text:
        text += f"\n\n🌐 Web Dashboard:\n{DASHBOARD_URL}"
    return text

def strip_html_tags(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text or "")
    return clean.strip()

def send_chattime_webhook(message_text: str, alert_name: str = "DDC Data Warehouse — Laporan Cron & ELT") -> bool:
    global _LAST_WEBHOOK_TS
    now = time.time()
    # Cegah duplikasi pengiriman dalam rentang 3 detik
    if now - _LAST_WEBHOOK_TS < 3.0:
        return True
    _LAST_WEBHOOK_TS = now

    full_text = append_dashboard_link(strip_html_tags(message_text))
    payload = {
        "alert_name": alert_name,
        "value": full_text
    }

    try:
        req = urllib.request.Request(
            CHATTIME_WEBHOOK_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"✅ [Chattime Webhook] Terkirim! HTTP Status: {resp.status}")
            return True
    except Exception as e:
        print(f"❌ [Chattime Webhook] Gagal kirim: {e}")
        return False

# --- INTERCEPTOR OTOMATIS UNTUK TELEGRAM & REQUESTS/URLLIB ---
_orig_requests_request = requests.Session.request

def _patched_requests_request(self, method, url, *args, **kwargs):
    if url and "api.telegram.org" in str(url) and "sendMessage" in str(url):
        # Sisipkan link dashboard ke payload JSON atau Data Telegram
        msg_captured = None
        if "json" in kwargs and isinstance(kwargs["json"], dict) and "text" in kwargs["json"]:
            kwargs["json"]["text"] = append_dashboard_link(str(kwargs["json"]["text"]))
            msg_captured = kwargs["json"]["text"]
        elif "data" in kwargs and isinstance(kwargs["data"], dict) and "text" in kwargs["data"]:
            kwargs["data"]["text"] = append_dashboard_link(str(kwargs["data"]["text"]))
            msg_captured = kwargs["data"]["text"]
        elif "params" in kwargs and isinstance(kwargs["params"], dict) and "text" in kwargs["params"]:
            kwargs["params"]["text"] = append_dashboard_link(str(kwargs["params"]["text"]))
            msg_captured = kwargs["params"]["text"]

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
                        parsed["text"] = append_dashboard_link(str(parsed["text"]))
                        new_bytes = json.dumps(parsed).encode("utf-8")
                        if hasattr(url_or_req, "data"):
                            url_or_req.data = new_bytes
                        else:
                            data = new_bytes
                        send_chattime_webhook(parsed["text"])
                except Exception:
                    import urllib.parse
                    qs = urllib.parse.parse_qs(body_str)
                    if "text" in qs and qs["text"]:
                        new_text = append_dashboard_link(qs["text"][0])
                        qs["text"] = [new_text]
                        new_bytes = urllib.parse.urlencode(qs, doseq=True).encode("utf-8")
                        if hasattr(url_or_req, "data"):
                            url_or_req.data = new_bytes
                        else:
                            data = new_bytes
                        send_chattime_webhook(new_text)
        except Exception as e:
            print("⚠️ Urllib hook warning:", e)

    return _orig_urlopen(url_or_req, data=data, *args, **kwargs)

urllib.request.urlopen = _patched_urlopen
