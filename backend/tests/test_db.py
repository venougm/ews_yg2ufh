"""db layer tests on an in-memory DB (no live broker)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def test_region_crud(fresh_db):
    fresh_db.add_kabupaten("sleman", "Sleman", "diy")
    fresh_db.add_kabupaten("bantul", "Bantul", "diy")
    kabs = fresh_db.list_kabupaten()
    assert {k["id"] for k in kabs} == {"sleman", "bantul"}

    fresh_db.add_kecamatan("depok", "Depok", "sleman")
    fresh_db.add_kecamatan("kalasan", "Kalasan", "sleman")
    kecs = fresh_db.list_kecamatan("sleman")
    assert {k["id"] for k in kecs} == {"depok", "kalasan"}
    assert fresh_db.list_kecamatan("bantul") == []


def test_store_latest_and_history(fresh_db):
    payload1 = {"id": "slm-01", "kabupaten": "sleman", "ts": 1, "weather": {"temp": 25.0}}
    payload2 = {"id": "slm-01", "kabupaten": "sleman", "ts": 2, "weather": {"temp": 26.0}}
    fresh_db.store_reading(payload1)
    fresh_db.store_reading(payload2)

    latest = fresh_db.get_latest_per_node()
    assert len(latest) == 1
    assert latest[0]["node_id"] == "slm-01"
    assert latest[0]["ts"] == 2
    assert latest[0]["status"] == "online"

    history = fresh_db.get_history("slm-01", 24)
    assert len(history) == 2
    # Chronological ascending.
    assert history[0]["ts"] == 1
    assert history[1]["ts"] == 2


def test_resolve_threshold_global_vs_override(fresh_db):
    # Seeded global defaults.
    glob = fresh_db.resolve_threshold("slm-99")
    assert glob == {"tilt_siaga": 2.0, "tilt_awas": 5.0}

    fresh_db.set_threshold("node:slm-01", 1.0, 3.0)
    override = fresh_db.resolve_threshold("slm-01")
    assert override == {"tilt_siaga": 1.0, "tilt_awas": 3.0}
    # Other nodes still use global.
    assert fresh_db.resolve_threshold("slm-02") == {"tilt_siaga": 2.0, "tilt_awas": 5.0}

    rows = fresh_db.get_thresholds()
    assert rows[0]["scope"] == "global"
    assert any(r["scope"] == "node:slm-01" for r in rows)


def test_get_stale_nodes(fresh_db):
    now = datetime.now(timezone.utc)
    # Seed an old last_seen by storing a reading, then rewriting its timestamp.
    fresh_db.store_reading({"id": "slm-01", "kabupaten": "sleman"})
    old = (now - timedelta(seconds=600)).isoformat()
    fresh_db.set_status("slm-01", "online")
    # Force the last_seen_at into the past directly for the test.
    with fresh_db._db_lock:
        fresh_db._conn.execute(
            "UPDATE node_status SET last_seen_at = ? WHERE node_id = ?", (old, "slm-01")
        )
        fresh_db._conn.commit()

    stale = fresh_db.get_stale_nodes(180, now)
    assert stale == ["slm-01"]

    fresh_db.set_status("slm-01", "offline")
    assert fresh_db.get_stale_nodes(180, now) == []


def test_purge_old_readings(fresh_db):
    now = datetime.now(timezone.utc)
    recent = now.isoformat()
    old = (now - timedelta(days=400)).isoformat()
    fresh_db.store_reading({"id": "slm-01", "kabupaten": "sleman", "ts": 1}, received_at=recent)
    fresh_db.store_reading({"id": "slm-01", "kabupaten": "sleman", "ts": 2}, received_at=old)

    deleted = fresh_db.purge_old_readings(365, now)
    assert deleted == 1
    history = fresh_db.get_history("slm-01", 24 * 500)
    assert len(history) == 1
    assert history[0]["ts"] == 1
