# Catatan Keputusan — EWS_YG2UFH

## Sudah FIX
- Bikin firmware EWS sendiri yang ramping (bukan basis CA2RXU). CA2RXU hanya inspirasi UX.
- Transport: LoRa node -> gateway -> MQTT (WiFi). Bukan APRS.
- Hardware: semua LilyGO T-Beam. Satu firmware, peran dipilih saat setup.
- Prototipe: 3x T-Beam 915 = 2 node + 1 gateway.
- Frekuensi per-jaringan; pilih 433/915 saat setup, cocok dengan board fisik.
- EWS pakai 915. T-Beam 433 (CA2RXU: 2 WX + 1 tracker) tidak diganggu.
- Daya lega (50Wp + 50Ah) -> tidak perlu deep sleep rumit.
- Interval kirim 1 menit (awal); rencana adaptif menyusul.
- EPEVER di SETIAP node, via RS485/MAX485.
- Deteksi node hilang: WAJIB, logika di gateway.
- Node kirim status kesehatan (baterai, RSSI, uptime).
- Sirine di gateway via relay; trigger HANYA manual remote (MQTT). TIDAK otomatis.
  Alasan: hindari sirine bunyi sendiri karena sensor error (alarm fatigue, bikin
  warga panik & kehilangan kepercayaan). Keputusan membunyikan sirine = di tangan manusia.
- Ambang tilt memicu NOTIFIKASI/alarm ke MQTT (bukan sirine):
  - delta > 2 derajat dalam 10 menit  -> SIAGA (notifikasi)
  - delta > 5 derajat atau laju perubahan cepat -> AWAS (notifikasi prioritas)
  Angka ambang dapat dikonfigurasi; nilai final via kalibrasi lapangan.
- Sensor fleksibel via config; analog dibaca lewat ADS1115 (I2C), bukan ADC internal ESP32.
- Prototipe: 2 node + 1 gateway (fix).
- Node pertama: mulai dari BME280 + status baterai EPEVER. Sensor lain (tilt,
  extensometer, pH) ditambah bertahap di tengah jalan tanpa bongkar ulang kode.
- Sensor sebagai modul yang bisa diaktifkan; payload MQTT & protokol LoRa pakai
  JSON field-opsional sejak awal supaya nambah sensor tidak mengubah gateway/dashboard.

## Suara sirine (opsi, belum fix)
- Horn/sirine jadi: suara FIXED, hanya bisa atur pola nyala-mati via relay. Paling simpel & andal.
- Sirine multi-tone: pilih pola dari input pabrik via beberapa pin relay. Custom terbatas.
- DFPlayer Mini + speaker + microSD: suara BENAR-BENAR custom (rekaman sendiri,
  pesan beda per tingkat bahaya). Ditambahkan belakangan seperti sensor.
- Prototipe: mulai relay + sirine jadi. Slot DFPlayer disiapkan untuk nanti (TBD apakah dipasang dari awal).

## OPEN QUESTIONS (perlu diputuskan / dicari)
1. Jarak node-gateway 500 m - 1 km, sebagian terhalang pohon. Perlu dicek apakah
   1 gateway cukup atau butuh node relay (uji lapangan). Pengaruh ke setting LoRa (SF/BW/TxPower).
2. Jumlah node realistis per gateway (6 disebut; prototipe 2). Protokol harus anti-tabrakan.
3. Ambang tilt SIAGA/AWAS: angka final untuk NOTIFIKASI (bukan sirine) via kalibrasi lapangan.
4. Model controller EPEVER (Tracer, model TBD difoto) -> menentukan register Modbus.
5. Pin UART T-Beam untuk RS485 (hindari bentrok dengan GPS).
6. Skema `<node-id>` final (region = sleman sudah fix).
7. Sensor fisik mana yang dipakai per node (menentukan modul yang diaktifkan).
8. Sirine custom suara (DFPlayer) dipasang dari awal atau menyusul?

## Dashboard web (fitur yang diminta)
Konteks: `docs/mockup/dashboard.html` saat ini HANYA mockup statis (data dummy,
belum ke MQTT, tanpa backend, tanpa database, tanpa Python).

Fitur yang diminta untuk dashboard:
1. Peta Node — Sleman: peta asli (Leaflet + OpenStreetMap) menggantikan kotak dummy,
   node ditaruh di koordinat lat/lon.
2. Tambah node: form "+ Tambah Node" untuk menambah node baru di peta (nama, koordinat).
3. Login user/password: halaman login sebelum masuk dashboard (aksi seperti tambah node
   & bunyikan sirine butuh akses terbatas).
4. Menu chat: panel chat untuk komunikasi antar operator.

### Keputusan: MOCKUP DULU (sementara)
- Tahap sekarang = mockup HTML statis saja. BELUM pakai database, BELUM app Python.
- Di mockup: login = pura-pura (user/pass contoh di sisi klien, TIDAK aman),
  node & chat disimpan di localStorage browser (dummy, tidak persist ke server).
- Tujuan: review tampilan/alur dulu.

### Manajemen user & peran (RBAC) — 3 peran (fix)
Tiga peran, hak bertingkat:
| Peran    | Lihat | Bunyikan/matikan sirine | Tambah node/gateway | Tambah/kelola user |
|----------|:-----:|:-----------------------:|:-------------------:|:------------------:|
| monitor  |  ✓    |            –            |          –          |         –          |
| operator |  ✓    |            ✓            |          –          |         –          |
| admin    |  ✓    |            ✓            |          ✓          |         ✓          |

- monitor = read-only.
- operator = monitor + kendali sirine (manual, tetap dengan konfirmasi dua langkah).
- admin = operator + tambah node + tambah gateway + manajemen user (tambah/hapus user, set peran).
- Di mockup: peran disimulasikan di sisi klien (localStorage), UI menyembunyikan/menonaktifkan
  aksi sesuai peran. TIDAK aman beneran — penegakan hak WAJIB di backend saat app nyata
  (jangan hanya andalkan UI). Catat sebagai utang teknis untuk tahap FastAPI.

### Pencocokan data MQTT <-> node terdaftar via node_id (fix)
Kunci penghubung antara data yang dikirim alat dan node yang didaftarkan manual
adalah **`node_id`** — BUKAN koordinat, BUKAN nama lokasi.

Alur (contoh node "depok"):
1. Saat FLASH alat: operator set `node_id` (mis. `node-01`) + koordinat. Alat kirim
   ke MQTT membawa ID itu di tiap pesan: topic `yg2ufh/ews/sleman/node-01/data`,
   payload `{ "id":"node-01", ... }`.
2. Saat ADD manual di dashboard: operator daftarkan node dengan ID SAMA PERSIS
   (`node-01`) + nama "Depok" + koordinat.
3. Backend EWS (nanti): baca field `id` tiap pesan MQTT -> cari node terdaftar ber-ID
   sama -> tempelkan data (cuaca/tilt/daya) ke node itu. ID cocok = data masuk ke pin benar.

Konsekuensi WAJIB:
- ID di alat dan ID di dashboard HARUS identik (case-sensitive). `node-01` != `node-1` != `depok`.
  Salah ketik ID = data tidak nyambung. Ini sumber error paling umum.
- Form "Tambah/Edit Node" harus memberi teks bantuan: "ID harus sama persis dengan
  yang di-flash ke alat".
- Koordinat & nama lokasi = label tampilan saja; `node_id` = identitas (seperti nomor KTP).

### Deteksi node tak dikenal (backend, nanti)
Jika ada pesan MQTT masuk dengan `id` yang BELUM didaftarkan di dashboard, tampilkan
peringatan: "alat ber-ID `X` kirim data tapi belum terdaftar". Membantu operator
sadar ada salah ketik ID atau alat baru yang belum didaftarkan. (Belum di mockup —
butuh backend; dicatat sebagai fitur app nyata.)

### Edit & delete node/gateway = hak ADMIN (fix)
Menu edit (ubah nama/lokasi/koordinat/status) dan delete node/gateway hanya untuk
peran **admin**. Operator tetap read-only soal node (operator hanya +sirine).
Konsisten dengan tabel RBAC di atas.

### Halaman detail per-node (fix)
Klik kartu node -> buka halaman detail terpisah `node.html?id=<node_id>` berisi grafik
sensor (tilt dgn ambang SIAGA 2°/AWAS 5°, cuaca BME280, daya EPEVER) + health
(RSSI/SNR/uptime/fw). Pakai Chart.js (sama seperti dashboard APRS di mqtt-server).
Gateway -> halaman detail sederhana (status, node terpantau, kontrol sirine).
Pola meniru APRS `/weather/a/<callsign>` & `/telemetry/a/<callsign>`; saat app nyata,
URL jadi route backend dan grafik diisi data historis dari API/DB.
Di mockup: grafik pakai data dummy.

### Pendaftaran node/gateway ke dashboard = MANUAL (fix)
- Perangkat (T-Beam/Raspi/ESP32) yang sudah dikonfig TETAP mengirim data ke MQTT
  (`yg2ufh/ews/#`) seperti biasa.
- Namun untuk MUNCUL di dashboard EWS, node/gateway DIDAFTARKAN MANUAL oleh operator
  (isi ID + koordinat + lokasi). Setelah terdaftar, data sensor dari MQTT ditempelkan
  ke pin yang sudah didaftarkan.
- BERBEDA dari dashboard APRS (`c:\aws-kiro\mqtt-server`, proyek terpisah) yang
  auto-discovery: perangkat APRS otomatis muncul dari GPS di paket. EWS TIDAK pakai
  auto-discovery — pendaftaran manual dipilih demi koordinat akurat & kontrol siapa
  yang tampil (sistem keselamatan).
- Alasan tambahan: saat FIRST FLASH firmware, operator WAJIB memasukkan koordinat &
  lokasi node secara manual (lihat captive portal di technical-design.md §8). Jadi
  koordinat memang ditetapkan manusia sejak awal, bukan diambil dari GPS.
- Catatan: `mqtt-server` adalah proyek APRS (CA2RXU, callsign YG2UFH-10) — INSPIRASI UX,
  BUKAN basis EWS. Dashboard EWS berdiri sendiri.

### Dua dashboard terpisah, dipisah lewat PORT (Opsi A — fix)
Akan ada DUA dashboard independen di host `ews.example.com`:
- APRS (proyek `c:\aws-kiro\mqtt-server`, sudah ada) -> `ews.example.com:8000`,
  subscribe topik `aprs/#`.
- EWS (app baru, belum dibuat)                        -> `ews.example.com:8001`,
  subscribe topik `yg2ufh/ews/#`.

Pemisahan lewat PORT, bukan path/reverse-proxy. Dua proses FastAPI terpisah,
dua port, dua subscription MQTT berbeda.
- Alasan: paling simpel, sesuai keadaan sekarang, tanpa Nginx/Caddy.
- Konsekuensi: URL memakai angka port; port 8001 harus dibuka di firewall VPS.
- EWS & APRS tetap aplikasi TERPISAH (beda topik, beda skema data, beda tujuan:
  keselamatan vs hobi). TIDAK digabung jadi satu proses.
- Catatan: HTTPS/Web Serial (web flasher) butuh TLS; untuk dashboard EWS di port
  8001, TLS bisa ditambah belakangan (reverse proxy opsional di masa depan bila perlu).

Status: ini tahap "app beneran" NANTI. Sekarang EWS masih mockup HTML statis
(dibuka dari file lokal, belum ada port/proses).

### Backend EWS: JSON native, BUKAN APRS/aprslib (fix)
- Backend EWS parse payload JSON langsung (lihat format di technical-design.md §4).
- TIDAK memakai aprslib. Alasan: APRS/TNC2 format teks ringkas (posisi + telemetri
  terbatas), tidak muat data EWS yang kaya (tilt, extensometer, pH, EPEVER, dll).
- Library: paho-mqtt + json bawaan + FastAPI (pola mirip mqtt-server tapi tanpa aprslib).

### CHECKLIST ANTI-BENTROK dengan APRS (`mqtt-server` :8000) — WAJIB
APRS di `ews.example.com:8000` SUDAH JALAN NORMAL dan TIDAK BOLEH terganggu.
EWS harus memakai sumber daya SENDIRI di tiap titik berikut:

| Sumber daya      | APRS (sudah ada)      | EWS (harus BEDA)        |
|------------------|-----------------------|-------------------------|
| Port HTTP        | 8000                  | **8001**                |
| MQTT client_id   | `aprs-web-backend`    | **`ews-web-backend`**   |
| MQTT topic prefix| `aprs` (`aprs/#`)     | **`yg2ufh/ews` (`yg2ufh/ews/#`)** |
| File database    | `./data/aprs.db`      | **`./data/ews.db`**     |
| systemd service  | service APRS          | **`ews-web.service`**   |

PALING KRITIKAL: **client_id MQTT**. Broker menendang klien kedua bila dua klien
memakai client_id SAMA. Jika EWS pakai `aprs-web-backend`, APRS akan putus-nyambung.
EWS WAJIB `ews-web-backend`.

AMAN dibagi (tidak bentrok):
- Broker MQTT yang sama (`ews.example.com:1883`) — dirancang melayani banyak klien.
  APRS dengar `aprs/#`, EWS dengar `yg2ufh/ews/#`; tidak saling dengar.
- Satu VPS yang sama — asal port beda & service name beda.

Urutan deploy paling aman:
1. Bangun backend EWS + simulator node, UJI LOKAL dulu (APRS di VPS tak tersentuh).
2. Setelah terbukti, deploy ke VPS sebagai service TERPISAH (`ews-web.service`, :8001),
   TANPA menyentuh file/service APRS.

### Fitur tambahan yang diminta (BARU — perlu desain, belum dikerjakan)
Dicatat agar tidak hilang. Perlu dibahas prioritas & tahapannya.

1. **Edit threshold / ambang (toleransi) per node** — operator/admin bisa ubah ambang
   tilt SIAGA/AWAS (dan ambang sensor lain) dari dashboard, bukan hardcode. Nilai
   disimpan di backend. Selaras dgn keputusan "ambang dapat dikonfigurasi" di
   technical-design §7. (Hak edit: kemungkinan admin; perlu dikonfirmasi.)
2. **Edit suara alarm** — pilih/atur suara sirine yang nanti DIKIRIM ke alat (gateway)
   via MQTT. Terkait rencana DFPlayer (suara custom per tingkat bahaya) di decisions.md
   bagian "Suara sirine". Butuh: UI pilih pola/suara + perintah MQTT ke gateway.
   CATATAN: tetap tunduk aturan "sirine hanya manual" — ini mengatur SUARA, bukan
   memicu otomatis.
3. **Retensi data >= 12 bulan** — data sensor yang diterima disimpan minimal 12 bulan
   (untuk riwayat & laporan). Pengaruh ke desain DB (ukuran, indeks, mungkin
   downsampling data lama). SQLite mungkin cukup; evaluasi saat implementasi.
4. **Export laporan** — ekspor data (mis. CSV/PDF) per node/kabupaten/rentang waktu.
5. **Pengelompokan dashboard per wilayah (hierarki)** — DIY punya 5 kabupaten/kota.
   Hierarki: Provinsi DIY > Kabupaten/Kota > Kecamatan > Node.
   - Menu "Tambah Kabupaten" dan "Tambah Kecamatan".
   - Saat tambah/edit node, pilih node masuk kabupaten + kecamatan mana (grup).
   - Dashboard bisa difilter/dikelompokkan per kabupaten (lalu per kecamatan).
   - PENGARUH BESAR: `region` yang tadinya tunggal "sleman" jadi hierarki. Field node
     bertambah: kabupaten + kecamatan. Pengaruh ke skema node_id, topic MQTT, DB,
     dan UI dashboard. PERLU revisi technical-design (skema penamaan & topic).

Status: REQUIREMENT dicatat; prioritas & tahap implementasi perlu diputuskan bersama.

### Keputusan desain hierarki wilayah & fitur baru (fix sebagian)
- **Skala**: Yogyakarta hanya CONTOH/preview. Sistem harus bisa dipakai daerah lain.
  Hierarki wilayah dibuat GENERIK (tidak hardcode DIY/5 kabupaten):
  Provinsi > Kabupaten/Kota > Kecamatan > Node. Provinsi & kabupaten bisa ditambah bebas.
- **Topic MQTT**: `yg2ufh/ews/<kabupaten>/<node-id>/data`. Kecamatan = metadata di
  payload/DB (tidak masuk topic, agar topic tidak terlalu dalam).
- **node_id**: unik GLOBAL, pakai prefix kabupaten (mis. `slm-01`, `btl-01`).
- **Threshold/ambang**: default GLOBAL, bisa OVERRIDE per node. Disimpan di backend,
  bisa diedit dari dashboard (hak: admin — perlu konfirmasi final).
- **Laporan**: export PDF saja (bukan CSV).
- **Prefix `yg2ufh` (FIX, opsi a)**: dipertahankan sebagai PENANDA PEMILIK aplikasi
  (yg2ufh = pemilik sistem), meski node dipasang di daerah lain. Topic tetap
  `yg2ufh/ews/<kabupaten>/<node-id>/data`. Tidak diganti netral.
- Retensi data: minimal 12 bulan (lihat requirement di atas).
- Edit suara alarm: menyusul (butuh gateway + DFPlayer); tetap tunduk "sirine manual".

### DUA jenis "alarm" — JANGAN tertukar (fix)
1. **Sirine FISIK di lapangan** (relay di gateway): HANYA MANUAL. Tidak pernah otomatis.
   (keputusan lama, tetap berlaku — hindari warga panik karena sensor error.)
2. **Alarm DASHBOARD** (indikator untuk OPERATOR di layar): BOLEH OTOMATIS.
   Saat nilai sensor melewati ambang: kartu node BERKEDIP (merah=AWAS, kuning=SIAGA),
   browser mengeluarkan BUNYI beep (Web Audio, tanpa file), banner alarm menonjol,
   + tombol BISUKAN (mute). Ini hanya menarik perhatian operator, BUKAN sirine fisik.
   Alur: sensor buruk -> dashboard kedip+bunyi (otomatis) -> operator verifikasi ->
   operator tekan sirine (manual) -> sirine fisik bunyi. Memperkuat "sirine manual",
   bukan melanggar.

### Fokus kerja: BACKEND + FRONTEND nyata (fix)
- Berhenti menambal mockup statis. Bangun aplikasi FastAPI nyata (port 8001).
- Mockup `docs/mockup/` = ARSIP/referensi desain (opsi a). Frontend produksi dibangun
  BARU di `backend/app/static/`, mengambil desain dari mockup tapi ambil data dari API/WS.
- Mosquitto lokal DILEWATI dulu (belum terpasang di PC user). Backend diuji lewat injeksi
  langsung; demo end-to-end dgn broker belakangan (pakai mosquitto VPS saat deploy).

#### Scope TAHAP 1 (fondasi inti — data node)
Backend: config anti-bentrok EWS, DB (hierarki wilayah kabupaten/kecamatan + reading +
threshold global/override + retensi 12 bulan), MQTT ingest JSON (bukan aprslib),
REST API (nodes, kabupaten, kecamatan, history, thresholds), WebSocket realtime,
deteksi node offline, simulator node (tools/simulate_node.py).
Frontend (dari desain mockup, data dari API/WS): dashboard (peta Leaflet, kartu node/
gateway, ALARM dashboard berkedip + beep + bisukan, filter per kabupaten/kecamatan),
halaman detail node (grafik Chart.js dari API). RBAC UI (3 peran) boleh ikut tapi
penegakan auth nyata = tahap 2.

#### Database: SQLite dulu (fix)
- Tahap sekarang pakai **SQLite** (`data/ews.db`). Alasan: APRS (mqtt-server) sudah
  pakai & terbukti, tanpa server DB terpisah (satu file, mudah backup, tak nambah
  hal yang bisa bentrok di VPS), cukup untuk skala node EWS (JSON kecil tiap 1 menit,
  retensi 12 bulan tetap ringan).
- **Upgrade ke PostgreSQL NANTI** bila skala besar (ratusan node / banyak penulisan
  serentak / banyak operator). SQL mirip, migrasi tidak merombak total. Jangan
  over-engineer sekarang.

#### Scope TAHAP 2 (menyusul)
Login & chat NYATA (user di DB, password di-hash, sesi aman) — bukan localStorage.
Export laporan PDF. Edit suara alarm (kirim ke gateway). Deploy VPS (ews-web.service :8001).

#### Auth login = TINGKAT A (fix) — dikerjakan sekarang (bagian awal TAHAP 2)
Keputusan: pakai "login dasar yang benar", BUKAN sekadar hash.
- Password di-**hash bcrypt** di DB (passlib/bcrypt). Tidak pernah simpan plaintext.
- **Session cookie** httpOnly (login beneran) — bukan pura-pura di klien.
- **Proteksi endpoint**: endpoint yang MENGUBAH data (POST/PUT/DELETE nodes, kabupaten,
  kecamatan, thresholds) WAJIB login. Endpoint lihat (GET) boleh terbuka untuk sekarang.
- **RBAC 3 peran ditegakkan di BACKEND** (bukan cuma sembunyikan tombol di UI):
  monitor = lihat; operator = lihat + sirine; admin = semua + kelola user + tambah/
  edit/hapus node/gateway/kabupaten/kecamatan + edit threshold.
- Endpoint auth: POST /api/login, POST /api/logout, GET /api/me. User disimpan di tabel
  `users` (username, password_hash, role). Seed admin awal via env/CLI (bukan hardcode).
- Frontend: halaman/overlay login nyata memanggil /api/login; UI sembunyikan aksi sesuai
  peran dari GET /api/me (UI = kenyamanan; backend = penegak sebenarnya).

#### HTTPS (syarat sebelum PRODUKSI, belum sekarang)
- Untuk UJI/deploy awal: boleh HTTP polos di :8001 (login jalan tapi belum terenkripsi
  di jaringan — JANGAN dipakai untuk password sungguhan di internet publik).
- Sebelum dipakai publik beneran: WAJIB HTTPS. Caranya reverse proxy (Nginx/Caddy) +
  Let's Encrypt. Ini sedikit menggeser keputusan "pisah port" — ditinjau saat naik ke
  produksi. Dicatat sebagai syarat keamanan, bukan opsional.

### Jalur lanjut (BELUM dikerjakan — untuk login & chat yang beneran)
Login & chat yang nyata WAJIB backend + penyimpanan. Dua opsi dicatat:
- Python (FastAPI/Flask) + SQLite/PostgreSQL + MQTT client. (kandidat utama krn user sebut Python)
- atau Node.js.
Keputusan teknologi backend DITUNDA sampai mockup disetujui.

## PR / tugas tertunda (tidak urgent)
- Cari register map Modbus EPEVER sesuai model controller.
- Uji jangkauan LoRa di lapangan (medan berpohon).
- Dashboard: putuskan backend (Python FastAPI + SQLite vs Node.js) saat naik dari mockup ke app beneran.

## Ide: bridge APRS -> EWS (untuk demo pakai data YG2UFH-10, OPSIONAL/nanti)
Perangkat YG2UFH-10 (IGate LilyGo T-Beam) sudah kirim data cuaca ke proyek APRS
(topik `aprs-igate/#`, format APRS/TNC2). Formatnya BEDA dari EWS (JSON di topik
`yg2ufh/ews/#`), jadi EWS tidak bisa membacanya langsung.

Tiga opsi menampilkan data YG2UFH-10 di EWS:
1. MANUAL + simulator (demo tampilan): daftar node EWS di koordinat YG2UFH-10
   (-7.70776, 110.41006) lalu isi datanya pakai simulator. Cepat, tapi data dummy.
2. BRIDGE APRS->EWS (data asli): skrip kecil subscribe `aprs-igate/#`, parse cuaca
   YG2UFH-10, ubah ke JSON EWS, publish ke `yg2ufh/ews/.../data`. Perlu kode baru +
   parsing APRS (aprslib). Belum dibuat.
3. Alat EWS beneran (T-Beam flash firmware EWS, kirim JSON) — tujuan akhir.

Keputusan: untuk DEMO sekarang pakai opsi 1 (manual + simulator). Opsi 2 (bridge)
dicatat sebagai fitur terpisah bila ingin data YG2UFH-10 asli masuk EWS.
