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
import subprocess
import time

import paho.mqtt.client as mqtt

# ====================== KONFIGURASI (EDIT DI SINI) ======================
BROKER_HOST = "ISI_ALAMAT_SERVER"   # IP/domain server EWS (broker mosquitto)
BROKER_PORT = 1883
MQTT_USER   = "ews"                 # user mosquitto
MQTT_PASS   = "ISI_PASSWORD_EWS"    # password mosquitto user ews

NODE_ID     = "slm-rpi-01"          # harus sama dgn yg didaftarkan di dashboard
PROVINSI    = "diy"
KABUPATEN   = "sleman"
KECAMATAN   = "ngemplak"
INTERVAL    = 60                    # detik antar kiriman
# ========================================================================

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


def build_payload(seq: int) -> dict:
    """Opsi 1: petakan data Raspi ke field EWS supaya kartu dashboard terisi.
    - weather.temp  <- suhu CPU (°C)   (demo: dipakai sebagai 'suhu')
    - power.soc     <- 100 - RAM used% (demo: sisa RAM sebagai 'kapasitas')
    - health        <- rssi dummy + uptime + fw
    Field yang tak terbaca tidak dikirim (skema field-opsional)."""
    temp = cpu_temp_c()
    load = cpu_load_pct()
    mem = mem_used_pct()
    up = uptime_sec()

    payload: dict = {
        "id": NODE_ID,
        "provinsi": PROVINSI,
        "kabupaten": KABUPATEN,
        "kecamatan": KECAMATAN,
        "ts": int(time.time()),
        "seq": seq,
    }
    weather = {}
    if temp is not None:
        weather["temp"] = temp          # suhu CPU sebagai 'suhu' (demo)
    if load is not None:
        weather["hum"] = load           # beban CPU sebagai 'kelembapan' (demo)
    if weather:
        payload["weather"] = weather

    power = {}
    if mem is not None:
        power["soc"] = round(100.0 - mem, 1)   # sisa RAM sebagai 'kapasitas aki'
    if power:
        payload["power"] = power

    health = {"fw": "rpi-demo-0.1"}
    if up is not None:
        health["uptime"] = up
    payload["health"] = health

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="EWS Raspberry Pi demo sender")
    parser.add_argument("--once", action="store_true", help="kirim sekali lalu keluar")
    parser.add_argument("--interval", type=float, default=INTERVAL)
    args = parser.parse_args()

    client = mqtt.Client(client_id=CLIENT_ID)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(BROKER_HOST, BROKER_PORT)
    client.loop_start()

    topic = f"yg2ufh/ews/{KABUPATEN}/{NODE_ID}/data"
    seq = 1
    try:
        while True:
            payload = build_payload(seq)
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
