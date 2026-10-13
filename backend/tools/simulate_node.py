"""EWS node simulator: a standalone paho-mqtt publisher.

Publishes realistic EWS node JSON for slm-01 and slm-02 to
`yg2ufh/ews/sleman/<id>/data` every --interval seconds. Occasionally pushes a
tilt.delta across the SIAGA(2 deg)/AWAS(5 deg) thresholds to exercise the
backend alarm path.

ANTI-CONFLICT: the simulator's MQTT client_id MUST NOT equal the backend's
('ews-web-backend') and MUST NOT equal the APRS backend's id either -- a shared
client_id would kick the other client off the broker. Default here is
'ews-node-sim'.

Run (publishes forever every 5s):
    python tools/simulate_node.py --host yg2ufh.mooo.com
Run once (one round of readings, then exit):
    python tools/simulate_node.py --host yg2ufh.mooo.com --once
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time

import paho.mqtt.client as mqtt

try:
    from dotenv import load_dotenv
except Exception:  # dotenv optional for the simulator
    load_dotenv = None

BACKEND_CLIENT_ID = "ews-web-backend"
DEFAULT_CLIENT_ID = "ews-node-sim"

# The simulator must never share the backend's client_id (see module docstring).
assert DEFAULT_CLIENT_ID != BACKEND_CLIENT_ID, "node sim client_id must differ from the backend"

_NODES = [
    {"id": "slm-01", "kecamatan": "depok", "lat": -7.72, "lon": 110.38},
    {"id": "slm-02", "kecamatan": "kalasan", "lat": -7.77, "lon": 110.48},
]


def _build_payload(node: dict, seq: int, force_alarm: bool) -> dict:
    """One realistic reading. Early-stage fields only (weather/power/health) plus
    an occasional tilt block that crosses a threshold when force_alarm is set."""
    tilt_delta = round(random.uniform(0.0, 1.5), 2)
    if force_alarm:
        # Alternate between SIAGA-band (>=2) and AWAS-band (>=5) spikes.
        tilt_delta = random.choice([round(random.uniform(2.1, 4.9), 2),
                                    round(random.uniform(5.1, 8.0), 2)])
    payload = {
        "id": node["id"],
        "provinsi": "diy",
        "kabupaten": "sleman",
        "kecamatan": node["kecamatan"],
        "ts": int(time.time()),
        "seq": seq,
        "weather": {
            "temp": round(random.uniform(24.0, 31.0), 1),
            "hum": round(random.uniform(60.0, 95.0), 1),
            "press": round(random.uniform(1005.0, 1012.0), 1),
        },
        # EPEVER: tegangan aki (batt_v), tegangan solar/PV (pv_v), penggunaan daya
        # (load_a), kapasitas aki (soc). load_a di-kirim HANYA oleh slm-01 untuk
        # mendemokan "field opsional": slm-02 tidak mengirimnya, jadi di dashboard
        # 'Beban' tidak muncul untuk slm-02 tapi muncul untuk slm-01.
        "power": {
            "batt_v": round(random.uniform(12.0, 13.2), 2),
            "pv_v": round(random.uniform(15.0, 19.0), 1),
            "soc": random.randint(70, 100),
            **({"load_a": round(random.uniform(0.2, 1.5), 2)} if node["id"] == "slm-01" else {}),
        },
        "health": {
            "rssi": random.randint(-110, -80),
            "snr": round(random.uniform(5.0, 10.0), 1),
            "uptime": seq * 60,
            "fw": "0.1.0",
        },
        "tilt": {"x": tilt_delta, "y": round(random.uniform(0.0, 1.0), 2), "delta": tilt_delta},
    }
    return payload


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(override=False)

    parser = argparse.ArgumentParser(description="EWS node simulator (MQTT JSON publisher)")
    parser.add_argument("--host", default=os.environ.get("MQTT_BROKER_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_BROKER_PORT", "1883")))
    parser.add_argument("--user", default=os.environ.get("MQTT_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("MQTT_PASSWORD"))
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID,
                        help="MQTT client id (must NOT equal the backend's '%s')" % BACKEND_CLIENT_ID)
    parser.add_argument("--prefix", default=os.environ.get("MQTT_TOPIC_PREFIX", "yg2ufh/ews"))
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between rounds")
    parser.add_argument("--once", action="store_true", help="publish one round and exit")
    args = parser.parse_args()

    if args.client_id == BACKEND_CLIENT_ID:
        parser.error("--client-id must not equal the backend client_id '%s'" % BACKEND_CLIENT_ID)

    client = mqtt.Client(client_id=args.client_id)
    if args.user:
        client.username_pw_set(args.user, args.password)
    client.connect(args.host, args.port)
    client.loop_start()

    seq = 1
    try:
        while True:
            # ~1 in 4 rounds pushes a threshold-crossing tilt to exercise alarms.
            force_alarm = random.random() < 0.25
            for node in _NODES:
                payload = _build_payload(node, seq, force_alarm)
                topic = f"{args.prefix}/sleman/{node['id']}/data"
                client.publish(topic, json.dumps(payload), qos=1)
                print(f"published {topic} seq={seq} tilt_delta={payload['tilt']['delta']}")
            seq += 1
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("stopping simulator")
    finally:
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
