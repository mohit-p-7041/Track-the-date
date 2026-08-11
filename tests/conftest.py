"""Shared fixtures.

Every test gets its own database, built from the real `app/schema.sql` and
`app/seed.sql` in a temp directory. Nothing here touches `data/tecoma.db` —
that file holds 952 real products and the tests must never be able to write
to it, or nobody will dare run them on the shop laptop.

The temp database is built through `scripts.init_db.connect()` like everything
else, so the pragmas under test are the pragmas the app actually uses.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import get_conn  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.security import hash_pin  # noqa: E402
from scripts.init_db import connect  # noqa: E402

SCHEMA = ROOT / "app" / "schema.sql"
SEED = ROOT / "app" / "seed.sql"


def days(n: int) -> str:
    """ISO date n days from today. Negative is the past.

    Tests use offsets rather than fixed dates so they don't quietly start
    failing in November because someone hard-coded August.
    """
    return (dt.date.today() + dt.timedelta(days=n)).isoformat()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A fresh database file with the real schema and settings, no data."""
    path = tmp_path / "test.db"
    conn = connect(path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.executescript(SEED.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def db(db_path: Path):
    """An open connection to the fresh database, for testing rules directly."""
    conn = connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def sample(db: sqlite3.Connection) -> dict:
    """A small realistic dataset covering every state the home screen shows.

    Deliberately includes the awkward cases from the real export: mixed case,
    trailing whitespace, a curly apostrophe. See docs/DATA-NOTES.md.
    """
    pin_hash, pin_salt = hash_pin("1234")
    user_id = db.execute(
        "INSERT INTO users (name, pin_hash, pin_salt) VALUES (?, ?, ?)",
        ("Mohit", pin_hash, pin_salt),
    ).lastrowid

    cat_id = db.execute(
        "INSERT INTO categories (name, created_by) VALUES (?, ?)",
        ("Energy Drinks", user_id),
    ).lastrowid

    products = {
        "monster": ("9300601234567", "Monster Ultra Zero 500ml", cat_id),
        "shouty": ("9300609876543", "C/RIDGE WATER 1L  ", None),   # messy, uncategorised
        "curly": ("9300601111111", "Arnott’s Tim Tam 200g", None),
    }
    ids = {}
    for key, (barcode, name, category_id) in products.items():
        ids[key] = db.execute(
            "INSERT INTO products (barcode, name, category_id, created_by) "
            "VALUES (?, ?, ?, ?)",
            (barcode, name, category_id, user_id),
        ).lastrowid

    batches = {
        "overdue": (ids["monster"], days(-4), "active"),
        "due_soon": (ids["shouty"], days(2), "active"),
        "due_edge": (ids["curly"], days(7), "active"),      # exactly on the window
        "outside": (ids["monster"], days(30), "active"),    # beyond the window
        "resolved": (ids["curly"], days(1), "pulled"),      # dealt with, must not show
    }
    batch_ids = {}
    for key, (product_id, expiry, status) in batches.items():
        batch_ids[key] = db.execute(
            "INSERT INTO batches (product_id, expiry_date, status, added_by) "
            "VALUES (?, ?, ?, ?)",
            (product_id, expiry, status, user_id),
        ).lastrowid

    db.commit()
    return {"user_id": user_id, "cat_id": cat_id, "products": ids, "batches": batch_ids}


@pytest.fixture
def client(db_path: Path):
    """The real app, pointed at the temp database.

    If a future route opens a connection itself instead of depending on
    get_conn, it will read the shop's real database here and these tests will
    behave strangely. That is the signal to fix the route, not the fixture.
    """

    def override():
        conn = connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    fastapi_app.dependency_overrides[get_conn] = override
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
