"""One-off migration: four batch statuses become two, and products stop
carrying a person.

Iteration 3 items 3 and 7. Two changes that need the same table rebuilds, so
they run together rather than rewriting `products` and `batches` twice.

**Statuses.** `active` and `discounted` stay; `pulled` and `sold` are removed.
A batch now ends one of two ways — it gets a discount sticker, or it is deleted,
really deleted. The shop never used either of the removed statuses: 1757
`active` and 583 `pulled` arrived from the import, zero `sold`, zero
`discounted`. The `pulled` rows are unreachable under the new model and go with
it, which is also what happens to a retired account's expired batches.

**`products.created_by`.** Dropped. A batch is something somebody did and keeps
`added_by` / `resolved_by`; a product is just a fact about a barcode the shop
sells. The column turned out to hold nothing at all — 0 rows set, not the 2 the
punch list recorded — so nothing is lost.

**Take the Excel export first and keep the file.** It is the only copy of the
pulled history once this runs, and that is exactly what it was built for.

    python scripts/backup.py
    python scripts/export_xlsx.py
    cp data/tecoma.db /tmp/copy.db
    python scripts/migrate_statuses.py --db /tmp/copy.db --dry-run
    python scripts/migrate_statuses.py --db /tmp/copy.db
    python scripts/migrate_statuses.py            # then for real

The shop laptop does not need this. Its database comes from the importer, which
skips already-expired rows and only ever writes `active`.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.init_db import DB_PATH, connect  # noqa: E402

GONE = ("pulled", "sold")

# Both must match app/schema.sql. Rebuilt rather than altered because SQLite
# cannot add or remove a CHECK constraint in place, and rebuilding is version
# independent — ALTER TABLE ... DROP COLUMN needs SQLite 3.35, and the shop
# laptop has its own Python with its own bundled SQLite.
BATCHES_DDL = """
CREATE TABLE batches_migrated (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    expiry_date TEXT    NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    note        TEXT,
    status      TEXT    NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'discounted')),
    added_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TEXT
)
"""

PRODUCTS_DDL = """
CREATE TABLE products_migrated (
    id          INTEGER PRIMARY KEY,
    barcode     TEXT    NOT NULL UNIQUE
                        CHECK (length(barcode) BETWEEN 6 AND 18
                               AND barcode NOT GLOB '*[^0-9]*'),
    name        TEXT    NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    image_path  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_products_name     ON products(name)",
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_batches_unique_live
           ON batches(product_id, expiry_date)
        WHERE status IN ('active', 'discounted')""",
    """CREATE INDEX IF NOT EXISTS idx_batches_expiry
           ON batches(expiry_date)
        WHERE status IN ('active', 'discounted')""",
    "CREATE INDEX IF NOT EXISTS idx_batches_product ON batches(product_id)",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip the prompt (scratch copies)")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"No database at {args.db}.")

    conn = connect(args.db)
    conn.row_factory = sqlite3.Row

    batches_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='batches'"
    ).fetchone()["sql"]
    has_created_by = conn.execute(
        "SELECT COUNT(*) FROM pragma_table_info('products') WHERE name='created_by'"
    ).fetchone()[0]

    if "pulled" not in batches_sql and not has_created_by:
        print("Already migrated — two statuses, and no products.created_by.")
        return 0

    placeholders = ",".join("?" * len(GONE))
    doomed = conn.execute(
        f"SELECT status, COUNT(*) n FROM batches WHERE status IN ({placeholders}) "
        "GROUP BY status ORDER BY 2 DESC", GONE
    ).fetchall()
    batches_before = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
    attributed = conn.execute(
        "SELECT COUNT(*) FROM products WHERE created_by IS NOT NULL"
    ).fetchone()[0] if has_created_by else 0

    print(f"\n{args.db}")
    print(f"  {batches_before} batches\n")
    print("  Batches to delete, by status:")
    for row in doomed:
        print(f"      {row['status']:<10} {row['n']}")
    if not doomed:
        print("      none")
    print(f"\n  products.created_by: {'present' if has_created_by else 'already gone'}"
          f", {attributed} row(s) set")
    print("\n  Take the Excel export first — it is the only copy of this history.")

    if args.dry_run:
        print("\nDry run — nothing written.")
        return 0

    if args.db == DB_PATH and not args.yes:
        print("\nThis permanently deletes rows from the real database.")
        if input("Type 'yes' to go ahead: ").strip().lower() != "yes":
            print("Cancelled.")
            return 1

    # Foreign keys OFF for the rebuilds, and not optionally: with them on,
    # DROP TABLE products performs an implicit DELETE FROM, which fires
    # batches' ON DELETE CASCADE and takes every batch in the shop. A pragma
    # cannot be changed inside a transaction, so it goes here, before BEGIN.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")
    try:
        conn.execute(f"DELETE FROM batches WHERE status IN ({placeholders})", GONE)

        conn.execute(BATCHES_DDL)
        conn.execute(
            """INSERT INTO batches_migrated
                   (id, product_id, expiry_date, quantity, note, status,
                    added_by, added_at, resolved_by, resolved_at)
               SELECT id, product_id, expiry_date, quantity, note, status,
                      added_by, added_at, resolved_by, resolved_at
                 FROM batches"""
        )
        conn.execute("DROP TABLE batches")
        conn.execute("ALTER TABLE batches_migrated RENAME TO batches")

        if has_created_by:
            conn.execute(PRODUCTS_DDL)
            conn.execute(
                """INSERT INTO products_migrated
                       (id, barcode, name, category_id, image_path, created_at)
                   SELECT id, barcode, name, category_id, image_path, created_at
                     FROM products"""
            )
            conn.execute("DROP TABLE products")
            conn.execute("ALTER TABLE products_migrated RENAME TO products")

        for statement in INDEXES:
            conn.execute(statement)

        orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
        if orphans:
            raise RuntimeError(f"foreign_key_check found {len(orphans)} orphan row(s)")

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    batches_after = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
    statuses = conn.execute(
        "SELECT status, COUNT(*) n FROM batches GROUP BY status ORDER BY 2 DESC"
    ).fetchall()
    left = conn.execute(
        "SELECT COUNT(*) FROM pragma_table_info('products') WHERE name='created_by'"
    ).fetchone()[0]

    print(f"\n  batches: {batches_before} -> {batches_after}")
    for row in statuses:
        print(f"      {row['status']:<12} {row['n']}")
    print(f"  products.created_by: {'STILL PRESENT' if left else 'dropped'}")
    print(f"  products: {conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]}"
          "  (never deleted, even at zero batches)")
    print("\nDone. Run: python scripts/check_db.py")
    conn.close()
    return 1 if left else 0


if __name__ == "__main__":
    raise SystemExit(main())
