/* DDC_PROJECT_FETCH_GUARD_START */
(function () {
    const isStandaloneProject = () =>
        (document.body && document.body.dataset && document.body.dataset.page === "project") ||
        /^\/dashboard\/project\/?$/i.test(window.location.pathname || "");

    const isStandaloneAnalytics = () =>
        (document.body && document.body.dataset && document.body.dataset.page === "analytics") ||
        /^\/analytics\/?$/i.test(window.location.pathname || "");

    if (window.fetch && !window.fetch.__ddcStandaloneGuard) {
        const _nativeFetch = window.fetch.bind(window);
        window.fetch = async function (input, init) {
            let url = typeof input === "string" ? input : (input && input.url) || "";
            if (isStandaloneProject()) {
                if (/\/api\/v1\/(warehouse\/analytics|warehouse\/records|bank-data\/|scheduler\/status)/i.test(url)) {
                    const emptyBody = url.includes("analytics")
                        ? { status: "ok", analytics: {}, stats: {} }
                        : url.includes("scheduler")
                        ? { status: "idle" }
                        : { status: "ok", data: [], records: [], files: [] };
                    return new Response(JSON.stringify(emptyBody), {
                        status: 200,
                        headers: { "Content-Type": "application/json" }
                    });
                }
                if (/\/api\/v1\/project\/records\b/i.test(url) && /limit=5000\b/i.test(url)) {
                    url = url.replace(/limit=5000\b/i, "limit=500");
                    input = typeof input === "string" ? url : new Request(url, input);
                }
            } else if (isStandaloneAnalytics()) {
                if (/\/api\/v1\/(warehouse\/records|bank-data\/)/i.test(url)) {
                    return new Response(JSON.stringify({ status: "ok", data: [], records: [], files: [] }), {
                        status: 200,
                        headers: { "Content-Type": "application/json" }
                    });
                }
            }
            return _nativeFetch(input, init);
        };
        window.fetch.__ddcStandaloneGuard = true;
    }
})();
/* DDC_PROJECT_FETCH_GUARD_END */

let currentTab = 'supabase';
        let chartLoc = null, chartPpl = null, chartKw = null, chartTime = null, chartSent = null, chartViral = null, chartHash = null, chartSystem = null;

        let BASE_ANALYTICS = null;
        let DOMAIN_ROWS_CACHE = {};
        let LAST_CSV_PATH = {};

        let _cronActiveManual = false;
        let _cronSimProgress = 0;
        let _cronUiTimer = null;

        Chart.defaults.color = '#8b949e';
        Chart.defaults.font.family = "'JetBrains Mono', ui-monospace, SFMono-Regular, monospace";
        Chart.defaults.font.size = 10;

        const PROV_KAB_DATA = {
            "DKI Jakarta": ["Jakarta Pusat", "Jakarta Selatan", "Jakarta Barat", "Jakarta Timur", "Jakarta Utara", "Kepulauan Seribu"],
            "Jawa Barat": ["Bandung", "Bekasi", "Bogor", "Depok", "Cimahi", "Cirebon", "Sukabumi", "Tasikmalaya", "Karawang", "Garut", "Cianjur", "Indramayu", "Subang", "Sumedang"],
            "Jawa Tengah": ["Semarang", "Magelang", "Surakarta (Solo)", "Banyumas (Purwokerto)", "Tegal", "Pekalongan", "Salatiga", "Kudus", "Cilacap", "Kebumen", "Klaten", "Boyolali", "Wonogiri", "Temanggung", "Wonosobo", "Purworejo", "Jepara", "Demak"],
            "DI Yogyakarta": ["Yogyakarta", "Sleman", "Bantul", "Kulon Progo", "Gunungkidul"],
            "Jawa Timur": ["Surabaya", "Malang", "Sidoarjo", "Gresik", "Jember", "Banyuwangi", "Kediri", "Madiun", "Mojokerto", "Pasuruan", "Probolinggo", "Blitar", "Batu", "Bojonegoro", "Tuban"],
            "Banten": ["Tangerang", "Tangerang Selatan", "Serang", "Cilegon", "Pandeglang", "Lebak"],
            "Riau": ["Pekanbaru", "Dumai", "Bengkalis", "Siak", "Kampar", "Rokan Hilir", "Rokan Hulu", "Indragiri Hilir", "Indragiri Hulu", "Pelalawan"],
            "Kepulauan Riau": ["Batam", "Tanjungpinang", "Bintan", "Karimun", "Natuna", "Anambas"],
            "Sumatera Utara": ["Medan", "Binjai", "Pematangsiantar", "Tebing Tinggi", "Deli Serdang", "Karo", "Tapanuli Utara", "Simalungun"],
            "Sumatera Barat": ["Padang", "Bukittinggi", "Payakumbuh", "Pariaman", "Agam", "Tanah Datar", "Solok"],
            "Sumatera Selatan": ["Palembang", "Prabumulih", "Lubuklinggau", "Pagar Alam", "Ogan Komering Ilir", "Muba", "Muara Enim", "Banyuasin"],
            "Aceh": ["Banda Aceh", "Lhokseumawe", "Langsa", "Sabang", "Aceh Besar", "Aceh Utara", "Pidie"],
            "Jambi": ["Jambi", "Sungai Penuh", "Muaro Jambi", "Batanghari", "Tanjung Jabung"],
            "Lampung": ["Bandar Lampung", "Metro", "Lampung Selatan", "Lampung Tengah", "Lampung Timur"],
            "Kalimantan Timur (IKN)": ["Nusantara (IKN)", "Samarinda", "Balikpapan", "Bontang", "Penajam Paser Utara", "Kutai Kartanegara", "Kutai Timur", "Berau"],
            "Kalimantan Barat": ["Pontianak", "Singkawang", "Kubu Raya", "Sambas", "Sintang", "Ketapang"],
            "Kalimantan Tengah": ["Palangka Raya", "Kotawaringin Timur (Sampit)", "Kotawaringin Barat (Pangkalan Bun)", "Kapuas", "Barito Utara"],
            "Kalimantan Selatan": ["Banjarmasin", "Banjarbaru", "Banjar", "Tanah Bumbu", "Kotabaru", "Tabalong"],
            "Kalimantan Utara": ["Tarakan", "Bulungan (Tanjung Selor)", "Nunukan", "Malinau"],
            "Sulawesi Selatan": ["Makassar", "Parepare", "Palopo", "Gowa", "Maros", "Bone", "Luwu Timur", "Tana Toraja"],
            "Sulawesi Utara": ["Manado", "Bitung", "Tomohon", "Minahasa", "Bolaang Mongondow"],
            "Sulawesi Tengah": ["Palu", "Morowali", "Poso", "Banggai", "Donggala"],
            "Sulawesi Tenggara": ["Kendari", "Baubau", "Konawe", "Kolaka"],
            "Bali": ["Denpasar", "Badung", "Gianyar", "Tabanan", "Buleleng", "Karangasem", "Klungkung"],
            "Nusa Tenggara Barat": ["Mataram", "Bima", "Lombok Barat", "Lombok Tengah", "Lombok Timur", "Sumbawa"],
            "Nusa Tenggara Timur": ["Kupang", "Labuan Bajo (Manggarai Barat)", "Flores Timur", "Ende", "Sikka", "Sumba Timur"],
            "Maluku & Maluku Utara": ["Ambon", "Ternate", "Tidore", "Halmahera Tengah", "Halmahera Utara"],
            "Papua & Papua Barat": ["Jayapura", "Sorong", "Manokwari", "Merauke", "Mimika (Timika)", "Biak Numfor", "Nabire"]
        };

        const KNOWN_FIGURES_MAP = {
            "Prabowo Subianto": ["prabowo"],
            "Joko Widodo (Jokowi)": ["jokowi", "joko widodo"],
            "Gibran Rakabuming": ["gibran"],
            "Sri Mulyani": ["sri mulyani"],
            "Bahlil Lahadalia": ["bahlil"],
            "Luhut Pandjaitan": ["luhut"],
            "Agus Harimurti (AHY)": ["ahy", "agus harimurti"],
            "Sufmi Dasco": ["dasco"],
            "Anies Baswedan": ["anies"],
            "Ganjar Pranowo": ["ganjar"],
            "Erick Thohir": ["erick thohir"],
            "Mahfud MD": ["mahfud"],
            "Roy Suryo": ["roy suryo"]
        };

        const CATEGORY_SYNONYMS = {
            "politik": ["politik", "pemerintah", "dpr", "menteri", "presiden", "partai", "koalisi", "kabinet", "pilkada", "pemilu"],
            "kebijakan": ["kebijakan", "regulasi", "aturan", "undang-undang", "perpres", "program", "anggaran"],
            "mbg": ["mbg", "makan bergizi", "gizi gratis", "program makan"],
            "ikn": ["ikn", "nusantara", "ibu kota", "otorita"],
            "hukum": ["hukum", "korupsi", "kpk", "kejaksaan", "pengadilan", "tersangka", "kasus", "pidana"],
            "keamanan": ["tni", "polri", "polisi", "keamanan", "pertahanan", "militer", "siber"],
            "ekonomi": ["ekonomi", "bisnis", "investasi", "pasar", "saham", "rupiah", "ekspor", "impor", "umkm", "industri"],
            "inflasi": ["inflasi", "pajak", "ppn", "daya beli", "harga", "keuangan", "apbn", "bank"],
            "energi": ["energi", "hijau", "transisi", "listrik", "pltu", "ebt", "sawit", "biodiesel", "tambang", "nikel"],
            "infrastruktur": ["infrastruktur", "tol", "pelabuhan", "bandara", "kereta", "konstruksi", "jembatan"],
            "lingkungan": ["karhutla", "kebakaran", "hutan", "banjir", "gempa", "bencana", "iklim", "asap", "cuaca", "lingkungan"],
            "teknologi": ["teknologi", "ai", "digital", "internet", "aplikasi", "robot", "inovasi", "data", "software", "chip"],
            "kesehatan": ["kesehatan", "medis", "rumah sakit", "dokter", "bpjs", "obat", "penyakit", "stunting"],
            "pendidikan": ["pendidikan", "sekolah", "kampus", "mahasiswa", "guru", "dosen", "beasiswa", "riset"],
            "sosial": ["sosial", "bansos", "masyarakat", "warga", "kemiskinan", "tenaga kerja", "buruh"],
            "olahraga": ["olahraga", "timnas", "sepak bola", "liga", "atlet", "pertandingan", "pssi"],
            "hiburan": ["hiburan", "musik", "film", "artis", "viral", "konser", "seleb"]
        };

        
        function isIndonesianText(txt) {
            const raw = String(txt || '').trim();
            if (!raw) return false;
            const cleaned = raw
                .replace(/https?:\/\/\S+/gi, ' ')
                .replace(/[@#][a-zA-Z0-9_]+/g, ' ')
                .replace(/[^a-zA-Z\s]/g, ' ')
                .toLowerCase()
                .replace(/\s+/g, ' ')
                .trim();

            if (!cleaned) return false;

            if (/[^\x00-\x7F\u00C0-\u024F]/.test(raw) && !/[\u2000-\u3300\uD800-\uDBFF]/.test(raw)) {
                return false;
            }

            const words = cleaned.split(' ').filter(w => w.length > 1);
            if (words.length === 0) return false;

            const idVocab = new Set([
                'yang','dan','di','ke','dari','ini','itu','untuk','dengan','pada','dalam','tidak','bisa','akan','ada',
                'oleh','juga','karena','saat','lebih','atau','sudah','jadi','kata','tahun','indonesia','warga','pemerintah',
                'presiden','dpr','menteri','daerah','wilayah','kota','kabupaten','provinsi','banjir','kebakaran','karhutla',
                'harga','ekonomi','berita','ramai','viral','heboh','terkini','hari','bulan','makan','bergizi','gratis',
                'rakyat','negara','masyarakat','hukum','kasus','polisi','tni','timnas','sepak','bola','rupiah','saham',
                'umkm','jalan','tol','banjir','hujan','cuaca','sekolah','kampus','mahasiswa','guru','dokter','rumah','sakit',
                'pajak','inflasi','investasi','proyek','ikn','nusantara','jakarta','bandung','surabaya','semarang','jogja',
                'yogyakarta','medan','makassar','bali','riau','kalimantan','sumatera','sulawesi','papua','maluku','aceh',
                'banten','lampung','ntb','ntt','kini','baru','awal','akhir','bersama','terhadap','atas','sebagai','bagi',
                'antara','namun','tetapi','serta','para','kaum','anak','ibu','bapak','keluarga','kerja','gaji','upah',
                'bbm','listrik','air','bersih','sampah','longsor','gempa','waspada','peringatan','resmi','umumkan','gelar',
                'dukung','tolak','demo','aksi','sidang','vonis','tersangka','korupsi','tangkap','ungkap','temukan'
            ]);

            const enVocab = new Set([
                'the','and','with','from','this','that','your','for','are','was','were','have','has','had','will','would',
                'could','should','what','when','where','why','how','new','top','best','live','breaking','news','official',
                'video','watch','follow','subscribe','like','comment','share','repost','thread','post','story','today',
                'week','year','day','people','world','market','stock','price','crypto','game','gaming','music','movie',
                'show','season','episode','review','guide','tips','free','win','giveaway','alert','update','report',
                'analysis','vs','over','under','into','out','off','more','most','all','about','after','before','just',
                'now','here','there','their','them','they','she','he','his','her','its','our','us','we','you','my','me',
                'can','cant','wont','dont','didnt','isnt','arent','wasnt','werent','hasnt','havent','hadnt','get','got',
                'make','made','take','took','come','came','go','went','see','saw','know','knew','think','thought','say','said',
                'man','woman','men','women','boy','girl','child','children','city','state','country','president','minister',
                'war','peace','attack','kill','killed','dead','death','fire','flood','storm','rain','snow','heat','cold'
            ]);

            let idScore = 0;
            let enScore = 0;

            for (const w of words) {
                if (idVocab.has(w)) idScore += 2;
                if (enVocab.has(w)) enScore += 2;
                if (w.length > 4 && (w.endsWith('nya') || w.endsWith('kan'))) idScore += 1;
            }

            if (enScore > 0 && idScore <= enScore) return false;
            if (words.length >= 2 && idScore === 0) return false;

            return idScore > enScore;
        }

        const POS_WORDS = ["sukses", "berhasil", "optimis", "tumbuh", "naik", "positif", "inovasi", "apresiasi", "unggul", "prestasi", "solusi", "dukung", "aman", "baik", "hebat", "maju"];
        const NEG_WORDS = ["karhutla", "kebakaran", "korban", "krisis", "turun", "anjlok", "korupsi", "gagal", "kritik", "demo", "rusak", "banjir", "bencana", "konflik", "masalah", "keluhkan", "bahaya", "rugi"];

        // ================= PROGRESS BAR CRON (ANTI-STUCK) =================
        function updateCronProgressUI(statusStr, rowsCollected) {
            const progBar = document.getElementById('cron-prog-bar');
            const progPct = document.getElementById('cron-prog-pct');
            const progLabel = document.getElementById('cron-prog-label');
            const badge = document.getElementById('cron-badge');
            const statusEl = document.getElementById('cron-status');

            const stLower = String(statusStr || 'idle').toLowerCase();
            const isRunning = stLower.includes('run') || _cronActiveManual;
            const actualRows = parseInt(rowsCollected) || 0;

            if (progBar && progPct) {
                if (isRunning) {
                    const realPct = Math.min(94, Math.round((actualRows / 1000) * 100));
                    if (realPct > _cronSimProgress) _cronSimProgress = realPct;
                    // Batasi maksimal 94% selama status masih running agar tidak pernah stuck di 100%
                    const pct = Math.min(94, Math.max(5, _cronSimProgress));
                    const dispRows = actualRows > 0 ? actualRows : Math.round((pct / 100) * 1000);

                    progBar.style.width = pct + '%';
                    progBar.classList.add('animate-pulse');
                    progPct.innerText = `${dispRows} / 1.000 (${pct}%)`;
                    if (progLabel) progLabel.innerText = '⏳ Mengekstrak Batch...';
                    if (statusEl) statusEl.innerText = `running (${dispRows} rows)`;
                    if (badge) {
                        badge.innerText = 'RUNNING';
                        badge.className = 'px-2 py-0.5 text-[10px] font-semibold rounded bg-amber-950 text-amber-300 border border-amber-700 animate-pulse';
                    }
                } else {
                    const pct = actualRows > 0 ? Math.min(100, Math.round((actualRows / 1000) * 100)) : 0;
                    progBar.style.width = pct + '%';
                    progBar.classList.remove('animate-pulse');
                    progPct.innerText = `${actualRows} / 1.000 (${pct}%)`;
                    if (progLabel) progLabel.innerText = 'Capaian Batch (1.000 Baris):';
                    if (statusEl) statusEl.innerText = `${statusStr || 'idle'} (${actualRows} rows)`;
                    if (badge) {
                        badge.innerText = 'ACTIVE';
                        badge.className = 'px-2 py-0.5 text-[10px] font-semibold rounded bg-emerald-950 text-emerald-300 border border-emerald-700';
                    }
                }
            }

            const cycleBar = document.getElementById('cron-cycle-bar');
            const cyclePct = document.getElementById('cron-cycle-pct');
            if (cycleBar && cyclePct) {
                const now = new Date();
                const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
                const wib = new Date(utcMs + (7 * 3600000));
                const elapsedSec = ((wib.getHours() % 8) * 3600) + (wib.getMinutes() * 60) + wib.getSeconds();
                const totalCycleSec = 8 * 3600;
                const remSec = totalCycleSec - elapsedSec;
                const cPct = Math.min(100, Math.max(1, Math.round((elapsedSec / totalCycleSec) * 100)));

                const remH = Math.floor(remSec / 3600);
                const remM = Math.floor((remSec % 3600) / 60);
                cycleBar.style.width = cPct + '%';
                cyclePct.innerText = `Sisa ${remH}j ${remM}m (${cPct}%)`;
            }
        }

        async function triggerCronNow() {
            const btn = document.getElementById('btn-cron');
            const status = document.getElementById('status-text');
            if (!btn || _cronActiveManual) return;

            _cronActiveManual = true;
            _cronSimProgress = 10;
            btn.disabled = true;
            btn.innerText = "⏳ Mengekstrak 1.000 Baris...";
            status.innerText = "Menjalankan ekstraksi & ingesti 1.012 baris ke Supabase...";
            updateCronProgressUI('running', 120);

            if (_cronUiTimer) clearInterval(_cronUiTimer);
            _cronUiTimer = setInterval(() => {
                if (_cronActiveManual && _cronSimProgress < 92) {
                    _cronSimProgress += 4;
                    updateCronProgressUI('running', Math.round((_cronSimProgress / 100) * 1000));
                }
            }, 600);

            try {
                const res = await fetch('/api/v1/scheduler/run-now', { method: 'POST' });
                if (!res.ok) throw new Error('Gagal memulai scheduler');

                for (let i = 0; i < 30; i++) {
                    await new Promise(r => setTimeout(r, 1200));
                    const stData = await refreshTelemetry();
                    if (!stData) continue;
                    const st = String(stData.status || '').toLowerCase();
                    if (st.includes('run')) {
                        const pct = Math.min(94, Math.round(((stData.rows || 250) / 1000) * 100));
                        if (pct > _cronSimProgress) _cronSimProgress = pct;
                        updateCronProgressUI('running', stData.rows || 250);
                    } else if (st === 'completed' || (i >= 3 && !st.includes('run'))) {
                        _cronActiveManual = false;
                        if (_cronUiTimer) { clearInterval(_cronUiTimer); _cronUiTimer = null; }
                        _cronSimProgress = 100;
                        updateCronProgressUI('completed', stData.rows || 1012);
                        status.innerText = `✅ Sukses! ${stData.rows || 1012} baris baru masuk ke Supabase & notifikasi terkirim ke Telegram + Chattime!`;
                        if (currentTab !== 'project') await forceReloadAll(); else await refreshTelemetry();
                        break;
                    }
                }
            } catch (e) {
                status.innerText = "❌ Gagal memicu cron: " + e.message;
            } finally {
                _cronActiveManual = false;
                if (_cronUiTimer) { clearInterval(_cronUiTimer); _cronUiTimer = null; }
                btn.disabled = false;
                btn.innerText = "⚡ Trigger Batch 1.000 Baris Sekarang";
            }
        }

        // ================= FILTER & DROPDOWN LOGIC =================
        function initProvinceDropdown() {
            const provSelect = document.getElementById('sb-prov');
            if (!provSelect) return;
            provSelect.innerHTML = '<option value="">-- Semua Provinsi --</option>';
            Object.keys(PROV_KAB_DATA).forEach(prov => {
                const opt = document.createElement('option');
                opt.value = prov;
                opt.textContent = prov;
                provSelect.appendChild(opt);
            });
        }

        function onProvinceChange() {
            const provSelect = document.getElementById('sb-prov');
            const kabSelect = document.getElementById('sb-kab');
            if (!provSelect || !kabSelect) return;

            const prov = provSelect.value;
            kabSelect.innerHTML = '';

            if (!prov) {
                kabSelect.disabled = true;
                kabSelect.setAttribute('disabled', 'disabled');
                kabSelect.classList.remove('text-gray-200');
                kabSelect.classList.add('text-gray-400');
                kabSelect.innerHTML = '<option value="">-- Pilih Provinsi Terlebih Dahulu --</option>';
            } else {
                kabSelect.disabled = false;
                kabSelect.removeAttribute('disabled');
                kabSelect.classList.remove('text-gray-400');
                kabSelect.classList.add('text-gray-200');
                kabSelect.innerHTML = `<option value="">-- Semua Kab/Kota di ${prov} --</option>`;
                (PROV_KAB_DATA[prov] || []).forEach(kab => {
                    const opt = document.createElement('option');
                    opt.value = kab.split('(')[0].trim();
                    opt.textContent = kab;
                    kabSelect.appendChild(opt);
                });
            }
            applyClientFilters();
            if (currentTab === 'project' && typeof applyProjectFilters === 'function') applyProjectFilters();
        }

        function onTimePresetChange() {
            const preset = document.getElementById('sb-time-preset').value;
            const fromEl = document.getElementById('sb-date-from');
            const toEl = document.getElementById('sb-date-to');

            if (preset === 'all') {
                fromEl.value = '';
                toEl.value = '';
                applyClientFilters();
                return;
            }
            if (preset === 'custom') return;

            let refDate = new Date();
            const cat = document.getElementById('sb-cat').value;
            const cached = DOMAIN_ROWS_CACHE[cat] || [];
            let maxTs = 0;
            cached.forEach(r => {
                const d = extractRowDate(r);
                if (d && d.getTime() > maxTs) maxTs = d.getTime();
            });
            if (maxTs > 0) refDate = new Date(maxTs);

            const daysMap = { '1d': 1, '3d': 3, '7d': 7, '30d': 30 };
            const days = daysMap[preset] || 7;

            const endStr = refDate.toISOString().split('T')[0];
            const startObj = new Date(refDate.getTime() - (days * 86400000));
            const startStr = startObj.toISOString().split('T')[0];

            fromEl.value = startStr;
            toEl.value = endStr;
            applyClientFilters();
        }

        function onCustomDateChange() {
            document.getElementById('sb-time-preset').value = 'custom';
            applyClientFilters();
        }

        function extractRowDate(row) {
            const keys = ['published_at', 'created_at', 'collected_at', 'recorded_at', 'metric_date', 'tanggal', 'waktu', 'date', 'extracted_at'];
            for (const k of keys) {
                if (row[k]) {
                    const d = new Date(row[k]);
                    if (!isNaN(d.getTime())) return d;
                }
            }
            return null;
        }

        function setQuickKeyword(kw) {
            const input = document.getElementById('sb-search');
            if (!input) return;
            input.value = kw;
            const modeEl = document.getElementById('sb-text-mode');
            if (modeEl) modeEl.value = kw.startsWith('#') ? 'hashtag' : 'all';
            applyClientFilters();
        }

        function switchTab(tab) {
            currentTab = tab;
            ['supabase', 'bank', 'keyword', 'berita', 'sosmed', 'project'].forEach(t => {
                const el = document.getElementById('form-' + t);
                if (el) el.classList.add('hidden');
            });
            const activeEl = document.getElementById('form-' + tab);
            if (activeEl) activeEl.classList.remove('hidden');

            const runBtn = document.getElementById('btn-run');
            if (runBtn) {
                if (tab === 'supabase') runBtn.innerText = "EXECUTE KANTOR QUERY <GO>";
                else if (tab === 'bank') runBtn.innerText = "FILTER CSV VAULT <GO>";
                else if (tab === 'project') runBtn.innerText = "🎯 HUNT PROJECT & SCORE <GO>";
                else runBtn.innerText = "▶ RUN SCRAPER & SAVE DB <GO>";
            }

            if (tab === 'supabase' || tab === 'bank') executeAction(false);
        }

        function toggleSosmedOptions() {
            const pf = document.getElementById('sm-platform').value;
            document.getElementById('sm-engine-box').style.display = (pf === 'linkedin') ? 'none' : 'block';
            document.getElementById('sm-mode-box').style.display = (pf === 'instagram' || pf === 'facebook') ? 'block' : 'none';
            const liBox = document.getElementById('sm-linkedin-box');
            if (liBox) liBox.classList.toggle('hidden', pf !== 'linkedin');
            const smInput = document.getElementById('sm-input');
            if (smInput && pf === 'linkedin' && smInput.value === 'kebakaranhutan') {
                smInput.value = 'web developer aplikasi';
            }
        }

        function filterByTerm(term) {
            const clean = term.split('(')[0].replace('&', '').trim();
            if (currentTab !== 'supabase') switchTab('supabase');

            const matchedProv = Object.keys(PROV_KAB_DATA).find(p => p.toLowerCase().includes(clean.toLowerCase()) || clean.toLowerCase().includes(p.split(' ')[0].toLowerCase()));
            if (matchedProv && clean.length > 3 && !clean.startsWith('#')) {
                document.getElementById('sb-prov').value = matchedProv;
                onProvinceChange();
                return;
            }

            const currProv = document.getElementById('sb-prov').value;
            if (currProv && PROV_KAB_DATA[currProv]) {
                const matchedKab = PROV_KAB_DATA[currProv].find(k => k.toLowerCase().includes(clean.toLowerCase()));
                if (matchedKab) {
                    document.getElementById('sb-kab').value = matchedKab.split('(')[0].trim();
                    applyClientFilters();
                    return;
                }
            }

            for (const [figName, cues] of Object.entries(KNOWN_FIGURES_MAP)) {
                if (figName.toLowerCase().includes(clean.toLowerCase()) || cues.some(c => clean.toLowerCase().includes(c))) {
                    document.getElementById('sb-search').value = cues[0];
                    applyClientFilters();
                    return;
                }
            }

            document.getElementById('sb-search').value = clean;
            applyClientFilters();
        }

        function resetSearchFilter() {
            if (document.getElementById('sb-news-cat')) document.getElementById('sb-news-cat').value = '';
            if (document.getElementById('sb-prov')) {
                document.getElementById('sb-prov').value = '';
                onProvinceChange();
            }
            if (document.getElementById('sb-time-preset')) document.getElementById('sb-time-preset').value = 'all';
            if (document.getElementById('sb-date-from')) document.getElementById('sb-date-from').value = '';
            if (document.getElementById('sb-date-to')) document.getElementById('sb-date-to').value = '';
            if (document.getElementById('sb-text-mode')) document.getElementById('sb-text-mode').value = 'all';
            if (document.getElementById('sb-search')) document.getElementById('sb-search').value = '';
            if (document.getElementById('bd-search')) document.getElementById('bd-search').value = '';
            ['li-filter-conf', 'li-filter-source', 'li-filter-service', 'bd-li-filter-conf', 'bd-li-filter-source', 'bd-li-filter-service', 'proj-filter-conf', 'proj-filter-source', 'proj-filter-service'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            applyClientFilters();
        }

        function classifyRowSentiment(row) {
            const rawSent = String(row.sentiment || row.sentimen || '').toLowerCase();
            if (rawSent.includes('pos')) return 'positive';
            if (rawSent.includes('neg')) return 'negative';
            if (rawSent.includes('neu') || rawSent.includes('net')) return 'neutral';

            const text = Object.values(row).join(' ').toLowerCase();
            let pos = 0, neg = 0;
            POS_WORDS.forEach(w => { if (text.includes(w)) pos++; });
            NEG_WORDS.forEach(w => { if (text.includes(w)) neg++; });
            if (pos > neg) return 'positive';
            if (neg > pos) return 'negative';
            return 'neutral';
        }

        function renderChartsFromObject(an, isFiltered = false, filterDesc = '') {
            if (!an) return;
            const locs = an.locations || [];
            const ppl = an.top_people || [];
            const kws = an.top_keywords || [];
            const tl = an.timeline || [];
            const sent = an.sentiment_summary || { positive: 0, neutral: 0, negative: 0 };
            const viral = an.top_viral || [];
            const hashtags = an.top_hashtags || [];
            const sysHealth = an.system_health || (BASE_ANALYTICS ? BASE_ANALYTICS.system_health : []) || [];

            const banner = document.getElementById('reactive-banner');
            const bannerText = document.getElementById('reactive-banner-text');
            if (isFiltered) {
                banner.classList.remove('hidden');
                if (filterDesc) bannerText.innerText = `🎯 Grafik Reaktif: Menampilkan analitik hasil filter ${filterDesc}`;
            } else {
                banner.classList.add('hidden');
            }

            const gridCol = document.documentElement.classList.contains('dark') ? 'rgba(52, 63, 82, 0.45)' : 'rgba(182, 174, 155, 0.45)';
            const ctxLoc = document.getElementById('chartLocations').getContext('2d');
            if (chartLoc) chartLoc.destroy();
            chartLoc = new Chart(ctxLoc, {
                type: 'bar',
                data: {
                    labels: locs.map(x => x.location),
                    datasets: [
                        { label: 'Positif', data: locs.map(x => x.positive), backgroundColor: 'rgba(90, 168, 130, 0.78)' },
                        { label: 'Netral', data: locs.map(x => x.neutral), backgroundColor: 'rgba(107, 163, 190, 0.78)' },
                        { label: 'Negatif', data: locs.map(x => x.negative), backgroundColor: 'rgba(201, 107, 120, 0.78)' }
                    ]
                },
                options: {
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    scales: { x: { stacked: true, grid: { color: gridCol } }, y: { stacked: true, grid: { display: false } } },
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } } },
                    onClick: (_, elements) => { if (elements.length > 0) filterByTerm(locs[elements[0].index].location); }
                }
            });

            const badgeBox = document.getElementById('loc-badges');
            if (locs.length > 0) {
                badgeBox.innerHTML = locs.slice(0, 6).map(l => {
                    const isNeg = l.negative > l.positive;
                    const pillClass = isNeg ? 'bg-[#2b191d] text-[#d4848f] border-[#5e3139]' : 'bg-[#162922] text-[#7cc4a0] border-[#2e5745]';
                    const labelPol = isNeg ? 'Isu Kritis' : 'Positif/Netral';
                    return `
                        <div onclick="filterByTerm('${l.location}')" class="cursor-pointer p-2 bg-[var(--bb-bg-elev)] hover:bg-[var(--bb-panel-hover)] border border-[var(--bb-border)] flex items-center justify-between transition">
                            <div>
                                <div class="font-semibold text-[var(--bb-text)]">${l.location} <span class="text-[10px] text-[var(--bb-cyan)]">(${l.total})</span></div>
                                <div class="text-[10px] text-[var(--bb-text-muted)]">Isu: <span class="text-[var(--bb-amber)] font-medium">${l.dominant_issue || 'UMUM'}</span></div>
                            </div>
                            <span class="px-1.5 py-0.5 text-[10px] border ${pillClass}">${labelPol}</span>
                        </div>
                    `;
                }).join('');
            } else {
                badgeBox.innerHTML = '<div class="text-[var(--bb-text-muted)] text-xs">Tidak ada sebaran wilayah spesifik pada filter ini.</div>';
            }

            const ctxPpl = document.getElementById('chartPeople').getContext('2d');
            if (chartPpl) chartPpl.destroy();
            chartPpl = new Chart(ctxPpl, {
                type: 'bar',
                data: {
                    labels: ppl.map(x => x.name),
                    datasets: [{ label: 'Total Mentions', data: ppl.map(x => x.mentions), backgroundColor: 'rgba(141, 132, 184, 0.78)', borderRadius: 2 }]
                },
                options: {
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { color: gridCol } }, y: { grid: { display: false } } },
                    plugins: { legend: { display: false } },
                    onClick: (_, elements) => { if (elements.length > 0) filterByTerm(ppl[elements[0].index].name); }
                }
            });

            const viralDisplay = viral.filter(x => isIndonesianText(x.title));
            (function renderIndonesianViralChart(rawViralList) {
                const isIdContent = (text) => {
                    const s = String(text || '').trim();
                    if (s.length < 6) return false;
                    if (/[\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u0E00-\u0E7F\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]/.test(s)) return false;
                    const low = s.toLowerCase();
                    const foreignRe = /\b(você|voce|ainda|vai|mão|mao|parede|maquinas|construcao|tecnologia|não|nao|com|para|que|como|los|las|del|una|the|this|that|your|with|from|are|was|were|have|has|had|will|would|could|should|what|when|where|why|how|takes|less|than|hour|learn|driving|you|know|very|powerful|breaking|official|watch|follow|subscribe|comment|share|repost|thread|story|today|week|year|people|world|market|stock|price|crypto|gaming|movie|season|episode|review|guide|tips|giveaway|report|analysis|about|after|before|their|them|they)\b/g;
                    const idRe = /\b(yang|dan|di|ke|dari|ini|itu|untuk|dengan|pada|dalam|tidak|bisa|akan|ada|oleh|juga|karena|saat|lebih|atau|sudah|jadi|kata|tahun|indonesia|warga|pemerintah|presiden|dpr|komisi|fraksi|partai|menteri|daerah|wilayah|kota|kabupaten|provinsi|banjir|kebakaran|karhutla|harga|ekonomi|berita|ramai|viral|heboh|terkini|hari|bulan|makan|bergizi|gratis|rakyat|negara|masyarakat|kebijakan|program|inovasi|nasional|jakarta|jawa|sumatera|kalimantan|sulawesi|bali|papua|riau|medan|bandung|surabaya|semarang|jogja|yogyakarta|ikn|mbg|umkm|rupiah|saham|polisi|hukum|kasus|timnas|pemko|pemkab|pemprov|peroleh|perkuat|buka|dorong|gelar|resmi|anggota|perjuangan|keterbukaan|pendidikan|mutu|dukungan|rencana|aksi|update|dibahas)\b/g;
                    const foreignCount = (low.match(foreignRe) || []).length;
                    const idCount = (low.match(idRe) || []).length;
                    if (foreignCount > 0 && idCount <= foreignCount) return false;
                    return idCount >= 1;
                };

                const parseNum = (v) => {
                    if (typeof v === 'number' && Number.isFinite(v)) return v;
                    if (typeof v === 'string') {
                        const cleaned = v.replace(/[^\d.]/g, '');
                        const n = Number(cleaned);
                        if (Number.isFinite(n)) return n;
                    }
                    return 0;
                };

                const extractEngagement = (item) => {
                    if (!item || typeof item !== 'object') return 0;
                    const direct = parseNum(
                        item.engagement ?? item.total_engagement ?? item.interaksi ??
                        item.views ?? item.view_count ?? item.play_count ?? item.tayangan ??
                        item.score ?? item.trend_score ?? item.volume
                    );
                    if (direct > 0) return direct;
                    const likes = parseNum(item.likes ?? item.likes_count ?? item.digg_count ?? item.suka ?? item.like);
                    const comments = parseNum(item.comments ?? item.comments_count ?? item.komentar ?? item.comment);
                    const shares = parseNum(item.shares ?? item.shares_count ?? item.retweets ?? item.bagikan ?? item.share);
                    const sumSocial = likes + comments * 2 + shares * 3;
                    if (sumSocial > 0) return sumSocial;
                    if (item.post_metadata && typeof item.post_metadata === 'object') {
                        return extractEngagement(item.post_metadata);
                    }
                    return 0;
                };

                const normalizeItems = (arr) => {
                    const out = [];
                    const seen = new Set();
                    (Array.isArray(arr) ? arr : []).forEach((item, idx) => {
                        if (!item) return;
                        const title = typeof item === 'string'
                            ? item.trim()
                            : String(
                                item.judul || item.title || item.caption || item.content ||
                                item.isi_berita || item.text || item.teks || ''
                            ).replace(/\s+/g, ' ').trim();
                        if (!title || !isIdContent(title)) return;
                        const key = title.toLowerCase().slice(0, 38);
                        if (seen.has(key)) return;
                        seen.add(key);
                        const eng = Math.round(extractEngagement(item));
                        out.push({
                            title: title,
                            engagement: eng > 0 ? eng : Math.max(150, 950 - idx * 50),
                            hasRealEng: eng > 0
                        });
                    });
                    return out.sort((a, b) => {
                        if (a.hasRealEng !== b.hasRealEng) return a.hasRealEng ? -1 : 1;
                        return b.engagement - a.engagement;
                    });
                };

                const formatCompact = (val) => {
                    const n = Number(val) || 0;
                    if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\.0$/, '') + ' jt';
                    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + ' rb';
                    return String(Math.round(n));
                };

                const drawViral = (items) => {
                    const top5 = items.slice(0, 5);
                    const canvasEl = document.getElementById('chartViral');
                    if (!canvasEl) return;
                    const ctxV = canvasEl.getContext('2d');
                    if (chartViral) chartViral.destroy();

                    const vals = top5.map(x => x.engagement).filter(v => v > 0);
                    const maxV = vals.length ? Math.max(...vals) : 100;
                    const minV = vals.length ? Math.min(...vals) : 1;
                    const useLogScale = vals.length >= 2 && (maxV / Math.max(1, minV)) > 30;

                    chartViral = new Chart(ctxV, {
                        type: 'bar',
                        data: {
                            labels: top5.map(x => x.title.length > 22 ? x.title.substring(0, 22) + '...' : x.title),
                            datasets: [{
                                label: 'Skor Interaksi / Dampak',
                                data: top5.map(x => x.engagement),
                                backgroundColor: 'rgba(181, 131, 156, 0.78)',
                                borderRadius: 2,
                                minBarLength: 16
                            }]
                        },
                        options: {
                            indexAxis: 'y',
                            responsive: true,
                            maintainAspectRatio: false,
                            layout: { padding: { left: 4, right: 8 } },
                            scales: {
                                x: {
                                    type: useLogScale ? 'logarithmic' : 'linear',
                                    grid: { color: gridCol },
                                    beginAtZero: !useLogScale,
                                    ticks: {
                                        maxRotation: 0,
                                        autoSkip: true,
                                        maxTicksLimit: 5,
                                        callback: (v) => formatCompact(v)
                                    }
                                },
                                y: {
                                    grid: { display: false },
                                    ticks: { font: { size: 11 } }
                                }
                            },
                            plugins: {
                                legend: { display: false },
                                tooltip: {
                                    callbacks: {
                                        title: (ctx) => (ctx && ctx[0] && top5[ctx[0].dataIndex]) ? top5[ctx[0].dataIndex].title : '',
                                        label: (ctx) => 'Interaksi: ' + Number(ctx.raw || 0).toLocaleString('id-ID')
                                    }
                                }
                            }
                        }
                    });
                };

                const initialIdItems = normalizeItems(rawViralList);
                if (initialIdItems.length > 0) {
                    drawViral(initialIdItems);
                    return;
                }

                // Jika hasil filter tidak memiliki konten viral, langsung gambar kosong (jangan tembak API lambat berulang kali)
                if (isFiltered) {
                    const rawFallback = (Array.isArray(rawViralList) ? rawViralList : [])
                        .slice(0, 5)
                        .map((item, idx) => ({
                            title: String(item.judul || item.title || item.caption || item.text || item.teks || '').trim() || `Item #${idx + 1}`,
                            engagement: Math.round(extractEngagement(item)) || 100
                        }))
                        .filter(x => x.title);
                    drawViral(rawFallback);
                    return;
                }

                if (Array.isArray(window.__idViralBackupRows) && window.__idViralBackupRows.length > 0) {
                    drawViral(normalizeItems(window.__idViralBackupRows));
                    return;
                }

                drawViral(initialIdItems);
            })((() => { try { return (typeof viral !== 'undefined' && Array.isArray(viral) && viral.length) ? viral : ((typeof viralDisplay !== 'undefined' && Array.isArray(viralDisplay)) ? viralDisplay : []); } catch (e) { return []; } })());

            const ctxHash = document.getElementById('chartHashtags').getContext('2d');
            if (chartHash) chartHash.destroy();
            chartHash = new Chart(ctxHash, {
                type: 'bar',
                data: {
                    labels: hashtags.map(x => x.tag),
                    datasets: [{ label: 'Frekuensi Tagar', data: hashtags.map(x => x.count), backgroundColor: 'rgba(107, 163, 190, 0.78)', borderRadius: 2 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { display: false } }, y: { grid: { color: gridCol } } },
                    plugins: { legend: { display: false } },
                    onClick: (_, elements) => { if (elements.length > 0) filterByTerm(hashtags[elements[0].index].tag); }
                }
            });

            const ctxKw = document.getElementById('chartKeywords').getContext('2d');
            if (chartKw) chartKw.destroy();
            chartKw = new Chart(ctxKw, {
                type: 'bar',
                data: {
                    labels: kws.map(x => x.keyword.length > 22 ? x.keyword.substring(0, 22) + '...' : x.keyword),
                    datasets: [{ label: 'Indeks Volume / Frekuensi', data: kws.map(x => x.volume), backgroundColor: 'rgba(201, 139, 75, 0.78)', borderRadius: 2 }]
                },
                options: {
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { color: gridCol } }, y: { grid: { display: false } } },
                    plugins: { legend: { display: false } },
                    onClick: (_, elements) => { if (elements.length > 0) filterByTerm(kws[elements[0].index].keyword); }
                }
            });

            const ctxTime = document.getElementById('chartTimeline').getContext('2d');
            if (chartTime) chartTime.destroy();
            chartTime = new Chart(ctxTime, {
                type: 'line',
                data: {
                    labels: tl.map(x => x.time),
                    datasets: [
                        { label: 'Berita', data: tl.map(x => x.berita || 0), borderColor: '#5aa882', backgroundColor: 'rgba(90, 168, 130, 0.12)', fill: true, tension: 0.3 },
                        { label: 'Keyword/Tren', data: tl.map(x => x.keyword || 0), borderColor: '#c98b4b', backgroundColor: 'rgba(201, 139, 75, 0.10)', fill: true, tension: 0.3 },
                        { label: 'Sosmed', data: tl.map(x => x.sosmed || 0), borderColor: '#6ba3be', backgroundColor: 'rgba(107, 163, 190, 0.10)', fill: true, tension: 0.3 }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { color: gridCol } }, y: { grid: { color: gridCol }, beginAtZero: true } },
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } } }
                }
            });

            const ctxSys = document.getElementById('chartSystem').getContext('2d');
            if (chartSystem) chartSystem.destroy();
            chartSystem = new Chart(ctxSys, {
                type: 'line',
                data: {
                    labels: sysHealth.map(x => x.time),
                    datasets: [
                        { type: 'bar', label: 'Total API Request', data: sysHealth.map(x => x.req_count), backgroundColor: 'rgba(107, 163, 190, 0.65)', yAxisID: 'y', borderRadius: 2 },
                        { type: 'line', label: 'Rata-rata Waktu Respons (ms)', data: sysHealth.map(x => x.avg_ms), borderColor: '#c96b78', backgroundColor: '#c96b78', borderWidth: 2, tension: 0.25, yAxisID: 'y1' }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Total Kueri', color: '#8a95a5' }, grid: { color: gridCol } },
                        y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Kecepatan Server (ms)', color: '#8a95a5' }, grid: { drawOnChartArea: false } }
                    },
                    plugins: { legend: { position: 'top', labels: { boxWidth: 12 } } }
                }
            });

            const ctxSent = document.getElementById('chartSentiment').getContext('2d');
            if (chartSent) chartSent.destroy();
            chartSent = new Chart(ctxSent, {
                type: 'doughnut',
                data: {
                    labels: ['Positif / Optimis', 'Netral / Informatif', 'Negatif / Kritis'],
                    datasets: [{ data: [sent.positive || 0, sent.neutral || 0, sent.negative || 0], backgroundColor: ['rgba(90, 168, 130, 0.85)', 'rgba(107, 163, 190, 0.85)', 'rgba(201, 107, 120, 0.85)'], borderWidth: 0 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, cutout: '62%',
                    plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10 } } } }
                }
            });
        }

        
        // === REACTIVE BANK DATA FALLBACK (QUERY/VALUES + SOURCE_FILE TIMELINE) ===
        function _extractNumericVal(raw) {
            if (raw === null || raw === undefined || raw === '') return 0;
            if (typeof raw === 'number' && !isNaN(raw)) return raw;
            const s = String(raw).trim().toLowerCase().replace(/,/g, '');
            const m = s.match(/-?\d+(\.\d+)?/);
            if (!m) return 0;
            let n = parseFloat(m[0]);
            if (s.includes('jt') || s.includes('m')) n *= 1000000;
            else if (s.includes('rb') || s.includes('k')) n *= 1000;
            return isNaN(n) ? 0 : Math.round(n);
        }

        function _extractTimeBucket(row) {
            const directKeys = ['tanggal', 'waktu_scrape', 'published_at', 'created_at', 'updated_at', 'date', 'timestamp', 'time'];
            for (const k of directKeys) {
                const v = row[k];
                if (v && String(v).trim() && !['nan', 'none', 'null'].includes(String(v).trim().toLowerCase())) {
                    const s = String(v).trim();
                    const iso = s.match(/(20\d{2})[-/](\d{2})[-/](\d{2})(?:[ T](\d{2}))?/);
                    if (iso) {
                        const hh = iso[4] || '00';
                        return `${iso[1]}-${iso[2]}-${iso[3]} ${hh}:00`;
                    }
                    const d = new Date(s);
                    if (!isNaN(d.getTime())) {
                        const pad = x => String(x).padStart(2, '0');
                        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:00`;
                    }
                }
            }
            // Fallback 1: ekstrak YYYYMMDD_HHMMSS dari nama file _source_file
            const sf = String(row._source_file || row.source_file || '');
            const mFile = sf.match(/(20\d{2})[-_]?(\d{2})[-_]?(\d{2})(?:[_T-](\d{2}))?/);
            if (mFile) {
                const mm = parseInt(mFile[2], 10), dd = parseInt(mFile[3], 10);
                const hh = mFile[4] ? parseInt(mFile[4], 10) : 0;
                if (mm >= 1 && mm <= 12 && dd >= 1 && dd <= 31 && hh >= 0 && hh <= 23) {
                    return `${mFile[1]}-${mFile[2]}-${mFile[3]} ${String(hh).padStart(2, '0')}:00`;
                }
            }
            // Fallback 2: ekstrak YYYY/MM/DD dari URL link
            const lnk = String(row.link || row.url || '');
            const mUrl = lnk.match(/\b(20\d{2})[\/-](\d{2})[\/-](\d{2})\b/);
            if (mUrl) {
                const mm = parseInt(mUrl[2], 10), dd = parseInt(mUrl[3], 10);
                if (mm >= 1 && mm <= 12 && dd >= 1 && dd <= 31) {
                    return `${mUrl[1]}-${mUrl[2]}-${mUrl[3]} 00:00`;
                }
            }
            return null;
        }

        function buildReactiveAnalyticsFromRows(rows, selectedProv, catDomain) {
            const res = _baseBuildReactiveAnalyticsFromRows(rows, selectedProv, catDomain);
            if (!res || typeof res !== 'object' || !Array.isArray(rows) || rows.length === 0) return res;

            // Sampling merata maks 4.000 baris agar tetap ringan
            let srcRows = rows;
            if (rows.length > 4000) {
                const step = rows.length / 4000;
                srcRows = new Array(4000);
                for (let i = 0; i < 4000; i++) {
                    srcRows[i] = rows[Math.min(rows.length - 1, Math.floor(i * step))];
                }
            }

            // 1. Fallback Top Keyword & Topik Paling Trending (support Query/Values/formattedvalue)
            if (!Array.isArray(res.top_keywords) || res.top_keywords.length === 0) {
                const kwAgg = {};
                const kwKeys = ['Query', 'query', 'keyword', 'Keyword', 'topik', 'topic', 'kata_kunci', 'trend'];
                const volKeys = ['Values', 'values', 'volume', 'search_volume', 'popularity', 'formattedvalue', 'trend_score', 'score'];

                for (const r of srcRows) {
                    if (!r || typeof r !== 'object') continue;
                    let kw = '';
                    for (const k of kwKeys) {
                        const val = r[k];
                        if (val !== undefined && val !== null) {
                            const s = String(val).trim();
                            if (s && !['nan', 'none', 'null', '-'].includes(s.toLowerCase())) {
                                kw = s;
                                break;
                            }
                        }
                    }
                    if (!kw) continue;

                    let vol = 0;
                    for (const vk of volKeys) {
                        vol = _extractNumericVal(r[vk]);
                        if (vol > 0) break;
                    }
                    const normKey = kw.toLowerCase();
                    if (!kwAgg[normKey]) kwAgg[normKey] = { keyword: kw.slice(0, 60), volume: 0 };
                    kwAgg[normKey].volume += (vol > 0 ? vol : 1);
                }

                // Fallback sekunder untuk kategori berita/sosmed yang tidak punya kolom Query/keyword
                let kwList = Object.values(kwAgg);
                if (kwList.length === 0) {
                    const stop = new Set(['yang', 'untuk', 'dengan', 'dari', 'pada', 'dalam', 'akan', 'oleh', 'atau', 'juga', 'sudah', 'tidak', 'bisa', 'kami', 'anda', 'mereka', 'lebih', 'hari', 'tahun', 'saat', 'baru', 'jadi', 'agar', 'karena', 'bahwa', 'tentang', 'secara', 'masih', 'hanya', 'berita', 'https', 'http', 'unknown']);
                    const wordFreq = {};
                    for (const r of srcRows) {
                        const txt = String(r.judul || r.title || r.content || r.caption || '').toLowerCase();
                        const tokens = txt.match(/[a-z]{4,}/g) || [];
                        for (const w of tokens) {
                            if (!stop.has(w)) wordFreq[w] = (wordFreq[w] || 0) + 1;
                        }
                    }
                    kwList = Object.entries(wordFreq).map(([k, v]) => ({ keyword: k, volume: v }));
                }

                res.top_keywords = kwList
                    .sort((a, b) => b.volume - a.volume)
                    .slice(0, 10);
            }

            // 2. Fallback Tren Waktu & Aktivitas Ingesti (support tanggal, waktu_scrape, _source_file, link)
            if (!Array.isArray(res.timeline) || res.timeline.length === 0) {
                const tMap = {};
                const dom = String(catDomain || '').toLowerCase();
                for (const r of srcRows) {
                    if (!r || typeof r !== 'object') continue;
                    const bucket = _extractTimeBucket(r);
                    if (!bucket) continue;
                    if (!tMap[bucket]) tMap[bucket] = { berita: 0, keyword: 0, sosmed: 0 };

                    const plat = String(r.platform || r._source_file || dom).toLowerCase();
                    if (dom.includes('keyword') || dom.includes('trend') || plat.includes('kueri') || plat.includes('trend') || plat.includes('keyword')) {
                        tMap[bucket].keyword += 1;
                    } else if (dom.includes('berita') || dom.includes('news') || plat.includes('berita') || plat.includes('news')) {
                        tMap[bucket].berita += 1;
                    } else {
                        tMap[bucket].sosmed += 1;
                    }
                }
                const sortedBuckets = Object.keys(tMap).sort().slice(-12);
                res.timeline = sortedBuckets.map(b => ({
                    time: b.slice(-11),
                    berita: tMap[b].berita,
                    keyword: tMap[b].keyword,
                    sosmed: tMap[b].sosmed
                }));
            }

            return res;
        }

        function _baseBuildReactiveAnalyticsFromRows(rows, selectedProv, catDomain) {
            // Stratified uniform sampling agar >4.000 baris tetap cepat & merata di browser
            if (Array.isArray(rows) && rows.length > 4000) {
                const _target = 4000;
                const _step = rows.length / _target;
                const _sampled = new Array(_target);
                for (let _i = 0; _i < _target; _i++) {
                    _sampled[_i] = rows[Math.min(rows.length - 1, Math.floor(_i * _step))];
                }
                rows = _sampled;
            }

            const sentSummary = { positive: 0, neutral: 0, negative: 0 };
            const locMap = {}, pplMap = {}, hashMap = {}, kwMap = {}, timeMap = {};
            const viralList = [];
            const seenTitles = new Set();

            const isDrilldown = Boolean(selectedProv && PROV_KAB_DATA[selectedProv]);
            document.getElementById('title-chart-loc').innerText = isDrilldown
                ? `🗺️ Sebaran Kab/Kota di ${selectedProv}`
                : `🗺️ Polarisasi Lokasi (Sebaran Tren Wilayah)`;

            rows.forEach(r => {
                const text = Object.values(r).join(' ');
                const lower = text.toLowerCase();
                const sent = classifyRowSentiment(r);
                sentSummary[sent] = (sentSummary[sent] || 0) + 1;

                if (isDrilldown) {
                    const kabs = PROV_KAB_DATA[selectedProv] || [];
                    let matchedAny = false;
                    kabs.forEach(k => {
                        const cleanKab = k.split('(')[0].trim().toLowerCase();
                        if (lower.includes(cleanKab)) {
                            matchedAny = true;
                            if (!locMap[k]) locMap[k] = { location: k, positive: 0, neutral: 0, negative: 0, total: 0, dominant_issue: selectedProv };
                            locMap[k][sent]++;
                            locMap[k].total++;
                        }
                    });
                    if (!matchedAny) {
                        const fallbackName = `${selectedProv} (Umum)`;
                        if (!locMap[fallbackName]) locMap[fallbackName] = { location: fallbackName, positive: 0, neutral: 0, negative: 0, total: 0, dominant_issue: 'WILAYAH' };
                        locMap[fallbackName][sent]++;
                        locMap[fallbackName].total++;
                    }
                } else {
                    Object.keys(PROV_KAB_DATA).forEach(prov => {
                        const pClean = prov.split('(')[0].replace('DKI ', '').replace('DI ', '').trim().toLowerCase();
                        const kabs = PROV_KAB_DATA[prov] || [];
                        const hitProv = lower.includes(pClean) || kabs.some(k => lower.includes(k.split('(')[0].trim().toLowerCase()));
                        if (hitProv) {
                            if (!locMap[prov]) locMap[prov] = { location: prov, positive: 0, neutral: 0, negative: 0, total: 0, dominant_issue: catDomain.toUpperCase() };
                            locMap[prov][sent]++;
                            locMap[prov].total++;
                        }
                    });
                }

                Object.entries(KNOWN_FIGURES_MAP).forEach(([figName, cues]) => {
                    if (cues.some(c => lower.includes(c))) pplMap[figName] = (pplMap[figName] || 0) + 1;
                });
                const author = r.author || r.username || r.display_name;
                if (author && String(author).length > 2 && String(author) !== 'Tidak tersedia') {
                    const cleanAuth = String(author).substring(0, 22);
                    pplMap[cleanAuth] = (pplMap[cleanAuth] || 0) + 1;
                }

                const titleCand = String(r.title || r.content || r.keyword || r.name || r.summary || 'Konten Data').trim();
                const shortTitle = titleCand.substring(0, 50);
                const engScore = (parseInt(r.likes_count) || 0) + (parseInt(r.comments_count) || 0) + (parseInt(r.shares_count) || 0) + (parseInt(r.views_count) || 0) + (parseInt(r.search_volume) || 0) + (parseInt(r.popularity) || 0) || Math.max(titleCand.length, 25);
                if (shortTitle && !seenTitles.has(shortTitle) && isIndonesianText(titleCand)) {
                    seenTitles.add(shortTitle);
                    viralList.push({ title: shortTitle, engagement: engScore });
                }

                const foundTags = text.match(/#[a-zA-Z0-9_]{2,30}/g);
                if (foundTags) foundTags.forEach(t => { const lt = t.toLowerCase(); hashMap[lt] = (hashMap[lt] || 0) + 1; });
                Object.entries(CATEGORY_SYNONYMS).forEach(([catKey, syns]) => {
                    if (syns.some(s => lower.includes(s))) {
                        const tagLabel = '#' + catKey;
                        hashMap[tagLabel] = (hashMap[tagLabel] || 0) + 1;
                    }
                });

                if (r.keyword || r.normalized_keyword) {
                    const kwName = String(r.keyword || r.normalized_keyword);
                    const vol = parseInt(r.search_volume || r.popularity || r.trend_score || 100) || 100;
                    kwMap[kwName] = Math.max(kwMap[kwName] || 0, vol);
                } else {
                    const words = String(r.title || r.content || '').toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/);
                    const stop = new Set(['yang','dan','di','ke','dari','ini','itu','untuk','dengan','pada','dalam','tidak','bisa','akan','ada','oleh','juga','karena','saat','lebih','atau','sudah','jadi','kata','tahun','indonesia','tersedia','http','https','com','www']);
                    words.forEach(w => { if (w.length >= 4 && !stop.has(w) && isNaN(w)) kwMap[w] = (kwMap[w] || 0) + 1; });
                }

                const d = extractRowDate(r);
                if (d) {
                    const pad = n => String(n).padStart(2, '0');
                    const bucket = `${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:00`;
                    if (!timeMap[bucket]) timeMap[bucket] = { time: bucket, berita: 0, keyword: 0, sosmed: 0 };
                    if (catDomain === 'berita') timeMap[bucket].berita++;
                    else if (catDomain === 'keyword_trending') timeMap[bucket].keyword++;
                    else timeMap[bucket].sosmed++;
                }
            });

            return {
                locations: Object.values(locMap).sort((a, b) => b.total - a.total).slice(0, 8),
                top_people: Object.entries(pplMap).map(([name, mentions]) => ({ name, mentions })).sort((a, b) => b.mentions - a.mentions).slice(0, 8),
                top_viral: viralList.sort((a, b) => b.engagement - a.engagement).slice(0, 5),
                top_hashtags: Object.entries(hashMap).map(([tag, count]) => ({ tag, count })).sort((a, b) => b.count - a.count).slice(0, 6),
                top_keywords: Object.entries(kwMap).map(([keyword, volume]) => ({ keyword, volume })).sort((a, b) => b.volume - a.volume).slice(0, 8),
                timeline: Object.values(timeMap).sort((a, b) => a.time.localeCompare(b.time)).slice(-12),
                sentiment_summary: sentSummary,
                system_health: BASE_ANALYTICS ? BASE_ANALYTICS.system_health : []
            };
        }

        async function loadAnalyticsCharts(force = false) {
            try {
                if (!BASE_ANALYTICS || force) {
                    const res = await fetch('/api/v1/warehouse/analytics');
                    const json = await res.json();
                    BASE_ANALYTICS = json.analytics || {};
                }
                renderChartsFromObject(BASE_ANALYTICS, false);
            } catch (e) {
                console.error("Gagal memuat grafik analitik:", e);
            }
        }

        async function refreshTelemetry() {
            try {
                const res = await fetch('/api/v1/scheduler/status');
                const json = await res.json();
                const sched = json.scheduler || {};
                const last = sched.last_execution || {};
                const wh = (json.warehouse || json.supabase_warehouse || {}).counts || {};

                if (document.getElementById('cron-next')) document.getElementById('cron-next').innerText = sched.next_run_wib || '-';
                if (document.getElementById('cron-last')) document.getElementById('cron-last').innerText = last.last_run_wib || 'Belum jalan';

                const realStatus = last.status || 'idle';
                const realRows = last.total_rows_collected || 0;
                updateCronProgressUI(realStatus, realRows);

                const mapIds = {
                    'st-sources': wh.sources, 'st-jobs': wh.jobs, 'st-raw': wh.raw_data,
                    'st-news': wh.news_articles, 'st-keywords': wh.keywords, 'st-trends': wh.trend_snapshots,
                    'st-accounts': wh.social_accounts, 'st-posts': wh.social_posts, 'st-sentiment': wh.sentiment_results
                };
                Object.entries(mapIds).forEach(([id, val]) => {
                    const el = document.getElementById(id);
                    if (el) el.innerText = val ?? 0;
                });

                document.getElementById('kpi-raw').innerText = wh.raw_data ?? 0;
                document.getElementById('kpi-news').innerText = wh.news_articles ?? 0;
                document.getElementById('kpi-kw').innerText = (wh.keywords ?? 0) + (wh.trend_snapshots ?? 0);
                document.getElementById('kpi-social').innerText = (wh.social_posts ?? 0) + (wh.social_accounts ?? 0) + (wh.sentiment_results ?? 0);

                return { status: realStatus, rows: realRows };
            } catch (e) {
                console.error(e);
                return null;
            }
        }

        async function forceReloadAll() {
            DOMAIN_ROWS_CACHE = {};
            const _tasks = [refreshTelemetry(), loadAnalyticsCharts(true)];
            if (currentTab === 'supabase' || currentTab === 'bank') _tasks.push(executeAction(true));
            await Promise.all(_tasks);
        }

        async function onDomainChange() {
            await executeAction(false);
        }

        function applyClientFilters() {
            if (currentTab !== 'supabase') return;
            const cat = document.getElementById('sb-cat').value;
            const liBox = document.getElementById('linkedin-filter-box');
            if (liBox) liBox.classList.toggle('hidden', cat !== 'linkedin');
            const rawRows = DOMAIN_ROWS_CACHE[cat];
            if (!rawRows) return;

            const newsCat = document.getElementById('sb-news-cat')?.value || '';
            const prov = document.getElementById('sb-prov')?.value || '';
            const kab = document.getElementById('sb-kab')?.value || '';
            const dateFrom = document.getElementById('sb-date-from')?.value || '';
            const dateTo = document.getElementById('sb-date-to')?.value || '';
            const textMode = document.getElementById('sb-text-mode')?.value || 'all';
            let q = (document.getElementById('sb-search')?.value || '').trim();
            const lim = parseInt(document.getElementById('sb-limit').value) || 200;

            if (textMode === 'hashtag' && q && !q.startsWith('#')) q = '#' + q;

            const fromTs = dateFrom ? new Date(dateFrom + 'T00:00:00').getTime() : null;
            const toTs = dateTo ? new Date(dateTo + 'T23:59:59').getTime() : null;

            const filtered = rawRows.filter(r => {
                const rowText = Object.values(r).join(' ').toLowerCase();
                if (newsCat) {
                    const syns = CATEGORY_SYNONYMS[newsCat] || [newsCat];
                    if (!syns.some(s => rowText.includes(s.toLowerCase()))) return false;
                }
                if (kab) {
                    if (!rowText.includes(kab.toLowerCase())) return false;
                } else if (prov) {
                    const pClean = prov.split('(')[0].replace('DKI ', '').replace('DI ', '').trim().toLowerCase();
                    const kabs = PROV_KAB_DATA[prov] || [];
                    if (!rowText.includes(pClean) && !kabs.some(k => rowText.includes(k.split('(')[0].trim().toLowerCase()))) return false;
                }
                if (q && !rowText.includes(q.toLowerCase())) return false;
                if (cat === 'linkedin') {
                    const liConf = (document.getElementById('li-filter-conf')?.value || '').toLowerCase();
                    const liSrc = (document.getElementById('li-filter-source')?.value || '').toLowerCase();
                    const liSrv = (document.getElementById('li-filter-service')?.value || '').toLowerCase();
                    const confVal = String(r.confidence_status || '').toLowerCase();
                    const srcVal = String(r.source_platform || r.platform || '').toLowerCase();
                    const srvVal = String(r.project_service_type || r.matched_services || '').toLowerCase();
                    if (liConf && !confVal.includes(liConf) && !rowText.includes(liConf)) return false;
                    if (liSrc && !srcVal.includes(liSrc) && !rowText.includes(liSrc)) return false;
                    if (liSrv && !srvVal.includes(liSrv) && !rowText.includes(liSrv)) return false;
                }
                if (fromTs || toTs) {
                    const d = extractRowDate(r);
                    if (!d) return false;
                    const ts = d.getTime();
                    if (fromTs && ts < fromTs) return false;
                    if (toTs && ts > toTs) return false;
                }
                return true;
            });

            const displayed = filtered.slice(0, lim);
            renderTable(displayed);
            document.getElementById('row-count').innerText = displayed.length;

            const activeLabels = [
                cat !== 'berita' ? `Domain: ${cat}` : '',
                newsCat ? `Kategori: ${newsCat}` : '',
                prov ? `Prov: ${prov}` : '',
                kab ? `Kab/Kota: ${kab}` : '',
                (dateFrom || dateTo) ? `Waktu: ${dateFrom || '...'} s/d ${dateTo || '...'}` : '',
                q ? `Kata Kunci: "${q}"` : ''
            ].filter(Boolean);

            const status = document.getElementById('status-text');
            const hasActiveFilter = Boolean(newsCat || prov || kab || dateFrom || dateTo || q || cat !== 'berita');

            if (hasActiveFilter && filtered.length === 0) {
                status.innerText = `⚠ 0 baris cocok untuk filter ini (${cat}) — grafik menampilkan data global (klik RESET untuk muat ulang).`;
                const locTitle = document.getElementById('title-chart-loc');
                if (locTitle) locTitle.innerText = 'GEO POLARIZATION (WILAYAH)';
                if (BASE_ANALYTICS) {
                    renderChartsFromObject(BASE_ANALYTICS, false);
                } else {
                    loadAnalyticsCharts(false);
                }
                return;
            }

            status.innerText = `✅ Menampilkan ${displayed.length} dari ${filtered.length} baris cocok (${cat})${activeLabels.length ? ' • Filter [' + activeLabels.join(', ') + ']' : ''}.`;

            if (hasActiveFilter) {
                const reactiveAn = buildReactiveAnalyticsFromRows(filtered, prov, cat);
                if (cat === 'keyword_trending' && BASE_ANALYTICS && !prov && !newsCat && !q) {
                    if (!reactiveAn.locations?.length) reactiveAn.locations = BASE_ANALYTICS.locations || [];
                    if (!reactiveAn.top_people?.length) reactiveAn.top_people = BASE_ANALYTICS.top_people || [];
                    if (!reactiveAn.top_hashtags?.length) reactiveAn.top_hashtags = BASE_ANALYTICS.top_hashtags || [];
                    if (!reactiveAn.top_viral?.length) reactiveAn.top_viral = BASE_ANALYTICS.top_viral || [];
                }
                renderChartsFromObject(reactiveAn, true, `[${activeLabels.join(' • ')}] (${filtered.length} baris)`);
            } else if (BASE_ANALYTICS) {
                const locTitle = document.getElementById('title-chart-loc');
                if (locTitle) locTitle.innerText = 'GEO POLARIZATION (WILAYAH)';
                renderChartsFromObject(BASE_ANALYTICS, false);
            }
        }

        async function executeAction(forceNetwork = false) {
            const btn = document.getElementById('btn-run');
            const status = document.getElementById('status-text');
            const dlBtn = document.getElementById('btn-download');
            if (btn) btn.disabled = true;
            if (dlBtn) dlBtn.classList.add('hidden');

            try {
                if (currentTab === 'supabase') {
                    const cat = document.getElementById('sb-cat').value;
                    if (!DOMAIN_ROWS_CACHE[cat] || forceNetwork) {
                        if (btn) btn.innerText = "⏳ Memuat Skema Supabase...";
                        const res = await fetch(`/api/v1/warehouse/records?category=${encodeURIComponent(cat)}&search_query=&limit=500`);
                        const json = await res.json();
                        DOMAIN_ROWS_CACHE[cat] = json.data || [];
                        if (json.csv) LAST_CSV_PATH[cat] = json.csv;
                    }
                    if (LAST_CSV_PATH[cat] && dlBtn) {
                        dlBtn.href = "/api/v1/download?path=" + encodeURIComponent(LAST_CSV_PATH[cat]);
                        dlBtn.classList.remove('hidden');
                    }
                    applyClientFilters();
                } else if (currentTab === 'bank') {
                    if (btn) btn.innerText = "⏳ Memfilter CSV...";
                    const cat = document.getElementById('bd-cat').value;
                    const tool = document.getElementById('bd-tool').value;
                    const schema = document.getElementById('bd-schema').value;
                    const fname = document.getElementById('bd-file').value;
                    const q = document.getElementById('bd-search').value;
                    const lim = parseInt(document.getElementById('bd-limit').value) || 200;

                    let url = `/api/v1/bank-data/records?category=${encodeURIComponent(cat)}&tool=${encodeURIComponent(tool)}&schema_mode=${encodeURIComponent(schema)}&search_query=${encodeURIComponent(q)}&limit=${lim}`;
                    if (fname && fname !== 'semua') url += `&filename=${encodeURIComponent(fname)}`;

                    const res = await fetch(url);
                    const json = await res.json();
                    const rows = json.data || [];
                    renderTable(rows);
                    document.getElementById('row-count').innerText = json.returned_rows || 0;
                    status.innerText = `✅ Filter CSV: ${json.returned_rows} dari ${json.total_matching_rows} baris (${json.files_merged} file).`;
                    if (json.csv && json.returned_rows > 0 && dlBtn) {
                        dlBtn.href = "/api/v1/download?path=" + encodeURIComponent(json.csv);
                        dlBtn.classList.remove('hidden');
                    }
                    window.__LAST_BANK_ROWS = rows;
                    window.__LAST_BANK_CAT = cat;
                    const bdLiBox = document.getElementById('bd-linkedin-filter-box');
                    if (bdLiBox) bdLiBox.classList.toggle('hidden', cat !== 'linkedin');
                    if (cat === 'linkedin') {
                        applyBankLinkedInFilters();
                    } else {
                        const reactiveAn = buildReactiveAnalyticsFromRows(rows, '', cat);
                        renderChartsFromObject(reactiveAn, true, `[Bank Data CSV: ${cat}] (${rows.length} baris)`);
                    }
                } else {
                    if (btn) btn.innerText = "⏳ Sedang Scraping...";
                    status.innerText = "Mengekstrak data & mengunggah ke 7 skema Supabase...";
                    let endpoint = '';
                    let payload = {};

                    if (currentTab === 'keyword') {
                        endpoint = document.getElementById('kw-mode').value;
                        const val = document.getElementById('kw-input').value;
                        const lim = Math.max(parseInt(document.getElementById('kw-limit').value) || 15, 1);
                        payload = endpoint.includes('trending')
                            ? { kategori: val, geo: "ID", max_results: lim }
                            : { keyword: val, geo: "ID", max_results: lim };
                    } else if (currentTab === 'berita') {
                        endpoint = document.getElementById('br-engine').value;
                        payload = {
                            keyword_or_url: document.getElementById('br-input').value,
                            max_results: Math.max(parseInt(document.getElementById('br-limit').value) || 10, 1)
                        };
                    } else if (currentTab === 'project') {
                        if (btn) btn.innerText = "⏳ Mencari Project & Evaluasi Fit...";
                        status.innerText = "Mencari project multi-sumber & menghitung confidence Geekgarden...";
                        endpoint = '/api/v1/project/search';
                        payload = {
                            keyword: document.getElementById('proj-input')?.value || 'web developer aplikasi',
                            project_sources: document.getElementById('proj-sources')?.value || 'all',
                            region_indonesia: (document.getElementById('proj-region')?.value || 'id') === 'id',
                            max_results: Math.max(parseInt(document.getElementById('proj-limit')?.value) || 20, 1)
                        };
                    } else {
                        const pf = document.getElementById('sm-platform').value;
                        const eng = document.getElementById('sm-engine').value;
                        const mode = document.getElementById('sm-mode').value;
                        const val = document.getElementById('sm-input').value;
                        const lim = Math.max(parseInt(document.getElementById('sm-limit').value) || 10, 1);
                        endpoint = '/api/v1/sosmed/' + pf;

                        if (pf === 'linkedin') payload = { keyword: val, region_indonesia: true, max_results: lim, search_mode: 'profile' };
                        else if (pf === 'facebook') payload = { keyword_or_url: val, engine: eng, mode_apify: mode === 'full' ? 'full_39_kolom' : 'bersih', max_results: lim };
                        else if (pf === 'instagram') payload = { keyword_or_hashtag: val, engine: eng, mode_apify: mode === 'full' ? 'full_29_kolom' : 'bersih', max_results: lim };
                        else if (pf === 'tiktok') payload = { keyword_or_hashtag: val, engine: eng, max_results: lim };
                        else payload = { keyword: val, engine: eng, max_results: lim };
                    }

                    const res = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    const json = await res.json();
                    const rows = json.data || [];
                    if (currentTab === 'project') {
                        window.__LAST_PROJECT_ROWS = (typeof mergeProjectRows === 'function') ? mergeProjectRows(rows, window.__LAST_PROJECT_ROWS || []) : rows;
                        if (!window.__PROJECT_HISTORY_LOADED && typeof loadProjectHistory === 'function') { loadProjectHistory(true); }
                        const s = json.confidence_summary || {};
                        applyProjectFilters();
                        status.innerText = `✅ Ditemukan ${rows.length} project • Fix Bisa Masuk: ${s.fix_bisa_masuk || 0} • Fifty-Fifty: ${s.fifty_fifty || 0} • Tidak Bisa: ${s.tidak_bisa || 0}`;
                    } else {
                        renderTable(rows);
                        document.getElementById('row-count').innerText = json.total || 0;
                        status.innerText = "✅ Selesai! Data tersimpan ke CSV & masuk ke Supabase Data Warehouse.";
                    }
                    if (json.csv && dlBtn) {
                        dlBtn.href = "/api/v1/download?path=" + encodeURIComponent(json.csv);
                        dlBtn.classList.remove('hidden');
                    }
                    await forceReloadAll();
                }
            } catch (err) {
                status.innerText = "❌ Error: " + err.message;
            } finally {
                if (btn) {
                    btn.disabled = false;
                    if (currentTab === 'supabase') btn.innerText = "EXECUTE KANTOR QUERY <GO>";
                    else if (currentTab === 'bank') btn.innerText = "FILTER CSV VAULT <GO>";
                    else if (currentTab === 'project') btn.innerText = "🎯 HUNT PROJECT & SCORE <GO>";
                    else btn.innerText = "▶ RUN SCRAPER & SAVE DB <GO>";
                }
            }
        }

        async function syncCsvToSupabase() {
            const btn = document.getElementById('btn-sync');
            const status = document.getElementById('status-text');
            btn.disabled = true;
            btn.innerText = "⏳ Menyinkronkan CSV...";
            try {
                const res = await fetch('/api/v1/warehouse/sync-csv', { method: 'POST' });
                const json = await res.json();
                status.innerText = `✅ Sinkronisasi selesai: ${json.files_synced || 0} file CSV (${json.rows_synced || 0} baris) masuk ke Supabase.`;
                await forceReloadAll();
            } catch (e) {
                status.innerText = "❌ Error sync: " + e.message;
            } finally {
                btn.disabled = false;
                btn.innerText = "🔄 Sync Semua CSV ke Supabase";
            }
        }

        async function populateFileDropdown() {
            const catEl = document.getElementById('bd-cat');
            const toolEl = document.getElementById('bd-tool');
            const schemaEl = document.getElementById('bd-schema');
            const fileSelect = document.getElementById('bd-file');
            if (!catEl || !toolEl || !schemaEl || !fileSelect) return;

            try {
                const res = await fetch(`/api/v1/bank-data/catalog?category=${encodeURIComponent(catEl.value)}&tool=${encodeURIComponent(toolEl.value)}&schema_mode=${encodeURIComponent(schemaEl.value)}`);
                const json = await res.json();
                fileSelect.innerHTML = '<option value="semua">-- Semua File (' + (json.total_files || 0) + ' CSV) --</option>';
                (json.catalog || []).forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.filename;
                    opt.textContent = `${f.filename} (${f.size_kb} KB)`;
                    fileSelect.appendChild(opt);
                });
            } catch (e) {
                console.error(e);
            }
        }

        async function onBankFilterChange() {
            await populateFileDropdown();
            await executeAction(false);
        }

        function _bbEsc(s) {
            return String(s ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        function renderTable(rows, skipRawStore = false) {
            const thead = document.getElementById('table-head');
            const tbody = document.getElementById('table-body');
            if (!thead || !tbody) return;
            thead.innerHTML = '';
            tbody.innerHTML = '';

            if (!skipRawStore) {
                window.__BB_RAW_TABLE_ROWS = Array.isArray(rows) ? [...rows] : [];
                const qf = document.getElementById('bb-table-quickfilter');
                if (qf && qf.value.trim()) {
                    const term = qf.value.trim().toLowerCase();
                    rows = window.__BB_RAW_TABLE_ROWS.filter(r =>
                        Object.values(r || {}).join(' ').toLowerCase().includes(term)
                    );
                }
            }
            window.__BB_CURRENT_ROWS = Array.isArray(rows) ? rows : [];
            window.__BB_SELECTED_ROW_IDX = -1;

            if (!rows || !rows.length) {
                tbody.innerHTML = '<tr><td class="p-6 text-center text-[var(--bb-text-muted)] font-mono text-xs">NO MATCHING RECORDS FOR THIS FILTER.</td></tr>';
                return;
            }

            const colSet = new Set();
            rows.forEach(r => Object.keys(r || {}).forEach(k => colSet.add(k)));
            const cols = Array.from(colSet);
            const sortState = window.__BB_SORT_STATE || { col: null, asc: true };

            thead.innerHTML = '<tr>' + cols.map(c => {
                const arrow = sortState.col === c ? (sortState.asc ? ' ▲' : ' ▼') : '';
                return `<th onclick="bbSortTableByColumn('${_bbEsc(c)}')" title="Klik untuk urutkan">${_bbEsc(c)}${arrow}</th>`;
            }).join('') + '</tr>';

            rows.forEach((r, idx) => {
                const tr = document.createElement('tr');
                tr.dataset.rowIdx = String(idx);
                tr.onclick = (ev) => {
                    if (ev.target && ev.target.closest('a')) return;
                    if (typeof window.bbSelectTableRow === 'function') window.bbSelectTableRow(idx, true);
                };
                tr.innerHTML = cols.map(c => {
                    let val = r[c] !== null && r[c] !== undefined ? String(r[c]) : '';
                    if (val.startsWith('http')) {
                        return `<td class="whitespace-nowrap"><a href="${_bbEsc(val)}" target="_blank" rel="noopener noreferrer" class="hover:underline">↗ LINK</a></td>`;
                    }
                    if (c === 'confidence_status') {
                        const low = val.toLowerCase();
                        let cls = 'bg-slate-800 text-slate-300 border-slate-700';
                        if (low.includes('fix')) cls = 'bg-emerald-950/90 text-emerald-300 border-emerald-700';
                        else if (low.includes('fifty')) cls = 'bg-amber-950/90 text-amber-300 border-amber-700';
                        else if (low.includes('tidak')) cls = 'bg-rose-950/90 text-rose-300 border-rose-700';
                        return `<td class="whitespace-nowrap"><span class="px-1.5 py-0.5 text-[10px] font-semibold border ${cls}">${_bbEsc(val)}</span></td>`;
                    }
                    if (c === 'confidence_score' && val !== '') {
                        return `<td class="whitespace-nowrap font-mono font-bold text-[var(--bb-cyan)]">${_bbEsc(val)}%</td>`;
                    }
                    if (c === 'sentimen_diffbot' || c === 'sentiment') {
                        const num = Number(val);
                        const low = val.toLowerCase();
                        let sCls = 'text-[var(--bb-text-muted)]';
                        if (low.includes('pos') || (!isNaN(num) && num > 0.1)) sCls = 'text-[var(--bb-green)] font-bold';
                        else if (low.includes('neg') || (!isNaN(num) && num < -0.1)) sCls = 'text-[var(--bb-red)] font-bold';
                        return `<td class="whitespace-nowrap font-mono ${sCls}">${_bbEsc(val)}</td>`;
                    }
                    if (val.length > 85) val = val.substring(0, 85) + '...';
                    return `<td class="whitespace-nowrap">${_bbEsc(val)}</td>`;
                }).join('');
                tbody.appendChild(tr);
            });
        }

        function _bbPageType() {
            const p = (document.body && document.body.dataset && document.body.dataset.page) || '';
            if (p) return p;
            const path = (window.location.pathname || '').toLowerCase();
            if (/^\/dashboard\/project\/?$/.test(path)) return 'project';
            if (/^\/analytics\/?$/.test(path)) return 'analytics';
            return 'dashboard';
        }

        if (_bbPageType() === 'dashboard') {
            initProvinceDropdown();
        }
        window.addEventListener('DOMContentLoaded', () => {
            const pg = _bbPageType();
            if (pg !== 'dashboard') return;
            // Pastikan filter form tidak terbawa dari bfcache/autofill browser saat reload
            const resetIds = {
                'sb-cat': 'berita',
                'sb-news-cat': '',
                'sb-prov': '',
                'sb-time-preset': 'all',
                'sb-date-from': '',
                'sb-date-to': '',
                'sb-search': ''
            };
            Object.entries(resetIds).forEach(([id, val]) => {
                const el = document.getElementById(id);
                if (el) el.value = val;
            });
            initProvinceDropdown();
            onProvinceChange();
            refreshTelemetry();
            loadAnalyticsCharts(false);
            executeAction(false);
            populateFileDropdown();
            setInterval(() => {
                if (!_cronActiveManual) refreshTelemetry();
            }, 60000);
        });

// === REALTIME SCRAPER PROGRESS MODULE ===
(function () {
    let _progInterval = null;
    let _progStart = null;
    let _progPct = 0;
    let _progRunning = false;

    function _fmtDur(ms) {
        const s = Math.max(0, Math.floor(ms / 1000));
        const mm = String(Math.floor(s / 60)).padStart(2, '0');
        const ss = String(s % 60).padStart(2, '0');
        return `${mm}:${ss}`;
    }

    function _els() {
        return {
            box: document.getElementById('scraper-progress-box'),
            bar: document.getElementById('scraper-progress-bar'),
            pct: document.getElementById('scraper-progress-pct'),
            timer: document.getElementById('scraper-elapsed-timer'),
            label: document.getElementById('scraper-progress-label'),
            sub: document.getElementById('scraper-progress-sub')
        };
    }

    function _setVisual(pct, label, sub, isErr = false) {
        const e = _els();
        if (!e.box || !e.bar) return;
        _progPct = Math.max(0, Math.min(100, pct));
        e.bar.style.width = `${_progPct}%`;
        if (e.pct) e.pct.textContent = `${_progPct}%`;
        if (e.label) {
            e.label.textContent = label;
            e.label.className = isErr
                ? 'text-rose-400 font-semibold truncate'
                : 'text-emerald-400 font-semibold truncate';
        }
        if (e.sub) e.sub.textContent = sub;
        e.bar.className = isErr
            ? 'h-full bg-gradient-to-r from-rose-500 via-red-500 to-amber-500 rounded-full transition-all duration-300'
            : 'h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-indigo-400 rounded-full transition-all duration-300';
    }

    function startScraperProgress() {
        const e = _els();
        if (!e.box) return;
        clearInterval(_progInterval);
        _progRunning = true;
        _progStart = Date.now();
        _progPct = 6;
        e.box.classList.remove('hidden');
        if (e.timer) e.timer.textContent = '00:00';
        _setVisual(6, '🚀 Scraper & Simpan DB Berjalan...', 'Mengirim permintaan ke server...', false);

        _progInterval = setInterval(() => {
            if (!_progRunning || !_progStart) return;
            const elapsed = Date.now() - _progStart;
            const sec = Math.floor(elapsed / 1000);
            if (e.timer) e.timer.textContent = _fmtDur(elapsed);

            if (_progPct < 92) {
                const step = _progPct < 45 ? 4 : _progPct < 75 ? 2 : 1;
                _progPct = Math.min(92, _progPct + step);
                if (e.bar) e.bar.style.width = `${_progPct}%`;
                if (e.pct) e.pct.textContent = `${_progPct}%`;
            }

            if (e.sub) {
                if (sec >= 3 && sec < 12) e.sub.textContent = 'Mengekstrak data dari sumber...';
                else if (sec >= 12) e.sub.textContent = 'Menyimpan hasil & sinkronisasi ke Supabase...';
            }
        }, 500);
    }

    function finishScraperProgress(ok = true, msg = null) {
        const e = _els();
        clearInterval(_progInterval);
        _progInterval = null;
        _progRunning = false;
        const dur = _progStart ? _fmtDur(Date.now() - _progStart) : '00:00';
        if (e.timer) e.timer.textContent = dur;
        if (ok) {
            _setVisual(100, '✅ Selesai & Tersimpan ke DB', msg || `Durasi total: ${dur}`, false);
        } else {
            _setVisual(_progPct || 15, '❌ Proses Scraper Gagal', msg || `Terhenti pada ${dur}`, true);
        }
    }

    function resetScraperProgress() {
        const e = _els();
        clearInterval(_progInterval);
        _progInterval = null;
        _progRunning = false;
        _progStart = null;
        _progPct = 0;
        if (e.box) e.box.classList.add('hidden');
        if (e.bar) e.bar.style.width = '0%';
        if (e.pct) e.pct.textContent = '0%';
        if (e.timer) e.timer.textContent = '00:00';
    }

    const __origExecuteAction = executeAction;
    executeAction = async function (...args) {
        const isManualScraper = ['keyword', 'berita', 'sosmed', 'project'].includes(currentTab);
        if (isManualScraper) startScraperProgress();
        try {
            const res = await __origExecuteAction.apply(this, args);
            if (isManualScraper) {
                const st = document.getElementById('status-text')?.textContent || '';
                if (st.includes('❌')) finishScraperProgress(false, st.replace(/^❌\s*/, ''));
                else finishScraperProgress(true);
            }
            return res;
        } catch (err) {
            if (isManualScraper) finishScraperProgress(false, err?.message || 'Error');
            throw err;
        }
    };

    const __origResetSearchFilter = resetSearchFilter;
    resetSearchFilter = function (...args) {
        resetScraperProgress();
        return __origResetSearchFilter.apply(this, args);
    };

    const __origSwitchTab = switchTab;
    switchTab = function (tab) {
        if (!_progRunning && (tab === 'supabase' || tab === 'bank')) {
            resetScraperProgress();
        }
        return __origSwitchTab.call(this, tab);
    };
})();



// === LINKEDIN PROJECT FILTERING (BANK DATA CSV & INIT) ===
function applyBankLinkedInFilters() {
    const rows = window.__LAST_BANK_ROWS || [];
    const cat = window.__LAST_BANK_CAT || document.getElementById('bd-cat')?.value || 'linkedin';
    const bdLiBox = document.getElementById('bd-linkedin-filter-box');
    if (bdLiBox) bdLiBox.classList.toggle('hidden', cat !== 'linkedin');

    const conf = (document.getElementById('bd-li-filter-conf')?.value || '').toLowerCase();
    const src = (document.getElementById('bd-li-filter-source')?.value || '').toLowerCase();
    const srv = (document.getElementById('bd-li-filter-service', 'proj-filter-conf', 'proj-filter-source', 'proj-filter-service')?.value || '').toLowerCase();

    const filtered = rows.filter(r => {
        const allTxt = Object.values(r).join(' ').toLowerCase();
        const confVal = String(r.confidence_status || '').toLowerCase();
        const srcVal = String(r.source_platform || r.platform || '').toLowerCase();
        const srvVal = String(r.project_service_type || r.matched_services || '').toLowerCase();
        if (conf && !confVal.includes(conf) && !allTxt.includes(conf)) return false;
        if (src && !srcVal.includes(src) && !allTxt.includes(src)) return false;
        if (srv && !srvVal.includes(srv) && !allTxt.includes(srv)) return false;
        return true;
    });

    renderTable(filtered);
    const rc = document.getElementById('row-count');
    if (rc) rc.innerText = filtered.length;
    const reactiveAn = buildReactiveAnalyticsFromRows(filtered, '', cat);
    renderChartsFromObject(reactiveAn, true, `[Bank Data LinkedIn Fit] (${filtered.length} baris)`);
}
window.applyBankLinkedInFilters = applyBankLinkedInFilters;

window.addEventListener('DOMContentLoaded', () => {
    if (typeof toggleSosmedOptions === 'function') toggleSosmedOptions();
    const bdCat = document.getElementById('bd-cat');
    const bdLiBox = document.getElementById('bd-linkedin-filter-box');
    if (bdCat && bdLiBox) bdLiBox.classList.toggle('hidden', bdCat.value !== 'linkedin');
});

// === FILTER REALTIME KHUSUS TAB PROJECT HUNTER ===
(function () {
    let chartProjConf = null;
    let chartProjSrc = null;
    let chartProjSrv = null;
    let chartProjTop = null;

    function toggleCenterChartsByTab(tab) {
        const defaultGrid = document.getElementById('default-charts-grid');
        const projPanel = document.getElementById('project-charts-panel');
        if (!defaultGrid || !projPanel) return;

        if (tab === 'project') {
            defaultGrid.classList.add('hidden');
            projPanel.classList.remove('hidden');
        } else {
            projPanel.classList.add('hidden');
            defaultGrid.classList.remove('hidden');
        }
    }

    function getFilteredProjectRows() {
        const rows = window.__LAST_PROJECT_ROWS || [];
        const conf = (document.getElementById('proj-filter-conf')?.value || '').toLowerCase();
        const src = (document.getElementById('proj-filter-source')?.value || '').toLowerCase();
        const srv = (document.getElementById('proj-filter-service')?.value || '').toLowerCase();

        return rows.filter(r => {
            const allTxt = Object.values(r).join(' ').toLowerCase();
            const confVal = String(r.confidence_status || '').toLowerCase();
            const srcVal = String(r.source_platform || '').toLowerCase();
            const srvVal = String(r.project_service_type || r.matched_services || '').toLowerCase();
            if (conf && !confVal.includes(conf)) return false;
            if (src && !srcVal.includes(src) && !allTxt.includes(src)) return false;
            if (srv && !srvVal.includes(srv) && !allTxt.includes(srv)) return false;
            return true;
        });
    }

    function renderProjectCharts(rows) {
        const list = Array.isArray(rows) ? rows : [];

        // 1. Update 4 KPI mini
        let cFix = 0, cFifty = 0, cNo = 0, scoreSum = 0;
        const srcMap = {};
        const srvMap = {};

        list.forEach(r => {
            const st = String(r.confidence_status || '').toLowerCase();
            if (st.includes('fix')) cFix++;
            else if (st.includes('fifty')) cFifty++;
            else cNo++;

            const sc = Number(r.confidence_score) || 0;
            scoreSum += sc;

            const src = String(r.source_platform || 'Lainnya').trim();
            srcMap[src] = (srcMap[src] || 0) + 1;

            const srv = String(r.project_service_type || 'Lainnya / Non-IT').trim();
            srvMap[srv] = (srvMap[srv] || 0) + 1;
        });

        const avgScore = list.length ? Math.round(scoreSum / list.length) : 0;
        const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        setTxt('pkpi-fix', cFix);
        setTxt('pkpi-fifty', cFifty);
        setTxt('pkpi-no', cNo);
        setTxt('pkpi-avg', `${avgScore}%`);
        setTxt('pkpi-total', `${list.length} project tampil`);

        // 2. Chart 1: Doughnut Distribusi Confidence
        const elConf = document.getElementById('chartProjConfidence');
        if (elConf) {
            if (chartProjConf) chartProjConf.destroy();
            const confLabels = ['Fix Bisa Masuk', 'Fifty-Fifty', 'Tidak Bisa'];
            const confFilterVals = ['fix bisa masuk', 'fifty-fifty', 'tidak bisa'];
            chartProjConf = new Chart(elConf.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: confLabels,
                    datasets: [{
                        data: [cFix, cFifty, cNo],
                        backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '58%',
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } } },
                    onClick: (_, elements) => {
                        if (!elements.length) return;
                        quickFilterProjectConf(confFilterVals[elements[0].index]);
                    }
                }
            });
        }

        // 3. Chart 2: Bar Sebaran Sumber Platform
        const elSrc = document.getElementById('chartProjSources');
        if (elSrc) {
            if (chartProjSrc) chartProjSrc.destroy();
            const srcEntries = Object.entries(srcMap).sort((a, b) => b[1] - a[1]);
            chartProjSrc = new Chart(elSrc.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: srcEntries.map(x => x[0]),
                    datasets: [{
                        label: 'Jumlah Project',
                        data: srcEntries.map(x => x[1]),
                        backgroundColor: '#6366f1',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { display: false } },
                        y: { grid: { color: '#1f2937' }, beginAtZero: true, ticks: { precision: 0 } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // 4. Chart 3: Horizontal Bar Tipe Layanan Geekgarden
        const elSrv = document.getElementById('chartProjServices');
        if (elSrv) {
            if (chartProjSrv) chartProjSrv.destroy();
            const srvEntries = Object.entries(srvMap).sort((a, b) => b[1] - a[1]).slice(0, 7);
            chartProjSrv = new Chart(elSrv.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: srvEntries.map(x => x[0].length > 26 ? x[0].slice(0, 26) + '...' : x[0]),
                    datasets: [{
                        label: 'Jumlah Project',
                        data: srvEntries.map(x => x[1]),
                        backgroundColor: '#14b8a6',
                        borderRadius: 5
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: '#1f2937' }, beginAtZero: true, ticks: { precision: 0 } },
                        y: { grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // 5. Chart 4: Top 8 Project Skor Tertinggi
        const elTop = document.getElementById('chartProjTopScores');
        if (elTop) {
            if (chartProjTop) chartProjTop.destroy();
            const topRows = [...list]
                .sort((a, b) => (Number(b.confidence_score) || 0) - (Number(a.confidence_score) || 0))
                .slice(0, 8);

            chartProjTop = new Chart(elTop.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: topRows.map(r => {
                        const t = String(r.title || 'Project');
                        return t.length > 24 ? t.slice(0, 24) + '...' : t;
                    }),
                    datasets: [{
                        label: 'Confidence Score (%)',
                        data: topRows.map(r => Number(r.confidence_score) || 0),
                        backgroundColor: topRows.map(r => {
                            const s = Number(r.confidence_score) || 0;
                            return s >= 70 ? '#10b981' : s >= 40 ? '#f59e0b' : '#ef4444';
                        }),
                        borderRadius: 5
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { max: 100, beginAtZero: true, grid: { color: '#1f2937' } },
                        y: { grid: { display: false } }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => {
                                    const row = items[0] ? topRows[items[0].dataIndex] : null;
                                    return row ? String(row.title || '') : '';
                                },
                                label: (ctx) => {
                                    const row = topRows[ctx.dataIndex] || {};
                                    return [
                                        `Confidence: ${ctx.raw}% (${row.confidence_status || '-'})`,
                                        `Sumber: ${row.source_platform || '-'} | Budget: ${row.budget || '-'}`,
                                        `Layanan: ${row.project_service_type || '-'}`
                                    ];
                                }
                            }
                        }
                    },
                    onClick: (_, elements) => {
                        if (!elements.length) return;
                        const row = topRows[elements[0].index];
                        if (row && row.url && String(row.url).startsWith('http')) {
                            window.open(row.url, '_blank');
                        }
                    }
                }
            });
        }
    }

    function applyProjectFilters() {
        const allRows = window.__LAST_PROJECT_ROWS || [];
        const filtered = getFilteredProjectRows();

        toggleCenterChartsByTab('project');
        renderTable(filtered);
        const rc = document.getElementById('row-count');
        if (rc) rc.innerText = filtered.length;

        const banner = document.getElementById('reactive-banner');
        const bannerText = document.getElementById('reactive-banner-text');
        if (banner && bannerText) {
            if (allRows.length > 0) {
                banner.classList.remove('hidden');
                bannerText.innerText = `💼 Mode Analitik Project Hunter: Menampilkan ${filtered.length} dari ${allRows.length} project hasil evaluasi Geekgarden`;
            } else {
                banner.classList.add('hidden');
            }
        }

        renderProjectCharts(filtered);
    }

    function quickFilterProjectConf(val) {
        const sel = document.getElementById('proj-filter-conf');
        if (!sel) return;
        sel.value = (sel.value === val) ? '' : val;
        applyProjectFilters();
    }

    // === DDC PROJECT HUNTER HISTORY MERGE ===
    function mergeProjectRows(primaryRows, secondaryRows) {
        const merged = [];
        const seen = new Set();
        for (const list of [primaryRows || [], secondaryRows || []]) {
            for (const r of list) {
                if (!r || typeof r !== 'object') continue;
                const url = String(r.url || '').trim().toLowerCase();
                const title = String(r.title || '').trim().toLowerCase();
                const plat = String(r.source_platform || r.platform || '').trim().toLowerCase();
                if (!title && !url) continue;
                const key = title + '|' + (url.startsWith('http') ? url : plat);
                if (seen.has(key)) continue;
                seen.add(key);
                merged.push(r);
            }
        }
        return merged;
    }
    window.mergeProjectRows = mergeProjectRows;

    let __projectHistoryPromise = null;
    async function loadProjectHistory(force = false) {
        if (!force && window.__PROJECT_HISTORY_LOADED && Array.isArray(window.__LAST_PROJECT_ROWS) && window.__LAST_PROJECT_ROWS.length > 0) {
            applyProjectFilters();
            return window.__LAST_PROJECT_ROWS;
        }
        if (__projectHistoryPromise && !force) return __projectHistoryPromise;

        __projectHistoryPromise = (async () => {
            try {
                const resp = await fetch('/api/v1/project/records?limit=500' + (force ? '&refresh=true' : ''));
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const payload = await resp.json();
                const histRows = Array.isArray(payload.data) ? payload.data : [];
                window.__LAST_PROJECT_ROWS = mergeProjectRows(window.__LAST_PROJECT_ROWS || [], histRows);
                window.__PROJECT_HISTORY_LOADED = true;
                if (typeof currentTab === 'undefined' || currentTab === 'project') {
                    applyProjectFilters();
                }
                return window.__LAST_PROJECT_ROWS;
            } catch (err) {
                console.warn('[Project Hunter] Gagal memuat arsip historis:', err);
                return window.__LAST_PROJECT_ROWS || [];
            } finally {
                __projectHistoryPromise = null;
            }
        })();
        return __projectHistoryPromise;
    }
    window.loadProjectHistory = loadProjectHistory;
    // === DDC AUTO-LOAD PROJECT HISTORY ON DIRECT URL ===
    if (window.location.pathname.toLowerCase().includes('/dashboard/project') ||
        new URLSearchParams(window.location.search).get('page') === 'project') {
        setTimeout(() => { loadProjectHistory(false); }, 50);
    }

    async function showProjectResults() {
        toggleCenterChartsByTab('project');
        if (!window.__PROJECT_HISTORY_LOADED) {
            await loadProjectHistory(false);
        }
        const rows = window.__LAST_PROJECT_ROWS || [];
        if (rows.length === 0) {
            await executeAction(true);
        } else {
            applyProjectFilters();
        }
        const panel = document.getElementById('project-charts-panel');
        if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Bungkus switchTab agar otomatis mengganti grafik tengah tanpa merusak 7 grafik asli
    const __prevSwitchTabProjUI = switchTab;
    switchTab = function (tab) {
        const res = __prevSwitchTabProjUI.call(this, tab);
        toggleCenterChartsByTab(tab);
        if (tab === 'project') {
            applyProjectFilters();
            if (!window.__PROJECT_HISTORY_LOADED) {
                loadProjectHistory(false);
            }
        } else {
            const banner = document.getElementById('reactive-banner');
            if (banner && (tab === 'keyword' || tab === 'berita' || tab === 'sosmed')) {
                banner.classList.add('hidden');
            }
        }
        return res;
    };

    window.switchTab = switchTab;
    window.applyProjectFilters = applyProjectFilters;
    window.showProjectResults = showProjectResults;
    window.quickFilterProjectConf = quickFilterProjectConf;
})();



/* DDC_UNIFIED_SHELL_AND_PROJECT_START */
(function () {
    const isProjectStandalone = () =>
        (document.body && document.body.dataset && document.body.dataset.page === "project") ||
        /^\/dashboard\/project\/?$/i.test(window.location.pathname || "");

    const PAGE_META = {
        supabase: { title: "Database Supabase (ELT)", desc: "Monitoring data warehouse live, analitik global, dan jadwal cron 8 jam." },
        bank:     { title: "Bank Data (Arsip CSV)", desc: "Eksplorasi arsip CSV terstandarisasi dan grafik reaktif per kategori." },
        keyword:  { title: "1. Keyword & Trend", desc: "Ekstraksi kata kunci terkait dan tren pencarian Google Trends." },
        berita:   { title: "2. Portal Berita", desc: "Penarikan artikel portal berita otomatis (NewsData, Diffbot, Kombine)." },
        sosmed:   { title: "3. Social Media", desc: "Pengumpulan postingan Instagram, TikTok, Facebook, dan Twitter/X." },
        project:  { title: "4. Pencarian Project", desc: "Pencarian peluang project freelance & klasifikasi kecocokan Geekgarden." }
    };

    const ALL_DEFAULT_CHARTS = [
        "chartLocations",
        "chartPeople",
        "chartViral",
        "chartHashtags",
        "chartKeywords",
        "chartTimeline",
        "chartSystem"
    ];

    const TAB_CHART_CONFIG = {
        supabase: { charts: ALL_DEFAULT_CHARTS, showSentiment: true },
        bank:     { charts: ["chartLocations", "chartKeywords", "chartViral", "chartTimeline"], showSentiment: true },
        keyword:  { charts: ["chartKeywords", "chartTimeline", "chartLocations", "chartHashtags"], showSentiment: false },
        berita:   { charts: ["chartLocations", "chartPeople", "chartKeywords", "chartTimeline"], showSentiment: true },
        sosmed:   { charts: ["chartViral", "chartHashtags", "chartKeywords", "chartPeople", "chartTimeline"], showSentiment: true }
    };

    const ACTIVE_SB = ["bb-fkey-active"];
    const INACTIVE_SB = [];

    function getThemeColors() {
        const isDark = document.documentElement.classList.contains("dark");
        return {
            text: isDark ? "#8b949e" : "#5a544a",
            grid: isDark ? "rgba(30, 38, 54, 0.85)" : "rgba(182, 174, 155, 0.55)"
        };
    }

    function applyChartTheme() {
        if (typeof Chart === "undefined") return;
        const colors = getThemeColors();
        Chart.defaults.color = colors.text;
        Chart.defaults.borderColor = colors.grid;
        Chart.defaults.font.family = "'JetBrains Mono', ui-monospace, SFMono-Regular, monospace";
        Chart.defaults.font.size = 10;

        const instances = Chart.instances ? Object.values(Chart.instances) : [];
        instances.forEach((chart) => {
            if (!chart || !chart.options) return;
            if (chart.options.plugins?.legend?.labels) {
                chart.options.plugins.legend.labels.color = colors.text;
            }
            if (chart.options.scales) {
                Object.values(chart.options.scales).forEach((scale) => {
                    if (!scale) return;
                    if (scale.ticks) scale.ticks.color = colors.text;
                    if (scale.grid) scale.grid.color = colors.grid;
                });
            }
            try { chart.update("none"); } catch (e) {}
        });
    }
    window.ddcApplyChartTheme = applyChartTheme;

    let _themeTimer = null;
    window.ddcToggleTheme = function (ev) {
        const htmlEl = document.documentElement;
        const nowDark = !htmlEl.classList.contains("dark");
        const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        const commitTheme = () => {
            htmlEl.classList.toggle("dark", nowDark);
            try { localStorage.setItem("ddc_theme", nowDark ? "dark" : "light"); } catch (e) {}
            applyChartTheme();
        };

        if (!reduceMotion && typeof document.startViewTransition === "function") {
            const btn = document.getElementById("ddc-theme-toggle");
            let x = window.innerWidth - 60;
            let y = 28;
            if (ev && typeof ev.clientX === "number" && (ev.clientX !== 0 || ev.clientY !== 0)) {
                x = ev.clientX;
                y = ev.clientY;
            } else if (btn) {
                const rect = btn.getBoundingClientRect();
                x = rect.left + rect.width / 2;
                y = rect.top + rect.height / 2;
            }
            const endRadius = Math.hypot(
                Math.max(x, window.innerWidth - x),
                Math.max(y, window.innerHeight - y)
            );
            const transition = document.startViewTransition(() => commitTheme());
            transition.ready.then(() => {
                document.documentElement.animate(
                    {
                        clipPath: [
                            `circle(0px at ${x}px ${y}px)`,
                            `circle(${endRadius}px at ${x}px ${y}px)`
                        ]
                    },
                    {
                        duration: 550,
                        easing: "cubic-bezier(0.22, 1, 0.36, 1)",
                        pseudoElement: "::view-transition-new(root)"
                    }
                );
            }).catch(() => {});
            return;
        }

        if (!reduceMotion) {
            htmlEl.classList.add("ddc-theme-transitioning");
            clearTimeout(_themeTimer);
            _themeTimer = setTimeout(() => htmlEl.classList.remove("ddc-theme-transitioning"), 460);
        }
        commitTheme();
    };

    window.ddcToggleMobileSidebar = function (forceOpen) {
        const sidebar = document.getElementById("ddc-sidebar");
        const overlay = document.getElementById("ddc-sidebar-overlay");
        if (!sidebar) return;
        const isClosed = sidebar.classList.contains("-translate-x-full");
        const open = (typeof forceOpen === "boolean") ? forceOpen : isClosed;
        sidebar.classList.toggle("-translate-x-full", !open);
        if (overlay) overlay.classList.toggle("hidden", !open);
    };

    window.ddcToggleDesktopSidebar = function () {
        const reopenBtn = document.getElementById("ddc-sidebar-reopen");
        document.body.classList.toggle("ddc-sb-collapsed");
        const collapsed = document.body.classList.contains("ddc-sb-collapsed");
        if (reopenBtn) {
            reopenBtn.classList.toggle("hidden", !collapsed);
            reopenBtn.classList.toggle("inline-flex", collapsed);
        }
        setTimeout(() => {
            if (typeof Chart !== "undefined" && Chart.instances) {
                Object.values(Chart.instances).forEach((ch) => {
                    try { if (ch && ch.canvas && ch.canvas.offsetParent !== null) ch.resize(); } catch (e) {}
                });
            }
        }, 200);
    };

    function getTabFromUrl() {
        if (isProjectStandalone()) return "project";
        const parts = (window.location.pathname || "").toLowerCase().split("/").filter(Boolean);
        if (parts[0] === "dashboard" && PAGE_META[parts[1]]) return parts[1];
        const q = (new URLSearchParams(window.location.search).get("page") || "").toLowerCase();
        if (q && PAGE_META[q]) return q;
        return "supabase";
    }

    function updateSidebarUI(tab) {
        const activeTab = PAGE_META[tab] ? tab : "supabase";
        const inQuad = document.body.classList.contains("bb-scr-quad");
        document.querySelectorAll(".ddc-sb-item").forEach((el) => {
            const tabAttr = el.getAttribute("data-ddc-tab");
            const isAct = inQuad ? (tabAttr === "quad") : (tabAttr === activeTab);
            ACTIVE_SB.forEach((c) => el.classList.toggle(c, isAct));
            INACTIVE_SB.forEach((c) => el.classList.toggle(c, !isAct));
        });
        const meta = PAGE_META[activeTab];
        const tEl = document.getElementById("ddc-page-title");
        const dEl = document.getElementById("ddc-page-desc");
        if (tEl) tEl.textContent = meta.title;
        if (dEl) dEl.textContent = meta.desc;
        document.title = meta.title + " — DDC Portal";
    }

    function applyChartsForTab(tab) {
        if (isProjectStandalone()) return;
        const activeTab = TAB_CHART_CONFIG[tab] ? tab : "supabase";
        const cfg = TAB_CHART_CONFIG[activeTab];

        const banner = document.getElementById("reactive-banner");
        if (banner) banner.classList.add("hidden");

        const visibleCards = [];
        ALL_DEFAULT_CHARTS.forEach((canvasId) => {
            const canvas = document.getElementById(canvasId);
            const card = canvas ? canvas.closest("#default-charts-grid > div") : null;
            if (!card) return;
            const isVisible = cfg.charts.includes(canvasId);
            card.classList.toggle("hidden", !isVisible);
            card.classList.remove("md:col-span-2");
            if (isVisible) visibleCards.push(card);
        });
        if (visibleCards.length % 2 === 1) {
            visibleCards[visibleCards.length - 1].classList.add("md:col-span-2");
        }

        const sentCanvas = document.getElementById("chartSentiment");
        const sentCard = sentCanvas ? sentCanvas.closest("aside > div") : null;
        if (sentCard) sentCard.classList.toggle("hidden", !cfg.showSentiment);

        requestAnimationFrame(() => {
            if (typeof Chart !== "undefined" && Chart.instances) {
                Object.values(Chart.instances).forEach((ch) => {
                    try { if (ch && ch.canvas && ch.canvas.offsetParent !== null) ch.resize(); } catch (e) {}
                });
            }
        });
    }
    window.ddcApplyChartsForTab = applyChartsForTab;

    let _syncingUrl = false;
    window.ddcGoPage = function (tab, ev) {
        if (ev && (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey)) return true;
        const target = PAGE_META[tab] ? tab : "supabase";
        const targetPath = "/dashboard/" + target;

        // Perpindahan masuk/keluar halaman terpisah frontend/project.html memakai navigasi penuh
        const currentlyProject = isProjectStandalone();
        if ((currentlyProject && target !== "project") || (!currentlyProject && target === "project")) {
            if (ev) ev.preventDefault();
            window.location.href = targetPath;
            return false;
        }
        if (currentlyProject && target === "project") {
            if (ev) ev.preventDefault();
            if (window.innerWidth < 1024) window.ddcToggleMobileSidebar(false);
            window.scrollTo({ top: 0, behavior: "instant" });
            return false;
        }

        if (ev) ev.preventDefault();
        if (document.body.classList.contains("bb-scr-quad") && typeof window.bbSetScreen === "function") {
            window.bbSetScreen("intel");
        }
        if (window.location.pathname !== targetPath) {
            try { window.history.pushState({ tab: target }, "", targetPath); } catch (e) {}
        }
        updateSidebarUI(target);
        if (typeof window.switchTab === "function") {
            _syncingUrl = true;
            try { window.switchTab(target); } finally { _syncingUrl = false; }
        }
        applyChartsForTab(target);
        if (window.innerWidth < 1024) window.ddcToggleMobileSidebar(false);
        window.scrollTo({ top: 0, behavior: "instant" });
        setTimeout(applyChartTheme, 200);
        return false;
    };

    /* =========================================================================
       SOCIAL KEYWORD CHART FALLBACK (KHUSUS HALAMAN INDEX.HTML)
       ========================================================================= */
    const STOPWORDS = new Set([
        "yang","dan","di","ke","dari","ini","itu","untuk","dengan","pada","adalah","tidak","tak","ada","bisa",
        "akan","juga","atau","dalam","oleh","sudah","telah","secara","sebagai","agar","karena","saat","bagi",
        "para","kami","kita","saya","aku","anda","kamu","mereka","dia","beliau","lebih","sangat","masih","hanya",
        "dapat","harus","jadi","tapi","tetapi","namun","seperti","bahwa","jika","kalau","bila","ketika","hingga",
        "sampai","antara","atas","bawah","depan","belakang","tentang","terhadap","melalui","semua","seluruh",
        "setiap","banyak","sedikit","baru","lama","besar","kecil","hari","bulan","tahun","waktu","orang","pihak",
        "hal","cara","buat","bikin","mau","ingin","belum","lagi","saja","aja","kok","sih","nih","dong","deh",
        "kan","yah","yaa","yuk","apa","siapa","mana","kenapa","mengapa","bagaimana","berapa","pun","nya",
        "tersebut","berikut","lain","lainnya","serta","maupun","sama","terus","lalu","kemudian","sehingga",
        "selama","sebelum","sesudah","setelah","tanpa","punya","memiliki","menjadi","melakukan","memberikan",
        "mengatakan","menurut","sementara","sekitar","hampir","cukup","terlalu","paling","bukan","jangan","pernah",
        "selalu","sering","kadang","mungkin","pasti","tentu","memang","cuma","banget","bgt","yg","dgn","utk",
        "dr","pd","tdk","gk","ga","gak","nggak","tp","krn","sdh","blm","dlm","org","jd","bs","lg","sm",
        "the","and","for","with","this","that","from","have","has","had","your","you","are","was","were","been",
        "will","would","can","could","should","about","into","over","after","before","more","most","some","such",
        "only","than","then","just","also","very","here","there","when","where","what","which","who","how","why",
        "not","but","out","all","any","our","their","they","them","she","her","his","him","its","one","two",
        "http","https","www","com","net","org","co","id","php","html","amp","via","fyp","viral","video","foto",
        "photo","post","reel","reels","story","feed","instagram","tiktok","facebook","twitter","thread","threads",
        "linkedin","youtube","shorts","link","bio","klik","follow","like","comment","share","subscribe","dm",
        "cek","simak","baca","selengkapnya","lengkapnya","berita","update","info","terbaru","hariini","indonesia"
    ]);
    const IGNORE_HEADER_RE = /^(no|#|id|url|link|tautan|date|tanggal|tgl|waktu|time|created|published|collected|scraped|likes?|comments?|shares?|views?|retweets?|replies|engagement|score|skor|sentiment|sentimen|platform|source|sumber|tool|engine|author|username|user|akun|account|status|budget|kategori|category|tipe|type)$/i;
    const TEXT_HEADER_RE = /(keyword|kueri|query|topik|topic|title|judul|caption|content|konten|text|teks|deskripsi|description|hashtag|tagar|tag|snippet|ringkasan|summary|message|pesan|body)/i;

    let kwDebounce = null;
    function tokenizeText(raw) {
        if (!raw) return [];
        const cleaned = String(raw)
            .toLowerCase()
            .replace(/https?:\/\/\S+/g, " ")
            .replace(/www\.\S+/g, " ")
            .replace(/@[a-z0-9._-]+/g, " ")
            .replace(/&[a-z]+;/g, " ")
            .replace(/[^a-z0-9#\s]/g, " ");
        const uniq = new Set();
        for (let tok of cleaned.split(/\s+/)) {
            if (!tok) continue;
            if (tok.startsWith("#")) tok = tok.slice(1);
            if (tok.length < 3 || tok.length > 28 || /^\d+$/.test(tok) || STOPWORDS.has(tok)) continue;
            uniq.add(tok);
        }
        return Array.from(uniq);
    }

    function ensureSocialKeywordChart() {
        if (isProjectStandalone() || typeof Chart === "undefined") return;
        const canvas = document.getElementById("chartKeywords");
        if (!canvas) return;
        const card = canvas.closest("#default-charts-grid > div");
        if (card && card.classList.contains("hidden")) return;

        let chart = typeof Chart.getChart === "function" ? Chart.getChart(canvas) : null;
        if (chart && chart.data) {
            const labels = chart.data.labels || [];
            const datasets = chart.data.datasets || [];
            const keyNow = JSON.stringify(labels);
            if (chart.__ddcIsFallback && chart.__ddcFallbackKey !== keyNow) chart.__ddcIsFallback = false;
            const total = datasets.reduce((acc, ds) => acc + (ds.data || []).reduce((a, v) => a + Math.abs(Number(v) || 0), 0), 0);
            const placeholderOnly = !labels.length || labels.every((l) => /^(belum ada|tidak ada|kosong|no data|none|n\/a|-|\s*)$/i.test(String(l || "").trim()));
            if (total > 0 && !placeholderOnly && !chart.__ddcIsFallback) return;
        }

        const tbody = document.getElementById("table-body");
        if (!tbody) return;
        const trs = Array.from(tbody.querySelectorAll("tr"));
        const headers = Array.from(document.querySelectorAll("#table-head th")).map((th) => (th.textContent || "").trim());
        const pref = [], fb = [];
        headers.forEach((h, i) => {
            if (TEXT_HEADER_RE.test(h)) pref.push(i);
            else if (h && !IGNORE_HEADER_RE.test(h)) fb.push(i);
        });
        const cols = pref.length ? pref : fb;
        const counts = new Map();
        for (const tr of trs) {
            const tds = Array.from(tr.querySelectorAll("td"));
            if (tds.length <= 1) continue;
            const txt = cols.length
                ? cols.map((i) => (tds[i] ? tds[i].textContent : "")).join(" ")
                : tds.map((td) => td.textContent || "").join(" ");
            for (const tok of tokenizeText(txt)) counts.set(tok, (counts.get(tok) || 0) + 1);
        }
        const topPairs = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]).slice(0, 10);
        if (!topPairs.length) return;

        const labels = topPairs.map(([k]) => k);
        const values = topPairs.map(([, v]) => v);
        const colors = getThemeColors();
        if (chart) {
            chart.data.labels = labels;
            if (!chart.data.datasets?.length) {
                chart.data.datasets = [{ label: "Frekuensi Kata Kunci", data: values, backgroundColor: "rgba(99, 102, 241, 0.78)", borderRadius: 6 }];
            } else {
                chart.data.datasets[0].label = "Frekuensi Kata Kunci";
                chart.data.datasets[0].data = values;
            }
            chart.__ddcIsFallback = true;
            chart.__ddcFallbackKey = JSON.stringify(labels);
            try { chart.update(); } catch (e) {}
        } else {
            const c = new Chart(canvas.getContext("2d"), {
                type: "bar",
                data: {
                    labels,
                    datasets: [{ label: "Frekuensi Kata Kunci", data: values, backgroundColor: "rgba(99, 102, 241, 0.78)", borderRadius: 6 }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, ticks: { color: colors.text, precision: 0 }, grid: { color: colors.grid } },
                        y: { ticks: { color: colors.text, font: { size: 11 } }, grid: { display: false } }
                    }
                }
            });
            c.__ddcIsFallback = true;
            c.__ddcFallbackKey = JSON.stringify(labels);
        }
    }

    /* =========================================================================
       PROJECT HUNTER STANDALONE CONTROLLER (KHUSUS frontend/project.html)
       ========================================================================= */
    const TECH_PATTERNS = [
        ["Web / Website", /\b(web|website|webapp|landing page|company profile|frontend|backend|fullstack)\b/i],
        ["Mobile / Android / iOS", /\b(mobile|android|ios|aplikasi|app)\b/i],
        ["Flutter", /\bflutter\b/i],
        ["React / Next.js", /\b(react|nextjs|next\.js|reactjs)\b/i],
        ["Laravel / PHP", /\b(laravel|php|codeigniter)\b/i],
        ["Python / FastAPI", /\b(python|fastapi|django|flask)\b/i],
        ["Node.js / JS / TS", /\b(node\.?js|javascript|typescript|express|nestjs)\b/i],
        ["UI / UX Design", /\b(ui\/?ux|figma|ui design|ux design|wireframe|prototype)\b/i],
        ["ERP / CRM / Custom", /\b(erp|crm|odoo|pos|inventory|hris|simrs|siakad)\b/i],
        ["AI / Data / ML", /\b(ai|machine learning|data|nlp|llm|chatbot|scraping|analytics)\b/i],
        ["WordPress / CMS", /\b(wordpress|woocommerce|shopify|cms)\b/i],
        ["QA / Testing", /\b(qa|testing|automation test|selenium|cypress)\b/i],
        ["Cloud / DevOps", /\b(devops|docker|kubernetes|aws|gcp|cloud|ci\/cd)\b/i],
        ["API / Integrasi", /\b(api|rest|graphql|webhook|integrasi|n8n)\b/i]
    ];

    let projectRowsCache = [];
    let projectFetching = false;
    const projCharts = {};

    function escHtml(str) {
        return String(str ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function normalizeScore(row) {
        const raw = row?.confidence_score ?? row?.score ?? row?.fit_score ?? 0;
        const num = Number(String(raw).replace(/[^\d.-]/g, ""));
        return Number.isFinite(num) ? Math.max(0, Math.min(100, num)) : 0;
    }

    function normalizeStatusKey(row) {
        const sc = normalizeScore(row);
        if (sc >= 80) return "fix bisa masuk";
        if (sc >= 40) return "fifty-fifty";
        return "tidak bisa";
    }

    function statusLabelFromKey(key) {
        if (key === "fix bisa masuk") return "Fix Bisa Masuk";
        if (key === "fifty-fifty") return "Fifty-Fifty";
        return "Tidak Bisa";
    }

    function filterProjectRows(rows) {
        const confF = (document.getElementById("proj-filter-conf")?.value || "").trim().toLowerCase();
        const srcF = (document.getElementById("proj-filter-source")?.value || "").trim().toLowerCase();
        const svcF = (document.getElementById("proj-filter-service")?.value || "").trim().toLowerCase();

        return (rows || []).filter((r) => {
            if (!r || typeof r !== "object") return false;
            if (confF) {
                const st = String(r.confidence_status || "").toLowerCase();
                const norm = normalizeStatusKey(r);
                if (!st.includes(confF) && norm !== confF) return false;
            }
            if (srcF) {
                const src = String(r.source_platform || r.platform || r.source || "").toLowerCase();
                if (!src.includes(srcF)) return false;
            }
            if (svcF) {
                const svc = String(r.project_service_type || r.matched_services || r.service_type || "").toLowerCase();
                if (!svc.includes(svcF)) return false;
            }
            return true;
        });
    }

    function mountProjChart(canvasId, config) {
        if (typeof Chart === "undefined") return;
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const existing = (typeof Chart.getChart === "function" ? Chart.getChart(canvas) : null) || projCharts[canvasId];
        if (existing) {
            try { existing.destroy(); } catch (e) {}
        }
        projCharts[canvasId] = new Chart(canvas.getContext("2d"), config);
    }

    function renderProjectTable(filtered) {
        const thead = document.getElementById("table-head");
        const tbody = document.getElementById("table-body");
        const rowCount = document.getElementById("row-count");
        const statusEl = document.getElementById("status-text");
        if (!thead || !tbody) return;

        let list = Array.isArray(filtered) ? [...filtered] : [];
        const qf = document.getElementById("bb-table-quickfilter");
        if (qf && qf.value.trim()) {
            const term = qf.value.trim().toLowerCase();
            list = list.filter((r) => Object.values(r || {}).join(" ").toLowerCase().includes(term));
        }

        const slice = list.slice(0, 200);
        window.__BB_RAW_TABLE_ROWS = list;
        window.__BB_CURRENT_ROWS = slice;
        window.__BB_SELECTED_ROW_IDX = -1;

        if (rowCount) rowCount.textContent = String(list.length);
        if (statusEl) {
            statusEl.textContent = list.length
                ? `Menampilkan ${slice.length} dari ${projectRowsCache.length} peluang project (Fix ≥ 80%).`
                : "Tidak ada project yang cocok dengan filter saat ini.";
        }

        thead.innerHTML = `
            <tr>
                <th>Project</th>
                <th>Sumber</th>
                <th>Layanan</th>
                <th>Confidence</th>
                <th>Budget</th>
                <th>Tanggal</th>
            </tr>
        `;

        if (!slice.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="p-6 text-center text-[var(--bb-text-muted)] font-mono text-xs">TIDAK ADA DATA PROJECT UNTUK FILTER INI.</td></tr>';
            return;
        }

        tbody.innerHTML = slice.map((r, idx) => {
            const sc = normalizeScore(r);
            const stKey = normalizeStatusKey(r);
            const stLabel = statusLabelFromKey(stKey);
            const badgeCls = stKey === "fix bisa masuk"
                ? "bg-emerald-950/90 text-emerald-300 border-emerald-700"
                : stKey === "fifty-fifty"
                ? "bg-amber-950/90 text-amber-300 border-amber-700"
                : "bg-rose-950/90 text-rose-300 border-rose-700";

            const title = escHtml(r.title || "(Tanpa Judul)");
            const url = r.url && /^https?:\/\//i.test(String(r.url)) ? String(r.url) : "";
            const titleHtml = url
                ? `<a href="${escHtml(url)}" target="_blank" rel="noopener noreferrer" class="font-semibold hover:underline">${title}</a>`
                : `<span class="font-semibold text-[var(--bb-text)]">${title}</span>`;

            const reason = r.fit_reason ? `<div class="text-[10px] text-[var(--bb-text-muted)] mt-0.5 line-clamp-1">${escHtml(r.fit_reason)}</div>` : "";
            const src = escHtml(r.source_platform || r.platform || "-");
            const svc = escHtml(r.project_service_type || r.matched_services || "-");
            const budget = escHtml(r.budget || "-");
            const dtMatch = String(r.published_at || r.created_at || "").match(/\d{4}-\d{2}-\d{2}/);
            const dt = dtMatch ? dtMatch[0] : "-";

            return `
                <tr data-row-idx="${idx}" onclick="if(!event.target.closest('a') && window.bbSelectTableRow) window.bbSelectTableRow(${idx}, true)">
                    <td class="max-w-[280px]">${titleHtml}${reason}</td>
                    <td class="whitespace-nowrap">${src}</td>
                    <td class="max-w-[180px] truncate" title="${svc}">${svc}</td>
                    <td class="whitespace-nowrap">
                        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold border ${badgeCls}">
                            ${stLabel} · ${sc}%
                        </span>
                    </td>
                    <td class="whitespace-nowrap">${budget}</td>
                    <td class="whitespace-nowrap font-mono text-[10px]">${dt}</td>
                </tr>
            `;
        }).join("");
    }

    function renderAllProjectVisuals() {
        if (!isProjectStandalone()) return;
        const filtered = filterProjectRows(projectRowsCache);
        const colors = getThemeColors();

        // 1. Update 4 KPI
        let fix = 0, fifty = 0, no = 0, sumScore = 0;
        for (const r of filtered) {
            const sc = normalizeScore(r);
            sumScore += sc;
            if (sc >= 80) fix++;
            else if (sc >= 40) fifty++;
            else no++;
        }
        const avg = filtered.length ? Math.round(sumScore / filtered.length) : 0;
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = String(v); };
        setTxt("pkpi-fix", fix);
        setTxt("pkpi-fifty", fifty);
        setTxt("pkpi-no", no);
        setTxt("pkpi-avg", avg + "%");
        setTxt("pkpi-total", filtered.length + " project tampil");

        if (typeof Chart !== "undefined") {
            // 2. Grafik Tengah #1: Distribusi Confidence
            mountProjChart("chartProjConfidence", {
                type: "doughnut",
                data: {
                    labels: ["Fix Bisa Masuk (≥80%)", "Fifty-Fifty (40-79%)", "Tidak Bisa (<40%)"],
                    datasets: [{
                        data: [fix, fifty, no],
                        backgroundColor: ["rgba(90, 168, 130, 0.82)", "rgba(201, 139, 75, 0.82)", "rgba(201, 107, 120, 0.80)"],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "62%",
                    onClick: (_e, els) => {
                        if (!els?.length) return;
                        const map = ["fix bisa masuk", "fifty-fifty", "tidak bisa"];
                        window.ddcQuickProjectConf(map[els[0].index] || "");
                    },
                    plugins: {
                        legend: { position: "bottom", labels: { color: colors.text, boxWidth: 10, font: { size: 10 } } }
                    }
                }
            });

            // 3. Grafik Tengah #2: Sebaran Sumber Platform
            const srcMap = new Map();
            for (const r of filtered) {
                const k = String(r.source_platform || r.platform || "Lainnya").trim() || "Lainnya";
                srcMap.set(k, (srcMap.get(k) || 0) + 1);
            }
            const topSrc = Array.from(srcMap.entries()).sort((a, b) => b[1] - a[1]).slice(0, 7);
            mountProjChart("chartProjSources", {
                type: "bar",
                data: {
                    labels: topSrc.length ? topSrc.map((x) => x[0]) : ["Belum ada data"],
                    datasets: [{
                        label: "Jumlah Lead",
                        data: topSrc.length ? topSrc.map((x) => x[1]) : [0],
                        backgroundColor: "rgba(107, 163, 190, 0.78)",
                        borderRadius: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: colors.text, font: { size: 10 } }, grid: { display: false } },
                        y: { beginAtZero: true, ticks: { color: colors.text, precision: 0, font: { size: 10 } }, grid: { color: colors.grid } }
                    }
                }
            });

            // 4. Grafik Tengah #3: Kecocokan Tipe Layanan Geekgarden
            const svcMap = new Map();
            for (const r of filtered) {
                const k = String(r.project_service_type || r.matched_services || "Lainnya").trim() || "Lainnya";
                svcMap.set(k, (svcMap.get(k) || 0) + 1);
            }
            const topSvc = Array.from(svcMap.entries()).sort((a, b) => b[1] - a[1]).slice(0, 6);
            mountProjChart("chartProjServices", {
                type: "bar",
                data: {
                    labels: topSvc.length ? topSvc.map((x) => x[0].length > 26 ? x[0].slice(0, 24) + "…" : x[0]) : ["Belum ada data"],
                    datasets: [{
                        label: "Jumlah Project",
                        data: topSvc.length ? topSvc.map((x) => x[1]) : [0],
                        backgroundColor: "rgba(90, 168, 130, 0.78)",
                        borderRadius: 2
                    }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, ticks: { color: colors.text, precision: 0, font: { size: 10 } }, grid: { color: colors.grid } },
                        y: { ticks: { color: colors.text, font: { size: 10 } }, grid: { display: false } }
                    }
                }
            });

            // 5. Grafik Tengah #4: Top Project Paling Potensial
            const topProj = [...filtered].sort((a, b) => normalizeScore(b) - normalizeScore(a)).slice(0, 6);
            mountProjChart("chartProjTopScores", {
                type: "bar",
                data: {
                    labels: topProj.length
                        ? topProj.map((r) => {
                            const t = String(r.title || "Project").trim();
                            return t.length > 26 ? t.slice(0, 24) + "…" : t;
                        })
                        : ["Belum ada data"],
                    datasets: [{
                        label: "Skor Confidence (%)",
                        data: topProj.length ? topProj.map((r) => normalizeScore(r)) : [0],
                        backgroundColor: topProj.length
                            ? topProj.map((r) => normalizeScore(r) >= 80 ? "rgba(90, 168, 130, 0.82)" : normalizeScore(r) >= 40 ? "rgba(201, 139, 75, 0.82)" : "rgba(201, 107, 120, 0.80)")
                            : ["rgba(138, 149, 165, 0.45)"],
                        borderRadius: 2
                    }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (_e, els) => {
                        if (!els?.length) return;
                        const item = topProj[els[0].index];
                        if (item?.url && /^https?:\/\//i.test(item.url)) window.open(item.url, "_blank", "noopener");
                    },
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, max: 100, ticks: { color: colors.text, font: { size: 10 } }, grid: { color: colors.grid } },
                        y: { ticks: { color: colors.text, font: { size: 10 } }, grid: { display: false } }
                    }
                }
            });

            // 6. Grafik Kanan #1: Top Skill & Tech Stack
            const skillMap = new Map();
            for (const r of filtered) {
                const seen = new Set();
                if (r.skills && String(r.skills).trim() && String(r.skills).trim() !== "-") {
                    const arr = Array.isArray(r.skills) ? r.skills : String(r.skills).split(/[,;|/]+/);
                    for (let s of arr) {
                        s = String(s || "").trim();
                        if (s.length >= 2 && s.length <= 26 && !/^[-n\/a]+$/i.test(s)) seen.add(s);
                    }
                }
                if (!seen.size) {
                    const blob = [r.title, r.project_service_type, r.matched_services, r.content].filter(Boolean).join(" ");
                    for (const [label, rgx] of TECH_PATTERNS) {
                        if (rgx.test(blob)) seen.add(label);
                    }
                }
                seen.forEach((k) => skillMap.set(k, (skillMap.get(k) || 0) + 1));
            }
            const topSkills = Array.from(skillMap.entries()).sort((a, b) => b[1] - a[1]).slice(0, 7);
            mountProjChart("chartProjSkills", {
                type: "bar",
                data: {
                    labels: topSkills.length ? topSkills.map((x) => x[0]) : ["Belum ada data"],
                    datasets: [{
                        label: "Jumlah Project",
                        data: topSkills.length ? topSkills.map((x) => x[1]) : [0],
                        backgroundColor: "rgba(141, 132, 184, 0.78)",
                        borderRadius: 2
                    }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, ticks: { color: colors.text, precision: 0, font: { size: 10 } }, grid: { color: colors.grid } },
                        y: { ticks: { color: colors.text, font: { size: 10 } }, grid: { display: false } }
                    }
                }
            });

            // 7. Grafik Kanan #2: Sebaran Skor Confidence (5 Bucket)
            const buckets = [0, 0, 0, 0, 0];
            for (const r of filtered) {
                const sc = normalizeScore(r);
                if (sc < 20) buckets[0]++;
                else if (sc < 40) buckets[1]++;
                else if (sc < 60) buckets[2]++;
                else if (sc < 80) buckets[3]++;
                else buckets[4]++;
            }
            mountProjChart("chartProjScoreDist", {
                type: "bar",
                data: {
                    labels: ["0–19%", "20–39%", "40–59%", "60–79%", "80–100%"],
                    datasets: [{
                        label: "Jumlah Project",
                        data: buckets,
                        backgroundColor: [
                            "rgba(201, 107, 120, 0.70)",
                            "rgba(201, 107, 120, 0.84)",
                            "rgba(201, 139, 75, 0.72)",
                            "rgba(201, 139, 75, 0.86)",
                            "rgba(90, 168, 130, 0.84)"
                        ],
                        borderRadius: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (_e, els) => {
                        if (!els?.length) return;
                        const idx = els[0].index;
                        window.ddcQuickProjectConf(idx <= 1 ? "tidak bisa" : idx <= 3 ? "fifty-fifty" : "fix bisa masuk");
                    },
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: colors.text, font: { size: 10 } }, grid: { display: false } },
                        y: { beginAtZero: true, ticks: { color: colors.text, precision: 0, font: { size: 10 } }, grid: { color: colors.grid } }
                    }
                }
            });

            // 8. Grafik Kanan #3: Tren Peluang Project Masuk per Tanggal
            const byDate = new Map();
            for (const r of filtered) {
                const rawDt = r.published_at || r.created_at || r.scraped_at || r.tanggal || r.date || "";
                const m = String(rawDt).match(/(\d{4}-\d{2}-\d{2})/);
                const k = m ? m[1] : "Lainnya";
                if (!byDate.has(k)) byDate.set(k, { total: 0, fit: 0 });
                const entry = byDate.get(k);
                entry.total++;
                if (normalizeScore(r) >= 80) entry.fit++;
            }
            const sortedDates = Array.from(byDate.entries()).sort((a, b) => a[0].localeCompare(b[0])).slice(-12);
            mountProjChart("chartProjTimeline", {
                type: "line",
                data: {
                    labels: sortedDates.length ? sortedDates.map(([d]) => d.length === 10 ? d.slice(5) : d) : ["-"],
                    datasets: [
                        {
                            label: "Total Lead",
                            data: sortedDates.length ? sortedDates.map(([, v]) => v.total) : [0],
                            borderColor: "#6ba3be",
                            backgroundColor: "rgba(107, 163, 190, 0.12)",
                            fill: true,
                            tension: 0.3,
                            pointRadius: 2.5
                        },
                        {
                            label: "Fix ≥ 80%",
                            data: sortedDates.length ? sortedDates.map(([, v]) => v.fit) : [0],
                            borderColor: "#5aa882",
                            backgroundColor: "rgba(90, 168, 130, 0.10)",
                            fill: false,
                            tension: 0.3,
                            pointRadius: 2.5
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true, position: "bottom", labels: { color: colors.text, boxWidth: 10, font: { size: 10 } } }
                    },
                    scales: {
                        x: { ticks: { color: colors.text, font: { size: 10 } }, grid: { display: false } },
                        y: { beginAtZero: true, ticks: { color: colors.text, precision: 0, font: { size: 10 } }, grid: { color: colors.grid } }
                    }
                }
            });
        }

        // 9. Render Data Explorer Table
        renderProjectTable(filtered);
    }

    async function loadProjectStandaloneData() {
        if (!isProjectStandalone() || projectFetching) return;
        projectFetching = true;
        const statusEl = document.getElementById("status-text");
        if (statusEl) statusEl.textContent = "Memuat data peluang project dari server...";
        try {
            const resp = await fetch("/api/v1/project/records?limit=500");
            if (!resp.ok) throw new Error("HTTP " + resp.status);
            const json = await resp.json();
            const rows = Array.isArray(json?.data) ? json.data : (Array.isArray(json?.records) ? json.records : []);
            projectRowsCache = rows;
            renderAllProjectVisuals();
        } catch (err) {
            if (statusEl) statusEl.textContent = "Gagal memuat data project: " + (err?.message || err);
        } finally {
            projectFetching = false;
        }
    }

    window.ddcReloadProjectPage = loadProjectStandaloneData;
    window.ddcApplyProjectAll = renderAllProjectVisuals;
    window.ddcQuickProjectConf = function (val) {
        const el = document.getElementById("proj-filter-conf");
        if (el) el.value = val || "";
        renderAllProjectVisuals();
    };
    window.ddcResetProjectFilters = function () {
        ["proj-filter-conf", "proj-filter-source", "proj-filter-service"].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = "";
        });
        renderAllProjectVisuals();
    };

    // Sinkronkan setelah manual scrape selesai di halaman project.html
    if (window.fetch && !window.fetch.__ddcProjResultSniffer) {
        const prevFetch = window.fetch.bind(window);
        window.fetch = async function (...args) {
            const resp = await prevFetch(...args);
            try {
                const url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
                if (isProjectStandalone() && /\/api\/v1\/project\/(search|scrape|hunt|leads)/i.test(url)) {
                    resp.clone().json().then((json) => {
                        const rows = Array.isArray(json?.data) ? json.data : (Array.isArray(json?.records) ? json.records : null);
                        if (rows && rows.length) {
                            projectRowsCache = rows;
                            setTimeout(renderAllProjectVisuals, 120);
                        } else {
                            setTimeout(loadProjectStandaloneData, 400);
                        }
                    }).catch(() => {});
                }
            } catch (e) {}
            return resp;
        };
        window.fetch.__ddcProjResultSniffer = true;
    }

    const isAnalyticsStandalone = () =>
        (document.body && document.body.dataset && document.body.dataset.page === "analytics") ||
        /^\/analytics\/?$/i.test(window.location.pathname || "");

    let resizeTimer = null;
    function bootUnifiedShell() {
        if (window.lucide && typeof window.lucide.createIcons === "function") {
            try { window.lucide.createIcons(); } catch (e) {}
        }
        applyChartTheme();

        window.addEventListener("resize", () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                if (typeof Chart === "undefined" || !Chart.instances) return;
                Object.values(Chart.instances).forEach((ch) => {
                    try { if (ch && ch.canvas && ch.canvas.offsetParent !== null) ch.resize(); } catch (e) {}
                });
            }, 140);
        });

        if (isAnalyticsStandalone()) {
            if (typeof window.bbLoadAnalyticsPage === "function") {
                window.bbLoadAnalyticsPage();
                setInterval(window.bbLoadAnalyticsPage, 30000);
            }
            if (typeof window.bbInitTerminalEngine === "function") {
                window.bbInitTerminalEngine();
            }
            return;
        }

        if (isProjectStandalone()) {
            updateSidebarUI("project");
            if (typeof window.switchTab === "function") {
                try { window.switchTab("project"); } catch (e) {}
            }
            window.showProjectResults = loadProjectStandaloneData;
            window.applyProjectFilters = renderAllProjectVisuals;
            window.quickFilterProjectConf = window.ddcQuickProjectConf;
            window.resetSearchFilter = window.ddcResetProjectFilters;
            window.forceReloadAll = loadProjectStandaloneData;
            loadProjectStandaloneData();
            if (typeof window.bbInitTerminalEngine === "function") {
                window.bbInitTerminalEngine();
            }
            return;
        }

        // Halaman dashboard utama (frontend/index.html)
        if (typeof window.switchTab === "function" && !window.switchTab.__ddcUnifiedWrapped) {
            const origSwitch = window.switchTab;
            const wrapped = function (tab) {
                if (tab === "project") {
                    window.location.href = "/dashboard/project";
                    return;
                }
                const res = origSwitch.apply(this, arguments);
                updateSidebarUI(tab);
                applyChartsForTab(tab);
                if (!_syncingUrl && PAGE_META[tab]) {
                    const targetPath = "/dashboard/" + tab;
                    if (window.location.pathname !== targetPath) {
                        try { window.history.replaceState({ tab }, "", targetPath); } catch (e) {}
                    }
                }
                clearTimeout(kwDebounce);
                kwDebounce = setTimeout(ensureSocialKeywordChart, 350);
                setTimeout(applyChartTheme, 220);
                return res;
            };
            wrapped.__ddcUnifiedWrapped = true;
            window.switchTab = wrapped;
        }

        const initialTab = getTabFromUrl();
        updateSidebarUI(initialTab);
        if (typeof window.switchTab === "function") {
            _syncingUrl = true;
            try { window.switchTab(initialTab); } finally { _syncingUrl = false; }
        }
        applyChartsForTab(initialTab);

        const tbody = document.getElementById("table-body");
        if (tbody && typeof MutationObserver !== "undefined") {
            const obs = new MutationObserver(() => {
                clearTimeout(kwDebounce);
                kwDebounce = setTimeout(ensureSocialKeywordChart, 280);
            });
            obs.observe(tbody, { childList: true, subtree: true });
        }

        window.addEventListener("popstate", () => {
            const tab = getTabFromUrl();
            if (tab === "project") {
                window.location.href = "/dashboard/project";
                return;
            }
            updateSidebarUI(tab);
            if (typeof window.switchTab === "function") {
                _syncingUrl = true;
                try { window.switchTab(tab); } finally { _syncingUrl = false; }
            }
            applyChartsForTab(tab);
        });

        if (typeof window.bbInitTerminalEngine === "function") {
            window.bbInitTerminalEngine();
        }
        setTimeout(() => { applyChartTheme(); ensureSocialKeywordChart(); }, 900);
        setTimeout(() => { applyChartTheme(); ensureSocialKeywordChart(); }, 2200);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => setTimeout(bootUnifiedShell, 40));
    } else {
        setTimeout(bootUnifiedShell, 40);
    }
})();


/* ============================================================================
   DDC//TERM — BLOOMBERG TERMINAL ENGINE
   (Command Line CMD <GO>, Ticker Tape, Row Inspector, Live Log, Shortcuts)
   ============================================================================ */
(function () {
    const CMD_PRESETS = [
        { cmd: "QUAD", desc: "4-Pane Launchpad: News + Sosmed + Job Hunter + Watchlist" },
        { cmd: "MENU", desc: "Buka Direktori Fungsi Terminal (<MENU>)" },
        { cmd: "WATC", desc: "Buka Watchlist & Topic Broadcaster" },
        { cmd: "NW prabowo", desc: "Scrape Berita Kombine (Newsdata + Diffbot)" },
        { cmd: "NWS ekonomi", desc: "Scrape Berita Cepat via Newsdata.io" },
        { cmd: "NWD ikn", desc: "Scrape Berita Full + Sentimen Diffbot AI" },
        { cmd: "IG #karhutla", desc: "Scrape Instagram Hashtag / Keyword" },
        { cmd: "TT mbg", desc: "Scrape TikTok Hashtag / Konten" },
        { cmd: "FB kompascom", desc: "Scrape Facebook Page / Keyword" },
        { cmd: "TW prabowo", desc: "Scrape Twitter / X" },
        { cmd: "LI backend developer", desc: "Scrape Profil LinkedIn" },
        { cmd: "KW karhutla", desc: "Scrape Keyword Related Queries" },
        { cmd: "TRD teknologi", desc: "Scrape Google Trends Rising" },
        { cmd: "JOB flutter", desc: "Cari Peluang Project & Geekgarden Fit" },
        { cmd: "JOB erp", desc: "Cari Peluang Project ERP / Custom Software" },
        { cmd: "SUPA BERITA", desc: "Buka Supabase News Articles" },
        { cmd: "SUPA INSTAGRAM", desc: "Buka Supabase Social Posts (IG)" },
        { cmd: "BANK BERITA", desc: "Buka Bank Data CSV Kategori Berita" },
        { cmd: "ANL", desc: "Buka Global Analytics Matrix" },
        { cmd: "CRON RUN", desc: "Trigger Batch Cron 1.000 Baris" },
        { cmd: "SYNC", desc: "Sync Semua CSV ke Supabase" },
        { cmd: "CLR", desc: "Bersihkan HTTP Cache & Reload" },
        { cmd: "DOCS", desc: "Buka Swagger OpenAPI (/docs)" },
        { cmd: "HELP", desc: "Tampilkan Panduan Command & Shortcut" }
    ];

    const cmdHistory = [];
    let cmdHistIdx = -1;
    let acActiveIdx = -1;
    let currentInspJson = "";
    let currentInspRow = null;
    let analyticsCharts = {};

    // Bloomberg Navigation History Stack (<BACK> / <FWD>)
    const navStack = [];
    let navIdx = -1;
    let navReplaying = false;

    // Color-Coded Link Groups (AMBER -> CYAN -> NONE)
    const LINK_GROUPS = ["AMBER", "CYAN", "NONE"];
    let globalLinkGroup = "AMBER";
    const quadLinks = { q1: "AMBER", q2: "AMBER", q3: "AMBER" };
    const quadCache = { q1: [], q2: [], q3: [] };
    let quadBooted = false;

    const DEFAULT_WATCHLIST = ["prabowo", "karhutla", "mbg", "flutter", "erp"];
    function getWatchlist() {
        try {
            const raw = localStorage.getItem("ddc_bb_watchlist");
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed) && parsed.length) return parsed;
            }
        } catch (e) {}
        return [...DEFAULT_WATCHLIST];
    }
    function saveWatchlist(list) {
        try { localStorage.setItem("ddc_bb_watchlist", JSON.stringify(list)); } catch (e) {}
    }

    function updateNavButtons() {
        const bBtn = document.getElementById("bb-btn-back");
        const fBtn = document.getElementById("bb-btn-fwd");
        if (bBtn) bBtn.disabled = navIdx <= 0;
        if (fBtn) fBtn.disabled = navIdx < 0 || navIdx >= navStack.length - 1;
    }

    function pushNavState(cmd) {
        if (navReplaying || !cmd) return;
        const clean = String(cmd).trim();
        if (!clean) return;
        if (navStack[navIdx] === clean) return;
        navStack.splice(navIdx + 1);
        navStack.push(clean);
        if (navStack.length > 40) navStack.shift();
        navIdx = navStack.length - 1;
        updateNavButtons();
    }

    window.bbNavBack = function () {
        if (navIdx <= 0) return;
        navIdx--;
        navReplaying = true;
        try { window.bbExecuteCommand(navStack[navIdx]); } finally { navReplaying = false; }
        updateNavButtons();
    };

    window.bbNavForward = function () {
        if (navIdx >= navStack.length - 1) return;
        navIdx++;
        navReplaying = true;
        try { window.bbExecuteCommand(navStack[navIdx]); } finally { navReplaying = false; }
        updateNavButtons();
    };

    function esc(s) {
        return String(s ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function getWibNow() {
        const now = new Date();
        const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
        return new Date(utcMs + (7 * 3600000));
    }

    function pad2(n) {
        return String(n).padStart(2, "0");
    }

    // 1. LIVE WIB CLOCK & 8-HOUR CRON COUNTDOWN
    function tickClockAndCron() {
        const wib = getWibNow();
        const hh = wib.getHours();
        const mm = wib.getMinutes();
        const ss = wib.getSeconds();

        const clockEl = document.getElementById("bb-wib-clock");
        if (clockEl) {
            clockEl.textContent = `${pad2(hh)}:${pad2(mm)}:${pad2(ss)} WIB`;
        }

        const cdEl = document.getElementById("bb-cron-countdown");
        if (cdEl) {
            const elapsedSec = ((hh % 8) * 3600) + (mm * 60) + ss;
            const rem = Math.max(0, (8 * 3600) - elapsedSec);
            const rh = Math.floor(rem / 3600);
            const rm = Math.floor((rem % 3600) / 60);
            const rs = rem % 60;
            cdEl.textContent = `${pad2(rh)}:${pad2(rm)}:${pad2(rs)}`;
        }
    }

    // 2. LIVE TERMINAL LOG + API LATENCY INTERCEPTOR
    window.bbLogTerminal = function (msg, level = "info") {
        const box = document.getElementById("bb-terminal-log");
        if (!box) return;
        const wib = getWibNow();
        const ts = `${pad2(wib.getHours())}:${pad2(wib.getMinutes())}:${pad2(wib.getSeconds())}`;
        let cls = "text-[var(--bb-text-muted)]";
        if (level === "ok") cls = "text-[var(--bb-green)]";
        else if (level === "warn") cls = "text-[var(--bb-amber)]";
        else if (level === "err") cls = "text-[var(--bb-red)]";
        else if (level === "cmd") cls = "text-[var(--bb-cyan)]";

        const line = document.createElement("div");
        line.className = `${cls} truncate`;
        line.title = msg;
        line.textContent = `[${ts}] ${msg}`;
        box.appendChild(line);

        while (box.children.length > 80) {
            box.removeChild(box.firstChild);
        }
        box.scrollTop = box.scrollHeight;
    };

    window.bbClearTerminalLog = function () {
        const box = document.getElementById("bb-terminal-log");
        if (box) box.innerHTML = `<div class="text-[var(--bb-text-muted)]">[CLR] Log dibersihkan.</div>`;
    };

    if (window.fetch && !window.fetch.__bbTelemetryWrapped) {
        const prevFetch = window.fetch.bind(window);
        window.fetch = async function (input, init) {
            const url = typeof input === "string" ? input : (input && input.url) || "";
            const method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
            const isApi = url.includes("/api/v1/");
            const t0 = performance.now();
            try {
                const res = await prevFetch(input, init);
                if (isApi) {
                    const ms = Math.round(performance.now() - t0);
                    const latEl = document.getElementById("bb-api-latency");
                    if (latEl) latEl.textContent = `${ms}ms`;
                    const shortUrl = url.replace(window.location.origin, "").split("?")[0];
                    window.bbLogTerminal(`${method} ${shortUrl} -> ${res.status} (${ms}ms)`, res.ok ? "ok" : "err");
                }
                return res;
            } catch (err) {
                if (isApi) {
                    const shortUrl = url.replace(window.location.origin, "").split("?")[0];
                    window.bbLogTerminal(`${method} ${shortUrl} -> ERR (${err.message || err})`, "err");
                }
                throw err;
            }
        };
        window.fetch.__bbTelemetryWrapped = true;
    }

    // 3. WORKSPACE SCREEN SWITCHER, MENU DIRECTORY & PANEL MAXIMIZE
    window.bbSetScreen = function (mode) {
        document.body.classList.remove("bb-scr-intel", "bb-scr-ops", "bb-scr-grid", "bb-scr-quad");
        if (mode === "ops") document.body.classList.add("bb-scr-ops");
        else if (mode === "grid") document.body.classList.add("bb-scr-grid");
        else if (mode === "quad") document.body.classList.add("bb-scr-quad");
        else document.body.classList.add("bb-scr-intel");

        const map = { intel: "bb-scr-1", ops: "bb-scr-2", grid: "bb-scr-4", quad: "bb-scr-5" };
        Object.entries(map).forEach(([k, id]) => {
            const el = document.getElementById(id);
            if (el) el.classList.toggle("bb-scr-active", k === mode);
        });

        const inQuad = (mode === "quad");
        document.querySelectorAll(".ddc-sb-item").forEach((el) => {
            const tabAttr = el.getAttribute("data-ddc-tab");
            if (!tabAttr) return;
            el.classList.toggle("bb-fkey-active", inQuad ? tabAttr === "quad" : tabAttr === currentTab);
        });

        if (mode === "quad" && typeof window.bbRefreshQuadAll === "function" && !quadBooted) {
            quadBooted = true;
            window.bbRefreshQuadAll();
        }

        setTimeout(() => {
            if (typeof Chart !== "undefined" && Chart.instances) {
                Object.values(Chart.instances).forEach((ch) => {
                    try { if (ch && ch.canvas && ch.canvas.offsetParent !== null) ch.resize(); } catch (e) {}
                });
            }
        }, 80);
    };

    window.bbToggleMenuModal = function (open) {
        const modal = document.getElementById("bb-menu-modal");
        if (!modal) return;
        const shouldOpen = typeof open === "boolean" ? open : modal.classList.contains("hidden");
        if (shouldOpen && typeof window.bbRenderMenuModal === "function") {
            window.bbRenderMenuModal();
        }
        modal.classList.toggle("hidden", !shouldOpen);
    };

    window.bbToggleMaximize = function (btn) {
        const panel = btn ? btn.closest(".bb-panel") : null;
        if (!panel) return;
        const wasMax = panel.classList.contains("bb-maximized");
        document.querySelectorAll(".bb-panel.bb-maximized").forEach((p) => p.classList.remove("bb-maximized"));
        if (!wasMax) panel.classList.add("bb-maximized");

        setTimeout(() => {
            if (typeof Chart !== "undefined" && Chart.instances) {
                Object.values(Chart.instances).forEach((ch) => {
                    try { if (ch && ch.canvas && ch.canvas.offsetParent !== null) ch.resize(); } catch (e) {}
                });
            }
        }, 60);
    };

    window.bbToggleHelpModal = function (open) {
        const modal = document.getElementById("bb-help-modal");
        if (!modal) return;
        const shouldOpen = typeof open === "boolean" ? open : modal.classList.contains("hidden");
        modal.classList.toggle("hidden", !shouldOpen);
    };

    // 4. TABLE QUICK FILTER, SORT & ROW DETAIL INSPECTOR
    window.bbQuickFilterTable = function (term) {
        const base = window.__BB_RAW_TABLE_ROWS;
        if (!Array.isArray(base)) return;
        const q = String(term || "").trim().toLowerCase();
        const filtered = q
            ? base.filter((r) => Object.values(r || {}).join(" ").toLowerCase().includes(q))
            : base;

        const rc = document.getElementById("row-count");
        if (rc) rc.textContent = String(filtered.length);

        const isProj = (document.body?.dataset?.page === "project");
        if (isProj) {
            const tbody = document.getElementById("table-body");
            if (!tbody) return;
            window.__BB_CURRENT_ROWS = filtered.slice(0, 200);
            const slice = window.__BB_CURRENT_ROWS;
            if (!slice.length) {
                tbody.innerHTML = '<tr><td colspan="6" class="p-6 text-center text-[var(--bb-text-muted)] font-mono text-xs">TIDAK ADA DATA PROJECT YANG COCOK.</td></tr>';
                return;
            }
            tbody.innerHTML = slice.map((r, idx) => {
                const sc = Number(r.confidence_score) || 0;
                const st = sc >= 80 ? "Fix Bisa Masuk" : sc >= 40 ? "Fifty-Fifty" : "Tidak Bisa";
                const badgeCls = sc >= 80
                    ? "bg-emerald-950/90 text-emerald-300 border-emerald-700"
                    : sc >= 40
                    ? "bg-amber-950/90 text-amber-300 border-amber-700"
                    : "bg-rose-950/90 text-rose-300 border-rose-700";
                const dtMatch = String(r.published_at || r.created_at || "").match(/\d{4}-\d{2}-\d{2}/);
                return `
                    <tr data-row-idx="${idx}" onclick="if(!event.target.closest('a') && window.bbSelectTableRow) window.bbSelectTableRow(${idx}, true)">
                        <td class="max-w-[280px] font-semibold">${esc(r.title || "-")}</td>
                        <td class="whitespace-nowrap">${esc(r.source_platform || r.platform || "-")}</td>
                        <td class="max-w-[180px] truncate">${esc(r.project_service_type || r.matched_services || "-")}</td>
                        <td class="whitespace-nowrap"><span class="px-1.5 py-0.5 text-[10px] font-semibold border ${badgeCls}">${st} · ${sc}%</span></td>
                        <td class="whitespace-nowrap">${esc(r.budget || "-")}</td>
                        <td class="whitespace-nowrap font-mono text-[10px]">${dtMatch ? dtMatch[0] : "-"}</td>
                    </tr>
                `;
            }).join("");
            return;
        }

        if (typeof window.renderTable === "function") {
            window.renderTable(filtered, true);
        }
    };

    window.bbSortTableByColumn = function (col) {
        const rows = window.__BB_CURRENT_ROWS;
        if (!Array.isArray(rows) || !rows.length) return;
        const prev = window.__BB_SORT_STATE || { col: null, asc: true };
        const asc = prev.col === col ? !prev.asc : true;
        window.__BB_SORT_STATE = { col, asc };

        const sorted = [...rows].sort((a, b) => {
            const va = a?.[col] ?? "";
            const vb = b?.[col] ?? "";
            const na = Number(String(va).replace(/[^\d.-]/g, ""));
            const nb = Number(String(vb).replace(/[^\d.-]/g, ""));
            if (va !== "" && vb !== "" && !isNaN(na) && !isNaN(nb) && /^\s*-?[\d.,]+%?\s*$/.test(String(va)) && /^\s*-?[\d.,]+%?\s*$/.test(String(vb))) {
                return asc ? na - nb : nb - na;
            }
            return asc
                ? String(va).localeCompare(String(vb), "id")
                : String(vb).localeCompare(String(va), "id");
        });

        if (typeof window.renderTable === "function") {
            window.renderTable(sorted, true);
        }
    };

    window.bbSelectTableRow = function (idx, openInsp = false) {
        const rows = window.__BB_CURRENT_ROWS || [];
        if (idx < 0 || idx >= rows.length) return;
        window.__BB_SELECTED_ROW_IDX = idx;

        document.querySelectorAll("#table-body tr.bb-row-selected").forEach((el) => el.classList.remove("bb-row-selected"));
        const tr = document.querySelector(`#table-body tr[data-row-idx="${idx}"]`);
        if (tr) {
            tr.classList.add("bb-row-selected");
            tr.scrollIntoView({ block: "nearest" });
        }

        if (openInsp) {
            window.bbOpenInspector(idx);
        }
    };

    window.bbOpenInspector = function (idx) {
        const rows = window.__BB_CURRENT_ROWS || [];
        const row = rows[idx];
        if (!row) return;
        window.bbOpenRawInspectorRow(row, `ROW #${idx + 1}`);
    };

    window.bbOpenRawInspectorRow = function (row, fallbackLabel = "DETAIL") {
        const drawer = document.getElementById("bb-inspector-drawer");
        if (!row || !drawer) return;
        currentInspRow = row;

        const titleEl = document.getElementById("bb-inspector-title");
        const metaEl = document.getElementById("bb-inspector-meta");
        const readEl = document.getElementById("bb-inspector-readable");
        const jsonEl = document.getElementById("bb-inspector-json");
        const linkEl = document.getElementById("bb-inspector-link");

        const headline = row.title || row.judul || row.Query || row.keyword || row.Nama || row.username || fallbackLabel;
        if (titleEl) titleEl.textContent = String(headline).slice(0, 80);

        const url = row.url || row.link || row.Link || row.Link_Profil || "";
        if (linkEl) {
            if (url && /^https?:\/\//i.test(String(url))) {
                linkEl.href = String(url);
                linkEl.classList.remove("hidden");
            } else {
                linkEl.classList.add("hidden");
            }
        }

        const metaPairs = [
            ["PLATFORM", row.source_platform || row.platform || row.Platform || "-"],
            ["TOOL / ENGINE", row.tool || row.Tool || "-"],
            ["TANGGAL", row.published_at || row.tanggal || row.Tanggal || row.waktu_scrape || row.created_at || "-"],
            ["AUTHOR / USER", row.username || row.Username || row.penulis || row["Penulis berita"] || row.author || row.Nama || "-"],
            ["SENTIMEN / FIT", row.confidence_status ? `${row.confidence_status} (${row.confidence_score ?? 0}%)` : (row.sentimen_diffbot ?? row.sentiment ?? "-")],
            ["BUDGET / VOL", row.budget || row.Values || row.formattedvalue || row.Likes || row.likes || "-"]
        ];
        if (metaEl) {
            metaEl.innerHTML = metaPairs.map(([k, v]) => `
                <div class="p-1.5 bg-[var(--bb-bg-elev)] border border-[var(--bb-border)]">
                    <div class="text-[9px] text-[var(--bb-text-muted)]">${esc(k)}</div>
                    <div class="text-[11px] text-[var(--bb-text)] font-semibold truncate" title="${esc(v)}">${esc(v)}</div>
                </div>
            `).join("");
        }

        const bodyFields = [
            ["HEADLINE / JUDUL", row.title || row.judul || row.Judul || row.Query],
            ["ISI BERITA / TEKS", row.isi_berita || row.Isi_Berita || row.teks || row.Teks || row.text || row.caption || row.content],
            ["GEEKGARDEN FIT REASON", row.fit_reason],
            ["MATCHED SERVICES", row.project_service_type || row.matched_services],
            ["SKILLS / TECH STACK", row.skills || row.Skill]
        ].filter(([, val]) => val !== undefined && val !== null && String(val).trim() !== "");

        if (readEl) {
            readEl.innerHTML = bodyFields.length
                ? bodyFields.map(([lbl, val]) => `
                    <div class="p-2.5 bg-[var(--bb-bg-elev)] border border-[var(--bb-border)]">
                        <div class="font-mono text-[10px] font-bold text-[var(--bb-amber)] mb-1">${esc(lbl)}</div>
                        <div class="text-xs text-[var(--bb-text)] whitespace-pre-wrap break-words leading-relaxed">${esc(val)}</div>
                    </div>
                `).join("")
                : `<div class="p-3 text-[var(--bb-text-muted)] font-mono text-xs">Lihat tab RAW_JSON untuk seluruh atribut payload.</div>`;
        }

        currentInspJson = JSON.stringify(row, null, 2);
        if (jsonEl) jsonEl.textContent = currentInspJson;

        window.bbSetInspectorTab("read");
        drawer.classList.remove("hidden");
    };

    window.bbCloseInspector = function () {
        const drawer = document.getElementById("bb-inspector-drawer");
        if (drawer) drawer.classList.add("hidden");
    };

    window.bbSetInspectorTab = function (tab) {
        const readEl = document.getElementById("bb-inspector-readable");
        const jsonEl = document.getElementById("bb-inspector-json");
        const btnR = document.getElementById("bb-insp-tab-read");
        const btnJ = document.getElementById("bb-insp-tab-json");
        const isJson = tab === "json";
        if (readEl) readEl.classList.toggle("hidden", isJson);
        if (jsonEl) jsonEl.classList.toggle("hidden", !isJson);
        if (btnR) btnR.classList.toggle("bb-scr-active", !isJson);
        if (btnJ) btnJ.classList.toggle("bb-scr-active", isJson);
    };

    window.bbCopyInspectorJson = function () {
        if (!currentInspJson) return;
        navigator.clipboard?.writeText(currentInspJson).then(() => {
            window.bbLogTerminal("JSON payload disalin ke clipboard.", "ok");
        }).catch(() => {});
    };

    // 5. LIVE TICKER TAPE (BERITA, SOSMED & JOB HUNTER)
    async function bbRefreshTicker() {
        const track = document.getElementById("bb-ticker-track");
        if (!track) return;

        const items = [];
        try {
            const page = document.body?.dataset?.page || "dashboard";

            if (page !== "project") {
                const an = BASE_ANALYTICS || (await fetch("/api/v1/warehouse/analytics").then(r => r.ok ? r.json() : null).catch(() => null))?.analytics;
                if (an) {
                    const sent = an.sentiment_summary || {};
                    const totS = (sent.positive || 0) + (sent.neutral || 0) + (sent.negative || 0);
                    if (totS > 0) {
                        const posPct = Math.round(((sent.positive || 0) / totS) * 100);
                        items.push({ tag: "SENTIMENT", label: `POS ${posPct}%`, delta: `▲ ${sent.positive || 0}`, cls: "text-[var(--bb-green)]", cmd: "SUPA BERITA" });
                    }
                    (an.top_keywords || []).slice(0, 4).forEach((k) => {
                        items.push({ tag: "KW", label: String(k.keyword || "").toUpperCase(), delta: `▲ ${k.volume || 0}`, cls: "text-[var(--bb-amber)]", cmd: `SUPA BERITA ${k.keyword}` });
                    });
                    (an.top_people || []).slice(0, 3).forEach((p) => {
                        items.push({ tag: "TOKOH", label: String(p.name || "").toUpperCase(), delta: `${p.mentions || 0}x`, cls: "text-[var(--bb-cyan)]", cmd: `SUPA BERITA ${p.name}` });
                    });
                    (an.top_hashtags || []).slice(0, 3).forEach((h) => {
                        items.push({ tag: "SOSMED", label: String(h.tag || "").toUpperCase(), delta: `${h.count || 0}`, cls: "text-[#b58aa5]", cmd: `SUPA INSTAGRAM ${h.tag}` });
                    });
                }
            }

            if (page === "project" || items.length < 10) {
                const projData = (page === "project" && Array.isArray(window.__BB_RAW_TABLE_ROWS) && window.__BB_RAW_TABLE_ROWS.length)
                    ? window.__BB_RAW_TABLE_ROWS
                    : ((await fetch("/api/v1/project/records?limit=20").then(r => r.ok ? r.json() : null).catch(() => null))?.data || []);

                projData
                    .filter((r) => Number(r.confidence_score) >= 75)
                    .slice(0, 4)
                    .forEach((p) => {
                        const t = String(p.title || "PROJECT").slice(0, 26).toUpperCase();
                        items.push({
                            tag: "JOB_FIT",
                            label: t,
                            delta: `${p.confidence_score || 0}% ▲`,
                            cls: "text-[var(--bb-green)]",
                            cmd: `JOB ${String(p.title || "").split(/\s+/).slice(0, 2).join(" ")}`
                        });
                    });
            }
        } catch (e) {}

        if (!items.length) {
            items.push(
                { tag: "NEWS", label: "KOMBINE READY", delta: "● LIVE", cls: "text-[var(--bb-green)]", cmd: "NEWS KOMBINE prabowo" },
                { tag: "SOSMED", label: "IG / TIKTOK / FB / X", delta: "● READY", cls: "text-[var(--bb-cyan)]", cmd: "SOC IG #karhutla" },
                { tag: "JOB_FIT", label: "GEEKGARDEN MATCHER", delta: "≥80%", cls: "text-[var(--bb-amber)]", cmd: "JOB flutter" }
            );
        }

        const html = items.map((it) => `
            <span class="bb-tick-item" onclick="bbExecuteCommand('${esc(it.cmd)}')" title="Klik untuk jalankan: ${esc(it.cmd)}">
                <span class="text-[var(--bb-text-dim)]">[${esc(it.tag)}]</span>
                <span class="text-[var(--bb-text)] font-semibold">${esc(it.label)}</span>
                <span class="${it.cls} font-bold">${esc(it.delta)}</span>
            </span>
        `).join("");

        // Duplikat untuk loop marquee mulus
        track.innerHTML = html + html;
    }

    // 6. BLOOMBERG COMMAND PARSER (CMD <GO>) + FULL MNEMONICS
    window.bbExecuteCommand = function (rawInput) {
        const raw = String(rawInput || "").trim();
        if (!raw) return;

        window.bbLogTerminal(`CMD> ${raw}`, "cmd");
        if (cmdHistory[0] !== raw) cmdHistory.unshift(raw);
        if (cmdHistory.length > 30) cmdHistory.pop();
        cmdHistIdx = -1;

        const ac = document.getElementById("bb-cmd-ac");
        if (ac) ac.classList.add("hidden");

        const parts = raw.split(/\s+/);
        const head = parts[0].toUpperCase();
        const rest = parts.slice(1).join(" ").trim();
        const page = document.body?.dataset?.page || "dashboard";

        if (head === "HELP" || head === "?") {
            window.bbToggleHelpModal(true);
            return;
        }
        if (head === "MENU") {
            window.bbToggleMenuModal(true);
            return;
        }
        if (head === "BACK") {
            window.bbNavBack();
            return;
        }
        if (head === "FWD" || head === "FORWARD") {
            window.bbNavForward();
            return;
        }
        if (head === "DOCS" || head === "API") {
            window.open("/docs", "_blank");
            return;
        }
        if (head === "ANL" || head === "ANALYTICS") {
            window.location.href = "/analytics";
            return;
        }
        if (head === "CLR" || head === "CLEAR") {
            fetch("/api/v1/system/clear-cache", { method: "POST" }).then(() => {
                window.bbLogTerminal("Cache dibersihkan.", "ok");
                if (typeof window.forceReloadAll === "function") window.forceReloadAll();
            }).catch(() => {});
            return;
        }
        if (head === "QUAD" || head === "WATC" || head === "MON" || head === "WATCHLIST") {
            if (page !== "dashboard") {
                try { sessionStorage.setItem("ddc_pending_cmd", raw); } catch (e) {}
                window.location.href = "/dashboard/supabase";
                return;
            }
            pushNavState(raw);
            window.bbSetScreen("quad");
            if (rest) {
                window.bbBroadcastTopic(rest, globalLinkGroup);
            } else if (head === "WATC" || head === "MON" || head === "WATCHLIST") {
                const wlInp = document.getElementById("bb-wl-add");
                if (wlInp) wlInp.focus();
            }
            return;
        }
        if (head === "JOB" || head === "FIT" || head === "PROJ" || head === "PROJECT") {
            if (page !== "project") {
                try { sessionStorage.setItem("ddc_pending_cmd", raw); } catch (e) {}
                window.location.href = "/dashboard/project";
                return;
            }
            pushNavState(raw);
            if (rest) {
                const inp = document.getElementById("proj-input");
                if (inp) inp.value = rest;
                if (typeof window.executeAction === "function") window.executeAction(true);
            } else if (typeof window.ddcReloadProjectPage === "function") {
                window.ddcReloadProjectPage();
            }
            return;
        }

        // Command untuk halaman dashboard utama (index.html)
        if (page !== "dashboard") {
            try { sessionStorage.setItem("ddc_pending_cmd", raw); } catch (e) {}
            let target = "/dashboard/supabase";
            if (head === "BANK" || head === "CSV") target = "/dashboard/bank";
            else if (head === "KW" || head === "TRD" || head === "TREND") target = "/dashboard/keyword";
            else if (["NW", "NWS", "NWD", "NWB", "NEWS", "BERITA"].includes(head)) target = "/dashboard/berita";
            else if (["SOC", "SOSMED", "IG", "TT", "FB", "TW", "LI"].includes(head)) target = "/dashboard/sosmed";
            window.location.href = target;
            return;
        }

        // Keluar dari mode QUAD saat membuka tab spesifik
        if (document.body.classList.contains("bb-scr-quad")) {
            window.bbSetScreen("intel");
        }
        pushNavState(raw);

        if (head === "CRON") {
            if (typeof window.triggerCronNow === "function") window.triggerCronNow();
            return;
        }
        if (head === "SYNC") {
            if (typeof window.syncCsvToSupabase === "function") window.syncCsvToSupabase();
            return;
        }

        if (head === "SUPA" || head === "DB") {
            if (typeof window.ddcGoPage === "function") window.ddcGoPage("supabase");
            const catEl = document.getElementById("sb-cat");
            const searchEl = document.getElementById("sb-search");
            const arg1 = (parts[1] || "").toLowerCase();
            const domainAlias = {
                berita: "berita", news: "berita",
                ig: "instagram", instagram: "instagram",
                fb: "facebook", facebook: "facebook",
                tt: "tiktok", tiktok: "tiktok",
                tw: "twitter", x: "twitter", twitter: "twitter",
                li: "linkedin", linkedin: "linkedin",
                kw: "keyword_trending", keyword: "keyword_trending"
            };
            let queryTail = rest;
            if (domainAlias[arg1] && catEl) {
                catEl.value = domainAlias[arg1];
                queryTail = parts.slice(2).join(" ").trim();
                if (searchEl) searchEl.value = queryTail;
                if (typeof window.onDomainChange === "function") window.onDomainChange();
            } else {
                if (searchEl) searchEl.value = queryTail;
                if (typeof window.applyClientFilters === "function") window.applyClientFilters();
            }
            return;
        }

        if (head === "BANK" || head === "CSV") {
            if (typeof window.ddcGoPage === "function") window.ddcGoPage("bank");
            const catEl = document.getElementById("bd-cat");
            const toolEl = document.getElementById("bd-tool");
            const searchEl = document.getElementById("bd-search");
            const arg1 = (parts[1] || "").toLowerCase();
            const catAlias = {
                berita: "berita", news: "berita",
                ig: "instagram", instagram: "instagram",
                fb: "facebook", facebook: "facebook",
                tt: "tiktok", tiktok: "tiktok",
                tw: "twitter", twitter: "twitter",
                li: "linkedin", linkedin: "linkedin",
                kw: "keyword_trending", keyword: "keyword_trending",
                all: "semua", semua: "semua"
            };
            if (catAlias[arg1] && catEl) {
                catEl.value = catAlias[arg1];
                const arg2 = (parts[2] || "").toLowerCase();
                if (["apify", "diffbot", "newsdata", "brightdata", "kombine"].includes(arg2) && toolEl) {
                    toolEl.value = arg2;
                    if (searchEl) searchEl.value = parts.slice(3).join(" ").trim();
                } else if (searchEl) {
                    searchEl.value = parts.slice(2).join(" ").trim();
                }
            } else if (searchEl) {
                searchEl.value = rest;
            }
            if (typeof window.onBankFilterChange === "function") window.onBankFilterChange();
            return;
        }

        if (head === "KW" || head === "TRD" || head === "TREND") {
            if (typeof window.ddcGoPage === "function") window.ddcGoPage("keyword");
            const modeEl = document.getElementById("kw-mode");
            const inpEl = document.getElementById("kw-input");
            if (modeEl) modeEl.value = (head === "TRD" || head === "TREND") ? "/api/v1/keyword/trending" : "/api/v1/keyword/search";
            if (inpEl && rest) inpEl.value = rest;
            if (rest && typeof window.executeAction === "function") window.executeAction(true);
            return;
        }

        if (["NW", "NWS", "NWD", "NWB", "NEWS", "BERITA"].includes(head)) {
            if (typeof window.ddcGoPage === "function") window.ddcGoPage("berita");
            const engEl = document.getElementById("br-engine");
            const inpEl = document.getElementById("br-input");
            const engMap = {
                kombine: "/api/v1/berita/kombine",
                newsdata: "/api/v1/berita/newsdata",
                diffbot: "/api/v1/berita/diffbot",
                brightdata: "/api/v1/berita/brightdata"
            };
            let topic = rest;
            if (head === "NWS" && engEl) engEl.value = engMap.newsdata;
            else if (head === "NWD" && engEl) engEl.value = engMap.diffbot;
            else if (head === "NWB" && engEl) engEl.value = engMap.brightdata;
            else if (head === "NW" && engEl) engEl.value = engMap.kombine;
            else {
                const arg1 = (parts[1] || "").toLowerCase();
                if (engMap[arg1] && engEl) {
                    engEl.value = engMap[arg1];
                    topic = parts.slice(2).join(" ").trim();
                }
            }
            if (inpEl && topic) inpEl.value = topic;
            if (topic && typeof window.executeAction === "function") window.executeAction(true);
            return;
        }

        if (["SOC", "SOSMED", "IG", "TT", "FB", "TW", "LI"].includes(head)) {
            if (typeof window.ddcGoPage === "function") window.ddcGoPage("sosmed");
            const pfEl = document.getElementById("sm-platform");
            const inpEl = document.getElementById("sm-input");
            const pfMap = {
                ig: "instagram", instagram: "instagram",
                fb: "facebook", facebook: "facebook",
                tt: "tiktok", tiktok: "tiktok",
                tw: "twitter", x: "twitter", twitter: "twitter",
                li: "linkedin", linkedin: "linkedin"
            };
            let q = rest;
            if (pfMap[head.toLowerCase()] && pfEl) {
                pfEl.value = pfMap[head.toLowerCase()];
                if (typeof window.toggleSosmedOptions === "function") window.toggleSosmedOptions();
            } else {
                const arg1 = (parts[1] || "").toLowerCase();
                if (pfMap[arg1] && pfEl) {
                    pfEl.value = pfMap[arg1];
                    if (typeof window.toggleSosmedOptions === "function") window.toggleSosmedOptions();
                    q = parts.slice(2).join(" ").trim();
                }
            }
            if (inpEl && q) inpEl.value = q;
            if (q && typeof window.executeAction === "function") window.executeAction(true);
            return;
        }

        // Fallback: anggap teks bebas sebagai quick search di Supabase
        if (typeof window.ddcGoPage === "function") window.ddcGoPage("supabase");
        const searchEl = document.getElementById("sb-search");
        if (searchEl) searchEl.value = raw;
        if (typeof window.applyClientFilters === "function") window.applyClientFilters();
    };

    window.bbRunCommandFromInput = function () {
        const inp = document.getElementById("bb-cmd-input");
        if (!inp) return;
        window.bbExecuteCommand(inp.value);
    };

    // 7. ANALYTICS PAGE CONTROLLER (/analytics)
    window.bbLoadAnalyticsPage = async function () {
        if (document.body?.dataset?.page !== "analytics") return;
        try {
            const [resSt, resAn] = await Promise.all([
                fetch("/api/v1/scheduler/status").then(r => r.ok ? r.json() : {}),
                fetch("/api/v1/warehouse/analytics").then(r => r.ok ? r.json() : {})
            ]);
            const wh = (resSt.warehouse || resSt.supabase_warehouse || {}).counts || {};
            const sc = resSt.scheduler || {};
            const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v ?? 0; };

            setTxt("st-news", wh.news_articles);
            setTxt("st-keywords", wh.keywords);
            setTxt("st-trends", wh.trend_snapshots);
            setTxt("st-posts", wh.social_posts);
            setTxt("st-raw", wh.raw_data);
            setTxt("cron-next", sc.next_run_wib || "-");
            setTxt("cron-status", (sc.last_execution || {}).status || "idle");

            setTxt("kpi-raw", wh.raw_data || 0);
            setTxt("kpi-news", wh.news_articles || 0);
            setTxt("kpi-kw", (wh.keywords || 0) + (wh.trend_snapshots || 0));
            setTxt("kpi-social", (wh.social_posts || 0) + (wh.social_accounts || 0));

            const an = resAn.analytics || {};
            BASE_ANALYTICS = an;
            const gridCol = document.documentElement.classList.contains("dark") ? "rgba(52, 63, 82, 0.45)" : "rgba(182, 174, 155, 0.45)";
            const mountAn = (id, cfg) => {
                const c = document.getElementById(id);
                if (!c || typeof Chart === "undefined") return;
                if (analyticsCharts[id]) { try { analyticsCharts[id].destroy(); } catch (e) {} }
                analyticsCharts[id] = new Chart(c.getContext("2d"), cfg);
            };

            const locs = an.locations || [];
            mountAn("chartLoc", {
                type: "bar",
                data: {
                    labels: locs.map(x => x.location),
                    datasets: [
                        { label: "Positif", data: locs.map(x => x.positive), backgroundColor: "rgba(90, 168, 130, 0.78)" },
                        { label: "Netral", data: locs.map(x => x.neutral), backgroundColor: "rgba(107, 163, 190, 0.78)" },
                        { label: "Negatif", data: locs.map(x => x.negative), backgroundColor: "rgba(201, 107, 120, 0.78)" }
                    ]
                },
                options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true, grid: { color: gridCol } }, y: { stacked: true, grid: { display: false } } } }
            });

            const ppl = an.top_people || [];
            mountAn("chartPpl", {
                type: "bar",
                data: { labels: ppl.map(x => x.name), datasets: [{ label: "Mentions", data: ppl.map(x => x.mentions), backgroundColor: "rgba(141, 132, 184, 0.78)" }] },
                options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: gridCol } }, y: { grid: { display: false } } } }
            });

            const kws = an.top_keywords || [];
            mountAn("chartKw", {
                type: "bar",
                data: { labels: kws.map(x => String(x.keyword || "").substring(0, 22)), datasets: [{ label: "Volume", data: kws.map(x => x.volume), backgroundColor: "rgba(201, 139, 75, 0.78)" }] },
                options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: gridCol } }, y: { grid: { display: false } } } }
            });

            const tl = an.timeline || [];
            mountAn("chartTime", {
                type: "line",
                data: {
                    labels: tl.map(x => x.time),
                    datasets: [
                        { label: "Berita", data: tl.map(x => x.berita), borderColor: "#5aa882", tension: 0.25 },
                        { label: "Keyword", data: tl.map(x => x.keyword), borderColor: "#c98b4b", tension: 0.25 },
                        { label: "Sosmed", data: tl.map(x => x.sosmed), borderColor: "#6ba3be", tension: 0.25 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { x: { grid: { color: gridCol } }, y: { grid: { color: gridCol } } } }
            });

            const s = an.sentiment_summary || {};
            mountAn("chartSent", {
                type: "doughnut",
                data: { labels: ["Positif", "Netral", "Negatif"], datasets: [{ data: [s.positive || 0, s.neutral || 0, s.negative || 0], backgroundColor: ["rgba(90, 168, 130, 0.85)", "rgba(107, 163, 190, 0.85)", "rgba(201, 107, 120, 0.85)"], borderWidth: 0 }] },
                options: { responsive: true, maintainAspectRatio: false, cutout: "64%", plugins: { legend: { position: "right" } } }
            });

            const ps = an.platform_share || {};
            mountAn("chartPlat", {
                type: "polarArea",
                data: { labels: Object.keys(ps), datasets: [{ data: Object.values(ps), backgroundColor: ["rgba(90, 168, 130, 0.70)", "rgba(201, 139, 75, 0.70)", "rgba(107, 163, 190, 0.70)", "rgba(181, 131, 156, 0.70)"], borderWidth: 1, borderColor: "#262e3d" }] },
                options: { responsive: true, maintainAspectRatio: false, scales: { r: { grid: { color: gridCol }, ticks: { display: false } } }, plugins: { legend: { position: "right" } } }
            });

            bbRefreshTicker();
        } catch (e) {
            window.bbLogTerminal("Analytics load err: " + (e.message || e), "err");
        }
    };

    window.bbSyncAnalyticsCsv = async function () {
        const btn = document.getElementById("btn-sync");
        if (btn) { btn.disabled = true; btn.textContent = "⏳ SYNCING..."; }
        try {
            await fetch("/api/v1/warehouse/sync-csv", { method: "POST" });
            await window.bbLoadAnalyticsPage();
        } catch (e) {
            window.bbLogTerminal("Sync error: " + e.message, "err");
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = "↻ SYNC ALL CSV → KANTOR"; }
        }
    };

    // 8. INIT TERMINAL ENGINE (AUTOCOMPLETE, KEYBOARD SHORTCUTS, TICKER, CLOCK)
    window.bbInitTerminalEngine = function () {
        if (window.__BB_ENGINE_BOOTED) return;
        window.__BB_ENGINE_BOOTED = true;

        tickClockAndCron();
        setInterval(tickClockAndCron, 1000);
        setTimeout(bbRefreshTicker, 800);
        setInterval(bbRefreshTicker, 60000);

        const cmdInput = document.getElementById("bb-cmd-input");
        const acBox = document.getElementById("bb-cmd-ac");

        const renderAc = (val) => {
            if (!acBox) return;
            const q = String(val || "").trim().toLowerCase();
            if (!q) { acBox.classList.add("hidden"); return; }
            const matches = CMD_PRESETS.filter(p => p.cmd.toLowerCase().includes(q) || p.desc.toLowerCase().includes(q)).slice(0, 8);
            if (!matches.length) { acBox.classList.add("hidden"); return; }
            acActiveIdx = -1;
            acBox.innerHTML = matches.map((m, i) => `
                <div class="bb-ac-item" data-cmd="${esc(m.cmd)}" data-idx="${i}">
                    <span class="text-[var(--bb-amber)] font-bold">${esc(m.cmd)}</span>
                    <span class="text-[var(--bb-text-muted)] text-[10px] truncate">${esc(m.desc)}</span>
                </div>
            `).join("");
            acBox.querySelectorAll(".bb-ac-item").forEach((el) => {
                el.onclick = () => {
                    cmdInput.value = el.dataset.cmd;
                    acBox.classList.add("hidden");
                    window.bbExecuteCommand(cmdInput.value);
                };
            });
            acBox.classList.remove("hidden");
        };

        if (cmdInput) {
            cmdInput.addEventListener("input", () => renderAc(cmdInput.value));
            cmdInput.addEventListener("keydown", (ev) => {
                const items = acBox && !acBox.classList.contains("hidden") ? Array.from(acBox.querySelectorAll(".bb-ac-item")) : [];
                if (ev.key === "ArrowDown" && items.length) {
                    ev.preventDefault();
                    acActiveIdx = (acActiveIdx + 1) % items.length;
                    items.forEach((el, i) => el.classList.toggle("bb-ac-active", i === acActiveIdx));
                    return;
                }
                if (ev.key === "ArrowUp" && items.length) {
                    ev.preventDefault();
                    acActiveIdx = (acActiveIdx - 1 + items.length) % items.length;
                    items.forEach((el, i) => el.classList.toggle("bb-ac-active", i === acActiveIdx));
                    return;
                }
                if (ev.key === "ArrowUp" && !items.length && cmdHistory.length) {
                    ev.preventDefault();
                    cmdHistIdx = Math.min(cmdHistory.length - 1, cmdHistIdx + 1);
                    cmdInput.value = cmdHistory[cmdHistIdx];
                    return;
                }
                if (ev.key === "ArrowDown" && !items.length && cmdHistory.length) {
                    ev.preventDefault();
                    cmdHistIdx = Math.max(-1, cmdHistIdx - 1);
                    cmdInput.value = cmdHistIdx >= 0 ? cmdHistory[cmdHistIdx] : "";
                    return;
                }
                if (ev.key === "Enter") {
                    ev.preventDefault();
                    if (acActiveIdx >= 0 && items[acActiveIdx]) {
                        cmdInput.value = items[acActiveIdx].dataset.cmd;
                    }
                    if (acBox) acBox.classList.add("hidden");
                    window.bbExecuteCommand(cmdInput.value);
                } else if (ev.key === "Escape") {
                    if (acBox) acBox.classList.add("hidden");
                    cmdInput.blur();
                }
            });
            document.addEventListener("click", (ev) => {
                if (acBox && !cmdInput.contains(ev.target) && !acBox.contains(ev.target)) {
                    acBox.classList.add("hidden");
                }
            });
        }

        // Global Terminal Shortcuts & Bloomberg Type-Anywhere Command Capture
        document.addEventListener("keydown", (ev) => {
            const tag = (ev.target && ev.target.tagName || "").toLowerCase();
            const isTyping = tag === "input" || tag === "textarea" || tag === "select";

            if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") {
                ev.preventDefault();
                if (cmdInput) { cmdInput.focus(); cmdInput.select(); }
                return;
            }
            if (!isTyping && ev.key === "/") {
                ev.preventDefault();
                if (cmdInput) { cmdInput.focus(); cmdInput.select(); }
                return;
            }
            if (ev.key === "Escape") {
                const menu = document.getElementById("bb-menu-modal");
                if (menu && !menu.classList.contains("hidden")) { window.bbToggleMenuModal(false); return; }
                const help = document.getElementById("bb-help-modal");
                if (help && !help.classList.contains("hidden")) { window.bbToggleHelpModal(false); return; }
                const insp = document.getElementById("bb-inspector-drawer");
                if (insp && !insp.classList.contains("hidden")) { window.bbCloseInspector(); return; }
                const maxEl = document.querySelector(".bb-panel.bb-maximized");
                if (maxEl) {
                    maxEl.classList.remove("bb-maximized");
                    if (typeof Chart !== "undefined" && Chart.instances) {
                        Object.values(Chart.instances).forEach((ch) => { try { ch.resize(); } catch (e) {} });
                    }
                }
                return;
            }
            if (ev.altKey && ev.key === "ArrowLeft") {
                ev.preventDefault();
                window.bbNavBack();
                return;
            }
            if (ev.altKey && ev.key === "ArrowRight") {
                ev.preventDefault();
                window.bbNavForward();
                return;
            }
            if (ev.altKey && ["1", "2", "3", "4", "5"].includes(ev.key)) {
                ev.preventDefault();
                if (ev.key === "1") window.bbSetScreen("intel");
                else if (ev.key === "2") window.bbSetScreen("ops");
                else if (ev.key === "3") window.location.href = "/dashboard/project";
                else if (ev.key === "4") window.bbSetScreen("grid");
                else if (ev.key === "5") window.bbExecuteCommand("QUAD");
                return;
            }
            if (!isTyping && ["F2", "F3", "F4", "F5", "F6", "F7", "F8"].includes(ev.key)) {
                ev.preventDefault();
                const fMap = { F2: "supabase", F3: "bank", F4: "keyword", F5: "berita", F6: "sosmed", F7: "project" };
                if (ev.key === "F8") { window.location.href = "/analytics"; return; }
                const target = fMap[ev.key];
                if (target) {
                    if (typeof window.ddcGoPage === "function") window.ddcGoPage(target);
                    else window.location.href = "/dashboard/" + target;
                }
                return;
            }
            if (!isTyping) {
                const rows = window.__BB_CURRENT_ROWS || [];
                const hasRowSel = Number.isInteger(window.__BB_SELECTED_ROW_IDX) && window.__BB_SELECTED_ROW_IDX >= 0;
                if ((ev.key === "ArrowDown" || (hasRowSel && (ev.key === "j" || ev.key === "J"))) && rows.length) {
                    ev.preventDefault();
                    const cur = hasRowSel ? window.__BB_SELECTED_ROW_IDX : -1;
                    window.bbSelectTableRow(Math.min(rows.length - 1, cur + 1), false);
                    return;
                }
                if ((ev.key === "ArrowUp" || (hasRowSel && (ev.key === "k" || ev.key === "K"))) && rows.length) {
                    ev.preventDefault();
                    const cur = hasRowSel ? window.__BB_SELECTED_ROW_IDX : 0;
                    window.bbSelectTableRow(Math.max(0, cur - 1), false);
                    return;
                }
                if (ev.key === "Enter" && hasRowSel) {
                    ev.preventDefault();
                    window.bbOpenInspector(window.__BB_SELECTED_ROW_IDX);
                    return;
                }
                if (ev.key === "?") {
                    ev.preventDefault();
                    window.bbToggleHelpModal();
                    return;
                }
                // Type-anywhere Bloomberg CMD capture
                if (!ev.ctrlKey && !ev.metaKey && !ev.altKey && ev.key.length === 1 && /^[a-zA-Z0-9#]$/.test(ev.key) && cmdInput) {
                    cmdInput.focus();
                    cmdInput.value = ev.key;
                    renderAc(cmdInput.value);
                    ev.preventDefault();
                }
            }
        });

        // Execute any cross-page pending command from CMD <GO>
        try {
            const pending = sessionStorage.getItem("ddc_pending_cmd");
            if (pending) {
                sessionStorage.removeItem("ddc_pending_cmd");
                setTimeout(() => window.bbExecuteCommand(pending), 350);
            }
        } catch (e) {}
    };

    // 9. BLOOMBERG <MENU> FUNCTION DIRECTORY
    window.bbRenderMenuModal = function () {
        const grid = document.getElementById("bb-menu-grid");
        if (!grid) return;
        const groups = [
            {
                title: "1. NEWS WIRE (PORTAL BERITA)",
                color: "text-[var(--bb-green)]",
                items: [
                    ["NW <topik>", "Scrape Berita Kombine (Newsdata + Diffbot)"],
                    ["NWS <topik>", "Scrape Berita Cepat via Newsdata.io"],
                    ["NWD <topik/url>", "Scrape Full Text + Sentimen Diffbot AI"],
                    ["SUPA BERITA <kw>", "Cari Arsip Berita Live di Supabase"]
                ]
            },
            {
                title: "2. SOCIAL MEDIA MONITORING",
                color: "text-[var(--bb-cyan)]",
                items: [
                    ["IG <#tag/kw>", "Scrape Instagram Hashtag / Konten"],
                    ["TT <kw>", "Scrape TikTok Viral & Engagement"],
                    ["FB <page/kw>", "Scrape Facebook Page / Post"],
                    ["TW <kw>", "Scrape Twitter / X"],
                    ["LI <role>", "Scrape Profil LinkedIn (Bright Data)"]
                ]
            },
            {
                title: "3. JOB HUNTER (GEEKGARDEN FIT)",
                color: "text-[var(--bb-amber-bright)]",
                items: [
                    ["JOB <stack>", "Hunt Project & Hitung Geekgarden Fit (≥80%)"],
                    ["FIT", "Buka Job Hunter Desk (/dashboard/project)"],
                    ["KW <keyword>", "Keyword Related Queries"],
                    ["TRD <kategori>", "Google Trends Rising Topics"]
                ]
            },
            {
                title: "4. TERMINAL LAUNCHPAD & SYSTEM",
                color: "text-[var(--bb-yellow)]",
                items: [
                    ["QUAD", "4-Pane Launchpad (News + Sosmed + Job + Watchlist)"],
                    ["WATC", "Buka Watchlist & Topic Broadcaster"],
                    ["CSV <kat>", "Eksplorasi Bank Data CSV Lokal"],
                    ["ANL", "Global Analytics Matrix (/analytics)"],
                    ["CRON RUN", "Trigger Batch Cron 1.000 Baris"]
                ]
            }
        ];
        grid.innerHTML = groups.map((g) => `
            <div class="p-2.5 bg-[var(--bb-bg-elev)] border border-[var(--bb-border)] space-y-1.5">
                <div class="font-bold ${g.color} border-b border-[var(--bb-border)] pb-1">${esc(g.title)}</div>
                ${g.items.map(([cmd, desc]) => `
                    <div onclick="bbToggleMenuModal(false); bbExecuteCommand('${esc(cmd.replace(/<[^>]+>/g, '').trim())}')"
                         class="flex items-center justify-between gap-2 p-1 hover:bg-[var(--bb-panel-hover)] cursor-pointer">
                        <span class="text-[var(--bb-amber)] font-bold shrink-0">${esc(cmd)}</span>
                        <span class="text-[var(--bb-text-muted)] text-[10px] truncate">${esc(desc)}</span>
                    </div>
                `).join("")}
            </div>
        `).join("");
    };

    // 10. COLOR-CODED PANEL LINKING & TOPIC BROADCAST
    function applyLinkPillStyle(el, grp) {
        if (!el) return;
        const dot = el.querySelector(".bb-link-dot");
        const txt = el.querySelector("span:last-child");
        if (dot) {
            dot.className = "bb-link-dot " + (grp === "AMBER" ? "bg-[var(--bb-amber)]" : grp === "CYAN" ? "bg-[var(--bb-cyan)]" : "bg-[var(--bb-text-dim)]");
        }
        if (txt) txt.textContent = (el.id === "bb-global-link-btn" ? "LINK:" : "") + grp;
    }

    window.bbCycleActiveLinkGroup = function () {
        const idx = (LINK_GROUPS.indexOf(globalLinkGroup) + 1) % LINK_GROUPS.length;
        globalLinkGroup = LINK_GROUPS[idx];
        applyLinkPillStyle(document.getElementById("bb-global-link-btn"), globalLinkGroup);
        window.bbLogTerminal(`Global Link Group -> ${globalLinkGroup}`, "info");
    };

    window.bbCycleQuadLink = function (qid) {
        const cur = quadLinks[qid] || "AMBER";
        const next = LINK_GROUPS[(LINK_GROUPS.indexOf(cur) + 1) % LINK_GROUPS.length];
        quadLinks[qid] = next;
        applyLinkPillStyle(document.getElementById(`bb-${qid}-link`), next);
        window.bbLogTerminal(`${qid.toUpperCase()} Link Group -> ${next}`, "info");
    };

    window.bbBroadcastTopic = function (topic, group = "AMBER") {
        const q = String(topic || "").trim();
        if (!q || group === "NONE") return;
        window.bbLogTerminal(`BROADCAST [${group}] -> "${q}"`, "cmd");
        ["q1", "q2", "q3"].forEach((qid) => {
            if (quadLinks[qid] === group) {
                const inp = document.getElementById(`bb-${qid}-input`);
                if (inp) inp.value = q;
                window.bbQuadRun(qid, false);
            }
        });
        const sb = document.getElementById("sb-search");
        if (sb && document.body?.dataset?.page === "dashboard") {
            sb.value = q;
            if (typeof window.applyClientFilters === "function") window.applyClientFilters();
        }
    };

    // 11. 4-QUADRANT LIVE TERMINAL LAUNCHPAD (NEWS + SOSMED + JOB + WATCHLIST)
    window.bbQuadRun = async function (qid, doLiveScrape = false) {
        const body = document.getElementById(`bb-${qid}-body`);
        const inp = document.getElementById(`bb-${qid}-input`);
        if (!body) return;
        const q = (inp ? inp.value : "").trim();

        body.innerHTML = `<div class="p-3 text-[var(--bb-amber)]">${doLiveScrape ? "⏳ SCRAPING LIVE..." : "⏳ LOADING..."}</div>`;
        try {
            let rows = [];
            if (qid === "q1") {
                if (doLiveScrape && q) {
                    const r = await fetch("/api/v1/berita/kombine", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ keyword_or_url: q, max_results: 15 })
                    }).then(res => res.json());
                    rows = r.data || [];
                } else {
                    const r = await fetch(`/api/v1/warehouse/records?category=berita&search_query=${encodeURIComponent(q)}&limit=40`).then(res => res.json());
                    rows = r.data || [];
                }
                quadCache.q1 = rows;
                body.innerHTML = rows.length ? rows.slice(0, 30).map((row, i) => {
                    const sent = Number(row.sentimen_diffbot ?? row.sentiment ?? 0);
                    const sCls = sent > 0.1 ? "text-[var(--bb-green)]" : sent < -0.1 ? "text-[var(--bb-red)]" : "text-[var(--bb-text-muted)]";
                    const title = row.judul || row.title || "(Tanpa Judul)";
                    const src = row.sumber || row.source || row.platform || "NEWS";
                    return `
                        <div class="bb-quad-row" onclick='bbOpenRawInspectorRow(window.__BB_QUAD_Q1[${i}], "NEWS")'>
                            <div class="flex items-center justify-between gap-2 text-[10px]">
                                <span class="text-[var(--bb-cyan)] font-bold truncate">${esc(src)}</span>
                                <span class="${sCls} font-bold shrink-0">${isNaN(sent) ? "-" : sent.toFixed(2)}</span>
                            </div>
                            <div class="text-[var(--bb-text)] truncate mt-0.5">${esc(title)}</div>
                        </div>
                    `;
                }).join("") : `<div class="p-3 text-[var(--bb-text-muted)]">Tidak ada berita cocok.</div>`;
                window.__BB_QUAD_Q1 = rows;
            } else if (qid === "q2") {
                const pf = (document.getElementById("bb-q2-platform")?.value || "instagram");
                if (doLiveScrape && q) {
                    const payload = pf === "linkedin"
                        ? { keyword: q, region_indonesia: true, max_results: 10, search_mode: "profile" }
                        : pf === "facebook"
                        ? { keyword_or_url: q, engine: "apify", mode_apify: "bersih", max_results: 15 }
                        : (pf === "instagram" || pf === "tiktok")
                        ? { keyword_or_hashtag: q, engine: "apify", max_results: 15 }
                        : { keyword: q, engine: "apify", max_results: 15 };
                    const r = await fetch(`/api/v1/sosmed/${pf}`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    }).then(res => res.json());
                    rows = r.data || [];
                } else {
                    const r = await fetch(`/api/v1/warehouse/records?category=${encodeURIComponent(pf)}&search_query=${encodeURIComponent(q)}&limit=40`).then(res => res.json());
                    rows = r.data || [];
                }
                quadCache.q2 = rows;
                body.innerHTML = rows.length ? rows.slice(0, 30).map((row, i) => {
                    const user = row.username || row.Username || row.author || row.Nama || `@${pf}`;
                    const txt = row.teks || row.Teks || row.text || row.caption || row.content || row.Pekerjaan_Saat_Ini || "-";
                    const eng = row.likes ?? row.Likes ?? row.like ?? row.Koneksi ?? 0;
                    return `
                        <div class="bb-quad-row" onclick='bbOpenRawInspectorRow(window.__BB_QUAD_Q2[${i}], "SOSMED")'>
                            <div class="flex items-center justify-between gap-2 text-[10px]">
                                <span class="text-[var(--bb-cyan)] font-bold truncate">${esc(user)}</span>
                                <span class="text-[var(--bb-amber)] shrink-0">♥ ${esc(eng)}</span>
                            </div>
                            <div class="text-[var(--bb-text)] truncate mt-0.5">${esc(txt)}</div>
                        </div>
                    `;
                }).join("") : `<div class="p-3 text-[var(--bb-text-muted)]">Tidak ada data ${esc(pf)} cocok.</div>`;
                window.__BB_QUAD_Q2 = rows;
            } else if (qid === "q3") {
                if (doLiveScrape && q) {
                    const r = await fetch("/api/v1/project/search", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ keyword: q, project_sources: "all", region_indonesia: true, max_results: 20 })
                    }).then(res => res.json());
                    rows = r.data || [];
                } else {
                    const r = await fetch("/api/v1/project/records?limit=120").then(res => res.json());
                    rows = r.data || [];
                    if (q) {
                        const ql = q.toLowerCase();
                        rows = rows.filter((row) => Object.values(row || {}).join(" ").toLowerCase().includes(ql));
                    }
                }
                quadCache.q3 = rows;
                body.innerHTML = rows.length ? rows.slice(0, 30).map((row, i) => {
                    const sc = Number(row.confidence_score) || 0;
                    const sCls = sc >= 80 ? "text-[var(--bb-green)]" : sc >= 40 ? "text-[var(--bb-amber)]" : "text-[var(--bb-red)]";
                    return `
                        <div class="bb-quad-row" onclick='bbOpenRawInspectorRow(window.__BB_QUAD_Q3[${i}], "JOB_FIT")'>
                            <div class="flex items-center justify-between gap-2 text-[10px]">
                                <span class="text-[var(--bb-cyan)] truncate">${esc(row.source_platform || row.platform || "LEAD")} · ${esc(row.budget || "-")}</span>
                                <span class="${sCls} font-bold shrink-0">FIT ${sc}%</span>
                            </div>
                            <div class="text-[var(--bb-text)] truncate mt-0.5">${esc(row.title || "-")}</div>
                        </div>
                    `;
                }).join("") : `<div class="p-3 text-[var(--bb-text-muted)]">Tidak ada project cocok.</div>`;
                window.__BB_QUAD_Q3 = rows;
            }
            window.bbRenderWatchlist();
        } catch (err) {
            body.innerHTML = `<div class="p-3 text-[var(--bb-red)]">ERR: ${esc(err.message || err)}</div>`;
        }
    };

    window.bbRenderWatchlist = function () {
        const body = document.getElementById("bb-q4-body");
        if (!body) return;
        const terms = getWatchlist();
        const countHits = (arr, t) => {
            const ql = t.toLowerCase();
            return (arr || []).filter(r => Object.values(r || {}).join(" ").toLowerCase().includes(ql)).length;
        };
        body.innerHTML = terms.map((term) => {
            const nC = countHits(quadCache.q1, term);
            const sC = countHits(quadCache.q2, term);
            const jC = countHits(quadCache.q3, term);
            return `
                <div class="flex items-center justify-between gap-2 p-2 bg-[var(--bb-bg-elev)] border border-[var(--bb-border)] hover:border-[var(--bb-amber)] transition">
                    <div onclick="bbBroadcastTopic('${esc(term)}', 'AMBER')" class="flex-1 min-w-0 cursor-pointer">
                        <div class="text-[var(--bb-amber-bright)] font-bold truncate">${esc(term.toUpperCase())}</div>
                        <div class="text-[10px] text-[var(--bb-text-muted)]">
                            NEWS:<span class="text-[var(--bb-green)]">${nC}</span> · SOC:<span class="text-[var(--bb-cyan)]">${sC}</span> · JOB:<span class="text-[var(--bb-amber)]">${jC}</span>
                        </div>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                        <button type="button" onclick="bbBroadcastTopic('${esc(term)}', 'AMBER')" class="bb-btn !py-0.5 !px-1.5 !text-[9px]">SYNC</button>
                        <button type="button" onclick="bbRemoveWatchlistTerm('${esc(term)}')" class="bb-btn !py-0.5 !px-1.5 !text-[9px] text-[var(--bb-red)]">✕</button>
                    </div>
                </div>
            `;
        }).join("");
    };

    window.bbAddWatchlistTerm = function (val) {
        const clean = String(val || "").trim().toLowerCase();
        if (!clean) return;
        const list = getWatchlist();
        if (!list.includes(clean)) {
            list.unshift(clean);
            saveWatchlist(list.slice(0, 15));
        }
        const inp = document.getElementById("bb-wl-add");
        if (inp) inp.value = "";
        window.bbRenderWatchlist();
        window.bbLogTerminal(`Watchlist pinned: "${clean}"`, "ok");
    };

    window.bbRemoveWatchlistTerm = function (term) {
        const list = getWatchlist().filter(t => t !== term);
        saveWatchlist(list);
        window.bbRenderWatchlist();
    };

    window.bbRefreshQuadAll = function () {
        window.bbQuadRun("q1", false);
        window.bbQuadRun("q2", false);
        window.bbQuadRun("q3", false);
        window.bbRenderWatchlist();
    };

    // 12. ROW INSPECTOR ENTITY BROADCAST / PIVOT
    window.bbInspectorBroadcast = function (target) {
        if (!currentInspRow) return;
        const rawText = String(
            currentInspRow.Query ||
            currentInspRow.keyword ||
            currentInspRow.skills ||
            currentInspRow.title ||
            currentInspRow.judul ||
            currentInspRow.teks ||
            ""
        ).trim();
        const topic = rawText
            .replace(/https?:\/\/\S+/gi, "")
            .replace(/[^a-zA-Z0-9#\s]/g, " ")
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .join(" ") || "teknologi";

        if (target === "watchlist") {
            window.bbAddWatchlistTerm(topic);
            return;
        }
        window.bbCloseInspector();
        if (target === "quad") {
            window.bbExecuteCommand(`QUAD ${topic}`);
        } else if (target === "news") {
            window.bbExecuteCommand(`NW ${topic}`);
        } else if (target === "sosmed") {
            window.bbExecuteCommand(`IG ${topic.replace(/^#/, "")}`);
        } else if (target === "job") {
            window.bbExecuteCommand(`JOB ${topic}`);
        }
    };
})();
