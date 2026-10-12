"""Broker-free demo injector.

Calls `app.mqtt_ingest.process_reading` directly with sample payloads, so local
verification works with no mosquitto installed. Prints each stored node_id and
whether the reading triggered an alarm. Uses a temporary in-memory DB so it
never touches the runtime data/ews.db.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Allow running as `python tools/inject_sample.py` from the backend/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use an in-memory DB so the demo leaves no files behind.
os.environ.setdefault("DB_PATH", ":memory:")

from app import db, mqtt_ingest  # noqa: E402

_SAMPLES = [
    {
        "id": "slm-01",
        "provinsi": "diy",
        "kabupaten": "sleman",
        "kecamatan": "depok",
        "ts": int(time.time()),
        "seq": 1,
        "weather": {"temp": 27.4, "hum": 82.1, "press": 1008.3},
        "power": {"batt_v": 12.8, "pv_v": 18.2, "soc": 87},
        "health": {"rssi": -92, "snr": 7.5, "uptime": 3600, "fw": "0.1.0"},
        "tilt": {"x": 0.4, "y": 0.1, "delta": 0.3},
    },
    {
        "id": "slm-02",
        "provinsi": "diy",
        "kabupaten": "sleman",
        "kecamatan": "kalasan",
        "ts": int(time.time()),
        "seq": 1,
        "weather": {"temp": 26.1, "hum": 90.4, "press": 1007.1},
        "power": {"batt_v": 12.4, "pv_v": 17.1, "soc": 78},
        "health": {"rssi": -101, "snr": 6.2, "uptime": 7200, "fw": "0.1.0"},
        # Crosses AWAS (>= 5 deg): should emit a reading + an alarm message.
        "tilt": {"x": 6.2, "y": 1.1, "delta": 6.2},
    },
]


def main() -> int:
    db.init_db(os.environ["DB_PATH"])

    broadcasts = []
    for sample in _SAMPLES:
        mqtt_ingest.process_reading(sample, broadcasts.append)

    stored = db.get_latest_per_node()
    print(f"stored {len(stored)} node(s):")
    for row in stored:
        print(f"  - {row['node_id']} (kabupaten={row['kabupaten']}, status={row['status']})")

    readings = [m for m in broadcasts if m["type"] == "reading"]
    alarms = [m for m in broadcasts if m["type"] == "alarm"]
    print(f"broadcast {len(readings)} reading message(s), {len(alarms)} alarm message(s)")
    for a in alarms:
        print(f"  - ALARM level={a['level']} source={a['source']} reason={a['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
