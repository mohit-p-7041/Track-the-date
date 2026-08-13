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


@pytest.fixture(autouse=True)
def photo_dir(tmp_path: Path, monkeypatch) -> Path:
    """Photos go to a temp folder for every test, never to data/photos.

    Autouse for the same reason the database is temporary: the suite has to be
    safe to run on the shop laptop, and an upload test writing into the real
    photo folder would leave litter that check_db.py then reports on.
    """
    directory = tmp_path / "photos"
    directory.mkdir()
    monkeypatch.setenv("TTD_PHOTO_DIR", str(directory))
    return directory


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
            "INSERT INTO products (barcode, name, category_id) VALUES (?, ?, ?)",
            (barcode, name, category_id),
        ).lastrowid

    # Two statuses only. `resolved` was 'pulled' until 13 Aug, when the four
    # statuses became two — a batch is active or discounted, and anything else
    # that happens to it is a real deletion, so there is no status left that
    # means "dealt with and hidden". It is `discounted` now: still on the shelf,
    # still shown, with a sticker on it.
    batches = {
        "overdue": (ids["monster"], days(-4), "active"),
        "due_soon": (ids["shouty"], days(2), "active"),
        "due_edge": (ids["curly"], days(7), "active"),      # exactly on the window
        "outside": (ids["monster"], days(30), "active"),    # beyond the window
        "discounted": (ids["curly"], days(1), "discounted"),
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


STAFF_NAME = "Test Staff"
STAFF_PIN = "1234"


@pytest.fixture
def anon_client(db_path: Path):
    """The app with nobody signed in. For the login screen and the gate.

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


@pytest.fixture
def staff(db_path: Path) -> dict:
    """One member of staff who can sign in, separate from the `sample` data.

    Named distinctly from `sample`'s user so the two fixtures compose — every
    screen is behind a PIN now, so most tests need both.
    """
    pin_hash, pin_salt = hash_pin(STAFF_PIN)
    conn = connect(db_path)
    user_id = conn.execute(
        "INSERT INTO users (name, pin_hash, pin_salt) VALUES (?, ?, ?)",
        (STAFF_NAME, pin_hash, pin_salt),
    ).lastrowid
    conn.commit()
    conn.close()
    return {"id": user_id, "name": STAFF_NAME, "pin": STAFF_PIN}


@pytest.fixture
def client(anon_client: TestClient, staff: dict):
    """The real app with someone signed in — the state every screen assumes.

    Signs in through the actual login route rather than forging a cookie, so
    if login breaks, every screen test says so.
    """
    response = anon_client.post(
        "/login", data={"user_id": staff["id"], "pin": staff["pin"]}, follow_redirects=False
    )
    assert response.status_code == 303, "the client fixture could not sign in"
    return anon_client
