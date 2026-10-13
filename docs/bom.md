# Kebutuhan Alat & Bahan (BOM) — EWS_YG2UFH

Wilayah: **Yogyakarta, Kabupaten Sleman**
Status: perencanaan. Daftar ini dibagi antara yang SUDAH DIMILIKI dan yang PERLU DIBELI.

Legenda:
- [x] sudah dimiliki
- [ ] perlu dibeli / belum ada
- (opsional) = tambahan bertahap, bukan untuk prototipe awal

---

## A. Perangkat inti (per prototipe: 2 node + 1 gateway)

| Item | Jumlah | Status | Catatan |
|---|---|---|---|
| LilyGO T-Beam 915 MHz | 3 | [x] | 2 untuk node, 1 untuk gateway |
| Antena LoRa 915 MHz (SMA) | 3 | [ ] cek | pastikan sesuai 915, bukan 433. Gain lebih tinggi untuk jarak 500m-1km |
| Kabel USB-C (flashing & debug) | 1-3 | [ ] cek | untuk flash via web flasher |

Catatan: T-Beam 433 (2 WX + 1 tracker, firmware CA2RXU) TIDAK dipakai di project ini.

---

## B. Sensor — NODE (tahap awal: BME280 + EPEVER)

| Item | Antarmuka | Status | Catatan |
|---|---|---|---|
| Sensor BME280 (suhu/lembab/tekanan) | I2C | [x] | sudah dimiliki |
| Kabel jumper / konektor I2C | - | [ ] cek | 4 kabel: VCC, GND, SDA, SCL |

### Sensor tambahan NODE (opsional, bertahap)
| Item | Antarmuka | Status | Catatan |
|---|---|---|---|
| (opsional) Sensor tilt MPU6050 atau ADXL345 | I2C | [ ] | kemiringan tanah (inti EWS longsor) |
| (opsional) ADS1115 (ADC 16-bit) | I2C | [ ] | untuk baca sensor analog (extensometer/pH) |
| (opsional) Extensometer (draw-wire / AS5600) | I2C/analog | [ ] | perpanjangan/retakan tanah |
| (opsional) Sensor pH tanah (Atlas EZO-pH / probe analog) | I2C/analog | [ ] | |
| (opsional) Rain gauge DFRobot SEN0575 | I2C/UART | [ ] | curah hujan |

---

## C. Daya & solar (per node, SUDAH DIMILIKI)

| Item | Jumlah | Status | Catatan |
|---|---|---|---|
| Panel surya 50 Wp | per node | [x] | sudah dimiliki |
| Aki/baterai 50 Ah | per node | [x] | sudah dimiliki |
| Solar charge controller EPEVER (Tracer, model TBD) | per node | [x] | model difoto nanti -> menentukan register Modbus |

---

## D. Pembacaan EPEVER (RS485) — per node

| Item | Jumlah | Status | Catatan |
|---|---|---|---|
| Modul RS485-to-TTL (MAX485 / MAX3485) | per node | [ ] | menghubungkan EPEVER ke UART T-Beam |
| Kabel RS485 (RJ45/2-wire A-B) | per node | [ ] cek | sesuai port RS485 EPEVER |

---

## E. Gateway — tambahan khusus

| Item | Jumlah | Status | Catatan |
|---|---|---|---|
| Modul relay 5V (1-2 channel) | 1 | [ ] | mengendalikan sirine (isolasi dari daya besar) |
| Sirine / horn alarm | 1 | [ ] | tegangan sesuai (12V/220V) -> lewat relay/kontaktor |
| (opsional) DFPlayer Mini + speaker + microSD | 1 set | [ ] | suara CUSTOM (rekaman pesan evakuasi) — tahap lanjut |
| Sumber WiFi/internet di lokasi gateway | 1 | [ ] cek | untuk kirim ke MQTT (WiFi / modem 4G) |

---

## F. Enclosure & lapangan (semua perangkat)

| Item | Status | Catatan |
|---|---|---|
| Box outdoor tahan air (IP65+) | [ ] | lindungi elektronik dari hujan Sleman |
| Cable gland | [ ] | lubang kabel kedap air |
| Tiang / mounting | [ ] | pasang node & antena |
| Proteksi surja / grounding | [ ] | PENTING: lokasi terbuka rawan petir |
| Terminal block, sekring, kabel daya | [ ] | distribusi daya rapi & aman |

---

## G. Server & infrastruktur (SUDAH ADA)

| Item | Status | Catatan |
|---|---|---|
| MQTT server `ews.example.com:1883` | [x] | broker sudah jalan |
| Server web flasher `ews.example.com` (HTTPS) | [ ] | WAJIB HTTPS untuk Web Serial. Terpisah dari MQTT/APRS :8000 |
| Repo GitHub `venougm` | [x] | |

---

## Ringkasan belanja prioritas (untuk prototipe BME280 + EPEVER)

Minimum agar 1 node + 1 gateway bisa jalan end-to-end:
1. Antena LoRa 915 (3x) — jika belum ada
2. Modul RS485 MAX485 (per node) + kabel RS485
3. Modul relay 5V + sirine (gateway)
4. Box outdoor + cable gland + proteksi petir
5. Sumber WiFi/internet di gateway

Sudah dimiliki: T-Beam 915 (3), BME280, panel surya 50Wp, aki 50Ah, EPEVER Tracer.
