# EWS T-Beam Firmware (YG2UFH)

Firmware untuk sistem peringatan dini (Early Warning System) berbasis LilyGO
**T-Beam v1.2** (ESP32 + LoRa SX1276 @ **915 MHz** + GPS NEO-6M + PMIC AXP2101).

Arsitektur meniru iGate LoRa APRS **CA2RXU**, diadaptasi untuk EWS: **satu
firmware, dua peran** yang dipilih lewat web config — **NODE** (seperti tracker)
dan **GATEWAY** (seperti iGate). MQTT memakai **JSON native** (tanpa aprslib).

---

## Peran

| Peran | Tugas |
|-------|-------|
| **NODE** | Baca sensor di lapangan. Kirim ke MQTT langsung bila ada WiFi; kalau tidak, kirim paket ringkas (compact) ke gateway via LoRa. |
| **GATEWAY** | Terima paket LoRa dari node, mekar-kan jadi JSON penuh, publish ke MQTT internet. Deteksi node hilang. Kelola sirine (manual). |

Peran ditentukan **hanya** dari `Config.identity.role` (0 = NODE, 1 = GATEWAY)
yang diset lewat web config. **Jumper ROLE di PCB (MCP23017 GPB2) TIDAK dibaca**
untuk logika peran.

Sensor dan sirine **fleksibel di kedua peran** — tinggal diaktifkan/dinonaktifkan
lewat web config, bukan ditentukan oleh peran.

---

## Build & Flash (PlatformIO)

`pio` tidak ada di PATH pada mesin build ini, jadi panggil lewat modul Python:

```sh
python -m pip install --upgrade platformio
python -m platformio --version

# compile firmware
python -m platformio run -e ttgo-t-beam-ews

# flash firmware ke board (USB)
python -m platformio run -e ttgo-t-beam-ews -t upload

# upload aset web + default config ke SPIFFS (WAJIB sekali di awal)
python -m platformio run -e ttgo-t-beam-ews -t uploadfs
```

`uploadfs` mengunggah isi folder `data/` ke partisi SPIFFS:
`index.html`, `style.css`, `script.js`, `wilayah.json`, dan `ews_conf.json`
(default config). **Web config tidak akan tampil** kalau `uploadfs` belum
dijalankan.

Env default: `ttgo-t-beam-ews` (lihat `platformio.ini`). Build pertama mengunduh
toolchain + semua `lib_deps` — beri waktu yang cukup.

### Output untuk WEB FLASHER (esp-web-tools)

Cara flashing yang disepakati untuk operator/relawan lapangan adalah **web
flasher** (esp-web-tools): halaman statis + tombol "Connect/Install" di Chrome/Edge
via WebSerial, tanpa perlu install IDE/driver. Halaman flasher itu dibangun
terpisah; di sini kita cukup menghasilkan **satu binary gabungan** (`firmware.bin`
merged) + `manifest.json` yang dikonsumsi esp-web-tools.

Setelah `pio run` menghasilkan artefak di `.pio/build/ttgo-t-beam-ews/`
(`bootloader.bin`, `partitions.bin`, `firmware.bin`), gabungkan jadi satu image
dengan `esptool`:

```sh
# esptool ikut terpasang bersama PlatformIO
python -m esptool --chip esp32 merge_bin -o firmware-merged.bin \
  --flash_mode dio --flash_freq 40m --flash_size 4MB \
  0x1000  .pio/build/ttgo-t-beam-ews/bootloader.bin \
  0x8000  .pio/build/ttgo-t-beam-ews/partitions.bin \
  0xe000  ~/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin \
  0x10000 .pio/build/ttgo-t-beam-ews/firmware.bin
```

> Catatan: aset SPIFFS (`data/`) tidak termasuk di `firmware-merged.bin` di atas.
> Untuk flasher yang juga menanam web UI, tambahkan image SPIFFS pada offset
> partisi `spiffs` (lihat `partitions_ews.csv`, offset `0x3D0000`):
> `python -m platformio run -e ttgo-t-beam-ews -t buildfs` menghasilkan
> `.pio/build/ttgo-t-beam-ews/spiffs.bin`, lalu tambahkan
> `0x3D0000 .pio/build/ttgo-t-beam-ews/spiffs.bin` ke perintah `merge_bin`.

`manifest.json` minimal untuk esp-web-tools:

```json
{
  "name": "EWS T-Beam YG2UFH",
  "version": "0.1.0",
  "builds": [
    {
      "chipFamily": "ESP32",
      "parts": [
        { "path": "firmware-merged.bin", "offset": 0 }
      ]
    }
  ]
}
```

Letakkan `firmware-merged.bin` + `manifest.json` di halaman statis
esp-web-tools (mis. GitHub Pages). Halaman flasher-nya **tidak** dibangun di repo
firmware ini.

---

## Alur konfigurasi: AP → Client

1. **Boot pertama** (atau setelah reset config): tidak ada kredensial WiFi →
   perangkat jadi **Access Point**.
   - SSID: `EWS-<nodeId>` bila `nodeId` sudah ada, selainnya `YG2UFH-EWS-Setup`.
   - Sandi AP default: `1234567890` · IP: `http://192.168.4.1`.
2. Buka `http://192.168.4.1` di browser → tampil form **Setup Perangkat EWS**
   (tema gelap, aksen merah YG2UFH, Bahasa Indonesia; mengikuti
   `docs/mockup/device-setup.html`). Section yang bisa diatur:
   Peran, Identitas & Lokasi, WiFi + Auto-AP, MQTT, LoRa, Sensor, Sirine, Lanjutan.
3. Browser memuat `GET /api/config` (nilai sekarang) dan `GET /api/wilayah`
   (sumber dropdown bertingkat), lalu operator mengisi form.
4. Tekan **Simpan & Jalankan** → `POST /api/config` → firmware memvalidasi,
   menyimpan via `Config.writeFile()` ke `/ews_conf.json` di SPIFFS, membalas,
   lalu **reboot jadi WiFi client** dan mulai bekerja sesuai peran.
5. Kalau WiFi gagal konek dan **Auto-AP** aktif, perangkat kembali jadi AP agar
   bisa di-setting ulang.

### Wilayah = dropdown bertingkat (anti-typo)

Provinsi → Kabupaten/Kota → Kecamatan → Kelurahan/Desa adalah **dropdown
bertingkat** (`<select>`), **bukan input teks bebas**. Pilih provinsi mengisi opsi
kabupaten; kabupaten mengisi kecamatan; kecamatan mengisi kelurahan. Opsi
menampilkan nama (mis. "Sleman") tetapi yang disimpan adalah **slug** huruf kecil
(mis. `sleman`).

Alasan: slug **kabupaten masuk ke topic MQTT**
(`yg2ufh/ews/<kabupaten>/<node_id>/data`) — satu typo memutus routing di backend.
Dropdown menghilangkan risiko salah ketik.

Sumber data: `data/wilayah.json` di SPIFFS (disajikan apa adanya lewat
`GET /api/wilayah`). Seed saat ini hanya contoh **DIY** (Sleman/Bantul/Kulon
Progo/Gunungkidul/Kota Yogyakarta beserta kecamatan + kelurahan), sama dengan
mockup. **Daftar lengkap Kemendagri/BPS bisa dimasukkan belakangan** ke file yang
sama tanpa mengubah firmware.

### HTTP API web config

| Metode & path | Fungsi |
|---------------|--------|
| `GET /` | Form setup (mode AP). |
| `GET /api/config` | Config aktif sebagai JSON (bentuk sama dengan `writeFile()`). |
| `GET /api/wilayah` | Pohon wilayah untuk dropdown bertingkat. |
| `POST /api/config` | Validasi → simpan → balas → reboot ke client mode. |

Server HTTP memakai `WebServer.h` dari Arduino core.

---

## Skema topic MQTT & bentuk JSON

Base topic: `yg2ufh/ews/<kabupaten>/<node_id>`. **Kabupaten dan node_id** adalah
satu-satunya bagian dinamis di topic.

| Topic | Arah | Retained | Isi |
|-------|------|----------|-----|
| `.../data` | publish | tidak | JSON pengukuran penuh |
| `.../status` | publish | ya | `online` / `offline` (Last Will = `offline`) |
| `.../siren/state` | publish | ya | `on` / `off` |
| `.../siren/cmd` | subscribe | — | `ON` / `OFF` / `PATTERN:x` |

> **`kelurahan` adalah metadata di payload JSON, BUKAN bagian dari topic.** Ini
> menjaga topic tidak terlalu dalam; kelurahan tetap ikut di dalam JSON data.

Bentuk JSON `.../data` (field opsional — hanya grup sensor yang aktif yang
dikirim):

```json
{
  "id": "slm-01",
  "provinsi": "diy",
  "kabupaten": "sleman",
  "kecamatan": "pakem",
  "kelurahan": "purwobinangun",
  "ts": 1760003200,
  "seq": 1234,
  "weather": { "temp": 27.4, "hum": 82.1, "press": 1008.3 },
  "power":   { "batt_v": 12.8, "pv_v": 18.2, "load_a": 1.1, "soc": 87 },
  "rain":    { "mm": 0.0 },
  "gps":     { "lat": -7.72, "lon": 110.38, "fix": 1 },
  "health":  { "uptime": 3600, "rssi": -58, "fw": "0.1.0" }
}
```

---

## Format paket LoRa (compact)

Paket udara adalah **minimal-JSON ringkas** (bukan JSON gemuk MQTT) — satu baris,
kecil, tetap bisa dibaca manusia. Tanpa prefix APRS. Gateway memekarkan key pendek
kembali jadi JSON penuh. Didokumentasikan identik di `include/ews_packet.h`.

Header (selalu ada): `n` network_id, `d` node_id, `s` seq, `t` msg_type
(`DATA` | `JOIN` | `ACK` | `CMD`).

```jsonc
// DATA (node -> gateway): hanya grup sensor aktif, key pendek
{"n":"ews1","d":"slm-01","s":1234,"t":"DATA",
 "kab":"sleman","kec":"pakem","kel":"purwobinangun",
 "w":{"t":27.4,"h":82.1,"p":1008.3},"pw":{"bv":12.8,"pv":18.2,"soc":87},
 "ti":{"x":5.2,"y":1.1,"dl":0.3},"r":{"mm":0.0},"g":{"la":-7.72,"lo":110.38,"fx":1}}

// JOIN (node daftar ke gateway): identitas + daftar sensor aktif
{"n":"ews1","d":"slm-01","s":1,"t":"JOIN",
 "kab":"sleman","kec":"pakem","kel":"purwobinangun","prov":"diy",
 "sen":["w","pw","ti","r","g"]}

// ACK (gateway -> node): konfirmasi seq
{"n":"ews1","d":"slm-gw-01","s":1234,"t":"ACK"}

// CMD (gateway -> node): mis. ubah interval
{"n":"ews1","d":"slm-01","s":0,"t":"CMD","cmd":"interval","val":60}
```

Pemetaan key pendek → JSON MQTT (dilakukan gateway):
`w`→weather{t→temp,h→hum,p→press}, `pw`→power{bv→batt_v,pv→pv_v,soc},
`ti`→tilt{x,y,dl→delta}, `r`→rain{mm}, `g`→gps{la→lat,lo→lon,fx→fix}.
Gateway mengisi `kabupaten`/`kecamatan`/`kelurahan` dari paket, atau dari tabel
registrasi JOIN bila tidak ada di paket.

---

## Sirine — MANUAL-ONLY

> ⚠ **Sirine HANYA berbunyi dari perintah manual operator** lewat MQTT
> (`.../siren/cmd`). Sirine **tidak pernah** dipicu otomatis dari data sensor
> atau ambang (threshold). Ambang tilt (SIAGA/AWAS) hanya menandai status di
> payload, tidak mengaktifkan relay. Relay sirine ada di MCP23017 GPA4.

---

## Referensi pin map

Sumber tunggal kebenaran: `include/board_pinout.h`. Ringkasan:

| Blok | Pin |
|------|-----|
| LoRa SX1276 | SCK 5, MISO 19, MOSI 27, CS/NSS 18, RST 23, DIO0 26 |
| I2C bus | SDA 21, SCL 22 |
| Alamat I2C | OLED `0x3C`, BME280 `0x76`, MCP23017 `0x20`, ADS1115 `0x48` |
| GPS NEO-6M (Serial1) | RX 34, TX 12 |
| MQ-135 | ADC GPIO35 (input-only) |
| Rain / Anemometer | pulsa GPIO33 / GPIO32 (pull-up, interrupt) |
| RS485 (EPEVER) | DI 13, RO 25, DE/RE 4 |
| DFPlayer | TX 2, RX 15 |
| MCP23017 | LED POWER/LORA/ALARM/FAULT = GPA0..3; **SIREN relay = GPA4**; BTN TEST/SILENCE = GPB0/1; ROLE jumper = GPB2 (**diabaikan**) |
| ADS1115 | AIN0 aki, AIN1 PV (lewat divider) |

> RST=23 / DIO0=26 diambil dari spec tugas (varian CA2RXU v1.2_915 memakai
> RST=14). AXP2101 (XPowersLib) di bus I2C **harus** di-init saat boot untuk
> menyalakan rail daya LoRa + GPS sebelum `radio.begin()` / GPS dipakai.
