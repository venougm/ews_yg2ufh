"""REST endpoints for alarm thresholds: global default + per-node overrides.

All handlers are plain `def` (not `async def`): db.py's sqlite3 calls block, so
FastAPI dispatches each through its own threadpool.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app import db
from app.schemas import ThresholdIn, ThresholdOut

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/thresholds", response_model=list[ThresholdOut])
def get_thresholds_route():
    """The global row plus every node override (scope 'node:<id>')."""
    try:
        rows = db.get_thresholds()
    except Exception as e:
        logger.error("GET /api/thresholds failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return [ThresholdOut(**row) for row in rows]


@router.put("/thresholds", response_model=ThresholdOut)
def put_thresholds_route(body: ThresholdIn):
    """Set the global threshold (scope 'global') or a node override
    (scope 'node:<id>')."""
    try:
        db.set_threshold(body.scope, body.tilt_siaga, body.tilt_awas)
    except Exception as e:
        logger.error("PUT /api/thresholds failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return ThresholdOut(scope=body.scope, tilt_siaga=body.tilt_siaga, tilt_awas=body.tilt_awas)
