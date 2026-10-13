# Arsitektur EWS_YG2UFH

Dokumen ini merangkum keputusan desain dari sesi perencanaan. Masih bisa berubah.

## 1. Tujuan

Early Warning System (EWS) longsor + stasiun cuaca + monitoring solar. Jaringan
node sensor mengirim data ke MQTT server pribadi `ews.example.com:1883`.
BUKAN APRS — APRS hanya dipakai sebagai inspirasi UX (kemudahan menambah node),
bukan basis kode maupun protokol.

## 2. Topologi

```
JARINGAN EWS 915 MHz (3x T-Beam 915 untuk prototipe)
-----------------------------------------------------
NODE (xN):  T-Beam 915
  - Sensor I2C: BME280 (cuaca), tilt (MPU6050/ADXL345), dll.
  - Sensor analog -> ADS1115 (I2C): extensometer, pH tanah
  - EPEVER via RS485 (modul MAX485 di UART) -- di SETIAP node
  - LoRa -> kirim JSON ke gateway tiap 1 menit (data + heartbeat + status)

GATEWAY (x1):  T-Beam 915
  - LoRa <- terima dari semua node
  - WiFi -> publish ke MQTT ews.example.com:1883
  - Deteksi node hilang -> alarm ke MQTT
  - Relay -> sirine (trigger: manual remote via MQTT + otomatis saat ambang bahaya)
  - (opsional nanti: upgrade ke Raspberry Pi untuk logika lokal)
```

## 3. Keputusan kunci

### 3.1 Satu firmware, dua peran
Flash semua T-Beam dengan `.bin` yang sama. Saat setup (captive portal / WiFiManager),
pilih peran: **Node Sensor** atau **Gateway**. Nambah node = flash + nyalakan + pilih peran.

### 3.2 Frekuensi per-jaringan
Satu jaringan = satu frekuensi. Pilihan 433 / 915 saat setup, HARUS cocok dengan
board fisik (board 915 hanya 915, board 433 hanya 433 — modul radio beda fisik).
Prototipe EWS pakai 915 (3 unit T-Beam 915 baru).

### 3.3 Daya
50 Wp solar + 50 Ah aki => sangat lega. Node tidak perlu deep sleep rumit; bisa
selalu nyala (lebih responsif, cocok untuk sistem keselamatan).

### 3.4 Interval
Kirim tiap 1 menit (versi awal). Rencana lanjut: adaptif (lebih sering saat tilt
berubah mendadak).

### 3.5 Sensor
Firmware dibuat fleksibel: baca "channel" sensor, aktif/non-aktif via config.
Dari sisi firmware, digital-I2C maupun analog-lewat-ADS1115 sama saja (semua jadi angka).
Keputusan hardware analog vs digital bisa ditunda, tidak memblok coding.

| Sensor | Antarmuka | Chip / Catatan |
|---|---|---|
| Cuaca (suhu/lembab/tekanan) | I2C | BME280 (0x76/0x77) |
| Tilt (kemiringan) | I2C | MPU6050 (0x68) / ADXL345 (0x53) |
| Extensometer | I2C via ADC | AS5600 (encoder) atau analog draw-wire -> ADS1115 (0x48) |
| pH tanah | I2C | Atlas EZO-pH (0x63) atau probe analog -> ADS1115 |
| Curah hujan | I2C/UART | DFRobot SEN0575 |
| Tegangan EPEVER | RS485/Modbus RTU | modul MAX485 di UART (BUKAN I2C) |

Prinsip jarak:
- Dalam box (<1-2 m): I2C digital langsung.
- Beberapa meter: sensor analog -> ADS1115 dekat sensor -> I2C ke board.
- Jauh/kritikal: output 4-20 mA (standar industri, kebal noise).

### 3.6 Deteksi node hilang (WAJIB untuk EWS)
Logika di GATEWAY (node mati tak bisa lapor sendiri). Tiap pesan node = heartbeat.
Gateway catat waktu terakhir dengar tiap node; jika > ambang (mis. 3x interval),
publish status `OFFLINE` ke MQTT => alarm. "Node diam" diperlakukan sebagai alarm,
karena bisa berarti node terseret/tertimbun longsor.
Node juga kirim status kesehatan tiap pesan: tegangan baterai (EPEVER/AXP), RSSI, uptime.

### 3.7 Sirine
Di gateway, lewat relay/kontaktor (bukan langsung dari pin GPIO).
Trigger DUA arah:
- Manual remote: dashboard/HP kirim perintah ke topic MQTT -> gateway nyalakan relay.
- Otomatis lokal: gateway nyalakan sirine sendiri bila ada node melaporkan tilt/
  pergerakan melebihi ambang bahaya (harus tetap bunyi walau internet putus).

### 3.8 EPEVER di setiap node
Setiap node punya solar + EPEVER + MAX485 sendiri. Perlu cek pin UART T-Beam yang
bebas (GPS T-Beam memakai UART tertentu) — pakai UART lain atau SoftwareSerial.
Register map Modbus tergantung model controller (Tracer AN / XTRA / Triron / dll.) — TBD.

## 4. MQTT (rencana)

- Broker: `ews.example.com:1883` (user/pass kosong untuk sekarang).
- Topic terstruktur, mis.: `yg2ufh/ews/<wilayah>/<node-id>/<sensor>/<metric>`.
- Perintah sirine: `yg2ufh/ews/<wilayah>/siren/cmd` (ON/OFF).
- Payload JSON.
- Server web flasher ini TERPISAH dari MQTT/APRS server port 8000.

## 5. Web flasher

- Statis, host di `ews.example.com` (WAJIB HTTPS untuk Web Serial).
- Pakai ESP Web Tools (seperti CA2RXU) tapi branding YG2UFH sendiri, firmware sendiri.
- Flash satu firmware ke semua T-Beam; peran & frekuensi dipilih setelah flash (captive portal).
- ESP Web Tools punya "Logs & Console" bawaan -> tidak perlu bikin serial monitor sendiri.

## 6. Hosting & workflow

- Repo GitHub: `venougm`.
- Build lokal dulu sebelum push.
- Firmware: PlatformIO.
