"""Offline-detection db query test."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def test_stale_node_detected(fresh_db):
    now = datetime.now(timezone.utc)
    fresh_db.store_reading({"id": "slm-01", "kabupaten": "sleman"})

    # Push last_seen_at well into the past so it is older than the threshold.
    old = (now - timedelta(seconds=500)).isoformat()
    with fresh_db._db_lock:
        fresh_db._conn.execute(
            "UPDATE node_status SET last_seen_at = ? WHERE node_id = ?", (old, "slm-01")
        )
        fresh_db._conn.commit()

    assert fresh_db.get_stale_nodes(180, now) == ["slm-01"]
    # A fresh node (just stored) is not stale.
    fresh_db.store_reading({"id": "slm-02", "kabupaten": "sleman"})
    assert "slm-02" not in fresh_db.get_stale_nodes(180, now)
