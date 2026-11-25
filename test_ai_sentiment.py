import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

GGAI_BASE_URL = "https://ggai-orch.geekdevops.my.id/v1"
GGAI_MODEL = "ggai-v1.0"
GGAI_API_KEY = ""
SKIP_SSL_VERIFY = False
TIMEOUT_SECONDS = 45

SAMPLE_TEXTS = [
    "Pemerintah mempercepat pembangunan infrastruktur energi hijau di Kalimantan dan menuai pujian investor.",
    "Kebakaran hutan di beberapa titik Sumatera kembali meluas sehingga warga mengeluhkan kabut asap tebal.",
    "Rapat koordinasi evaluasi anggaran semester kedua dijadwalkan berlangsung hari Kamis pagi.",
]


def load_dotenv_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            values[k] = v
    return values


def mask_key(key: str) -> str:
    if len(key) <= 10:
        return "***"
    return f"{key[:7]}...{key[-4:]}"


def build_endpoint(base_url: str, suffix: str) -> str:
    base = base_url.rstrip("/")
    suffix = suffix.lstrip("/")
    if base.endswith("/v1") and suffix.startswith("v1/"):
        suffix = suffix[3:]
    elif not base.endswith("/v1") and not suffix.startswith("v1/"):
        suffix = f"v1/{suffix}"
    return f"{base}/{suffix}"


def resolve_config() -> dict:
    dotenv = load_dotenv_file(Path(__file__).resolve().parent / ".env")

    def pick(local_val: str, env_key: str, placeholder: str = "") -> str:
        val = (local_val or "").strip()
        if val and val != placeholder:
            return val
        return (dotenv.get(env_key) or os.environ.get(env_key) or "").strip()

    return {
        "base_url": pick(GGAI_BASE_URL, "GGAI_BASE_URL").rstrip("/"),
        "model": pick(GGAI_MODEL, "GGAI_MODEL"),
        "api_key": pick(GGAI_API_KEY, "GGAI_API_KEY", "PASTE_SK_KEY_KANTOR_DI_SINI"),
        "skip_ssl": SKIP_SSL_VERIFY or (dotenv.get("SKIP_SSL_VERIFY") or "").strip() == "1",
    }


def main() -> None:
    cfg = resolve_config()
    base = cfg["base_url"]
    model = cfg["model"]
    api_key = cfg["api_key"]

    if not api_key:
        raise SystemExit(
            "ERROR: Isi dulu GGAI_API_KEY di test_ai_sentiment.py atau tambahkan GGAI_API_KEY=sk-... di .env."
        )
    if not api_key.startswith("sk-"):
        print(f"[WARN] Key terbaca ({mask_key(api_key)}) tidak diawali 'sk-'. Cek kembali GGAI_API_KEY.")

    ctx = ssl._create_unverified_context() if cfg["skip_ssl"] else ssl.create_default_context()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    models_url = build_endpoint(base, "models")
    chat_url = build_endpoint(base, "chat/completions")

    print(f"Target Base URL : {base}")
    print(f"Model           : {model}")
    print(f"Key Terkirim    : {mask_key(api_key)}")
    print("-" * 60)

    # 1. Cek daftar model
    try:
        req = urllib.request.Request(models_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            print(f"[OK] GET {models_url} -> HTTP {resp.status}")
            print("   Sample:", body[:300])
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        print(f"[WARN] GET {models_url} -> HTTP {exc.code}: {err_body[:300]}")
    except Exception as exc:
        print(f"[WARN] GET {models_url} -> {exc}")

    # 2. Tes Sentimen Analisis (3 teks berita/sosmed Indonesia)
    prompt = (
        "Analisis sentimen setiap teks berikut. Balas HANYA JSON valid berupa array objek "
        "tanpa teks pembuka atau markdown, dengan key: "
        "index (int), sentiment ('positif' | 'netral' | 'negatif'), "
        "score (float -1.0 sampai 1.0), dan reason (string singkat bahasa Indonesia).\n\n"
        + "\n".join(f"{i + 1}. {text}" for i, text in enumerate(SAMPLE_TEXTS))
    )

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": "Kamu adalah mesin analisis sentimen. Kembalikan hanya JSON valid tanpa markdown.",
            },
            {"role": "user", "content": prompt},
        ],
    }

    print(f"\n[TEST] POST {chat_url}")
    req = urllib.request.Request(
        chat_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=ctx) as resp:
            elapsed = time.perf_counter() - t0
            raw = resp.read().decode("utf-8", errors="ignore")
            print(f"[OK] HTTP {resp.status} ({elapsed:.2f} detik)")
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - t0
        err_body = exc.read().decode("utf-8", errors="ignore")
        raise SystemExit(f"[ERROR] HTTP {exc.code} ({elapsed:.2f} detik):\n{err_body[:1000]}")
    except Exception as exc:
        raise SystemExit(f"[ERROR] Koneksi gagal: {exc}")

    # 3. Parsing output JSON untuk validasi kesiapan di n8n
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        print("[WARN] Response bukan JSON:\n", raw[:1500])
        raise SystemExit(1)

    content = None
    if isinstance(outer, dict) and outer.get("choices"):
        msg = outer["choices"][0].get("message") or {}
        content = msg.get("content") or outer["choices"][0].get("text")

    print("\nRaw Response (potongan):")
    print(raw[:1200])

    if isinstance(content, str):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        print("\nHasil Parsing Sentimen AI:")
        try:
            parsed = json.loads(cleaned)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
            print("\n[OK] SIAP DIPAKAI DI N8N: output JSON valid untuk sentimen analisis.")
        except json.JSONDecodeError:
            print("[WARN] Konten AI belum murni JSON (butuh regex extractor di node Code n8n):")
            print(content[:1000])
    else:
        print("\n[INFO] Struktur response berbeda dari standar choices[0].message.content.")


if __name__ == "__main__":
    main()