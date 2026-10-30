# Web Flasher EWS T-Beam — cara build & host

Halaman ini (`index.html` + `manifest.json` + `firmware-merged.bin`) memakai
[esp-web-tools](https://esphome.github.io/esp-web-tools/) agar operator bisa
flash T-Beam dari browser Chrome/Edge via WebSerial — tanpa Arduino IDE/PlatformIO.

## Isi folder

| File | Fungsi |
|------|--------|
| `index.html` | Halaman flasher (tema YG2UFH, Bahasa Indonesia, tombol Install). |
| `manifest.json` | Dibaca esp-web-tools: menunjuk ke `firmware-merged.bin` di offset 0. |
| `build-merged-bin.ps1` | Script build: compile firmware + SPIFFS, gabung jadi `firmware-merged.bin`. |
| `firmware-merged.bin` | **Hasil build** (tidak di-commit; dihasilkan script). |

## 1. Build `firmware-merged.bin`

Dari root repo (Windows PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File webflasher\build-merged-bin.ps1
```

Script akan:
1. Install PlatformIO bila belum ada.
2. `pio run` — compile firmware (`../firmware`, env `ttgo-t-beam-ews`).
3. `pio run -t buildfs` — bikin image SPIFFS (web UI + `ews_conf.json` default).
4. `esptool merge_bin` — gabung bootloader + partitions + boot_app0 + firmware +
   **SPIFFS** jadi satu `firmware-merged.bin`.

Karena SPIFFS ikut digabung, operator yang flash lewat web flasher langsung dapat
web config UI (dropdown wilayah dll.) tanpa perlu `uploadfs` manual.

> Offset mengikuti `../firmware/partitions_ews.csv`:
> bootloader `0x1000`, partitions `0x8000`, boot_app0 `0xe000`,
> firmware `0x10000`, spiffs `0x3D0000`.

## 2. Tes lokal

WebSerial butuh **HTTPS atau localhost**. Buka via server lokal:

```powershell
# dari dalam folder webflasher
python -m http.server 8080
# lalu buka http://localhost:8080 di Chrome/Edge
```

Buka langsung lewat `file://` **tidak** akan bisa flash (WebSerial diblokir).

## 3. Host produksi (GitHub Pages)

1. Taruh `index.html`, `manifest.json`, `firmware-merged.bin` di folder yang
   di-serve GitHub Pages (atau hosting statis lain berbasis HTTPS).
2. Bagikan URL-nya ke operator. Mereka cukup colok USB + klik Install.

## Update versi firmware

Setiap firmware berubah:
1. Jalankan ulang `build-merged-bin.ps1` → `firmware-merged.bin` baru.
2. Naikkan `"version"` di `manifest.json`.
3. Deploy ulang ke hosting.

## Catatan

- Driver USB-serial: sebagian Windows butuh driver **CP210x** atau **CH9102/CH340**
  (tergantung chip USB di T-Beam). Kalau port tidak muncul, install driver dulu.
- `firmware-merged.bin` sengaja **tidak** di-commit ke git (file biner besar).
  Tambahkan ke `.gitignore` bila perlu, build on-demand / via CI.
