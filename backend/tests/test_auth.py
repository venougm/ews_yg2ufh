"""Auth 'Tingkat A' tests: hashing, user db layer, login/me/logout, RBAC
enforcement, user management, and startup seeding -- all broker-free.

The `client` fixture mirrors tests/test_api.py: it sets the MQTT env + an
in-memory DB, enables demo-user seeding and a known admin password, resets the
settings cache, then imports app.main inside the fixture (TestClient as a context
manager so the lifespan runs the seeding).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

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

    # Avoid leaking env into other test modules.
    os.environ.pop("EWS_SEED_DEMO_USERS", None)
    os.environ.pop("EWS_ADMIN_PASSWORD", None)


def _login(client, username, password):
    return client.post("/api/login", json={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def test_hash_password_roundtrip():
    from app.security import hash_password, verify_password

    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong", hashed) is False
    assert verify_password("secret123", "not-a-hash") is False


# ---------------------------------------------------------------------------
# db layer (fresh in-memory DB)
# ---------------------------------------------------------------------------

def test_user_db_crud(fresh_db):
    from app.security import hash_password

    fresh_db.create_user("alice", hash_password("pw"), "operator")
    fresh_db.create_user("bob", hash_password("pw2"), "monitor")

    assert fresh_db.count_users() == 2

    row = fresh_db.get_user("alice")
    assert row["role"] == "operator"
    assert "password_hash" in row  # get_user DOES include the hash (login path)

    listed = fresh_db.list_users()
    assert {u["username"] for u in listed} == {"alice", "bob"}
    # list_users must never leak the hash.
    assert all("password_hash" not in u for u in listed)

    fresh_db.update_role("bob", "admin")
    assert fresh_db.get_user("bob")["role"] == "admin"

    fresh_db.update_password("alice", hash_password("new"))
    assert fresh_db.get_user("alice")["password_hash"] != row["password_hash"]

    assert fresh_db.delete_user("alice") == 1
    assert fresh_db.delete_user("alice") == 0
    assert fresh_db.get_user("alice") is None


# ---------------------------------------------------------------------------
# login / me / logout
# ---------------------------------------------------------------------------

def test_login_success_sets_cookie(client):
    r = _login(client, "admin", "admin123")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert "ews_session" in r.cookies or "ews_session" in client.cookies


def test_login_wrong_password_401(client):
    r = _login(client, "admin", "nope")
    assert r.status_code == 401


def test_login_unknown_user_401(client):
    r = _login(client, "ghost", "whatever")
    assert r.status_code == 401


def test_me_logged_out_then_in_then_out(client):
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.json() == {"authenticated": False}

    assert _login(client, "operator", "operator").status_code == 200
    r = client.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    assert body["username"] == "operator"
    assert body["role"] == "operator"

    assert client.post("/api/logout").status_code == 200
    r = client.get("/api/me")
    assert r.json() == {"authenticated": False}


# ---------------------------------------------------------------------------
# RBAC on data-changing endpoints (KEBUTUHAN A)
# ---------------------------------------------------------------------------

def test_thresholds_put_rbac(client):
    payload = {"scope": "node:slm-01", "tilt_siaga": 1.5, "tilt_awas": 4.0}

    # No login -> 401.
    assert client.put("/api/thresholds", json=payload).status_code == 401

    # monitor -> 403.
    assert _login(client, "monitor", "monitor").status_code == 200
    assert client.put("/api/thresholds", json=payload).status_code == 403
    client.post("/api/logout")

    # operator -> 403.
    assert _login(client, "operator", "operator").status_code == 200
    assert client.put("/api/thresholds", json=payload).status_code == 403
    client.post("/api/logout")

    # admin -> 200.
    assert _login(client, "admin", "admin123").status_code == 200
    assert client.put("/api/thresholds", json=payload).status_code == 200


def test_nodes_and_regions_post_rbac(client):
    node = {"node_id": "slm-01", "nama": "N1", "kabupaten": "sleman", "lat": -7.7, "lon": 110.4}
    kab = {"id": "sleman", "nama": "Sleman", "provinsi": "diy"}

    # No login -> 401.
    assert client.post("/api/nodes", json=node).status_code == 401
    assert client.post("/api/kabupaten", json=kab).status_code == 401

    # monitor -> 403.
    assert _login(client, "monitor", "monitor").status_code == 200
    assert client.post("/api/nodes", json=node).status_code == 403
    assert client.post("/api/kabupaten", json=kab).status_code == 403
    client.post("/api/logout")

    # admin -> 201.
    assert _login(client, "admin", "admin123").status_code == 200
    assert client.post("/api/nodes", json=node).status_code == 201
    assert client.post("/api/kabupaten", json=kab).status_code == 201
    assert client.post(
        "/api/kabupaten/sleman/kecamatan",
        json={"id": "depok", "nama": "Depok", "kabupaten_id": "sleman"},
    ).status_code == 201


# GET stays open regardless of login.
def test_get_endpoints_open(client):
    assert client.get("/api/nodes").status_code == 200
    assert client.get("/api/thresholds").status_code == 200
    assert client.get("/api/kabupaten").status_code == 200


# ---------------------------------------------------------------------------
# User management (admin only)
# ---------------------------------------------------------------------------

def test_user_management_flow(client):
    # Non-admin rejected.
    assert client.get("/api/users").status_code == 401
    assert _login(client, "operator", "operator").status_code == 200
    assert client.get("/api/users").status_code == 403
    assert client.post(
        "/api/users", json={"username": "x", "password": "p", "role": "monitor"}
    ).status_code == 403
    client.post("/api/logout")

    # Admin can manage users.
    assert _login(client, "admin", "admin123").status_code == 200

    r = client.post("/api/users", json={"username": "carol", "password": "pw", "role": "operator"})
    assert r.status_code == 201
    assert r.json()["username"] == "carol"

    # Duplicate -> 409.
    assert client.post(
        "/api/users", json={"username": "carol", "password": "pw", "role": "operator"}
    ).status_code == 409

    # Invalid role -> 400.
    assert client.post(
        "/api/users", json={"username": "zed", "password": "pw", "role": "superuser"}
    ).status_code == 400

    # List includes carol, never a hash.
    r = client.get("/api/users")
    assert r.status_code == 200
    rows = r.json()
    assert any(u["username"] == "carol" for u in rows)
    assert all("password_hash" not in u for u in rows)

    # Delete self -> 400.
    assert client.delete("/api/users/admin").status_code == 400

    # Delete carol -> 200, then 404.
    assert client.delete("/api/users/carol").status_code == 200
    assert client.delete("/api/users/carol").status_code == 404


# ---------------------------------------------------------------------------
# Seeding (db-level, isolated from env)
# ---------------------------------------------------------------------------

def test_seed_admin_only_once(fresh_db):
    from app import auth_seed

    settings = SimpleNamespace(
        admin_user="admin", admin_password=None, seed_demo_users=False
    )
    auth_seed.seed_users(settings)
    assert fresh_db.count_users() == 1
    admin = fresh_db.get_user("admin")
    assert admin["role"] == "admin"

    # Re-seed does not add a second admin.
    auth_seed.seed_users(settings)
    assert fresh_db.count_users() == 1


def test_seed_demo_users(fresh_db):
    from app import auth_seed

    settings = SimpleNamespace(
        admin_user="admin", admin_password="admin123", seed_demo_users=True
    )
    auth_seed.seed_users(settings)

    assert fresh_db.get_user("operator")["role"] == "operator"
    assert fresh_db.get_user("monitor")["role"] == "monitor"
    assert fresh_db.get_user("admin")["role"] == "admin"
