"""parse_payload + missing-id handling tests (no live broker)."""

from __future__ import annotations

import json


def test_parse_valid_json():
    from app.mqtt_ingest import parse_payload

    raw = json.dumps({"id": "slm-01", "kabupaten": "sleman", "ts": 1760000000}).encode()
    parsed = parse_payload(raw)
    assert parsed is not None
    assert parsed["id"] == "slm-01"


def test_parse_optional_fields_only():
    from app.mqtt_ingest import parse_payload

    # A payload with just id + a single sensor block is valid (fields optional).
    parsed = parse_payload('{"id": "btl-01", "weather": {"temp": 25.0}}')
    assert parsed is not None
    assert parsed["id"] == "btl-01"
    assert "power" not in parsed


def test_parse_corrupt_returns_none_no_crash():
    from app.mqtt_ingest import parse_payload, parse_failures_counter

    before = parse_failures_counter.count
    assert parse_payload(b"{not valid json") is None
    assert parse_payload(b"") is None
    # A JSON array is valid JSON but not a reading object -> None.
    assert parse_payload(b"[1, 2, 3]") is None
    assert parse_failures_counter.count == before + 3


def test_missing_id_produces_no_store_and_no_broadcast(fresh_db):
    from app.mqtt_ingest import process_reading

    broadcasts = []
    # No 'id' field.
    process_reading({"kabupaten": "sleman", "ts": 1}, broadcasts.append)
    # Empty 'id'.
    process_reading({"id": "   ", "kabupaten": "sleman"}, broadcasts.append)

    assert broadcasts == []
    assert fresh_db.get_latest_per_node() == []
