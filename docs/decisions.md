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
Akan ada DUA dashboard independen di host `yg2ufh.mooo.com`:
- APRS (proyek `c:\aws-kiro\mqtt-server`, sudah ada) -> `yg2ufh.mooo.com:8000`,
  subscribe topik `aprs/#`.
- EWS (app baru, belum dibuat)                        -> `yg2ufh.mooo.com:8001`,
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

### Jalur lanjut (BELUM dikerjakan — untuk login & chat yang beneran)
Login & chat yang nyata WAJIB backend + penyimpanan. Dua opsi dicatat:
- Python (FastAPI/Flask) + SQLite/PostgreSQL + MQTT client. (kandidat utama krn user sebut Python)
- atau Node.js.
Keputusan teknologi backend DITUNDA sampai mockup disetujui.

## PR / tugas tertunda (tidak urgent)
- Cari register map Modbus EPEVER sesuai model controller.
- Uji jangkauan LoRa di lapangan (medan berpohon).
- Dashboard: putuskan backend (Python FastAPI + SQLite vs Node.js) saat naik dari mockup ke app beneran.
