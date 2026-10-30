# Catatan Progres Sesi — EWS YG2UFH

Ringkasan agar mudah lanjut di sesi berikutnya.
Terakhir diperbarui: sesi OLED/dokumentasi/push GitHub.

---

## ✅ SUDAH SELESAI

### Firmware produksi T-Beam (`EWS_YG2UFH/firmware/`)
- PlatformIO, env `ttgo-t-beam-ews`, build HIJAU (Flash 51.3%, RAM 3.7%).
- Satu firmware, dua peran GATEWAY/NODE (dipilih di web config, jumper diabaikan).
- Boot AP → web config → apply → WiFi client. Failover WiFi↔LoRa.
- MQTT JSON native (bukan aprslib), topic `yg2ufh/ews/<kabupaten>/<node_id>/data`.
- LoRa compact packet (n/d/s/t + short keys). Sirine MANUAL-ONLY.
- Field `kelurahan` ikut payload (metadata, TIDAK di topic).
- Pin: LoRa SX1276 SCK5 MISO19 MOSI27 CS18 RST23 DIO026; I2C 21/22; AXP2101 init boot.

### Backend (`EWS_YG2UFH/backend/`)
- FastAPI port 8001, MQTT ingest, SQLite `ews.db`, REST + WebSocket + auth RBAC.
- Support `kelurahan` SUDAH ditambah (tabel kelurahan FK→kecamatan, kolom
  nodes.kelurahan_id, migrasi additive aman, CRUD + schemas + routers). 56 tes lolos.
- Cara run: `.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001`
- Migrasi DB otomatis saat start (init_db PRAGMA-guard ALTER TABLE) — data lama aman.

### Web flasher (`EWS_YG2UFH/webflasher/`)
- esp-web-tools: index.html + manifest.json + firmware-merged.bin (3.94MB, di-commit).
- LIVE di GitHub Pages: https://venougm.github.io/ews_yg2ufh/webflasher/
- Build ulang binary: `powershell -File webflasher\build-merged-bin.ps1`

### Dokumentasi
- `docs/PANDUAN-PERANGKAT.md` — panduan operator (flash, setup, OLED, IO38, troubleshoot) + gambar OLED.
- `docs/mockup/` — device-setup.html, device-status.html, oled-screens.svg/png, dashboard.html, node.html.
- Dokumentasi + komentar kode sudah dirapikan dengan frasa netral.
- Keputusan firmware ada di `docs/firmware-decisions.md`.

### Git / GitHub
- Repo `venougm/ews_yg2ufh` — SEMUA ter-push, sinkron @ commit `8d1d388`.
- Repo `venougm/ews-tbeam-mainboard` (PCB + gerber) — ter-push, sinkron @ `aef3569`.
- Token GitHub yang pernah bocor di remote mainboard: SUDAH di-revoke user + remote dibersihkan.
- Audit keamanan: BERSIH (tidak ada kredensial/token/key ter-commit; .env/config.yaml/ews.db ter-gitignore).

---

## 🔜 BELUM / LANGKAH BERIKUT

### 1. Implementasi OLED + tombol IO38 (SUDAH disepakati, tinggal bangun)
Keputusan final (lihat PANDUAN-PERANGKAT.md §5 + mockup oled-screens.png):
- `display.cpp` saat ini MASIH minimal (cuma showStatus 1 baris). Perlu dibangun multi-halaman.
- 6 layar: Boot, Mode AP (SSID/pass/192.168.4.1), Gateway A (WiFi/MQTT/IP/nodes/Rx-Tx) + B
  (sensor/daya/sirine/uptime), Node A (sensor/daya/GPS fix+sat/`LoRa>GW #seq`) + B failover
  (IP/`WiFi>MQTT`), Alarm (SIAGA/AWAS), Transisi Setup (progress bar).
- Auto-rotate halaman ~4 detik. Indikator: bulatan kanan-atas=online, [GW]/[NODE]=peran.
- **Tombol USER IO38 (GPIO38, active-low) tahan 3 detik → masuk mode AP** untuk edit config.
  Mode AP SEMENTARA: timeout ~5 menit tanpa aktivitas → balik client otomatis.
- Hook data status ke OLED: IP, GPS fix+satelit, TX counter/seq, RSSI, MQTT, baterai, jumlah node.
- CARA: delegasikan ke workflow (sentuh display.cpp/.h, main.cpp, tombol IO38, mode AP timeout).

### 2. Deploy backend kelurahan ke server (user cek lokasi dulu)
- User BESOK cek path repo di server + cara run (uvicorn manual? systemd?).
- Langkah: `git pull origin main` → restart backend → migrasi jalan otomatis.
- Opsi: bikinkan systemd service biar restart rapi (tawarkan ke user).
- Backup `ews.db` dulu sebelum restart (jaga-jaga).

### 3. Temuan non-blocking reviewer firmware (perbaikan nanti, opsional)
- Jalur LoRa fallback node tidak kirim tilt/gas/angin yang jalur WiFi kirim.
- Gateway relay siren/cmd ke 1 sirine lokal untuk topic node manapun (ok utk prototipe).

---

## CATATAN PENTING / ANTI-BENTROK
- Project APRS TERPISAH: `c:\aws-kiro\mqtt-server` (port 8000, aprslib, topic aprs/#, DB aprs.db).
  JANGAN dicampur dengan EWS. mqtt-server ada 2 file belum di-commit (ROADMAP.md, bridge/) — project lain.
- `c:\aws-kiro\firm` = firmware referensi pihak ketiga (download), BUKAN repo, jangan di-push.
- `c:\aws-kiro\aws-credentials` = berisi key/ppk, JANGAN pernah di-push.
- EWS resource: port 8001, MQTT client_id `ews-web-backend`, topic `yg2ufh/ews`, DB `ews.db`.
- Sirine SELALU manual (tidak pernah auto dari sensor).
- Wilayah di web config = dropdown bertingkat (Provinsi→Kabupaten→Kecamatan→Kelurahan), simpan slug.
