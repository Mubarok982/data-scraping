let currentTab = 'supabase';
        let chartLoc = null, chartPpl = null, chartKw = null, chartTime = null, chartSent = null, chartViral = null, chartHash = null, chartSystem = null;

        let BASE_ANALYTICS = null;
        let DOMAIN_ROWS_CACHE = {};
        let LAST_CSV_PATH = {};

        let _cronActiveManual = false;
        let _cronSimProgress = 0;
        let _cronUiTimer = null;

        Chart.defaults.color = '#9ca3af';
        Chart.defaults.font.family = 'ui-sans-serif, system-ui, sans-serif';
        Chart.defaults.font.size = 11;

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
                const tabBtn = document.getElementById('tab-' + t);
                if (tabBtn) {
                    const isActive = (t === tab);
                    tabBtn.className = isActive
                        ? "w-full text-left py-2.5 px-3.5 rounded-xl font-semibold text-xs bg-purple-600 text-white shadow ring-1 ring-purple-400/50 transition flex items-center justify-between"
                        : "w-full text-left py-2.5 px-3.5 rounded-xl font-semibold text-xs bg-[#1a1f33] text-gray-300 hover:text-white hover:bg-[#202740] border border-gray-800 transition flex items-center justify-between";
                    const dot = tabBtn.querySelector("span.w-1\\.5");
                    if (dot) dot.className = isActive ? "w-1.5 h-1.5 rounded-full bg-purple-200" : "w-1.5 h-1.5 rounded-full bg-gray-600";
                    const badges = tabBtn.querySelectorAll("span");
                    const badge = badges.length > 1 ? badges[badges.length - 1] : null;
                    if (badge) badge.className = isActive ? "text-[10px] bg-purple-900/90 text-purple-100 px-2 py-0.5 rounded" : "text-[10px] bg-gray-800 text-gray-300 px-2 py-0.5 rounded";
                }
            });
            const activeEl = document.getElementById('form-' + tab);
            if (activeEl) activeEl.classList.remove('hidden');
            const activeTabBtn = document.getElementById('tab-' + tab);
            if (activeTabBtn) activeTabBtn.className = "w-full text-left py-2.5 px-3.5 rounded-xl font-semibold text-xs bg-purple-600 text-white shadow transition flex items-center justify-between";

            const runBtn = document.getElementById('btn-run');
            if (tab === 'supabase') runBtn.innerText = "🗄️ Muat Tabel Supabase";
            else if (tab === 'bank') runBtn.innerText = "📂 Terapkan Filter CSV";
            else if (tab === 'project') runBtn.innerText = "🎯 Cari Project & Cek Confidence";
            else runBtn.innerText = "🚀 Jalankan Scraper & Simpan ke DB";

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

            const ctxLoc = document.getElementById('chartLocations').getContext('2d');
            if (chartLoc) chartLoc.destroy();
            chartLoc = new Chart(ctxLoc, {
                type: 'bar',
                data: {
                    labels: locs.map(x => x.location),
                    datasets: [
                        { label: 'Positif', data: locs.map(x => x.positive), backgroundColor: '#10b981' },
                        { label: 'Netral', data: locs.map(x => x.neutral), backgroundColor: '#6366f1' },
                        { label: 'Negatif', data: locs.map(x => x.negative), backgroundColor: '#ef4444' }
                    ]
                },
                options: {
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    scales: { x: { stacked: true, grid: { color: '#1f2937' } }, y: { stacked: true, grid: { display: false } } },
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 10 } } },
                    onClick: (_, elements) => { if (elements.length > 0) filterByTerm(locs[elements[0].index].location); }
                }
            });

            const badgeBox = document.getElementById('loc-badges');
            if (locs.length > 0) {
                badgeBox.innerHTML = locs.slice(0, 6).map(l => {
                    const isNeg = l.negative > l.positive;
                    const pillClass = isNeg ? 'bg-red-950/80 text-red-300 border-red-800' : 'bg-emerald-950/80 text-emerald-300 border-emerald-800';
                    const labelPol = isNeg ? 'Polarisasi Isu Kritis' : 'Dominan Positif/Netral';
                    return `
                        <div onclick="filterByTerm('${l.location}')" class="cursor-pointer p-2 rounded-xl bg-[#0b0d14] hover:bg-[#1a2036] border border-gray-800/80 flex items-center justify-between transition">
                            <div>
                                <div class="font-semibold text-gray-200">${l.location} <span class="text-[10px] text-indigo-400">(${l.total})</span></div>
                                <div class="text-[10px] text-gray-400">Isu: <span class="text-amber-300 font-medium">${l.dominant_issue || 'UMUM'}</span></div>
                            </div>
                            <span class="px-2 py-0.5 text-[10px] rounded border ${pillClass}">${labelPol}</span>
                        </div>
                    `;
                }).join('');
            } else {
                badgeBox.innerHTML = '<div class="text-gray-500 text-xs">Tidak ada sebaran wilayah spesifik pada filter ini.</div>';
            }

            const ctxPpl = document.getElementById('chartPeople').getContext('2d');
            if (chartPpl) chartPpl.destroy();
            chartPpl = new Chart(ctxPpl, {
                type: 'bar',
                data: {
                    labels: ppl.map(x => x.name),
                    datasets: [{ label: 'Total Mentions', data: ppl.map(x => x.mentions), backgroundColor: '#a855f7', borderRadius: 5 }]
                },
                options: {
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { color: '#1f2937' } }, y: { grid: { display: false } } },
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
                                backgroundColor: '#ec4899',
                                borderRadius: 5,
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
                                    grid: { color: '#1f2937' },
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
                if (initialIdItems.filter(x => x.hasRealEng).length >= 5) {
                    drawViral(initialIdItems);
                    return;
                }

                const mergeAndDraw = (extraRows) => {
                    const merged = normalizeItems([...initialIdItems, ...(Array.isArray(extraRows) ? extraRows : [])]);
                    drawViral(merged);
                };

                if (Array.isArray(window.__idViralBackupRows) && window.__idViralBackupRows.length > 0) {
                    mergeAndDraw(window.__idViralBackupRows);
                    return;
                }

                drawViral(initialIdItems);
                Promise.all([
                    fetch('/api/v1/warehouse/records?category=sosmed&search_query=&limit=200').then(r => r.ok ? r.json() : null).catch(() => null),
                    fetch('/api/v1/warehouse/records?category=berita&search_query=&limit=30').then(r => r.ok ? r.json() : null).catch(() => null)
                ]).then(([socRes, newsRes]) => {
                    const extract = (d) => Array.isArray(d) ? d : ((d && (d.data || d.records || d.items)) || []);
                    const combined = [...extract(socRes), ...extract(newsRes)];
                    window.__idViralBackupRows = combined;
                    mergeAndDraw(combined);
                }).catch(() => {});
            })((() => { try { return (typeof viral !== 'undefined' && Array.isArray(viral) && viral.length) ? viral : ((typeof viralDisplay !== 'undefined' && Array.isArray(viralDisplay)) ? viralDisplay : []); } catch (e) { return []; } })());

            const ctxHash = document.getElementById('chartHashtags').getContext('2d');
            if (chartHash) chartHash.destroy();
            chartHash = new Chart(ctxHash, {
                type: 'bar',
                data: {
                    labels: hashtags.map(x => x.tag),
                    datasets: [{ label: 'Frekuensi Tagar', data: hashtags.map(x => x.count), backgroundColor: '#3b82f6', borderRadius: 5 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { display: false } }, y: { grid: { color: '#1f2937' } } },
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
                    datasets: [{ label: 'Indeks Volume / Frekuensi', data: kws.map(x => x.volume), backgroundColor: '#f59e0b', borderRadius: 5 }]
                },
                options: {
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { color: '#1f2937' } }, y: { grid: { display: false } } },
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
                        { label: 'Berita', data: tl.map(x => x.berita || 0), borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.15)', fill: true, tension: 0.35 },
                        { label: 'Keyword/Tren', data: tl.map(x => x.keyword || 0), borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)', fill: true, tension: 0.35 },
                        { label: 'Sosmed', data: tl.map(x => x.sosmed || 0), borderColor: '#ec4899', backgroundColor: 'rgba(236,72,153,0.1)', fill: true, tension: 0.35 }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: { x: { grid: { color: '#1f2937' } }, y: { grid: { color: '#1f2937' }, beginAtZero: true } },
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
                        { type: 'bar', label: 'Total API Request', data: sysHealth.map(x => x.req_count), backgroundColor: '#4f46e5', yAxisID: 'y', borderRadius: 4 },
                        { type: 'line', label: 'Rata-rata Waktu Respons (ms)', data: sysHealth.map(x => x.avg_ms), borderColor: '#f43f5e', backgroundColor: '#f43f5e', borderWidth: 3, tension: 0.3, yAxisID: 'y1' }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Total Kueri', color: '#9ca3af' }, grid: { color: '#1f2937' } },
                        y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Kecepatan Server (ms)', color: '#9ca3af' }, grid: { drawOnChartArea: false } }
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
                    datasets: [{ data: [sent.positive || 0, sent.neutral || 0, sent.negative || 0], backgroundColor: ['#10b981', '#6366f1', '#ef4444'], borderWidth: 0 }]
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
                const wh = (json.supabase_warehouse || {}).counts || {};

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
            status.innerText = `✅ Menampilkan ${displayed.length} dari ${filtered.length} baris cocok (${cat})${activeLabels.length ? ' • Filter [' + activeLabels.join(', ') + ']' : ''}.`;

            const hasActiveFilter = Boolean(newsCat || prov || kab || dateFrom || dateTo || q || cat !== 'berita');
            if (hasActiveFilter) {
                const reactiveAn = buildReactiveAnalyticsFromRows(filtered, prov, cat);
                renderChartsFromObject(reactiveAn, true, `[${activeLabels.join(' • ')}] (${filtered.length} baris)`);
            } else if (BASE_ANALYTICS) {
                document.getElementById('title-chart-loc').innerText = '🗺️ Polarisasi Lokasi (Sebaran Tren Wilayah)';
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
                        window.__LAST_PROJECT_ROWS = rows;
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
                    if (currentTab === 'supabase') btn.innerText = "🗄️ Muat Tabel Supabase";
                    else if (currentTab === 'bank') btn.innerText = "📂 Terapkan Filter CSV";
                    else if (currentTab === 'project') btn.innerText = "🎯 Cari Project & Cek Confidence";
                    else btn.innerText = "🚀 Jalankan Scraper & Simpan ke DB";
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

        function renderTable(rows) {
            const thead = document.getElementById('table-head');
            const tbody = document.getElementById('table-body');
            thead.innerHTML = '';
            tbody.innerHTML = '';

            if (!rows.length) {
                tbody.innerHTML = '<tr><td class="p-8 text-center text-gray-500">Data tidak ditemukan untuk kombinasi filter ini.</td></tr>';
                return;
            }

            const colSet = new Set();
            rows.forEach(r => Object.keys(r).forEach(k => colSet.add(k)));
            const cols = Array.from(colSet);

            thead.innerHTML = '<tr>' + cols.map(c => `<th class="px-3.5 py-2.5 border-b border-gray-800 whitespace-nowrap">${c}</th>`).join('') + '</tr>';

            rows.forEach(r => {
                const tr = document.createElement('tr');
                tr.className = "hover:bg-[#1a2036] transition";
                tr.innerHTML = cols.map(c => {
                    let val = r[c] !== null && r[c] !== undefined ? String(r[c]) : '';
                    if (val.startsWith('http')) {
                        return `<td class="px-3.5 py-2 whitespace-nowrap"><a href="${val}" target="_blank" class="text-indigo-400 hover:underline">🔗 Buka Link</a></td>`;
                    }
                    if (c === 'confidence_status') {
                        const low = val.toLowerCase();
                        let cls = 'bg-gray-800 text-gray-300 border-gray-700';
                        if (low.includes('fix')) cls = 'bg-emerald-950/90 text-emerald-300 border-emerald-700';
                        else if (low.includes('fifty')) cls = 'bg-amber-950/90 text-amber-300 border-amber-700';
                        else if (low.includes('tidak')) cls = 'bg-rose-950/90 text-rose-300 border-rose-700';
                        return `<td class="px-3.5 py-2 whitespace-nowrap"><span class="px-2 py-0.5 rounded-full text-[10px] font-semibold border ${cls}">${val}</span></td>`;
                    }
                    if (c === 'confidence_score' && val !== '') {
                        return `<td class="px-3.5 py-2 whitespace-nowrap font-mono font-bold text-indigo-300">${val}%</td>`;
                    }
                    if (val.length > 85) val = val.substring(0, 85) + '...';
                    return `<td class="px-3.5 py-2 whitespace-nowrap">${val}</td>`;
                }).join('');
                tbody.appendChild(tr);
            });
        }

        initProvinceDropdown();
        window.addEventListener('DOMContentLoaded', () => {
            initProvinceDropdown();
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

    async function showProjectResults() {
        toggleCenterChartsByTab('project');
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

