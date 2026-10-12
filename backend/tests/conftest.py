"""Shared test fixtures. Ensures the backend/ dir is importable as the package
root (so `import app...` works) and provides a fresh in-memory DB fixture."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def fresh_db():
    import app.db as db

    db.init_db(":memory:")
    yield db
