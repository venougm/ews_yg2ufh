#!/usr/bin/env python3
"""Pengirim data demo dari Raspberry Pi ke EWS (TANPA sensor tambahan).

Opsi 1 (demo): data kesehatan Raspi (suhu CPU, load, RAM, uptime) dipetakan ke
field EWS yang ada supaya kartu dashboard terisi dan "rame". Ini DEMO untuk
membuktikan jalur data asli Raspi -> MQTT -> backend EWS -> dashboard hidup.
Pemetaan sengaja longgar (suhu CPU ditaruh di weather.temp) — ganti dengan sensor
asli (BME280 dll) nanti; skema EWS field-opsional, jadi tinggal tambah field.

Cara pakai di Raspberry Pi:
  1) pip install paho-mqtt    (sekali saja)
  2) edit 4 nilai di bagian KONFIGURASI di bawah (broker, user, password, node)
  3) jalankan:  python3 rpi_demo_sender.py
     (atau sekali kirim:  python3 rpi_demo_sender.py --once)

node_id HARUS sama persis dengan node yang didaftarkan di dashboard
(menu "+ Tambah Node"), supaya datanya nyambung dan muncul di peta.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time

import paho.mqtt.client as mqtt

# ====================== KONFIGURASI (default; bisa di-override via argumen) ======================
# PENTING: JANGAN tulis password asli di sini lalu commit ke git (repo publik!).
# Beri password lewat argumen --password saat menjalankan, mis.:
#   python3 rpi_demo_sender.py --host localhost --user ews --password 'xxxxx'
BROKER_HOST = "localhost"           # IP/domain server EWS (broker mosquitto)
BROKER_PORT = 1883
MQTT_USER   = "ews"                 # user mosquitto
MQTT_PASS   = ""                    # KOSONGKAN di file; isi lewat --password

NODE_ID     = "slm-rpi-01"          # harus sama dgn yg didaftarkan di dashboard
PROVINSI    = "diy"
KABUPATEN   = "sleman"
KECAMATAN   = "ngemplak"
INTERVAL    = 60                    # detik antar kiriman
# ================================================================================================

CLIENT_ID = "ews-rpi-demo"          # beda dari backend (ews-web-backend) & sim


def cpu_temp_c() -> float | None:
    """Suhu CPU Raspi dalam Celsius (dari /sys, tanpa paket tambahan)."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None


def cpu_load_pct() -> float | None:
    """Perkiraan beban CPU (%) dari load average 1 menit / jumlah core."""
    try:
        load1, _, _ = os.getloadavg()
        cores = os.cpu_count() or 1
        return round(min(load1 / cores * 100.0, 100.0), 1)
    except Exception:
        return None


def mem_used_pct() -> float | None:
    """Persen RAM terpakai dari /proc/meminfo."""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    info[parts[0].strip()] = int(parts[1].strip().split()[0])  # kB
        total = info.get("MemTotal")
        avail = info.get("MemAvailable")
        if total and avail is not None:
            return round((total - avail) / total * 100.0, 1)
    except Exception:
        pass
    return None


def uptime_sec() -> int | None:
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return None


def build_payload(seq: int, node_id: str = NODE_ID, kabupaten: str = KABUPATEN) -> dict:
    """Opsi 1: petakan data Raspi ke field EWS supaya kartu dashboard terisi.
    - weather.temp  <- suhu CPU (°C)   (demo: dipakai sebagai 'suhu')
    - weather.hum   <- beban CPU (%)   (demo: dipakai sebagai 'kelembapan')
    - power.soc     <- 100 - RAM used% (demo: sisa RAM sebagai 'kapasitas')
    - tilt.delta    <- nilai demo kecil (biar kartu Tilt terisi)
    - health        <- uptime + fw

    FALLBACK: jika dijalankan di mesin yang BUKAN Raspi (mis. server, tanpa
    /sys/class/thermal), nilai sensor tak terbaca diganti angka dummy realistis
    supaya kartu dashboard tetap terisi untuk DEMO. Di Raspi asli, nilai asli
    yang dipakai (fallback tidak kepakai)."""
    temp = cpu_temp_c()
    load = cpu_load_pct()
    mem = mem_used_pct()
    up = uptime_sec()

    # Fallback dummy untuk demo di non-Raspi.
    if temp is None:
        temp = round(random.uniform(45.0, 60.0), 1)   # suhu CPU khas Raspi
    if load is None:
        load = round(random.uniform(5.0, 40.0), 1)
    if mem is None:
        mem = round(random.uniform(20.0, 70.0), 1)
    if up is None:
        up = seq * 60

    payload: dict = {
        "id": node_id,
        "provinsi": PROVINSI,
        "kabupaten": kabupaten,
        "kecamatan": KECAMATAN,
        "ts": int(time.time()),
        "seq": seq,
        "weather": {
            "temp": temp,                      # suhu CPU sebagai 'suhu' (demo)
            "hum": load,                       # beban CPU sebagai 'kelembapan' (demo)
            "press": round(random.uniform(1005.0, 1012.0), 1),
        },
        "power": {
            "batt_v": round(random.uniform(12.0, 13.2), 2),
            "pv_v": round(random.uniform(15.0, 19.0), 1),
            "soc": round(100.0 - mem, 1),      # sisa RAM sebagai 'kapasitas aki'
        },
        "tilt": {
            "delta": round(random.uniform(0.0, 1.2), 2),  # kecil, aman (demo)
        },
        "health": {
            "rssi": random.randint(-100, -70),
            "uptime": up,
            "fw": "rpi-demo-0.1",
        },
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="EWS Raspberry Pi demo sender")
    parser.add_argument("--host", default=os.environ.get("MQTT_BROKER_HOST", BROKER_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_BROKER_PORT", BROKER_PORT)))
    parser.add_argument("--user", default=os.environ.get("MQTT_USERNAME", MQTT_USER))
    parser.add_argument("--password", default=os.environ.get("MQTT_PASSWORD", MQTT_PASS),
                        help="password mosquitto (JANGAN taruh di file; pakai argumen ini)")
    parser.add_argument("--node-id", default=NODE_ID)
    parser.add_argument("--kabupaten", default=KABUPATEN)
    parser.add_argument("--once", action="store_true", help="kirim sekali lalu keluar")
    parser.add_argument("--interval", type=float, default=INTERVAL)
    args = parser.parse_args()

    client = mqtt.Client(client_id=CLIENT_ID)
    if args.user:
        client.username_pw_set(args.user, args.password)
    client.connect(args.host, args.port)
    client.loop_start()

    topic = f"yg2ufh/ews/{args.kabupaten}/{args.node_id}/data"
    seq = 1
    try:
        while True:
            payload = build_payload(seq, args.node_id, args.kabupaten)
            client.publish(topic, json.dumps(payload), qos=1)
            print(f"terkirim -> {topic}  seq={seq}  {json.dumps(payload)}")
            seq += 1
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("berhenti.")
    finally:
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
