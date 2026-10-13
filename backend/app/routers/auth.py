"""Auth endpoints: login / logout / me (session cookie, bcrypt verify).

All handlers are plain `def` (not `async def`): db.py's sqlite3 calls block, so
FastAPI dispatches each through its own threadpool. The signed-cookie session is
provided by Starlette's SessionMiddleware (added in main.py); handlers read/write
`request.session`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import get_current_user
from app.schemas import LoginIn
from app.security import verify_password

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login")
def login_route(body: LoginIn, request: Request):
    """Verify credentials; on success store the username in the session and
    return {username, role}. Invalid username OR password both return 401 with
    the same message (do not reveal which part was wrong)."""
    try:
        user = db.get_user(body.username)
        if user is None or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="username atau password salah")
        request.session["user"] = user["username"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("POST /api/login failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return {"username": user["username"], "role": user["role"]}


@router.post("/logout")
def logout_route(request: Request):
    try:
        request.session.clear()
    except Exception as e:
        logger.error("POST /api/logout failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    return {"ok": True}


@router.get("/me")
def me_route(request: Request):
    """Logged out -> {authenticated: false}; logged in -> {authenticated: true,
    username, role}. Always 200 so the frontend can poll it on page load."""
    try:
        user = get_current_user(request)
    except Exception as e:
        logger.error("GET /api/me failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
    if user is None:
        return {"authenticated": False}
    return {"authenticated": True, "username": user["username"], "role": user["role"]}
