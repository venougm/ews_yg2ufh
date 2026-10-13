"""Admin-only user management: list / create / delete users.

Every handler is guarded by `Depends(require_admin)`; the backend is the real
RBAC enforcer. List responses never include the password hash (db.list_users
omits it). All handlers are plain `def` so blocking sqlite runs in the threadpool.
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.deps import require_admin
from app.schemas import UserCreateIn, UserOut
from app.security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_ROLES = {"monitor", "operator", "admin"}


@router.get("/users", response_model=list[UserOut], dependencies=[Depends(require_admin)])
def list_users_route():
    try:
        rows = db.list_users()
    except Exception as e:
        logger.error("GET /api/users failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return [UserOut(**row) for row in rows]


@router.post("/users", response_model=UserOut, status_code=201,
             dependencies=[Depends(require_admin)])
def create_user_route(body: UserCreateIn):
    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail="role tidak valid")
    try:
        db.create_user(body.username, hash_password(body.password), body.role)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="username sudah ada")
    except Exception as e:
        logger.error("POST /api/users failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    user = db.get_user(body.username)
    return UserOut(username=user["username"], role=user["role"], created_at=user["created_at"])


@router.delete("/users/{username}")
def delete_user_route(username: str, current=Depends(require_admin)):
    if username == current["username"]:
        raise HTTPException(status_code=400, detail="tidak boleh menghapus akun sendiri")
    try:
        deleted = db.delete_user(username)
    except Exception as e:
        logger.error("DELETE /api/users/%s failed: %s", username, e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    if deleted == 0:
        raise HTTPException(status_code=404, detail="user tidak ditemukan")
    return {"ok": True}
