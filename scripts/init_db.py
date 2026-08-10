"""Create a fresh database from app/schema.sql + app/seed.sql.

    python scripts/init_db.py                 # create if missing
    python scripts/init_db.py --reset         # delete and rebuild (destructive)
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "tecoma.db"
SCHEMA = ROOT / "app" / "schema.sql"
SEED = ROOT / "app" / "seed.sql"


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the database with the pragmas the app expects."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL")
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

    cats = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    conn.close()

    print(f"Created {DB_PATH}")
    print(f"  {cats} categories seeded")
    print("\nNext: python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
