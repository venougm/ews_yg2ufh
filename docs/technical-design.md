# Desain Teknis — EWS_YG2UFH

Cetak biru firmware & protokol. **Belum ada kode.** Dokumen ini menetapkan format
data, topic MQTT, paket LoRa, dan library sebelum implementasi.

Wilayah: Yogyakarta / Sleman. Prototipe: 2 node + 1 gateway, T-Beam 915.

---

## 1. Peran perangkat (satu firmware)

Satu `.bin` untuk semua T-Beam. Peran dipilih saat setup (captive portal):

- **NODE**: baca sensor -> kirim paket LoRa ke gateway tiap 1 menit.
- **GATEWAY**: terima LoRa dari node -> publish ke MQTT; kelola sirine & deteksi node hilang.

---

## 2. Identitas & penamaan (hierarki wilayah)

Sistem dirancang GENERIK — Yogyakarta hanya contoh, bisa dipakai daerah lain.
Hierarki wilayah: **Provinsi > Kabupaten/Kota > Kecamatan > Node**.

- `yg2ufh` = penanda PEMILIK aplikasi (bukan wilayah). Tetap dipakai meski node
  dipasang di daerah lain.
- `provinsi` = mis. `diy` (opsional di topic; disimpan sebagai metadata).
- `kabupaten` = mis. `sleman`, `bantul`, `gunungkidul`, `kulonprogo`, `kotayogya`.
  Bisa ditambah bebas (tidak hardcode). Masuk ke topic MQTT.
- `kecamatan` = mis. `depok`, `kalasan`. METADATA di payload/DB (TIDAK di topic,
  agar topic tidak terlalu dalam).
- `node_id` = ID unik GLOBAL dengan **prefix kabupaten**: `slm-01`, `btl-01`,
  `gk-01`, dst. Unik se-seluruh sistem (bukan hanya per kabupaten) agar tidak
  bentrok. Gateway: `slm-gw-01`. Default dari chip ID ESP32, di-override di captive portal.
- Saat FIRST FLASH, operator mengisi: kabupaten, kecamatan, node_id, koordinat, lokasi.
- Satu "jaringan" ditandai `network_id` + frekuensi + (opsional) kata sandi LoRa,
  agar jaringan lain tidak saling mengganggu.

---

## 3. Skema Topic MQTT

Base: `yg2ufh/ews/<kabupaten>/<node_id>/...`
(`yg2ufh` = pemilik; `<kabupaten>` = grup wilayah; kecamatan = metadata di payload.)

### Data sensor (gateway yang publish, retained=false)
```
yg2ufh/ews/sleman/slm-01/weather/temperature     -> 27.4
yg2ufh/ews/sleman/slm-01/weather/humidity        -> 82.1
yg2ufh/ews/sleman/slm-01/weather/pressure        -> 1008.3
yg2ufh/ews/sleman/slm-01/power/battery_voltage   -> 12.8
yg2ufh/ews/sleman/slm-01/power/pv_voltage        -> 18.2
yg2ufh/ews/sleman/slm-01/tilt/angle_x            -> 5.2   (opsional, bertahap)
```

### Payload gabungan (satu JSON per node, lebih hemat) — DIREKOMENDASIKAN
```
yg2ufh/ews/sleman/slm-01/data   -> { JSON lengkap, lihat section 4 }
```
Dua gaya ini bisa dipakai bersamaan; gaya JSON gabungan jadi acuan utama,
per-metric topic untuk kemudahan dashboard sederhana.

### Status & health
```
yg2ufh/ews/sleman/slm-01/status   -> "online" | "offline"   (retained=true)
yg2ufh/ews/sleman/slm-01/health   -> { rssi, uptime, batt, ... }
```

### Sirine (gateway)
```
yg2ufh/ews/sleman/slm-gw-01/siren/cmd     <- "ON" | "OFF" | "PATTERN:evac"   (dari dashboard)
yg2ufh/ews/sleman/slm-gw-01/siren/state   -> "on" | "off"                     (status aktual, retained=true)
```

### Alarm / Notifikasi EWS (otomatis dari deteksi; TIDAK memicu sirine)
```
yg2ufh/ews/sleman/alarm   -> { level: "siaga|awas", source: "slm-01", reason: "tilt delta>5deg", ts }
```
Alarm ini hanya NOTIFIKASI untuk operator. Sirine tetap dibunyikan manual via `.../siren/cmd`.

Backend subscribe `yg2ufh/ews/#` lalu memilah kabupaten & node_id dari topic/payload.

---

## 4. Format payload JSON (node -> MQTT)

Prinsip: **field opsional**. Node hanya mengirim field untuk sensor yang aktif.
Nambah sensor = tambah field, gateway & dashboard tidak perlu diubah.

```json
{
  "id": "slm-01",
  "provinsi": "diy",
  "kabupaten": "sleman",
  "kecamatan": "depok",
  "ts": 1760000000,
  "seq": 1234,
  "weather": { "temp": 27.4, "hum": 82.1, "press": 1008.3 },
  "power":   { "batt_v": 12.8, "pv_v": 18.2, "load_a": 0.4, "soc": 87 },
  "tilt":    { "x": 5.2, "y": 1.1, "delta": 0.3 },
  "ext":     { "mm": 12.5 },
  "ph":      { "value": 6.4 },
  "rain":    { "mm": 0.0 },
  "gps":     { "lat": -7.72, "lon": 110.38, "fix": true },
  "health":  { "rssi": -92, "snr": 7.5, "uptime": 3600, "fw": "0.1.0" }
}
```

Catatan: `region` lama diganti hierarki `provinsi` + `kabupaten` + `kecamatan`.
`kabupaten` juga ada di topic; `kecamatan` hanya di payload/DB.
Tahap awal (BME280 + EPEVER) hanya mengisi:
`id, provinsi, kabupaten, kecamatan, ts, seq, weather, power, health`.

---

## 5. Protokol paket LoRa (node -> gateway)

Keterbatasan LoRa: payload kecil, rawan tabrakan. Desain:

- **Format paket ringkas** (bukan JSON mentah di udara — JSON terlalu besar untuk LoRa).
  Opsi: field biner padat ATAU JSON minimal terkompresi. Keputusan: mulai dari
  **JSON minimal** (mudah debug), optimasi ke biner bila perlu.
- **Header paket**: `network_id`, `node_id`, `seq`, `msg_type`.
  - `msg_type`: `DATA` (sensor) | `JOIN` (node daftar) | `ACK` | `CMD` (gateway->node, mis. set interval).
- **Anti-tabrakan**: tiap node kirim pada offset waktu berbeda dalam window 1 menit
  (mis. node-01 di detik ke-0, node-02 di detik ke-10) ATAU listen-before-talk sederhana.
  Untuk 2 node prototipe, offset statis cukup.
- **Reliabilitas**: gateway kirim `ACK`; bila node tidak dapat ACK, kirim ulang 1-2x.
  (Opsional di awal; bisa fire-and-forget dulu, karena interval 1 menit toleran drop.)
- **Setting radio** (disetel di captive portal, konsisten se-jaringan):
  Frekuensi 915 (atau 433), SF (spreading factor), BW (bandwidth), CR, TxPower.
  Jarak 500m-1km dengan pohon -> cenderung SF tinggi (jangkauan jauh, data rate rendah),
  TxPower maksimum legal. Nilai final ditentukan uji lapangan.

### JOIN / auto-register (kemudahan nambah node)
Node baru nyala -> kirim `JOIN` berisi `node_id` + daftar sensor aktif.
Gateway catat node tersebut (tabel node dikenal) -> langsung teruskan datanya ke MQTT.
Nambah node = flash + nyalakan + pilih peran/ID. Tidak perlu ubah gateway.

---

## 6. Deteksi node hilang (di gateway)

- Gateway simpan `last_seen[node_id]` tiap terima paket.
- Timer periodik: jika `now - last_seen > miss_threshold` (default 3x interval = 3 menit):
  - publish `.../status = offline` (retained).
  - publish `alarm { level: "siaga", reason: "node silent" }`.
- Saat node terdengar lagi -> `status = online`.
- Rasional EWS: node diam bisa berarti baterai habis, radio rusak, ATAU node
  terseret/tertimbun longsor -> diperlakukan sebagai alarm.

---

## 7. Logika sirine & alarm (di gateway)

**PENTING: sirine TIDAK PERNAH bunyi otomatis.** Hanya lewat perintah manual remote.
Alasan: sensor error di tengah malam tidak boleh membunyikan sirine sendiri
(alarm fatigue, warga panik & kehilangan kepercayaan). Keputusan membunyikan =
di tangan manusia yang sudah verifikasi.

Pemisahan jelas:
- **DETEKSI (otomatis, oleh mesin)**: gateway evaluasi data -> publish NOTIFIKASI/alarm ke MQTT.
- **AKSI SIRINE (manual, oleh manusia)**: operator lihat alarm -> verifikasi -> tekan sirine dari jauh.

### Sirine (hanya manual)
Subscribe `.../siren/cmd`. `ON` / `OFF` / `PATTERN:x` -> set pin relay.
Tidak ada jalur otomatis dari data sensor ke relay sirine.

### Ambang tilt -> NOTIFIKASI (bukan sirine)
- `delta > 2 derajat dalam 10 menit`  -> level **SIAGA**  -> publish alarm (notifikasi).
- `delta > 5 derajat` atau laju perubahan cepat -> level **AWAS** -> publish alarm (prioritas).
- Ambang **dapat dikonfigurasi** (bukan hardcode); angka final via kalibrasi lapangan.
- Alarm ini memberi tahu operator; operator yang memutuskan menekan sirine.

Sirine fisik:
- Prototipe: relay 5V -> horn/sirine jadi (pola nyala-mati diatur firmware).
- Lanjut (opsional): DFPlayer Mini + speaker untuk pesan suara custom per tingkat bahaya.

---

## 8. Konfigurasi & provisioning (captive portal)

Saat pertama nyala / tombol reset config ditekan, perangkat jadi AP WiFi
`YG2UFH-EWS-Setup`. User buka browser -> form konfig:

- **Peran**: Node / Gateway
- **Frekuensi LoRa**: 433 / 915 (harus cocok board fisik)
- **node_id / region**
- **Koordinat & lokasi (WAJIB saat first flash)**: operator memasukkan lat/lon +
  nama lokasi node secara MANUAL saat setup pertama. Koordinat ditetapkan manusia,
  bukan diambil otomatis dari GPS. Ini jadi sumber posisi node di dashboard
  (dashboard EWS memakai pendaftaran manual, bukan auto-discovery — lihat decisions.md).
- **Setting radio LoRa**: SF, BW, CR, TxPower (atau preset: "jauh" / "cepat")
- **Sensor aktif** (node): centang BME280, tilt, pH, ext, rain, EPEVER
- **WiFi** (gateway): SSID + password jaringan internet lokal
- **MQTT** (gateway): host `ews.example.com`, port `1883`, user/pass (kosong untuk sekarang)
- **Ambang sirine** (gateway): nilai ambang tilt dll.

Konfig disimpan di NVS/flash. Library: **WiFiManager** (atau captive portal custom).

---

## 9. Library PlatformIO (rencana)

Platform: `espressif32`. Framework: `arduino`.

| Fungsi | Library (kandidat) |
|---|---|
| LoRa (SX127x/SX126x) | RadioLib (mendukung banyak chip, fleksibel) |
| BME280 | Adafruit BME280 + Adafruit Unified Sensor |
| Tilt MPU6050 | Adafruit MPU6050 / MPU6050_light |
| ADC eksternal ADS1115 | Adafruit ADS1X15 |
| EPEVER Modbus RS485 | ModbusMaster |
| WiFi provisioning | WiFiManager (tzapu) |
| MQTT | PubSubClient atau arduino-mqtt (256dpi) |
| JSON | ArduinoJson |
| Manajemen daya T-Beam (AXP) | XPowersLib (axp20x untuk versi lama) |
| GPS (opsional) | TinyGPSPlus |

Catatan chip LoRa: perlu dipastikan modul di T-Beam 915 (SX1276 vs SX1262) ->
RadioLib menangani keduanya, tinggal pilih driver yang benar saat setup.

---

## 10. Catatan hardware yang masih harus diselesaikan

1. **Pin UART RS485**: T-Beam memakai UART untuk GPS. RS485 (MAX485) perlu UART
   lain / SoftwareSerial. Pin final ditentukan setelah cek board. Perlu juga pin
   kontrol arah MAX485 (DE/RE).
2. **Register Modbus EPEVER**: tergantung model Tracer (difoto nanti). Register
   umum Tracer: tegangan baterai, PV, arus, SOC.
3. **Pin relay sirine** (gateway): satu GPIO bebas -> relay.
4. **Pin I2C**: SDA/SCL default T-Beam untuk BME280 & sensor I2C lain (bus bersama).
5. **Chip LoRa & frekuensi board 915**: konfirmasi SX1276/SX1262 untuk driver RadioLib.

---

## 11. Roadmap implementasi (urutan, belum dikerjakan)

1. Skeleton firmware + captive portal + pilih peran.
2. NODE: baca BME280 + status baterai EPEVER -> kirim paket LoRa.
3. GATEWAY: terima LoRa -> publish JSON ke MQTT.
4. GATEWAY: deteksi node hilang -> status/alarm MQTT.
5. GATEWAY: alarm/notifikasi otomatis (deteksi) + sirine manual via MQTT (TANPA auto-trigger).
6. Uji end-to-end 1 node + 1 gateway, lalu 2 node.
7. Web flasher YG2UFH (build .bin + manifest + halaman HTTPS).
8. Tambah sensor bertahap: tilt, extensometer, pH, rain.

---

## 12. Backend dashboard EWS & fitur lanjutan

Backend FastAPI terpisah dari APRS (lihat decisions.md "CHECKLIST ANTI-BENTROK"):
port **8001**, client_id **`ews-web-backend`**, topik **`yg2ufh/ews/#`**, DB **`ews.db`**.
Parse JSON native (BUKAN aprslib).

### 12.1 Hierarki wilayah (grouping dashboard)
- Model: **Provinsi > Kabupaten/Kota > Kecamatan > Node**. Generik, bisa ditambah bebas
  (Yogyakarta hanya contoh; sistem dapat dipakai daerah lain).
- Tabel DB: `kabupaten` (id, nama, provinsi), `kecamatan` (id, nama, kabupaten_id).
  Node punya `kabupaten` + `kecamatan`.
- Dashboard: menu "Tambah Kabupaten" & "Tambah Kecamatan" (hak admin). Saat tambah/edit
  node, pilih kabupaten + kecamatan. Dashboard bisa difilter/dikelompokkan per kabupaten,
  lalu per kecamatan.
- node_id unik global dengan prefix kabupaten (mis. `slm-01`).

### 12.2 Threshold / ambang (dapat dikonfigurasi)
- Nilai ambang (tilt SIAGA/AWAS, dll.) disimpan di backend, BUKAN hardcode.
- **Default global** + **override per node**. Resolusi: ambang node = override node bila
  ada, selain itu pakai default global.
- Dashboard: menu edit threshold (hak admin). Backend memakai nilai ini saat evaluasi
  deteksi -> publish NOTIFIKASI/alarm (tetap TIDAK memicu sirine otomatis).
- Simpan di tabel `thresholds` (scope: `global` atau `node:<id>`).

### 12.3 Edit suara alarm (dikirim ke alat — menyusul)
- Dashboard: pilih pola/suara sirine; backend kirim perintah ke gateway via MQTT
  `yg2ufh/ews/<kabupaten>/<gw-id>/siren/cmd` (mis. `PATTERN:evac`).
- Terkait DFPlayer (suara custom per tingkat bahaya) — lihat decisions.md.
- TETAP tunduk aturan "sirine hanya manual": ini mengatur SUARA/pola, bukan auto-trigger.
- Status: menyusul (butuh gateway + DFPlayer). Desain disiapkan, implementasi belakangan.

### 12.4 Retensi data >= 12 bulan
- Semua reading disimpan minimal **12 bulan** untuk riwayat & laporan.
- DB: SQLite dengan indeks (node_id, ts). Evaluasi ukuran; bila perlu, downsample data
  lama (mis. simpan rata-rata per jam untuk data > beberapa bulan) agar DB tak membengkak.
- Tugas pembersihan periodik: hapus/arsipkan data lebih tua dari ambang retensi (configurable,
  default 12 bulan).

### 12.5 Export laporan PDF
- Export **PDF** (bukan CSV) per node / kabupaten / rentang waktu.
- Isi: ringkasan + grafik sensor + riwayat alarm pada periode terpilih.
- Berguna untuk pelaporan ke pihak terkait (mis. BPBD).
- Kandidat library: ReportLab atau WeasyPrint (TBD saat implementasi).

### 12.6 REST API (rencana)
```
GET  /api/kabupaten                       -> daftar kabupaten
GET  /api/kabupaten/{kab}/kecamatan       -> daftar kecamatan
GET  /api/nodes?kabupaten=&kecamatan=     -> node (filter grup), latest reading
GET  /api/nodes/{id}                      -> detail + latest
GET  /api/nodes/{id}/history?hours=N      -> riwayat (grafik)
GET  /api/thresholds                      -> global + override
PUT  /api/thresholds                      -> set (admin)
POST /api/report (kab/node, rentang) -> PDF
WS   /ws                                  -> push realtime
```
