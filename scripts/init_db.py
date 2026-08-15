"""Create a fresh database from app/schema.sql + app/seed.sql.

    python scripts/init_db.py                 # create if missing
    python scripts/init_db.py --reset         # delete and rebuild (destructive)
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# `TTD_DB` points the whole app at another database file. Added 13 Aug for the
# iPad session: the actions being tested are a real delete and a real discount,
# and the only way to try them on realistic data without destroying the shop's
# was to swap files by hand. This is the sibling of `TTD_PHOTO_DIR` in
# app/photos.py, which already exists so a LAN test cannot litter the real photo
# folder — the database deserved the same.
#
# Unset in production, which is every normal run: start.bat sets nothing, so the
# shop laptop always resolves to data/tecoma.db.
DB_PATH = Path(os.environ.get("TTD_DB") or ROOT / "data" / "tecoma.db")
SCHEMA = ROOT / "app" / "schema.sql"
SEED = ROOT / "app" / "seed.sql"


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the database with the pragmas the app expects.

    ALWAYS use this rather than sqlite3.connect() directly. journal_mode is a
    property of the file, but foreign_keys and synchronous are per-connection —
    open the file any other way and you silently lose both.

    synchronous = FULL means every commit is flushed to disk before the app is
    told it succeeded. That is what makes a closed lid or a flat battery safe:
    anything staff have saved is already on disk, not waiting in a buffer. It
    costs a few milliseconds per write, and this app does perhaps fifty writes
    a day, so the trade is free.
    """
    # check_same_thread=False because FastAPI runs a sync route and the
    # dependency that opened its connection on worker threads, and under two
    # iPads at once those are not guaranteed to be the same worker. The
    # connection is still only ever used by one request at a time — app/db.py
    # opens it per request and closes it on the way out — so this relaxes a
    # check that does not apply here rather than allowing real sharing.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete the existing database first")
    args = ap.parse_args()

    # These are gitignored, so a fresh clone won't have them.
    for d in ("photos", "backups", "imports"):
        (ROOT / "data" / d).mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        if not args.reset:
            print(f"Database already exists: {DB_PATH}")
            print("Nothing to do. Use --reset to rebuild it from scratch (destructive).")
            return 0
        confirm = input(f"Delete {DB_PATH} and all its data? Type 'yes': ")
        if confirm.strip().lower() != "yes":
            print("Cancelled.")
            return 1
        for suffix in ("", "-wal", "-shm"):
            Path(str(DB_PATH) + suffix).unlink(missing_ok=True)
        print("Deleted existing database.")

    conn = connect()
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.executescript(SEED.read_text(encoding="utf-8"))
    conn.commit()

    settings = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    conn.close()

    print(f"Created {DB_PATH}")
    print(f"  {settings} settings seeded, no categories (staff create those as they scan)")
    print("\nNext: python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
