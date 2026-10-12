# Rencana Implementasi — EWS TAHAP 1 (backend + frontend nyata)

Target: `c:/aws-kiro/EWS_YG2UFH/backend` — aplikasi FastAPI "EWS" (Early Warning System longsor)
yang meng-ingest JSON node dari MQTT (`yg2ufh/ews/#`), simpan ke SQLite, sajikan REST + WebSocket +
frontend nyata (dashboard peta Leaflet + detail node Chart.js), deteksi node offline, dan simulator
node. Pola meniru `c:/aws-kiro/mqtt-server` (JANGAN diubah/diimpor), TAPI parse **JSON native —
BUKAN aprslib**. Uji LOKAL tanpa hardware & tanpa broker eksternal. JANGAN commit/push.

> Catatan: workflow ini juga punya artefak FEAT di `.agents/tasks/task-ews-tahap1/` (dekomposisi
> fitur). Rencana ini adalah fallback yang setara isinya — kalau loop lama yang jalan, ikuti ini.

## Keputusan desain yang sudah FIX (dari docs + referensi)

- **Default anti-bentrok APRS** (decisions.md "CHECKLIST ANTI-BENTROK"): HTTP port `8001`,
  MQTT `client_id = ews-web-backend` (PALING KRITIS — client_id salah menendang APRS dari broker
  bersama), topic prefix `yg2ufh/ews` (subscribe `yg2ufh/ews/#`), DB `./data/ews.db`. Dibakar ke
  `app/config.py` DAN didokumentasikan di `.env.example`/`config.yaml.example`. JANGAN sentuh folder
  `mqtt-server`.
- **Precedence config** meniru mqtt-server: env var nyata > `.env` > `config.yaml` > default bawaan.
  `MQTT_BROKER_HOST` & `MQTT_TOPIC_PREFIX` satu-satunya key wajib.
- **Hierarki wilayah di DB** (technical-design §12.1): tabel `kabupaten`, `kecamatan`, `nodes`,
  `readings`, `thresholds`. `nodes` menautkan `node_id` ke kabupaten+kecamatan+koordinat. Pendaftaran
  node = manual (decisions.md), tapi reading dari MQTT tetap disimpan walau node belum terdaftar
  (surface sebagai "node tak dikenal").
- **Identitas node = field `id`** payload (decisions.md "Pencocokan data MQTT <-> node via node_id"):
  ingest meng-key semuanya pada `id`. Payload tanpa `id` string non-kosong di-drop (dilog).
- **Reading = kolom JSON generik** + kolom terindeks (`node_id, ts, received_at, kabupaten`): payload
  field-opsional (technical-design §4), nambah sensor tak mengubah skema.
- **Threshold global + override per node** (§12.2): resolusi = override node bila ada, selain itu
  default global. Dipakai backend saat evaluasi -> publish NOTIFIKASI (BUKAN memicu sirine otomatis).
- **Deteksi node offline di backend** (§6): task asyncio di lifespan membandingkan `now - last_seen`
  dengan `miss_threshold_sec` (default 180 = 3× interval 60 s); lewat ambang -> broadcast alarm
  `{type:"alarm", level:"siaga", source:node_id, reason:"node silent"}`; terdengar lagi -> online.
- **Retensi >= 12 bulan** (§12.4): task pembersihan periodik menghapus reading lebih tua dari
  `retention_days` (default 365, configurable).
- **Teruji tanpa broker**: pecah ingest jadi fungsi murni (`parse_payload`, `process_reading`,
  `on_message_impl`) seperti mqtt-server, jadi test menyuntik payload dan mengecek tersimpan +
  ter-broadcast tanpa jaringan. DUA try/except (parse vs pipeline) + `suppress_exceptions=True`.
- **Frontend nyata** dari desain mockup `docs/mockup/` (TIRU layout/gaya; JANGAN ubah mockup; JANGAN
  jadikan sumber data) tapi ambil data dari API/WS. Alarm DASHBOARD (berkedip + beep Web Audio +
  banner + bisukan) = otomatis; sirine fisik tetap manual (tidak dibuat di TAHAP 1 kecuali kontrol
  pada frontend yang mengirim perintah — di luar scope data node TAHAP 1).
- **TAHAP 2 — JANGAN dibuat sekarang**: Export PDF nyata, auth/login nyata, chat nyata, edit suara
  alarm. RBAC UI boleh ikut tapi tanpa penegakan backend.
- Python 3.11, pytest, NO aprslib. venv di `backend/.venv`. Windows PowerShell.

---

- [ ] 1. Scaffold paket backend + konfigurasi anti-bentrok.
      Buat pohon `backend/`: `app/__init__.py`, `app/routers/__init__.py`, `tools/`, `tests/`,
      `data/.gitkeep`, `app/static/`; `requirements.txt` (fastapi, uvicorn[standard], paho-mqtt,
      pyyaml, python-dotenv, pytest, httpx — TANPA aprslib); `.gitignore` (`.venv/`, `data/*.db*`,
      `__pycache__/`, `.env`, `config.yaml`). Tulis `app/config.py` sebagai `Settings` dataclass +
      `load_settings`/`get_settings`/`reset_settings_cache` meniru mqtt-server/app/config.py tapi
      default EWS: `mqtt_broker_port=1883`, `mqtt_client_id="ews-web-backend"`,
      `mqtt_topic_prefix="yg2ufh/ews"` (wajib), `db_path="./data/ews.db"`, `http_host="0.0.0.0"`,
      `http_port=8001`, `log_level="INFO"`, `history_lookback_hours=24`, `miss_threshold_sec=180`
      (min 1), `retention_days=365` (min 1); `mqtt_broker_host` wajib; `mqtt_username/password`
      opsional. Tulis `.env.example` + `config.yaml.example` dengan komentar anti-bentrok eksplisit
      (client_id/port/topic/db vs APRS).
      Files: backend/app/__init__.py, backend/app/routers/__init__.py, backend/app/config.py,
      backend/requirements.txt, backend/.gitignore, backend/.env.example, backend/config.yaml.example,
      backend/data/.gitkeep
      Verify: `python -m venv backend/.venv`; `backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`;
      lalu dari `backend/`: `.venv/Scripts/python.exe -c "import os; os.environ['MQTT_BROKER_HOST']='x'; from app.config import load_settings; s=load_settings('nope.env','nope.yaml'); assert s.mqtt_client_id=='ews-web-backend' and s.http_port==8001 and s.mqtt_topic_prefix=='yg2ufh/ews' and s.db_path=='./data/ews.db' and s.miss_threshold_sec==180; print('OK')"` — cetak OK.

- [ ] 2. Bangun lapisan penyimpanan SQLite `app/db.py` dengan skema hierarki wilayah.
      Koneksi module-level (`check_same_thread=False`) + `threading.Lock`, WAL, PRAGMA foreign_keys,
      disiplin lock meniru mqtt-server/app/db.py (BEGIN/commit/rollback per write). Skema:
      `kabupaten(id PK, nama, provinsi)`; `kecamatan(id PK, nama, kabupaten_id FK)`;
      `nodes(node_id PK, nama, tipe, kabupaten_id FK, kecamatan_id FK, lat, lon, lokasi, created_at)`;
      `readings(id PK, node_id, kabupaten, ts, received_at, lat, lon, payload_json)` index
      `(node_id, received_at, id)`; `node_status(node_id PK, first_seen_at, last_seen_at, status)`;
      `thresholds(scope PK, tilt_siaga, tilt_awas, updated_at)` (scope = `global` atau `node:<id>`),
      seed baris `global` default (tilt_siaga=2.0, tilt_awas=5.0). Fungsi: `init_db(db_path)` (buat
      skema + seed global threshold); CRUD wilayah (`add_kabupaten/list_kabupaten`,
      `add_kecamatan/list_kecamatan`); CRUD node (`upsert_node/list_nodes(filter)/get_node`);
      `store_reading(payload, received_at=None)->str` (insert reading + upsert node_status online);
      `get_latest_per_node()`, `get_history(node_id, hours)` (cutoff ISO di Python, newest-first LIMIT
      lalu reverse — SAMA seperti referensi); `set_status`, `get_stale_nodes(threshold_sec, now)`;
      `get_thresholds()/set_threshold(scope,...)/resolve_threshold(node_id)`;
      `purge_old_readings(retention_days, now)`.
      Files: backend/app/db.py
      Verify: ditutup step 8; interim dari `backend/`: `.venv/Scripts/python.exe -c "import app.db as d; d.init_db(':memory:'); d.store_reading({'id':'slm-01','kabupaten':'sleman','ts':1,'weather':{'temp':27.0}}); rows=d.get_latest_per_node(); assert rows[0]['node_id']=='slm-01'; t=d.resolve_threshold('slm-01'); assert t['tilt_siaga']==2.0 and t['tilt_awas']==5.0; print('OK')"` — cetak OK.

- [ ] 3. Bangun WebSocket connection manager `app/ws_manager.py`.
      Salin mqtt-server/app/ws_manager.py hampir verbatim: `ConnectionManager` dengan `asyncio.Lock`,
      `connect`/`disconnect`/`broadcast_json`/`broadcast_json_threadsafe`, singleton `manager`.
      Payload EWS generik (dict), tak perlu perubahan khusus.
      Files: backend/app/ws_manager.py
      Verify: dari `backend/`: `.venv/Scripts/python.exe -c "from app.ws_manager import manager; assert hasattr(manager,'broadcast_json_threadsafe'); print('OK')"` — cetak OK.

- [ ] 4. Bangun ingest JSON `app/mqtt_ingest.py` (TANPA aprslib) + evaluasi threshold.
      Fungsi murni: `parse_payload(raw)->dict|None` (json.loads, None+log+`parse_failures_counter`
      saat error, tak pernah raise); `evaluate_alarm(payload)` baca `tilt.delta`/`tilt.x`, bandingkan
      dengan `db.resolve_threshold(id)` -> None | `{level:"siaga|awas", reason}`;
      `process_reading(payload, broadcast_fn, received_at=None)` — validasi `id` string non-kosong
      (else log+return), `db.store_reading`, bangun WS payload `{type:"reading", node_id, kabupaten,
      ts, received_at, payload:<dict penuh>, alarm:<evaluate_alarm hasil>}`, panggil `broadcast_fn`
      sekali; bila alarm != None broadcast juga `{type:"alarm", level, source:id, reason, ts}`;
      `on_message_impl(topic, payload_bytes, broadcast_fn)` dua try/except (parse vs pipeline);
      `build_client(settings, main_loop)` meniru mqtt-server: `suppress_exceptions=True`, opsional
      `username_pw_set`, `on_connect` subscribe `<prefix>/#` qos=1, `on_disconnect` WARNING,
      `reconnect_delay_set(1,60)`, `on_message` -> `ws_manager.manager.broadcast_json_threadsafe`.
      Files: backend/app/mqtt_ingest.py
      Verify: ditutup step 8; interim dari `backend/`: `.venv/Scripts/python.exe -c "import app.db as d; d.init_db(':memory:'); from app.mqtt_ingest import on_message_impl; b=[]; on_message_impl('yg2ufh/ews/sleman/slm-01/data', b'{\"id\":\"slm-01\",\"kabupaten\":\"sleman\",\"ts\":1,\"weather\":{\"temp\":27}}', b.append); assert b and b[0]['node_id']=='slm-01'; on_message_impl('t', b'not json', b.append); print('OK')"` — cetak OK.

- [ ] 5. Bangun schemas + router REST/WS persis technical-design §12.6.
      `app/schemas.py`: Pydantic `KabupatenOut`, `KecamatanOut`, `NodeOut` (node_id, nama, tipe,
      kabupaten, kecamatan, lat, lon, status, ts, received_at, payload: dict|None, alarm: dict|None),
      `HistoryPointOut`, `ThresholdOut`, `ThresholdIn`. Router (plain `def`, try/except -> 500):
      `app/routers/regions.py` — `GET /kabupaten`, `POST /kabupaten`, `GET /kabupaten/{kab}/kecamatan`,
      `POST /kabupaten/{kab}/kecamatan`. `app/routers/nodes.py` — `GET /nodes?kabupaten=&kecamatan=`
      (latest per node, filter), `POST /nodes` (daftar manual), `GET /nodes/{id}` (404 bila unknown),
      `GET /nodes/{id}/history?hours=N` (ge=1,le=8760 untuk 12 bulan, default dari config).
      `app/routers/thresholds.py` — `GET /thresholds` (global + semua override), `PUT /thresholds`
      (set global atau `node:<id>`). `app/routers/ws.py` — `@router.websocket("/live")` push-only
      (mount `/ws` -> endpoint `/ws/live`). CATAT: `POST /report` PDF = TAHAP 2 (JANGAN dibuat).
      Files: backend/app/schemas.py, backend/app/routers/regions.py, backend/app/routers/nodes.py,
      backend/app/routers/thresholds.py, backend/app/routers/ws.py
      Verify: ditutup step 8; interim dari `backend/`: `.venv/Scripts/python.exe -c "import app.routers.nodes, app.routers.regions, app.routers.thresholds, app.routers.ws; print('OK')"` — cetak OK.

- [ ] 6. Rakit app + deteksi offline + retensi `app/main.py`.
      Lifespan: load settings, set log level, `db.init_db`, capture `main_loop`, build+connect MQTT
      client (connect dibungkus try/except -> WARNING, tak pernah crash), `loop_start()`; task asyncio
      deteksi offline (tiap ~30 s: `db.get_stale_nodes(miss_threshold_sec, now)`, flip offline +
      broadcast alarm `{type:"alarm", level:"siaga", source, reason:"node silent", ts}`, flip online
      saat pulih); task retensi (tiap ~6 jam: `db.purge_old_readings(retention_days, now)`). Shutdown:
      cancel task, `loop_stop()`, `disconnect()`. Include router di `/api` (nodes, regions,
      thresholds) & `/ws`; route halaman `GET /node.html` (FileResponse) seperti referensi; mount
      `StaticFiles(directory="app/static", html=True)` di `/` terakhir.
      Files: backend/app/main.py
      Verify: ditutup step 8; interim dari `backend/`: `.venv/Scripts/python.exe -c "import os; os.environ['MQTT_BROKER_HOST']='127.0.0.1'; os.environ['MQTT_TOPIC_PREFIX']='yg2ufh/ews'; from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app); assert c.get('/api/nodes').status_code==200 and c.get('/api/kabupaten').status_code==200 and c.get('/api/thresholds').status_code==200; print('OK')"` — cetak OK (lifespan start, connect ke broker mati TIDAK crash).

- [ ] 7. Bangun frontend nyata `app/static/` dari desain mockup, data dari API/WS.
      `index.html` dashboard: topbar branding YG2UFH + gaya warna mockup; peta Leaflet
      (OpenStreetMap) menaruh node dari `GET /api/nodes` (marker warna per status); kartu node/gateway
      dari API; filter kabupaten/kecamatan dari `GET /api/kabupaten` + `.../kecamatan`; ALARM dashboard
      — kartu berkedip (kelas `alarm-awas`/`alarm-siaga`), beep Web Audio (OscillatorNode, TANPA file),
      banner menonjol, tombol BISUKAN (mute); koneksi `WS /ws/live` untuk reading+alarm realtime;
      klik kartu -> `node.html?id=<node_id>`. `node.html` detail: Chart.js (tilt dengan garis ambang
      SIAGA/AWAS dari `GET /api/thresholds`, cuaca BME280, daya EPEVER) dari `GET /api/nodes/{id}/history`;
      health RSSI/SNR/uptime/fw dari latest. Leaflet & Chart.js via CDN (sama seperti mockup/APRS).
      RBAC UI boleh ikut (badge peran) tapi TANPA auth nyata (TAHAP 2). JANGAN pakai localStorage
      sebagai sumber data node — ambil dari API.
      Files: backend/app/static/index.html, backend/app/static/node.html,
      backend/app/static/css/app.css, backend/app/static/js/dashboard.js, backend/app/static/js/node.js
      Verify: dari `backend/` jalankan uvicorn di background (`Start-Process .venv/Scripts/python.exe -ArgumentList '-m','uvicorn','app.main:app','--port','8001'`), tunggu ~3 s, `Invoke-WebRequest http://127.0.0.1:8001/ -UseBasicParsing` status 200 & body memuat "YG2UFH"; `Invoke-WebRequest http://127.0.0.1:8001/node.html -UseBasicParsing` 200; `Invoke-WebRequest http://127.0.0.1:8001/api/nodes -UseBasicParsing` 200; lalu stop proses. (set env MQTT_BROKER_HOST=127.0.0.1, MQTT_TOPIC_PREFIX=yg2ufh/ews dulu.)

- [ ] 8. Tulis test suite `tests/`.
      `tests/test_parse.py`: JSON valid, field-opsional saja, payload korup -> None (tak crash),
      tanpa `id` -> tak store/broadcast. `tests/test_db.py`: wilayah CRUD, store+latest+history di
      `:memory:`, resolve_threshold global vs override, purge_old_readings. `tests/test_ingest_pipeline.py`:
      suntik payload via `on_message_impl` dengan fake broadcaster, cek tersimpan + broadcast key set
      benar + alarm saat tilt lewat ambang; malformed -> no row/no broadcast.
      `tests/test_offline.py`: seed last_seen basi -> `get_stale_nodes` mengembalikannya.
      `tests/test_api.py`: TestClient — `/api/nodes`, `/api/kabupaten` (POST lalu GET), `/api/thresholds`
      (PUT lalu GET), `/api/nodes/{id}` 404. Tak ada test yang konek broker live.
      Files: backend/tests/test_parse.py, backend/tests/test_db.py, backend/tests/test_ingest_pipeline.py,
      backend/tests/test_offline.py, backend/tests/test_api.py
      Verify: dari `backend/`: `.venv/Scripts/python.exe -m pytest tests/ -v` — semua lulus.

- [ ] 9. Tulis simulator node `tools/simulate_node.py` (pengganti hardware).
      Script paho-mqtt standalone dengan `client_id` BERBEDA dari backend (default `ews-node-sim` —
      WAJIB != `ews-web-backend`). Baca broker host/port/user/pass dari argparse + fallback `.env`.
      Publish JSON realistis untuk `slm-01`, `slm-02` ke `yg2ufh/ews/sleman/<id>/data` tiap N detik
      (`--interval`, default 5); nilai bervariasi (temp ~27±noise; tilt delta kadang melewati ambang
      SIAGA/AWAS untuk menguji alarm); field `id, provinsi, kabupaten, kecamatan, ts, seq, weather,
      power, health`. `--once` publish sekali lalu keluar. JUGA sediakan `tools/inject_sample.py`
      yang menyuntik langsung lewat `process_reading` TANPA broker (untuk demo lokal tanpa mosquitto).
      Files: backend/tools/simulate_node.py, backend/tools/inject_sample.py
      Verify: dari `backend/`: `.venv/Scripts/python.exe tools/simulate_node.py --help` cetak usage;
      `.venv/Scripts/python.exe tools/inject_sample.py` (set MQTT_BROKER_HOST+PREFIX, DB sementara)
      menyimpan reading & keluar 0. Konfirmasi `ews-node-sim != ews-web-backend` by inspection.

- [ ] 10. Tulis `backend/README.md` + verifikasi lokal menyeluruh + cleanup.
      README: setup (venv, pip install, copy `.env.example`->`.env`), run (`uvicorn app.main:app
      --port 8001`), uji lokal (mosquitto lokal + simulator, ATAU injeksi `tools/inject_sample.py`
      tanpa broker), cara run test, peringatan ANTI-BENTROK menonjol (port 8001 / `ews-web-backend` /
      `yg2ufh/ews` / `ews.db`, JANGAN konek broker produksi `yg2ufh.mooo.com` di test karena APRS
      :8000 live), dan catatan eksplisit: Export PDF & auth NYATA = TAHAP 2. Lalu: jalankan seluruh
      pytest, start/stop uvicorn 8001 terkontrol (background lalu stop dalam beberapa detik — JANGAN
      blocking), serve frontend & cek 200, hapus file DB sementara (`data/*.db*`) yang bukan untuk
      di-commit.
      Files: backend/README.md
      Verify: dari `backend/`: `.venv/Scripts/python.exe -m pytest tests/ -v` lulus; uvicorn
      start/stop bersih; tak ada proses uvicorn tersisa; `data/ews.db` sementara dibersihkan.

## Catatan / asumsi
- Login/chat NYATA, Export PDF, edit suara alarm, deploy VPS = TAHAP 2 (JANGAN dibuat sekarang).
- Mockup `docs/mockup/*` hanya referensi visual — JANGAN diubah, JANGAN diimpor, JANGAN jadi sumber
  data. Frontend produksi dibangun baru di `backend/app/static/`.
- Folder `c:/aws-kiro/mqtt-server` hanya dibaca sebagai pola — JANGAN disentuh/diimpor.
- Node yang kirim data tapi belum didaftarkan tetap muncul lewat `readings`/`node_status`
  ("node tak dikenal"); pendaftaran manual node mengisi metadata (nama/koordinat/wilayah).
