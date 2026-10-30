# Keputusan Firmware EWS — Model CA2RXU iGate (catatan dari user YG2UFH)

Tanggal dicatat: lanjutan sesi desain. Status: KEPUTUSAN FINAL konsep, belum coding.

## Ringkasan keputusan user

Firmware EWS meniru **arsitektur CA2RXU LoRa APRS iGate** (`c:\aws-kiro\firm`),
diadaptasi untuk EWS. Istilah dipetakan:

| CA2RXU | EWS (nama kita) |
|--------|-----------------|
| iGate  | **GATEWAY** |
| Tracker| **NODE** |

## Poin keputusan (dari user, verbatim-intent)

1. **Board: T-Beam 915 MHz** (semua perangkat). Chip LoRa perlu dikonfirmasi saat
   coding (SX1276 vs SX1262) — RadioLib menangani keduanya.

2. **Dua peran, satu firmware**: GATEWAY & NODE (seperti iGate & tracker CA2RXU).

3. **Sensor & sirine FLEKSIBEL di kedua peran**: baik GATEWAY maupun NODE bisa
   dipasangi sensor dan/atau sirine sesuai PCB mainboard. Tinggal
   DIAKTIFKAN / DINONAKTIFKAN lewat web-based config (bukan hardcode peran).
   Jadi gateway pun boleh punya sensor; node pun boleh punya sirine — terserah
   centang di web config.

4. **Model boot default = AP (Access Point)** setelah di-flash:
   - T-Beam pertama kali nyala -> jadi WiFi AP -> user buka web-based GUI untuk
     setting (peran, sensor on/off, sirine on/off, LoRa params, WiFi, MQTT, dll).
   - Setelah "Apply" -> otomatis beralih jadi **WiFi CLIENT**, konek ke access
     point penyedia internet.
   - Ini SAMA dengan konsep CA2RXU (web config lalu jalan).

5. **Failover WiFi -> LoRa (konsep CA2RXU)**:
   - GATEWAY: punya WiFi client -> kirim data ke MQTT (internet).
   - NODE: kalau TIDAK ada WiFi -> kirim data ke GATEWAY via LoRa.
   - (Node yang kebetulan dapat WiFi bisa kirim langsung; yang tidak -> LoRa ke gateway.)

6. **Web-based GUI untuk setting** — CONTOH TATA LETAK/GUI dari CA2RXU web config
   (`firm/data`, `firm/src/web_utils.cpp`). Yang bisa disetel lewat web:
   - Peran (Gateway/Node)
   - Sensor aktif/nonaktif (BME280, gas MQ-135, rain, anemo, tilt, ADS1115, EPEVER RS485)
   - Sirine aktif/nonaktif + relay
   - Parameter LoRa (frekuensi 915, SF, BW, CR, TxPower, sync word)
   - WiFi (SSID/pass penyedia internet)
   - MQTT (host ews.example.com, port 1883, user/pass, topic)
   - node_id, kabupaten, kecamatan, koordinat, lokasi
   - Ambang/threshold
   - Setting-setting lain mengikuti kebutuhan (contoh dari CA2RXU web GUI)

## Integrasi dengan server EWS (sudah ada, port 8001)

Firmware GATEWAY publish ke MQTT server EWS (`EWS_YG2UFH/backend`, port 8001):
- Topic data: `yg2ufh/ews/<kabupaten>/<node_id>/data` -> JSON native (BUKAN aprslib)
- Status (retained): `yg2ufh/ews/<kab>/<node>/status` -> online/offline
- Sirine (subscribe): `yg2ufh/ews/<kab>/<gw-id>/siren/cmd` -> ON/OFF/PATTERN
- Format JSON payload: lihat technical-design.md §4 (id wajib; weather/power/health dst opsional)

CATATAN: server EWS pakai `json.loads` native, JSON bersih — konsisten dgn
keputusan lama "jangan aprslib, pakai MQTT biasa". APRS (port 8000, mqtt-server)
adalah project TERPISAH, jangan dicampur.

## Beda dari technical-design.md lama (perlu diselaraskan saat coding)

- technical-design.md §1 & §8 bilang peran dipilih lewat captive portal + pilih
  Node/Gateway. Keputusan baru ini MEMPERTEGAS: default boot = AP, web GUI ala
  CA2RXU, sensor/sirine on-off per perangkat (bukan ditentukan peran), lalu apply
  -> switch ke client. Ini kompatibel, hanya GUI-nya mencontoh CA2RXU.
- Jumper ROLE di PCB: TIDAK jadi penentu peran (peran via web config). Jumper bisa
  dipakai lain / dibiarkan.

## Referensi kode untuk dicontoh (saat coding)
- `c:\aws-kiro\firm` = firmware CA2RXU asli (download user). Pelajari:
  - `src/web_utils.cpp` + `data/` -> web config GUI (AP mode, form setting)
  - `src/wifi_utils.cpp`, `network_manager.cpp` -> AP->client switch, failover
  - `src/lora_utils.cpp` -> RadioLib LoRa TX/RX
  - `src/configuration.cpp` -> simpan/muat config (NVS/JSON)
  - `platformio.ini`, `variants/` -> target board T-Beam
- `c:\aws-kiro\EWS_YG2UFH\docs\technical-design.md` -> format JSON, topic, protokol LoRa
- `c:\aws-kiro\EWS_YG2UFH\backend` -> server EWS (port 8001) yang menerima data

## Library (rencana, dari technical-design.md §9)
RadioLib, Adafruit BME280, Adafruit ADS1X15, ModbusMaster (EPEVER), WiFiManager
atau captive portal custom (CA2RXU pakai web server sendiri), PubSubClient,
ArduinoJson, XPowersLib (AXP2101), TinyGPSPlus.

## Langkah berikutnya (saat mulai coding)
1. Pelajari struktur web config CA2RXU (web_utils.cpp + data/) untuk ditiru GUI-nya.
2. Skeleton firmware PlatformIO: boot AP -> web GUI -> apply -> client.
3. Config schema (JSON/NVS): peran, sensor flags, sirine flag, LoRa, WiFi, MQTT, identitas.
4. NODE path: baca sensor aktif -> paket LoRa -> (atau WiFi/MQTT bila ada WiFi).
5. GATEWAY path: terima LoRa -> JSON -> MQTT publish; subscribe siren/cmd.
6. Failover WiFi<->LoRa.

---

## TAMBAHAN KEPUTUSAN (sesi mockup web config T-Beam)

Tanggal dicatat: sesi desain mockup web UI perangkat. Status: FINAL.

### A. Cara flash firmware ke T-Beam = WEB FLASHER (disetujui user)
- **Web flasher (esp-web-tools)** sebagai cara UTAMA untuk operator/relawan lapangan:
  halaman web statis YG2UFH (bisa di GitHub Pages) → "Connect" → "Install", cukup
  browser Chrome/Edge + kabel USB, TANPA install IDE/driver toolchain.
  Butuh output `firmware.bin` (merged) + `manifest.json` dari hasil `pio run`.
- **PlatformIO/Arduino** tetap dipakai developer (kita) untuk coding/debug/iterasi.
- Sejalan dgn technical-design.md §11 poin 7 ("Web flasher YG2UFH").
- TODO saat firmware jadi: buat halaman web flasher (esp-web-tools) + manifest +
  script build .bin gabungan (esptool merge_bin).

### B. Wilayah WAJIB dropdown bertingkat (anti-typo) — PENTING
- Field **Kabupaten/Kota, Kecamatan, Kelurahan/Desa** di web config HARUS berupa
  **dropdown (select) bertingkat**, BUKAN input teks bebas. Alasan: kabupaten masuk
  ke topic MQTT (`yg2ufh/ews/<kabupaten>/<node_id>/data`); typo = data node tidak
  terbaca backend. Dropdown menghilangkan risiko salah ketik.
- Struktur bertingkat: **Provinsi → Kabupaten/Kota → Kecamatan → Kelurahan/Desa**.
  Pilih provinsi → opsi kabupaten terisi; pilih kabupaten → kecamatan terisi;
  pilih kecamatan → kelurahan terisi.
- **Kelurahan/Desa adalah field BARU** (sebelumnya skema cuma provinsi/kabupaten/
  kecamatan). Tambahkan `kelurahan` sebagai METADATA di payload JSON (ikut kecamatan,
  TIDAK masuk topic agar topic tidak terlalu dalam). Backend perlu menampung field
  `kelurahan` ini (penyesuaian skema DB/dashboard menyusul).
- Nilai yang dikirim (slug) vs label: dropdown tampilkan nama (mis. "Sleman"),
  simpan slug (mis. "sleman") untuk topic/payload.
- Sumber data wilayah: daftar resmi (Kemendagri/BPS) sebagai data JSON yang di-embed
  di firmware (LittleFS) ATAU di-load dari backend. Mockup saat ini hanya contoh
  sebagian (DIY/Sleman) — firmware asli muat daftar lengkap daerah yang dipakai.
  Karena ukuran, pertimbangkan: embed hanya provinsi/kabupaten yang relevan, atau
  fetch dari backend saat AP punya akses (opsional).

### Mockup web UI perangkat (hasil sesi ini)
- `docs/mockup/device-setup.html` = halaman Setup/Config (mode AP) — form ala CA2RXU.
- `docs/mockup/device-status.html` = halaman Status/Dashboard (mode client).
- Gaya mengikuti `docs/mockup/dashboard.html` (tema gelap, aksen merah YG2UFH, Inter,
  Bahasa Indonesia). Firmware web UI asli (web_config.cpp) harus meniru tata letak ini.
