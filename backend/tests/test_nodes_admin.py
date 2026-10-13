"""Admin node & region management tests (FEAT-001) -- all broker-free.

Covers the reworked POST /api/nodes (full fields incl. lokasi + 409 on
duplicate), PUT /api/nodes/{id} (edit with node_id locked), DELETE
/api/nodes/{id} (unregister but retain readings), region POST RBAC, and the
optional admin-only region DELETE guards.

The `client` fixture mirrors tests/test_auth.py: MQTT env + in-memory DB,
demo-user seeding, known admin password, settings-cache reset, then app.main is
imported inside the fixture with TestClient as a context manager so the lifespan
seeding runs.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    os.environ["MQTT_BROKER_HOST"] = "127.0.0.1"
    os.environ["MQTT_TOPIC_PREFIX"] = "yg2ufh/ews"
    os.environ["DB_PATH"] = ":memory:"
    os.environ["EWS_SEED_DEMO_USERS"] = "true"
    os.environ["EWS_ADMIN_PASSWORD"] = "admin123"
    os.environ["SESSION_SECRET"] = "test-secret"

    from app.config import reset_settings_cache

    reset_settings_cache()

    from app.main import app

    with TestClient(app) as c:
        yield c

    os.environ.pop("EWS_SEED_DEMO_USERS", None)
    os.environ.pop("EWS_ADMIN_PASSWORD", None)


def _login(client, username, password):
    return client.post("/api/login", json={"username": username, "password": password})


def _register_node(client, node_id="slm-01", **overrides):
    body = {
        "node_id": node_id,
        "nama": "Node 1",
        "tipe": "sensor",
        "kabupaten": "sleman",
        "kecamatan": "depok",
        "lat": -7.72,
        "lon": 110.38,
        "lokasi": "Lereng Merapi",
    }
    body.update(overrides)
    return client.post("/api/nodes", json=body)


# ---------------------------------------------------------------------------
# POST /api/nodes -- full fields incl. lokasi, 409 on duplicate, validation
# ---------------------------------------------------------------------------

def test_post_node_full_fields_roundtrip(client):
    assert _login(client, "admin", "admin123").status_code == 200

    assert _register_node(client).status_code == 201

    # GET /api/nodes round-trips lat/lon.
    r = client.get("/api/nodes")
    assert r.status_code == 200
    nodes = {n["node_id"]: n for n in r.json()}
    assert "slm-01" in nodes
    assert nodes["slm-01"]["lat"] == -7.72
    assert nodes["slm-01"]["lon"] == 110.38

    # GET /api/nodes/{id} reflects the stored registry metadata.
    r = client.get("/api/nodes/slm-01")
    assert r.status_code == 200
    body = r.json()
    assert body["nama"] == "Node 1"
    assert body["tipe"] == "sensor"
    assert body["kabupaten"] == "sleman"
    assert body["kecamatan"] == "depok"


def test_post_duplicate_node_id_409(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert _register_node(client).status_code == 201
    # Second registration of the same node_id -> 409.
    assert _register_node(client).status_code == 409


def test_post_node_rejects_empty_node_id(client):
    assert _login(client, "admin", "admin123").status_code == 200
    r = client.post("/api/nodes", json={"node_id": "   "})
    assert r.status_code == 422


def test_post_node_rejects_out_of_range_coords(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert _register_node(client, node_id="bad-lat", lat=200.0).status_code == 422
    assert _register_node(client, node_id="bad-lon", lon=-999.0).status_code == 422


def test_post_node_rbac(client):
    node = {"node_id": "slm-01", "nama": "N1"}
    assert client.post("/api/nodes", json=node).status_code == 401
    assert _login(client, "monitor", "monitor").status_code == 200
    assert client.post("/api/nodes", json=node).status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/nodes/{node_id} -- edit, node_id locked, RBAC
# ---------------------------------------------------------------------------

def test_put_node_edits_fields(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert _register_node(client).status_code == 201

    r = client.put(
        "/api/nodes/slm-01",
        json={
            "nama": "Node Satu",
            "tipe": "gateway",
            "kabupaten": "sleman",
            "kecamatan": "depok",
            "lat": -7.70,
            "lon": 110.41,
            "lokasi": "Pos Pantau Baru",
        },
    )
    assert r.status_code == 200
    assert r.json()["node_id"] == "slm-01"

    r = client.get("/api/nodes/slm-01")
    body = r.json()
    assert body["nama"] == "Node Satu"
    assert body["tipe"] == "gateway"
    assert body["lat"] == -7.70
    assert body["lon"] == 110.41


def test_put_node_id_is_locked_to_path(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert _register_node(client).status_code == 201

    # Body cannot carry node_id (NodeUpdateIn has no such field); the path wins.
    r = client.put("/api/nodes/slm-01", json={"nama": "Renamed", "node_id": "evil-02"})
    assert r.status_code == 200
    assert r.json()["node_id"] == "slm-01"

    # The rogue id never created a second node.
    r = client.get("/api/nodes")
    ids = {n["node_id"] for n in r.json()}
    assert "evil-02" not in ids
    assert "slm-01" in ids


def test_put_node_promotes_ingest_only(client):
    # A node that was never registered can be promoted via PUT.
    assert _login(client, "admin", "admin123").status_code == 200
    r = client.put("/api/nodes/ingest-9", json={"nama": "Promoted", "lat": -7.0, "lon": 110.0})
    assert r.status_code == 200
    r = client.get("/api/nodes/ingest-9")
    assert r.status_code == 200
    assert r.json()["nama"] == "Promoted"


def test_put_node_rbac(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert _register_node(client).status_code == 201
    client.post("/api/logout")

    # Anonymous -> 401.
    assert client.put("/api/nodes/slm-01", json={"nama": "X"}).status_code == 401

    # monitor -> 403.
    assert _login(client, "monitor", "monitor").status_code == 200
    assert client.put("/api/nodes/slm-01", json={"nama": "X"}).status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/nodes/{node_id} -- unregister, retain readings, RBAC, 404
# ---------------------------------------------------------------------------

def test_delete_node_removes_registration(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert _register_node(client).status_code == 201

    assert client.delete("/api/nodes/slm-01").status_code == 200

    # Absent from GET /api/nodes.
    r = client.get("/api/nodes")
    assert all(n["node_id"] != "slm-01" for n in r.json())


def test_delete_node_retains_readings(client):
    from app import db

    assert _login(client, "admin", "admin123").status_code == 200
    assert _register_node(client, node_id="hist-01").status_code == 201

    # Store a reading directly (no broker) so there is history to preserve.
    now = datetime.now(timezone.utc).isoformat()
    db.store_reading(
        {"id": "hist-01", "ts": 1, "kabupaten": "sleman", "tilt": {"deg": 0.1}},
        received_at=now,
    )
    assert len(db.get_history("hist-01", 24)) == 1

    # Delete the registration -> node_status row gone, readings intact.
    assert client.delete("/api/nodes/hist-01").status_code == 200
    assert db.get_node("hist-01") is None
    assert len(db.get_history("hist-01", 24)) == 1


def test_delete_node_unknown_404(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert client.delete("/api/nodes/nope").status_code == 404


def test_delete_node_rbac(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert _register_node(client).status_code == 201
    client.post("/api/logout")

    assert client.delete("/api/nodes/slm-01").status_code == 401
    assert _login(client, "monitor", "monitor").status_code == 200
    assert client.delete("/api/nodes/slm-01").status_code == 403


# ---------------------------------------------------------------------------
# Region POST stays admin-only
# ---------------------------------------------------------------------------

def test_region_post_rbac(client):
    kab = {"id": "sleman", "nama": "Sleman", "provinsi": "diy"}
    kec = {"id": "depok", "nama": "Depok", "kabupaten_id": "sleman"}

    # Anonymous -> 401.
    assert client.post("/api/kabupaten", json=kab).status_code == 401

    # monitor -> 403.
    assert _login(client, "monitor", "monitor").status_code == 200
    assert client.post("/api/kabupaten", json=kab).status_code == 403
    client.post("/api/logout")

    # admin -> 201.
    assert _login(client, "admin", "admin123").status_code == 200
    assert client.post("/api/kabupaten", json=kab).status_code == 201
    assert client.post("/api/kabupaten/sleman/kecamatan", json=kec).status_code == 201


# ---------------------------------------------------------------------------
# Region DELETE (optional admin endpoints) -- guards + RBAC
# ---------------------------------------------------------------------------

def test_delete_kabupaten_guard_and_success(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert client.post(
        "/api/kabupaten", json={"id": "sleman", "nama": "Sleman", "provinsi": "diy"}
    ).status_code == 201
    assert client.post(
        "/api/kabupaten/sleman/kecamatan",
        json={"id": "depok", "nama": "Depok", "kabupaten_id": "sleman"},
    ).status_code == 201

    # Still referenced by a kecamatan -> 409.
    assert client.delete("/api/kabupaten/sleman").status_code == 409

    # Remove the kecamatan, then the kabupaten can go.
    assert client.delete("/api/kabupaten/sleman/kecamatan/depok").status_code == 200
    assert client.delete("/api/kabupaten/sleman").status_code == 200

    # Unknown -> 404.
    assert client.delete("/api/kabupaten/ghost").status_code == 404


def test_delete_kecamatan_guard_when_node_present(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert client.post(
        "/api/kabupaten", json={"id": "sleman", "nama": "Sleman", "provinsi": "diy"}
    ).status_code == 201
    assert client.post(
        "/api/kabupaten/sleman/kecamatan",
        json={"id": "depok", "nama": "Depok", "kabupaten_id": "sleman"},
    ).status_code == 201
    assert _register_node(client).status_code == 201  # node in kecamatan depok

    # A node still references the kecamatan -> 409.
    assert client.delete("/api/kabupaten/sleman/kecamatan/depok").status_code == 409


def test_region_delete_rbac(client):
    assert client.delete("/api/kabupaten/sleman").status_code == 401
    assert _login(client, "monitor", "monitor").status_code == 200
    assert client.delete("/api/kabupaten/sleman").status_code == 403
