"""Startup user seeding.

On an empty users table, create exactly one admin: the password comes from
`settings.admin_password` if set, otherwise a random one is generated and logged
ONCE (the only time it is ever shown). Optionally seed 'operator' and 'monitor'
demo users for UI testing -- never for production. Seeding is idempotent: a
non-empty users table is left untouched, and demo users are only created when
absent.
"""

from __future__ import annotations

import logging
import secrets

from app import db
from app.security import hash_password

logger = logging.getLogger(__name__)

_DEMO_USERS = (("operator", "operator"), ("monitor", "monitor"))


def seed_users(settings) -> None:
    if db.count_users() == 0:
        pw = settings.admin_password
        if not pw:
            pw = secrets.token_urlsafe(12)
            logger.warning(
                "seed: no EWS_ADMIN_PASSWORD set -- generated admin password for "
                "user %r: %s  (SIMPAN -- hanya ditampilkan sekali)",
                settings.admin_user, pw,
            )
        db.create_user(settings.admin_user, hash_password(pw), "admin")

    if settings.seed_demo_users:
        for username, role in _DEMO_USERS:
            if db.get_user(username) is None:
                db.create_user(username, hash_password(username), role)
                logger.info(
                    "seed: demo user %r (role %s) created -- FOR TESTING ONLY, "
                    "not for production", username, role,
                )
