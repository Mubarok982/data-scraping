import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from lxml import html as lxml_html

# Profil baseline layanan Geekgarden (diperkaya otomatis dari website geekgarden.id)
GEEKGARDEN_SERVICES = {
    "Web & Mobile Development": [
        "web", "website", "webapp", "mobile", "android", "ios", "flutter", "react",
        "react native", "nextjs", "next.js", "vue", "laravel", "codeigniter", "nodejs",
        "node.js", "golang", "python", "django", "fastapi", "fullstack", "frontend",
        "backend", "rest api", "api", "aplikasi", "e-commerce", "marketplace", "portal", "cms"
    ],
    "Custom Software & Enterprise (ERP/CRM)": [
        "custom software", "software house", "erp", "crm", "hrms", "saas",
        "sistem informasi", "dashboard", "inventory", "pos", "microservices",
        "integrasi sistem", "system integration", "enterprise", "digitalisasi", "warehouse"
    ],
    "UI/UX Design & Product": [
        "ui/ux", "ui ux", "figma", "wireframe", "prototype", "product design",
        "desain aplikasi", "desain web", "user experience", "user interface", "redesign"
    ],
    "QA & Software Testing": [
        "qa", "quality assurance", "software testing", "automation test",
        "selenium", "cypress", "playwright", "penetration test", "pentest", "bug fixing"
    ],
    "IT Staff Augmentation / Dedicated Team": [
        "staff augmentation", "outsourcing", "dedicated team", "it vendor",
        "software vendor", "subcontract", "mitra it", "konsultan it", "it consultant",
        "managed service", "developer freelance"
    ],
    "Data, AI & Cloud/DevOps": [
        "machine learning", "ai", "artificial intelligence", "data science",
        "data warehouse", "etl", "elt", "scraping", "scraper", "chatbot", "llm", "nlp",
        "computer vision", "devops", "cloud", "aws", "gcp", "azure", "docker", "kubernetes"
    ],
}

PROJECT_INTENT_SIGNALS = [
    "project", "proyek", "vendor", "software house", "agency", "agensi",
    "freelance", "kontrak", "contract", "rfp", "tender", "butuh developer",
    "dicari developer", "pembuatan aplikasi", "pembuatan website", "jasa pembuatan",
    "budget", "milestone", "outsource", "remote", "hiring developer", "build app"
]

OUT_OF_SCOPE_SIGNALS = [
    "konstruksi", "bangunan", "sipil", "arsitek", "interior", "catering",
    "supir", "driver", "kurir", "satpam", "cleaning service", "sales lapangan",
    "telemarketing", "notaris", "hukum pidana", "medis dokter", "perawat",
    "jahit", "konveksi", "percetakan spanduk", "video wedding", "fotografer nikah"
]

AMBIGUOUS_SIGNALS = [
    "hardware", "pcb", "embedded", "plc", "mikrokontroler", "iot sensor",
    "wordpress murah", "entry data", "data entry", "admin sosmed", "content creator",
    "seo only", "iklan meta ads", "full-time on-site only", "magang unpaid"
]

_GEEKGARDEN_WEB_CACHE = {"ts": 0.0, "tokens": set()}
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def sync_geekgarden_web_keywords(force: bool = False) -> set[str]:
    """Ambil kata kunci layanan langsung dari website geekgarden.id (cache 6 jam)."""
    now = time.time()
    if not force and _GEEKGARDEN_WEB_CACHE["tokens"] and (now - _GEEKGARDEN_WEB_CACHE["ts"] < 21600):
        return _GEEKGARDEN_WEB_CACHE["tokens"]

    tokens = set()
    urls = [
        "https://geekgarden.id/",
        "https://geekgarden.id/services/",
        "https://geekgarden.id/layanan/",
        "https://geekgarden.id/portofolio/",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=_HTTP_HEADERS, timeout=5)
            if r.status_code == 200 and r.text:
                tree = lxml_html.fromstring(r.text)
                headings = tree.xpath("//h1//text() | //h2//text() | //h3//text() | //title//text()")
                raw = " ".join(headings).lower()
                for w in re.findall(r"[a-z0-9\+\-\/]{4,}", raw):
                    tokens.add(w)
        except Exception:
            continue

    _GEEKGARDEN_WEB_CACHE["ts"] = now
    _GEEKGARDEN_WEB_CACHE["tokens"] = tokens
    return tokens


def evaluate_geekgarden_confidence(title: str, description: str = "", extra_tags: str = "") -> dict:
    """Evaluasi kecocokan project terhadap layanan Geekgarden -> Fix Bisa Masuk / Fifty-Fifty / Tidak Bisa."""
    text = f"{title} {description} {extra_tags}".lower()
    web_tokens = sync_geekgarden_web_keywords()

    matched_services = []
    matched_keywords = []
    for service_name, kw_list in GEEKGARDEN_SERVICES.items():
        hits = [kw for kw in kw_list if re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text)]
        if hits:
            matched_services.append(service_name)
            matched_keywords.extend(hits[:4])

    intent_hits = [k for k in PROJECT_INTENT_SIGNALS if k in text]
    oos_hits = [k for k in OUT_OF_SCOPE_SIGNALS if k in text]
    amb_hits = [k for k in AMBIGUOUS_SIGNALS if k in text]
    web_overlap = [w for w in web_tokens if len(w) > 4 and w in text][:5]

    score = 0
    if matched_services:
        score += 45
        score += min(25, len(set(matched_keywords)) * 6)
    if intent_hits:
        score += min(20, len(intent_hits) * 7)
    if web_overlap:
        score += min(10, len(web_overlap) * 2)

    if amb_hits:
        score -= min(22, len(amb_hits) * 11)
    if oos_hits:
        score -= min(70, len(oos_hits) * 35)

    score = max(0, min(100, int(score)))

    if score >= 80 and not oos_hits:
        status = "Fix Bisa Masuk"
        reason = f"Cocok kuat dengan layanan {', '.join(matched_services[:2])}."
    elif score >= 40 and not oos_hits:
        status = "Fifty-Fifty"
        if amb_hits:
            reason = f"Ada irisan IT ({', '.join(matched_services[:2]) or 'umum'}), namun ada aspek abu-abu: {', '.join(amb_hits[:2])}."
        else:
            reason = "Ada potensi masuk, perlu klarifikasi scope vendor/budget."
    else:
        status = "Tidak Bisa"
        if oos_hits:
            reason = f"Di luar cakupan software house (terdeteksi: {', '.join(oos_hits[:2])})."
        else:
            reason = "Tidak ditemukan kecocokan layanan IT/software development Geekgarden."

    return {
        "confidence_status": status,
        "confidence_score": score,
        "project_service_type": matched_services[0] if matched_services else "Lainnya / Non-IT",
        "matched_services": ", ".join(matched_services) if matched_services else "-",
        "fit_reason": reason,
    }


def _scrape_rss_query(query_str: str, default_source: str, keyword: str, max_results: int = 10) -> list[dict]:
    q = urllib.parse.quote(query_str)
    rss_url = f"https://news.google.com/rss/search?q={q}&hl=id&gl=ID&ceid=ID:id"
    rows = []
    try:
        r = requests.get(rss_url, headers=_HTTP_HEADERS, timeout=10)
        if r.status_code != 200:
            return rows
        tree = lxml_html.fromstring(r.content)
        for item in tree.xpath("//item")[:max_results]:
            title = (item.xpath("string(title)") or "").strip()
            link = (item.xpath("string(link)") or "").strip()
            desc = re.sub(r"<[^>]+>", " ", item.xpath("string(description)") or "").strip()
            desc = re.sub(r"\s+", " ", desc)
            pub_date = (item.xpath("string(pubDate)") or "").strip()

            low = f"{title} {link} {desc}".lower()
            src = default_source
            if "linkedin" in low:
                src = "LinkedIn Project Lead"
            elif "projects.co.id" in low:
                src = "Projects.co.id"
            elif "sribu" in low:
                src = "Sribu"
            elif "upwork" in low:
                src = "Upwork"
            elif "fastwork" in low:
                src = "Fastwork"

            fit = evaluate_geekgarden_confidence(title, desc, keyword)
            rows.append({
                "platform": "linkedin",
                "source_platform": src,
                "title": title,
                "budget": "Lihat detail",
                "skills": keyword,
                **fit,
                "content": desc[:350],
                "published_at": pub_date,
                "url": link,
            })
    except Exception:
        pass
    return rows


def scrape_linkedin_project_leads(keyword: str, region_indonesia: bool = True, max_results: int = 10, harvest_fn=None) -> list[dict]:
    """Cari postingan / kebutuhan project di LinkedIn (via snippet harvester + RSS fallback)."""
    rows = []
    loc_str = "Indonesia" if region_indonesia else ""
    dork = f'({keyword}) ("project" OR "vendor" OR "software house" OR "freelance" OR "RFP") {loc_str} site:linkedin.com'.strip()

    if callable(harvest_fn):
        try:
            snippets = harvest_fn(dork, max_items=max_results * 2) or []
            for s in snippets[:max_results]:
                title = str(s.get("title") or "").strip()
                desc = str(s.get("snippet") or "").strip()
                url = str(s.get("url") or "").strip()
                if not title or not url:
                    continue
                fit = evaluate_geekgarden_confidence(title, desc, f"{keyword} linkedin project")
                rows.append({
                    "platform": "linkedin",
                    "source_platform": "LinkedIn Project Lead",
                    "title": title,
                    "budget": "Negosiasi / B2B",
                    "skills": keyword,
                    **fit,
                    "content": desc[:350],
                    "published_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": url,
                })
        except Exception:
            pass

    if len(rows) < max_results:
        rss_q = f'({keyword}) ("project" OR "vendor" OR "software house" OR "freelance") {loc_str} site:linkedin.com'
        rows.extend(_scrape_rss_query(rss_q, "LinkedIn Project Lead", keyword, max_results - len(rows)))

    return rows[:max_results]


def scrape_freelancer_projects(keyword: str, max_results: int = 10) -> list[dict]:
    """Ambil project aktif dari Freelancer.com via Public JSON API."""
    url = "https://www.freelancer.com/api/projects/0.1/projects/active/"
    params = {
        "query": keyword,
        "limit": min(max_results, 25),
        "compact": "false",
        "job_details": "true",
    }
    rows = []
    try:
        r = requests.get(url, params=params, headers=_HTTP_HEADERS, timeout=12)
        if r.status_code != 200:
            return rows
        projects = r.json().get("result", {}).get("projects", [])
        for p in projects[:max_results]:
            title = p.get("title") or "Untitled Project"
            desc = p.get("preview_description") or ""
            jobs = ", ".join(j.get("name", "") for j in (p.get("jobs") or []) if isinstance(j, dict))
            curr = (p.get("currency") or {}).get("code", "USD")
            bmin = (p.get("budget") or {}).get("minimum", 0)
            bmax = (p.get("budget") or {}).get("maximum", 0)
            budget_str = f"{curr} {bmin}-{bmax}" if (bmin or bmax) else "Negosiasi"
            seo_url = p.get("seo_url", "")
            link = f"https://www.freelancer.com/projects/{seo_url}" if seo_url else "https://www.freelancer.com"

            fit = evaluate_geekgarden_confidence(title, desc, f"{jobs} project freelance")
            rows.append({
                "platform": "linkedin",
                "source_platform": "Freelancer.com",
                "title": title,
                "budget": budget_str,
                "skills": jobs or keyword,
                **fit,
                "content": desc[:350],
                "published_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "url": link,
            })
    except Exception:
        pass
    return rows


def scrape_projects_coid(keyword: str, max_results: int = 10) -> list[dict]:
    """Ambil project lokal Indonesia dari Projects.co.id."""
    q = urllib.parse.quote(keyword)
    url = f"https://projects.co.id/public/browse_projects/listing?search={q}"
    rows = []
    try:
        r = requests.get(url, headers=_HTTP_HEADERS, timeout=12)
        if r.status_code == 200 and r.text:
            tree = lxml_html.fromstring(r.text)
            links = tree.xpath("//a[contains(@href, '/public/browse_projects/view/')]")
            seen = set()
            for a in links:
                href = a.get("href", "")
                title = " ".join(a.xpath(".//text()")).strip()
                if not title or len(title) < 6 or href in seen:
                    continue
                seen.add(href)
                full_url = href if href.startswith("http") else f"https://projects.co.id{href}"
                parent_txt = " ".join(a.xpath("./ancestor::div[2]//text()"))
                clean_desc = re.sub(r"\s+", " ", parent_txt).strip()[:350]
                bmatch = re.search(r"Rp[\s\d\.,\-]+", clean_desc, re.I)
                budget_str = bmatch.group(0).strip() if bmatch else "Cek di Projects.co.id"

                fit = evaluate_geekgarden_confidence(title, clean_desc, f"{keyword} project indonesia")
                rows.append({
                    "platform": "linkedin",
                    "source_platform": "Projects.co.id",
                    "title": title,
                    "budget": budget_str,
                    "skills": keyword,
                    **fit,
                    "content": clean_desc,
                    "published_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": full_url,
                })
                if len(rows) >= max_results:
                    break
    except Exception:
        pass
    return rows


def scrape_web_freelance_leads(keyword: str, max_results: int = 10, harvest_fn=None) -> list[dict]:
    """Ambil lead project dari Sribu, Upwork, Fastwork, dan portal freelance lainnya."""
    rows = []
    dork = f'({keyword}) ("project" OR "pembuatan aplikasi" OR "freelance" OR "vendor") (site:sribu.com OR site:upwork.com OR site:fastwork.id OR site:projects.co.id)'
    if callable(harvest_fn):
        try:
            snippets = harvest_fn(dork, max_items=max_results * 2) or []
            for s in snippets[:max_results]:
                title = str(s.get("title") or "").strip()
                desc = str(s.get("snippet") or "").strip()
                url = str(s.get("url") or "").strip()
                if not title or not url:
                    continue
                low = url.lower()
                src = "Web Freelance Lain"
                if "sribu" in low:
                    src = "Sribu"
                elif "upwork" in low:
                    src = "Upwork"
                elif "fastwork" in low:
                    src = "Fastwork"
                elif "projects.co.id" in low:
                    src = "Projects.co.id"

                fit = evaluate_geekgarden_confidence(title, desc, f"{keyword} freelance project")
                rows.append({
                    "platform": "linkedin",
                    "source_platform": src,
                    "title": title,
                    "budget": "Lihat detail",
                    "skills": keyword,
                    **fit,
                    "content": desc[:350],
                    "published_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": url,
                })
        except Exception:
            pass

    if len(rows) < max_results:
        rows.extend(_scrape_rss_query(dork, "Web Freelance Lain", keyword, max_results - len(rows)))

    return rows[:max_results]


def run_project_hunter(
    keyword: str,
    sources: str = "all",
    region_indonesia: bool = True,
    max_results: int = 15,
    harvest_fn=None,
) -> list[dict]:
    """Orkestrator multi-sumber project + scoring confidence Geekgarden."""
    sync_geekgarden_web_keywords()
    per_source = max(4, max_results if sources != "all" else (max_results // 3) + 2)

    tasks = []
    if sources in ("all", "linkedin"):
        tasks.append(lambda: scrape_linkedin_project_leads(keyword, region_indonesia, per_source, harvest_fn))
    if sources in ("all", "projects_coid"):
        tasks.append(lambda: scrape_projects_coid(keyword, per_source))
    if sources in ("all", "freelancer"):
        tasks.append(lambda: scrape_freelancer_projects(keyword, per_source))
    if sources in ("all", "web_leads"):
        tasks.append(lambda: scrape_web_freelance_leads(keyword, per_source, harvest_fn))

    collected = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(fn) for fn in tasks]
        for fut in as_completed(futs):
            try:
                collected.extend(fut.result() or [])
            except Exception:
                pass

    # Deduplikasi & urutkan berdasarkan confidence_score tertinggi
    dedup = []
    seen = set()
    for r in collected:
        key = (r.get("url") or r.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        dedup.append(r)

    dedup.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)
    return dedup[:max_results]
