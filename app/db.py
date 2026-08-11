"""The one place the app opens the database.

Routes take `conn: Connection = Depends(get_conn)` rather than calling
connect() themselves. Two practical reasons:

  - The connection is closed even when a route raises. A leaked SQLite handle
    holds a lock on the file, and on Windows that means the next startup
    backup fails with a permission error rather than anything informative.

  - Tests can point the entire app at a temporary database with
    `app.dependency_overrides[get_conn] = ...`. No environment variables, no
    monkeypatching, and no chance of a test run writing to the shop's real
    data — which is the thing that makes an automated check suite safe to run
    on the laptop.

This still goes through scripts.init_db.connect(), so the pragmas are applied.
Never call sqlite3.connect() directly — see CLAUDE.md.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from scripts.init_db import connect


def get_conn() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency yielding a configured connection, closed on the way out."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
