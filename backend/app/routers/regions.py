"""REST endpoints for the region hierarchy: kabupaten & kecamatan.

All handlers are plain `def` (not `async def`): db.py's sqlite3 calls block, so
FastAPI dispatches each through its own threadpool, keeping the event loop free
for WebSocket broadcasts.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app import db
from app.schemas import KabupatenOut, KecamatanOut

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/kabupaten", response_model=list[KabupatenOut])
def get_kabupaten_route():
    try:
        rows = db.list_kabupaten()
    except Exception as e:
        logger.error("GET /api/kabupaten failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return [KabupatenOut(**row) for row in rows]


@router.post("/kabupaten", response_model=KabupatenOut, status_code=201)
def post_kabupaten_route(body: KabupatenOut):
    try:
        db.add_kabupaten(body.id, body.nama, body.provinsi)
    except Exception as e:
        logger.error("POST /api/kabupaten failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return body


@router.get("/kabupaten/{kab}/kecamatan", response_model=list[KecamatanOut])
def get_kecamatan_route(kab: str):
    try:
        rows = db.list_kecamatan(kab)
    except Exception as e:
        logger.error("GET /api/kabupaten/%s/kecamatan failed: %s", kab, e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return [KecamatanOut(**row) for row in rows]


@router.post("/kabupaten/{kab}/kecamatan", response_model=KecamatanOut, status_code=201)
def post_kecamatan_route(kab: str, body: KecamatanOut):
    try:
        db.add_kecamatan(body.id, body.nama, kab)
    except Exception as e:
        logger.error("POST /api/kabupaten/%s/kecamatan failed: %s", kab, e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    # Reflect the path kabupaten in the response regardless of the body value.
    return KecamatanOut(id=body.id, nama=body.nama, kabupaten_id=kab)
