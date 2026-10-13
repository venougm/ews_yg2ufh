"""Auth dependencies: current user resolution + role guards.

The signed-cookie session (Starlette SessionMiddleware) stores only the username
in `request.session['user']`; the authoritative role is read fresh from the DB on
every request so a role change or deletion takes effect immediately. If the stored
username no longer exists in the DB the session is cleared and the request is
treated as logged out.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app import db


def get_current_user(request: Request) -> dict | None:
    """The logged-in user row (username/role/created_at) or None. Clears the
    session if the stored username no longer resolves to a DB user."""
    username = request.session.get("user")
    if not username:
        return None
    user = db.get_user(username)
    if user is None:
        request.session.clear()
        return None
    return user


def require_login(request: Request) -> dict:
    """Return the current user or raise 401 when not logged in."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="belum login")
    return user


def require_role(*roles: str):
    """Dependency factory: require a logged-in user whose role is in `roles`,
    else 403."""

    def _dependency(request: Request) -> dict:
        user = require_login(request)
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="akses ditolak")
        return user

    return _dependency


require_admin = require_role("admin")
