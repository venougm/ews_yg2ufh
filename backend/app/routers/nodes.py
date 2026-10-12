"""REST endpoints for nodes: list (latest-per-node), register, detail, history.

All handlers are plain `def` (not `async def`): db.py's sqlite3 calls block, so
FastAPI dispatches each through its own threadpool.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Query

from app import db, mqtt_ingest
from app.config import get_settings
from app.schemas import HistoryPointOut, NodeOut

logger = logging.getLogger(__name__)

router = APIRouter()


def _latest_map() -> dict[str, dict]:
    """node_id -> latest-reading row, for merging into the node list/detail."""
    return {row["node_id"]: row for row in db.get_latest_per_node()}


def _node_out(node_id: str, registry: dict | None, latest: dict | None) -> NodeOut:
    """Build a NodeOut from the (optional) registry row and (optional) latest
    reading row. The reading's stored payload wins for kabupaten; the registry
    supplies name/type/kecamatan/coordinates."""
    payload = None
    alarm = None
    ts = None
    received_at = None
    status = None
    kabupaten = None
    lat = None
    lon = None

    if registry is not None:
        kabupaten = registry.get("kabupaten_id")

    if latest is not None:
        payload = json.loads(latest["payload_json"]) if latest.get("payload_json") else None
        ts = latest.get("ts")
        received_at = latest.get("received_at")
        status = latest.get("status")
        kabupaten = latest.get("kabupaten") or kabupaten
        lat = latest.get("lat")
        lon = latest.get("lon")
        if payload is not None:
            alarm = mqtt_ingest.evaluate_alarm(payload)

    return NodeOut(
        node_id=node_id,
        nama=(registry or {}).get("nama"),
        tipe=(registry or {}).get("tipe"),
        kabupaten=kabupaten,
        kecamatan=(registry or {}).get("kecamatan_id"),
        lat=lat if lat is not None else (registry or {}).get("lat"),
        lon=lon if lon is not None else (registry or {}).get("lon"),
        status=status,
        ts=ts,
        received_at=received_at,
        payload=payload,
        alarm=alarm,
    )


@router.get("/nodes", response_model=list[NodeOut])
def get_nodes_route(
    kabupaten: str | None = Query(default=None),
    kecamatan: str | None = Query(default=None),
):
    """Nodes with their latest reading, filtered optionally by kabupaten and
    kecamatan. Includes both registered nodes and nodes seen only via ingest."""
    try:
        registered = {n["node_id"]: n for n in db.list_nodes(kabupaten, kecamatan)}
        latest = _latest_map()
    except Exception as e:
        logger.error("GET /api/nodes failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")

    results = []
    seen = set()
    # Registered nodes first (respecting the region filter).
    for node_id, reg in registered.items():
        results.append(_node_out(node_id, reg, latest.get(node_id)))
        seen.add(node_id)

    # Nodes that only exist via ingest (never manually registered). Apply the
    # kabupaten filter using the reading's stored kabupaten; a kecamatan filter
    # cannot match an unregistered node (kecamatan is registry metadata), so
    # unregistered nodes are omitted when a kecamatan filter is set.
    if not kecamatan:
        for node_id, row in latest.items():
            if node_id in seen:
                continue
            if kabupaten and row.get("kabupaten") != kabupaten:
                continue
            results.append(_node_out(node_id, None, row))

    results.sort(key=lambda n: n.node_id)
    return results


@router.post("/nodes", response_model=NodeOut, status_code=201)
def post_node_route(body: NodeOut):
    """Manually register a node (coordinates/location/grouping). EWS uses manual
    registration, not auto-discovery, for dashboard positions."""
    try:
        db.upsert_node(
            node_id=body.node_id,
            nama=body.nama,
            tipe=body.tipe,
            kabupaten_id=body.kabupaten,
            kecamatan_id=body.kecamatan,
            lat=body.lat,
            lon=body.lon,
        )
        reg = db.get_node(body.node_id)
        latest = db.get_latest_per_node()
        latest_row = next((r for r in latest if r["node_id"] == body.node_id), None)
    except Exception as e:
        logger.error("POST /api/nodes failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return _node_out(body.node_id, reg, latest_row)


@router.get("/nodes/{node_id}", response_model=NodeOut)
def get_node_route(node_id: str):
    try:
        reg = db.get_node(node_id)
        latest = db.get_latest_per_node()
        latest_row = next((r for r in latest if r["node_id"] == node_id), None)
    except Exception as e:
        logger.error("GET /api/nodes/%s failed: %s", node_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")

    if reg is None and latest_row is None:
        raise HTTPException(status_code=404, detail="node not found")
    return _node_out(node_id, reg, latest_row)


@router.get("/nodes/{node_id}/history", response_model=list[HistoryPointOut])
def get_node_history_route(
    node_id: str,
    hours: int = Query(default=None, ge=1, le=8760),
):
    if hours is None:
        hours = get_settings().history_lookback_hours
    try:
        rows = db.get_history(node_id, hours)
    except Exception as e:
        logger.error("GET /api/nodes/%s/history failed: %s", node_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")

    points = []
    for row in rows:
        payload = json.loads(row["payload_json"]) if row.get("payload_json") else None
        points.append(
            HistoryPointOut(received_at=row["received_at"], ts=row.get("ts"), payload=payload)
        )
    return points
