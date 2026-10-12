"""Pipeline-injection integration test (modeled on mqtt-server's).

Feeds JSON payloads straight through parse -> store -> broadcast
(on_message_impl / process_reading) against an in-memory DB and a fake
broadcaster list, asserting rows land, the WS message key set matches the
contract, an alarm is broadcast when tilt crosses the threshold, and malformed
input produces no row and no broadcast.
"""

from __future__ import annotations

import json

EXPECTED_READING_KEYS = {"type", "node_id", "kabupaten", "ts", "received_at", "payload", "alarm"}
EXPECTED_ALARM_KEYS = {"type", "level", "source", "reason", "ts"}


def test_valid_reading_lands_in_db_and_broadcasts(fresh_db):
    from app.mqtt_ingest import on_message_impl

    broadcasts = []
    payload = {
        "id": "slm-01",
        "kabupaten": "sleman",
        "ts": 1760000000,
        "weather": {"temp": 27.4},
        "tilt": {"delta": 0.3},
    }
    on_message_impl("yg2ufh/ews/sleman/slm-01/data", json.dumps(payload).encode(), broadcasts.append)

    assert len(broadcasts) == 1  # reading only, no alarm (delta below siaga)
    msg = broadcasts[0]
    assert set(msg.keys()) == EXPECTED_READING_KEYS
    assert msg["type"] == "reading"
    assert msg["node_id"] == "slm-01"
    assert msg["alarm"] is None
    assert msg["payload"]["weather"]["temp"] == 27.4

    latest = fresh_db.get_latest_per_node()
    assert len(latest) == 1 and latest[0]["node_id"] == "slm-01"
    assert len(fresh_db.get_history("slm-01", 24)) == 1


def test_tilt_crossing_awas_emits_alarm(fresh_db):
    from app.mqtt_ingest import on_message_impl

    broadcasts = []
    payload = {"id": "slm-02", "kabupaten": "sleman", "ts": 2, "tilt": {"delta": 6.5}}
    on_message_impl("yg2ufh/ews/sleman/slm-02/data", json.dumps(payload).encode(), broadcasts.append)

    assert len(broadcasts) == 2
    reading, alarm = broadcasts
    assert reading["type"] == "reading"
    assert reading["alarm"] == {"level": "awas", "reason": alarm["reason"]}
    assert set(alarm.keys()) == EXPECTED_ALARM_KEYS
    assert alarm["type"] == "alarm"
    assert alarm["level"] == "awas"
    assert alarm["source"] == "slm-02"


def test_tilt_crossing_siaga_emits_siaga_alarm(fresh_db):
    from app.mqtt_ingest import on_message_impl

    broadcasts = []
    payload = {"id": "slm-03", "kabupaten": "sleman", "ts": 3, "tilt": {"delta": 3.0}}
    on_message_impl("yg2ufh/ews/sleman/slm-03/data", json.dumps(payload).encode(), broadcasts.append)

    assert len(broadcasts) == 2
    assert broadcasts[1]["level"] == "siaga"


def test_malformed_produces_no_row_no_broadcast(fresh_db):
    from app.mqtt_ingest import on_message_impl

    broadcasts = []
    on_message_impl("yg2ufh/ews/sleman/x/data", b"{broken json", broadcasts.append)

    assert broadcasts == []
    assert fresh_db.get_latest_per_node() == []


def test_missing_id_produces_no_row_no_broadcast(fresh_db):
    from app.mqtt_ingest import on_message_impl

    broadcasts = []
    on_message_impl("yg2ufh/ews/sleman/x/data", json.dumps({"kabupaten": "sleman"}).encode(), broadcasts.append)

    assert broadcasts == []
    assert fresh_db.get_latest_per_node() == []
