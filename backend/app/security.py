"""Password hashing helpers (bcrypt via passlib).

Passwords are only ever stored as bcrypt hashes -- never plaintext. `hash_password`
produces the stored hash; `verify_password` checks a candidate against a stored
hash and returns False (never raises) on any mismatch or malformed hash, so a
corrupt/legacy value simply fails the login instead of crashing the handler.
"""

from __future__ import annotations

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False
