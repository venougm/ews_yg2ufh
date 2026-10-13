"""REST endpoints for the region hierarchy: kabupaten & kecamatan.

All handlers are plain `def` (not `async def`): db.py's sqlite3 calls block, so
FastAPI dispatches each through its own threadpool, keeping the event loop free
for WebSocket broadcasts.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.deps import require_admin
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


@router.post("/kabupaten", response_model=KabupatenOut, status_code=201,
             dependencies=[Depends(require_admin)])
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


@router.post("/kabupaten/{kab}/kecamatan", response_model=KecamatanOut, status_code=201,
             dependencies=[Depends(require_admin)])
def post_kecamatan_route(kab: str, body: KecamatanOut):
    try:
        db.add_kecamatan(body.id, body.nama, kab)
    except Exception as e:
        logger.error("POST /api/kabupaten/%s/kecamatan failed: %s", kab, e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    # Reflect the path kabupaten in the response regardless of the body value.
    return KecamatanOut(id=body.id, nama=body.nama, kabupaten_id=kab)


@router.delete("/kabupaten/{kab_id}", dependencies=[Depends(require_admin)])
def delete_kabupaten_route(kab_id: str):
    """Delete a kabupaten (admin only). Refuses with 409 while any kecamatan or
    node still references it, so the region hierarchy is never left dangling."""
    try:
        kec_count = db.count_kecamatan_in_kabupaten(kab_id)
        node_count = db.count_nodes_in_kabupaten(kab_id)
    except Exception as e:
        logger.error("DELETE /api/kabupaten/%s guard failed: %s", kab_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    if kec_count > 0 or node_count > 0:
        raise HTTPException(
            status_code=409,
            detail="kabupaten masih dipakai kecamatan/node",
        )
    try:
        removed = db.delete_kabupaten(kab_id)
    except Exception as e:
        logger.error("DELETE /api/kabupaten/%s failed: %s", kab_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    if removed == 0:
        raise HTTPException(status_code=404, detail="kabupaten tidak ditemukan")
    return {"ok": True}


@router.delete("/kabupaten/{kab}/kecamatan/{kec_id}",
               dependencies=[Depends(require_admin)])
def delete_kecamatan_route(kab: str, kec_id: str):
    """Delete a kecamatan (admin only). Refuses with 409 while any node still
    references it. `kab` is part of the path for URL symmetry; deletion keys on
    kec_id (globally unique)."""
    try:
        node_count = db.count_nodes_in_kecamatan(kec_id)
    except Exception as e:
        logger.error(
            "DELETE /api/kabupaten/%s/kecamatan/%s guard failed: %s",
            kab, kec_id, e, exc_info=True,
        )
        raise HTTPException(status_code=500, detail="internal error")
    if node_count > 0:
        raise HTTPException(status_code=409, detail="kecamatan masih dipakai node")
    try:
        removed = db.delete_kecamatan(kec_id)
    except Exception as e:
        logger.error(
            "DELETE /api/kabupaten/%s/kecamatan/%s failed: %s",
            kab, kec_id, e, exc_info=True,
        )
        raise HTTPException(status_code=500, detail="internal error")
    if removed == 0:
        raise HTTPException(status_code=404, detail="kecamatan tidak ditemukan")
    return {"ok": True}
