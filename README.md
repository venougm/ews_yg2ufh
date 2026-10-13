# EWS_YG2UFH

Early Warning System (EWS) berbasis jaringan sensor LoRa untuk pemantauan
pergerakan tanah / longsor + cuaca + solar, dengan data dikirim ke MQTT server
pribadi `ews.example.com`.

Status: **PERENCANAAN** (belum masuk tahap coding firmware).

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
- T-Beam 433 yang sudah dipakai firmware CA2RXU (2 WX + 1 tracker) TIDAK diganggu — itu project APRS terpisah.

Wilayah: **Yogyakarta, Kabupaten Sleman**.

## Dokumen perencanaan

- [docs/architecture.md](docs/architecture.md) — arsitektur & keputusan desain.
- [docs/decisions.md](docs/decisions.md) — catatan keputusan (open questions & yang sudah fix).
- [docs/bom.md](docs/bom.md) — kebutuhan alat & bahan (sudah dimiliki vs perlu dibeli).
- [docs/technical-design.md](docs/technical-design.md) — cetak biru teknis: JSON, topic MQTT, protokol LoRa, library.

## Komponen project (rencana)

- `firmware/` — firmware EWS (PlatformIO), satu kode untuk Node & Gateway.
- `web-flasher/` — web flasher ber-branding YG2UFH (ESP Web Tools), host di `ews.example.com`.
- `docs/` — dokumentasi perencanaan & desain.
