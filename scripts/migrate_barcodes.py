"""One-off migration: put the barcode rule into an existing database.

Iteration 3 item 2. `app/schema.sql` now carries the rule as a CHECK
constraint, but SQLite cannot add a constraint to a table that already exists,
so the products table has to be rebuilt — and the rows that would fail the new
constraint have to go first, or the rebuild fails on them.

Three steps, in this order:

  1. Recover what normalising fixes. A leading AIM identifier (']' plus two
     characters) is the gun announcing the symbology, not part of the barcode.
     Stripping it turns ']C10118721274620198' into 16 valid digits, so those
     products keep their name, their photo and their history instead of being
     deleted as junk.
  2. Delete the products that still fail. Their batches go with them through
     ON DELETE CASCADE. A product is never deleted by staff — this is a
     migration cleaning up data the old app allowed, which is a different
     thing, and it is the only place in the codebase that deletes one.
  3. Rebuild `products` with the CHECK constraint and put the indexes back.

Run it against a copy first and read the numbers:

    cp data/tecoma.db /tmp/copy.db
    python scripts/migrate_barcodes.py --db /tmp/copy.db --dry-run
    python scripts/migrate_barcodes.py --db /tmp/copy.db

Then, on the real thing, after `python scripts/backup.py` and an Excel export:

    python scripts/migrate_barcodes.py

The shop laptop does not need this. Its database is built by running the
importer, which applies the same rule from app/catalogue.py as it reads.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.catalogue import parse_barcode  # noqa: E402
from scripts.init_db import DB_PATH, connect  # noqa: E402

# Must match app/schema.sql. Kept as text rather than read from that file
# because the file is a whole schema and this needs exactly one table.
PRODUCTS_DDL = """
CREATE TABLE products_migrated (
    id          INTEGER PRIMARY KEY,
    barcode     TEXT    NOT NULL UNIQUE
                        CHECK (length(barcode) BETWEEN 6 AND 18
                               AND barcode NOT GLOB '*[^0-9]*'),
    name        TEXT    NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    image_path  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL
)
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_products_name     ON products(name)",
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)",
)

FAILS_RULE = """NOT (length(barcode) BETWEEN 6 AND 18
                    AND barcode NOT GLOB '*[^0-9]*')"""


def survey(conn: sqlite3.Connection) -> tuple[list, list, list]:
    """Split the offending products into recoverable, colliding and doomed."""
    rows = conn.execute(
        f"""SELECT id, barcode, name,
                   (SELECT COUNT(*) FROM batches b WHERE b.product_id = p.id) AS batches
              FROM products p
             WHERE {FAILS_RULE}
             ORDER BY id"""
    ).fetchall()

    recoverable, colliding, doomed = [], [], []
    for row in rows:
        fixed, problem = parse_barcode(row["barcode"])
        if problem:
            doomed.append(row)
            continue
        clash = conn.execute(
            "SELECT id, name FROM products WHERE barcode = ? AND id != ?",
            (fixed, row["id"]),
        ).fetchone()
        (colliding if clash else recoverable).append((row, fixed, clash))
    return recoverable, colliding, doomed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change and write nothing")
    ap.add_argument("--yes", action="store_true",
                    help="skip the confirmation prompt (for a scratch copy)")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"No database at {args.db}.")

    conn = connect(args.db)
    conn.row_factory = sqlite3.Row

    already = conn.execute(
        "SELECT COUNT(*) FROM pragma_table_info('products') WHERE name = 'barcode'"
    ).fetchone()[0]
    if not already:
        sys.exit("No products table — is this the right database?")

    if "GLOB" in (conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='products'"
    ).fetchone()[0] or ""):
        print("The products table already carries the barcode CHECK. Nothing to do.")
        return 0

    products_before = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    batches_before = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
    recoverable, colliding, doomed = survey(conn)

    print(f"\n{args.db}")
    print(f"  {products_before} products, {batches_before} batches\n")

    print(f"  Recoverable by stripping the gun's prefix: {len(recoverable)}")
    for row, fixed, _ in recoverable:
        print(f"      {row['name'][:34]:<34} {row['barcode']!r} -> {fixed!r}")

    print(f"\n  To be deleted, with their batches: {len(doomed)} products, "
          f"{sum(r['batches'] for r in doomed)} batches")
    for row in doomed:
        print(f"      {row['name'][:34]:<34} {row['barcode'][:36]!r} "
              f"({row['batches']} batch(es))")

    if colliding:
        # Never happens in the shop's data. If it ever did, the right answer is
        # a merge decided by a person, not a guess made here.
        print(f"\n  COLLISION: {len(colliding)} normalised barcode(s) already exist.")
        for row, fixed, clash in colliding:
            print(f"      id={row['id']} {row['barcode']!r} -> {fixed!r} "
                  f"is already id={clash['id']} ({clash['name'][:30]})")
        sys.exit("\nRefusing to guess how to merge these. Resolve them by hand first.")

    if args.dry_run:
        print("\nDry run — nothing written.")
        return 0

    if args.db == DB_PATH and not args.yes:
        print("\nThis deletes rows from the real database.")
        print("Take a backup and an Excel export first:")
        print("    python scripts/backup.py")
        print("    python scripts/export_xlsx.py")
        if input("\nType 'yes' to go ahead: ").strip().lower() != "yes":
            print("Cancelled.")
            return 1

    # Foreign keys OFF for the rebuild, and this is not optional: with them on,
    # DROP TABLE products performs an implicit DELETE FROM, which fires
    # batches' ON DELETE CASCADE and takes every batch in the shop with it.
    # It is a pragma, so it cannot be changed inside a transaction — hence
    # here, before BEGIN.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")
    try:
        for row, fixed, _ in recoverable:
            conn.execute("UPDATE products SET barcode = ? WHERE id = ?", (fixed, row["id"]))

        # Explicit batch delete rather than leaning on the cascade, which is
        # switched off for the rebuild.
        for row in doomed:
            conn.execute("DELETE FROM batches WHERE product_id = ?", (row["id"],))
            conn.execute("DELETE FROM products WHERE id = ?", (row["id"],))

        conn.execute(PRODUCTS_DDL)
        conn.execute(
            """INSERT INTO products_migrated
                   (id, barcode, name, category_id, image_path, created_at, created_by)
               SELECT id, barcode, name, category_id, image_path, created_at, created_by
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

    products_after = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    batches_after = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
    still_bad = conn.execute(f"SELECT COUNT(*) FROM products WHERE {FAILS_RULE}").fetchone()[0]

    print(f"\n  products: {products_before} -> {products_after}")
    print(f"  batches : {batches_before} -> {batches_after}")
    print(f"  products still failing the rule: {still_bad}")
    print("\nDone. Run: python scripts/check_db.py")
    conn.close()
    return 0 if still_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
