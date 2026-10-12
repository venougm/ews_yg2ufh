"""REST API tests via FastAPI TestClient (no live broker).

Sets MQTT_BROKER_HOST/MQTT_TOPIC_PREFIX and an in-memory DB_PATH before importing
app.main so the lifespan loads valid settings and never crashes on a dead broker.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    os.environ["MQTT_BROKER_HOST"] = "127.0.0.1"
    os.environ["MQTT_TOPIC_PREFIX"] = "yg2ufh/ews"
    os.environ["DB_PATH"] = ":memory:"

    from app.config import reset_settings_cache

    reset_settings_cache()

    from app.main import app

    with TestClient(app) as c:
        yield c


def test_nodes_empty_ok(client):
    r = client.get("/api/nodes")
    assert r.status_code == 200
    assert r.json() == []


def test_kabupaten_post_then_get(client):
    r = client.post("/api/kabupaten", json={"id": "sleman", "nama": "Sleman", "provinsi": "diy"})
    assert r.status_code == 201

    r = client.get("/api/kabupaten")
    assert r.status_code == 200
    assert any(k["id"] == "sleman" for k in r.json())

    # kecamatan under the kabupaten.
    r = client.post("/api/kabupaten/sleman/kecamatan", json={"id": "depok", "nama": "Depok", "kabupaten_id": "sleman"})
    assert r.status_code == 201
    r = client.get("/api/kabupaten/sleman/kecamatan")
    assert r.status_code == 200
    assert any(k["id"] == "depok" for k in r.json())


def test_thresholds_put_then_get(client):
    r = client.get("/api/thresholds")
    assert r.status_code == 200
    assert any(t["scope"] == "global" for t in r.json())

    r = client.put("/api/thresholds", json={"scope": "node:slm-01", "tilt_siaga": 1.5, "tilt_awas": 4.0})
    assert r.status_code == 200

    r = client.get("/api/thresholds")
    scopes = {t["scope"]: t for t in r.json()}
    assert scopes["node:slm-01"]["tilt_awas"] == 4.0


def test_unknown_node_404(client):
    r = client.get("/api/nodes/does-not-exist")
    assert r.status_code == 404


def test_register_node_then_detail(client):
    r = client.post("/api/nodes", json={"node_id": "slm-01", "nama": "Node 1", "kabupaten": "sleman", "kecamatan": "depok", "lat": -7.72, "lon": 110.38})
    assert r.status_code == 201

    r = client.get("/api/nodes/slm-01")
    assert r.status_code == 200
    body = r.json()
    assert body["node_id"] == "slm-01"
    assert body["kabupaten"] == "sleman"
