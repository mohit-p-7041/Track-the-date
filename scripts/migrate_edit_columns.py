"""One-off migration: add `edited_by` and `edited_at` to batches.

Iteration 3 item 5. Correcting a wrong expiry date has to be attributed, the
same as adding or resolving one — "every write a person initiates records who"
is the reason PINs exist.

Purely additive, and the only migration here that is: `ALTER TABLE ADD COLUMN`
needs no table rebuild, deletes nothing, and works on every SQLite version this
will meet. It is still worth a backup, on the principle that anything touching
the shop's file gets one.

    python scripts/migrate_edit_columns.py --db /tmp/copy.db
    python scripts/migrate_edit_columns.py

The shop laptop does not need this — a fresh database gets both columns from
app/schema.sql.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.init_db import DB_PATH, connect  # noqa: E402

COLUMNS = (
    ("edited_by", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
    ("edited_at", "TEXT"),
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"No database at {args.db}.")

    conn = connect(args.db)
    conn.row_factory = sqlite3.Row
    have = {c["name"] for c in conn.execute("PRAGMA table_info(batches)")}

    missing = [(name, decl) for name, decl in COLUMNS if name not in have]
    if not missing:
        print("Already migrated — batches has edited_by and edited_at.")
        return 0

    print(f"\n{args.db}")
    for name, decl in missing:
        print(f"  add batches.{name}  {decl}")

    if args.dry_run:
        print("\nDry run — nothing written.")
        return 0

    for name, decl in missing:
        conn.execute(f"ALTER TABLE batches ADD COLUMN {name} {decl}")
    conn.commit()

    have = {c["name"] for c in conn.execute("PRAGMA table_info(batches)")}
    ok = all(name in have for name, _ in COLUMNS)
    print(f"\n  batches.edited_by / edited_at: {'present' if ok else 'MISSING'}")
    print(f"  rows: {conn.execute('SELECT COUNT(*) FROM batches').fetchone()[0]} (unchanged)")
    print("\nDone. Run: python scripts/check_db.py")
    conn.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
