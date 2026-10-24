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
