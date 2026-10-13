"""SQLite storage layer (EWS region hierarchy + readings + thresholds).

Owns one module-level connection created with `check_same_thread=False`, plus one
module-level `threading.Lock` (`_db_lock`). Every public function below acquires
`_db_lock` for the entire duration of its SQL work and creates a fresh
`conn.cursor()` inside that locked section -- never a shared or module-level
cursor, never a cursor held across calls.

The explicit `_db_lock` removes any dependency on SQLite's compile-time threading
mode: FastAPI's threadpool can run several read requests concurrently while the
MQTT ingest thread writes on its own schedule, and with every public function
serialized through `_db_lock`, only one thread ever touches the connection or
issues SQL at a time.

`_db_lock` is always acquired via `with _db_lock:` so the lock is released even if
the SQL work raises. Each write function additionally wraps its SQL in
`try/except Exception: _conn.rollback(); raise` inside the locked block, so a
failure partway through a multi-statement write leaves no half-committed
transaction behind.

History cutoffs are computed in Python via
`datetime.now(timezone.utc) - timedelta(...)` then `.isoformat()` -- the same
convention used to write `received_at` -- so string comparisons against the ISO
timestamps are correct (SQLite's `datetime('now')` emits a space-separated,
timezone-less string that sorts incorrectly against ISO `received_at`).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_conn: sqlite3.Connection | None = None
_db_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kabupaten (
    id          TEXT PRIMARY KEY,
    nama        TEXT NOT NULL,
    provinsi    TEXT
);

CREATE TABLE IF NOT EXISTS kecamatan (
    id              TEXT PRIMARY KEY,
    nama            TEXT NOT NULL,
    kabupaten_id    TEXT NOT NULL REFERENCES kabupaten(id)
);

-- kabupaten_id/kecamatan_id are stored WITHOUT a FK constraint, mirroring how
-- readings.kabupaten is a plain text column: a node can be registered (or seen
-- via ingest) carrying a kabupaten/kecamatan whose region row does not exist
-- yet, so the registry must not reject it. The region tables remain the source
-- of truth for the dashboard grouping menus.
CREATE TABLE IF NOT EXISTS nodes (
    node_id         TEXT PRIMARY KEY,
    nama            TEXT,
    tipe            TEXT,
    kabupaten_id    TEXT,
    kecamatan_id    TEXT,
    lat             REAL,
    lon             REAL,
    lokasi          TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id         TEXT NOT NULL,
    kabupaten       TEXT,
    ts              INTEGER,
    received_at     TEXT NOT NULL,
    lat             REAL,
    lon             REAL,
    payload_json    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_node_time ON readings (node_id, received_at, id);

CREATE TABLE IF NOT EXISTS node_status (
    node_id         TEXT PRIMARY KEY,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    status          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS thresholds (
    scope       TEXT PRIMARY KEY,
    tilt_siaga  REAL NOT NULL,
    tilt_awas   REAL NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Auth 'Tingkat A' users table. Added via the same executescript in init_db, so
-- CREATE TABLE IF NOT EXISTS makes it an additive, safe migration for existing
-- DBs. password_hash stores a bcrypt hash only -- never plaintext.
CREATE TABLE IF NOT EXISTS users (
    username        TEXT PRIMARY KEY,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
"""

# Default global tilt thresholds (degrees), per technical-design.md §7:
# SIAGA at a 2 degree tilt delta, AWAS at 5 degrees.
_DEFAULT_TILT_SIAGA = 2.0
_DEFAULT_TILT_AWAS = 5.0


def init_db(db_path: str) -> None:
    """(Re)initialize the module-level connection and schema. Safe to call once
    at startup; also used by tests to point at a fresh/in-memory DB. Seeds the
    'global' thresholds row if absent."""
    global _conn
    if db_path != ":memory:":
        parent = Path(db_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)

    # isolation_level left at default: each write issues its own explicit BEGIN.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    conn.execute(
        """
        INSERT INTO thresholds (scope, tilt_siaga, tilt_awas, updated_at)
        VALUES ('global', ?, ?, ?)
        ON CONFLICT(scope) DO NOTHING
        """,
        (_DEFAULT_TILT_SIAGA, _DEFAULT_TILT_AWAS, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    _conn = conn


def _ensure_initialized() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        init_db(os.environ.get("DB_PATH", "./data/ews.db"))
    return _conn


# ---------------------------------------------------------------------------
# Region CRUD
# ---------------------------------------------------------------------------

def add_kabupaten(kab_id: str, nama: str, provinsi: str | None = None) -> None:
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                INSERT INTO kabupaten (id, nama, provinsi)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    nama = excluded.nama,
                    provinsi = excluded.provinsi
                """,
                (kab_id, nama, provinsi),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def list_kabupaten() -> list[dict[str, Any]]:
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute("SELECT id, nama, provinsi FROM kabupaten ORDER BY id ASC")
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def add_kecamatan(kec_id: str, nama: str, kabupaten_id: str) -> None:
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                INSERT INTO kecamatan (id, nama, kabupaten_id)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    nama = excluded.nama,
                    kabupaten_id = excluded.kabupaten_id
                """,
                (kec_id, nama, kabupaten_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def list_kecamatan(kabupaten: str) -> list[dict[str, Any]]:
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nama, kabupaten_id FROM kecamatan WHERE kabupaten_id = ? ORDER BY id ASC",
            (kabupaten,),
        )
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------

def upsert_node(
    node_id: str,
    nama: str | None = None,
    tipe: str | None = None,
    kabupaten_id: str | None = None,
    kecamatan_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    lokasi: str | None = None,
) -> None:
    """Insert or update a node's registration metadata. On conflict, only
    overwrite a column when a non-None value is supplied this call (COALESCE),
    so a bare ingest-time upsert never wipes manually-registered metadata."""
    conn = _ensure_initialized()
    created_at = datetime.now(timezone.utc).isoformat()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                INSERT INTO nodes
                    (node_id, nama, tipe, kabupaten_id, kecamatan_id, lat, lon, lokasi, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    nama = COALESCE(excluded.nama, nodes.nama),
                    tipe = COALESCE(excluded.tipe, nodes.tipe),
                    kabupaten_id = COALESCE(excluded.kabupaten_id, nodes.kabupaten_id),
                    kecamatan_id = COALESCE(excluded.kecamatan_id, nodes.kecamatan_id),
                    lat = COALESCE(excluded.lat, nodes.lat),
                    lon = COALESCE(excluded.lon, nodes.lon),
                    lokasi = COALESCE(excluded.lokasi, nodes.lokasi)
                """,
                (node_id, nama, tipe, kabupaten_id, kecamatan_id, lat, lon, lokasi, created_at),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_node(node_id: str) -> dict[str, Any] | None:
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT node_id, nama, tipe, kabupaten_id, kecamatan_id, lat, lon, lokasi, created_at
            FROM nodes WHERE node_id = ?
            """,
            (node_id,),
        )
        row = cur.fetchone()
        columns = [d[0] for d in cur.description]
    if row is None:
        return None
    return dict(zip(columns, row))


def list_nodes(kabupaten: str | None = None, kecamatan: str | None = None) -> list[dict[str, Any]]:
    """Node registry filtered optionally by kabupaten/kecamatan. Returns the
    registered metadata only (latest readings are merged by get_latest_per_node)."""
    conn = _ensure_initialized()
    sql = (
        "SELECT node_id, nama, tipe, kabupaten_id, kecamatan_id, lat, lon, lokasi, created_at "
        "FROM nodes"
    )
    where = []
    params: list[Any] = []
    if kabupaten:
        where.append("kabupaten_id = ?")
        params.append(kabupaten)
    if kecamatan:
        where.append("kecamatan_id = ?")
        params.append(kecamatan)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY node_id ASC"
    with _db_lock:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


# ---------------------------------------------------------------------------
# Readings + status
# ---------------------------------------------------------------------------

def store_reading(payload: dict[str, Any], received_at: str | None = None) -> str:
    """Insert one `readings` row keyed on payload['id'] and upsert the node's
    `node_status` row to 'online', in a single transaction. The full payload is
    stored as JSON text; node_id/kabupaten/ts/lat/lon are pulled into indexed
    columns. Returns the ISO 8601 UTC `received_at` used for the row so callers
    (e.g. the WS broadcast) can report the same timestamp without a second query.
    """
    conn = _ensure_initialized()
    if received_at is None:
        received_at = datetime.now(timezone.utc).isoformat()
    node_id = payload["id"]
    kabupaten = payload.get("kabupaten")
    ts = payload.get("ts")
    gps = payload.get("gps") if isinstance(payload.get("gps"), dict) else {}
    lat = gps.get("lat")
    lon = gps.get("lon")
    payload_json = json.dumps(payload)
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                INSERT INTO readings
                    (node_id, kabupaten, ts, received_at, lat, lon, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (node_id, kabupaten, ts, received_at, lat, lon, payload_json),
            )
            cur.execute(
                """
                INSERT INTO node_status (node_id, first_seen_at, last_seen_at, status)
                VALUES (?, ?, ?, 'online')
                ON CONFLICT(node_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    status = 'online'
                """,
                (node_id, received_at, received_at),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return received_at


def get_latest_per_node() -> list[dict[str, Any]]:
    """Latest reading per node joined with its status. One row per node that has
    at least one stored reading."""
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT r.node_id, r.kabupaten, r.ts, r.received_at, r.lat, r.lon,
                   r.payload_json, s.status
            FROM readings r
            JOIN (
                SELECT node_id, MAX(id) AS max_id
                FROM readings
                GROUP BY node_id
            ) latest ON latest.max_id = r.id
            LEFT JOIN node_status s ON s.node_id = r.node_id
            ORDER BY r.node_id ASC
            """
        )
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def get_history(node_id: str, hours: int) -> list[dict[str, Any]]:
    """Reading rows for `node_id` within the last `hours`, chronological
    ascending. Cutoff computed in Python (ISO 8601 UTC); queried newest-first
    with LIMIT 10000 so the cap drops the oldest rows, then reversed in Python.
    """
    conn = _ensure_initialized()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT received_at, ts, payload_json
            FROM readings
            WHERE node_id = ?
              AND received_at >= ?
            ORDER BY received_at DESC, id DESC
            LIMIT 10000
            """,
            (node_id, cutoff),
        )
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    result = [dict(zip(columns, row)) for row in rows]
    result.reverse()
    return result


def set_status(node_id: str, status: str) -> None:
    """Set a node's status, creating the node_status row if the node has never
    been seen (first_seen/last_seen stamped now)."""
    conn = _ensure_initialized()
    now = datetime.now(timezone.utc).isoformat()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                INSERT INTO node_status (node_id, first_seen_at, last_seen_at, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET status = excluded.status
                """,
                (node_id, now, now, status),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_stale_nodes(threshold_sec: int, now: datetime | None = None) -> list[str]:
    """node_ids whose last_seen_at is older than now - threshold_sec and whose
    status is not already 'offline'."""
    conn = _ensure_initialized()
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(seconds=threshold_sec)).isoformat()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT node_id FROM node_status
            WHERE last_seen_at < ?
              AND status != 'offline'
            ORDER BY node_id ASC
            """,
            (cutoff,),
        )
        rows = cur.fetchall()
    return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

def get_thresholds() -> list[dict[str, Any]]:
    """The global row plus every node override, global first."""
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT scope, tilt_siaga, tilt_awas, updated_at
            FROM thresholds
            ORDER BY CASE WHEN scope = 'global' THEN 0 ELSE 1 END, scope ASC
            """
        )
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def set_threshold(scope: str, tilt_siaga: float, tilt_awas: float) -> None:
    conn = _ensure_initialized()
    updated_at = datetime.now(timezone.utc).isoformat()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                INSERT INTO thresholds (scope, tilt_siaga, tilt_awas, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scope) DO UPDATE SET
                    tilt_siaga = excluded.tilt_siaga,
                    tilt_awas = excluded.tilt_awas,
                    updated_at = excluded.updated_at
                """,
                (scope, tilt_siaga, tilt_awas, updated_at),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def resolve_threshold(node_id: str) -> dict[str, float]:
    """Resolved tilt thresholds for a node: the node override
    (scope 'node:<id>') if present, else the global row. Falls back to the
    hardcoded defaults only if even the global row is missing."""
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            "SELECT tilt_siaga, tilt_awas FROM thresholds WHERE scope = ?",
            (f"node:{node_id}",),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "SELECT tilt_siaga, tilt_awas FROM thresholds WHERE scope = 'global'"
            )
            row = cur.fetchone()
    if row is None:
        return {"tilt_siaga": _DEFAULT_TILT_SIAGA, "tilt_awas": _DEFAULT_TILT_AWAS}
    return {"tilt_siaga": row[0], "tilt_awas": row[1]}


def purge_old_readings(retention_days: int, now: datetime | None = None) -> int:
    """Delete readings older than `retention_days`. Returns the deleted count."""
    conn = _ensure_initialized()
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=retention_days)).isoformat()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute("DELETE FROM readings WHERE received_at < ?", (cutoff,))
            deleted = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return deleted


# ---------------------------------------------------------------------------
# Users (auth 'Tingkat A')
# ---------------------------------------------------------------------------

def create_user(username: str, password_hash: str, role: str) -> None:
    """Insert a new user. Lets sqlite3.IntegrityError propagate on a duplicate
    username so the router can map it to a 409."""
    conn = _ensure_initialized()
    created_at = datetime.now(timezone.utc).isoformat()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                INSERT INTO users (username, password_hash, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, password_hash, role, created_at),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_user(username: str) -> dict[str, Any] | None:
    """Full user row INCLUDING password_hash (used by login verification). API
    responses must use list_users() which omits the hash."""
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            "SELECT username, password_hash, role, created_at FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        columns = [d[0] for d in cur.description]
    if row is None:
        return None
    return dict(zip(columns, row))


def list_users() -> list[dict[str, Any]]:
    """All users, newest-safe ordering by username. Never returns password_hash."""
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute(
            "SELECT username, role, created_at FROM users ORDER BY username ASC"
        )
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def delete_user(username: str) -> int:
    """Delete a user; returns the number of rows removed (0 if not found)."""
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute("DELETE FROM users WHERE username = ?", (username,))
            deleted = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return deleted


def update_password(username: str, password_hash: str) -> None:
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (password_hash, username),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def update_role(username: str, role: str) -> None:
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                "UPDATE users SET role = ? WHERE username = ?",
                (role, username),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def count_users() -> int:
    conn = _ensure_initialized()
    with _db_lock:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        row = cur.fetchone()
    return int(row[0]) if row else 0
