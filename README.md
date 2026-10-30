# EWS_YG2UFH

Early Warning System (EWS) berbasis jaringan sensor LoRa untuk pemantauan
pergerakan tanah / longsor + cuaca + solar, dengan data dikirim ke MQTT server
pribadi `ews.example.com`.

Status: **IMPLEMENTASI** — firmware, backend, dan web flasher sudah jadi.

👉 **Panduan pemakaian perangkat (operator):** [docs/PANDUAN-PERANGKAT.md](docs/PANDUAN-PERANGKAT.md)
— flashing, setup pertama, cara baca OLED, tombol IO38, troubleshooting.

👉 **Web flasher (flash via browser):** https://venougm.github.io/ews_yg2ufh/webflasher/

## Ringkasan sistem

Jaringan node sensor di satu wilayah. Tiap node membaca sensor, mengirim data
via LoRa ke satu node gateway. Gateway meneruskan semua data ke MQTT server
lewat WiFi/internet. Gateway juga mengendalikan sirine (HANYA manual remote — tidak
otomatis, demi menghindari alarm palsu).

```
[Node sensor] --LoRa--+
[Node sensor] --LoRa--+--> [GATEWAY] --WiFi/MQTT--> ews.example.com:1883 --> dashboard
[Node sensor] --LoRa--+                  |
                                         +--> relay --> SIRINE
```

## Hardware

- Semua perangkat: **LilyGO T-Beam** (ESP32 + LoRa + WiFi + GPS + manajemen baterai AXP).
- Satu firmware untuk semua, peran (Node / Gateway) dan frekuensi dipilih saat setup.
- Prototipe awal: **3× T-Beam 915 MHz** = 2 node + 1 gateway.
- T-Beam 433 yang sudah dipakai project APRS (2 WX + 1 tracker) TIDAK diganggu — itu project terpisah.

Wilayah: **Yogyakarta, Kabupaten Sleman**.

## Dokumentasi

- [docs/PANDUAN-PERANGKAT.md](docs/PANDUAN-PERANGKAT.md) — **panduan operator**: flash, setup, OLED, troubleshooting.
- [firmware/README.md](firmware/README.md) — detail teknis firmware (build, MQTT, paket LoRa, pin map).
- [backend/README.md](backend/README.md) — backend FastAPI (REST, WebSocket, MQTT ingest, auth).
- [docs/technical-design.md](docs/technical-design.md) — cetak biru teknis: JSON, topic MQTT, protokol LoRa, library.
- [docs/architecture.md](docs/architecture.md) — arsitektur & keputusan desain.
- [docs/decisions.md](docs/decisions.md) — catatan keputusan.
- [docs/bom.md](docs/bom.md) — kebutuhan alat & bahan.
- [docs/firmware-decisions.md](docs/firmware-decisions.md) — keputusan firmware (arsitektur, web flasher, dropdown wilayah).

## Komponen project

- `firmware/` — firmware EWS (PlatformIO), satu kode untuk Node & Gateway.
- `backend/` — backend dashboard FastAPI (port 8001, MQTT ingest, SQLite).
- `webflasher/` — web flasher ber-branding YG2UFH (ESP Web Tools), host di GitHub Pages.
- `docs/` — dokumentasi + mockup (web config, status, OLED).
