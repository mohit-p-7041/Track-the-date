"""Sanity-check the database against the rules in SPEC.md.

    python scripts/check_db.py
    python scripts/check_db.py --expect-import    # also assert the beep import numbers

Run this after any schema change, any importer change, and before any commit that
touches data handling. It checks invariants rather than a golden output, so it
stays useful as the shop adds and resolves batches day to day.

Exit code 0 if everything passes, 1 if anything fails — so Claude Code (or a
git hook) can tell whether a change broke something.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.init_db import DB_PATH, connect  # noqa: E402

# Verified numbers from data/imports/beep_2026-08-10.xlsx — see docs/DATA-NOTES.md
EXPECTED_PRODUCTS = 952
EXPECTED_BATCHES = 2340
EXPECTED_PRE_EXPIRED = 583

results: list[tuple[bool, str, str]] = []


def check(passed: bool, label: str, detail: str = "") -> None:
    results.append((passed, label, detail))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--expect-import", action="store_true",
                    help="assert the counts from the original beep import")
    ap.add_argument("--today", type=str, default=None)
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"No database at {args.db}. Run: python scripts/init_db.py")

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    conn = connect(args.db)

    def q(sql: str, *params):
        """Scalar query. Returns None rather than raising if there's no row."""
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None

    # -------------------------------------------------- structural integrity

    check(q("""SELECT COUNT(*) FROM (
                 SELECT product_id, expiry_date FROM batches
                 WHERE status IN ('active','discounted')
                 GROUP BY product_id, expiry_date HAVING COUNT(*) > 1)""") == 0,
          "No duplicate live (product, expiry date) pairs",
          "the core rule — a product cannot have two live batches on one date")

    check(q("SELECT COUNT(*) FROM batches b LEFT JOIN products p ON p.id = b.product_id "
            "WHERE p.id IS NULL") == 0,
          "Every batch belongs to a real product")

    check(q("SELECT COUNT(*) FROM products p LEFT JOIN categories c ON c.id = p.category_id "
            "WHERE p.category_id IS NOT NULL AND c.id IS NULL") == 0,
          "No product points at a category that doesn't exist")

    check(q("SELECT COUNT(*) FROM products WHERE barcode IS NULL OR TRIM(barcode) = ''") == 0,
          "Every product has a barcode")

    check(q("SELECT COUNT(*) FROM batches WHERE expiry_date NOT GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'") == 0,
          "All expiry dates are ISO YYYY-MM-DD",
          "guards against a US-format date sneaking in")

    check(q("SELECT COUNT(*) FROM batches WHERE status NOT IN "
            "('active','discounted','pulled','sold')") == 0,
          "All batch statuses are valid")

    # ------------------------------------------------------- locked decisions

    check(q("SELECT COUNT(*) FROM batches WHERE quantity != 1") == 0,
          "No counting — every quantity is 1",
          "if this fails, someone enabled quantities; confirm that was intended")

    check(q("SELECT COUNT(*) FROM (SELECT name FROM categories "
            "GROUP BY name COLLATE NOCASE HAVING COUNT(*) > 1)") == 0,
          "No categories differing only by case")

    check(q("SELECT COUNT(*) FROM categories WHERE name COLLATE NOCASE = 'Uncategorised'") == 0,
          "No 'Uncategorised' sentinel category",
          "NULL category_id is how uncategorised is represented")

    cols = [d[1] for d in conn.execute("PRAGMA table_info(users)")]
    check("role" not in cols, "Users have no role column", "there are no roles by design")

    check(q("SELECT COUNT(*) FROM settings WHERE key = 'expiry_window_days'") == 1,
          "The 7-day window is configured, not hard-coded")

    # --------------------------------------------------------------- hygiene

    # NOT a failure. Items expire and sit active until someone resolves them —
    # that is the normal state of a shop on a Monday morning, and the whole
    # point of the home screen. Reported below as information only.
    overdue = q("SELECT COUNT(*) FROM batches WHERE status = 'active' AND expiry_date < ?",
                today.isoformat())

    missing = [r["image_path"] for r in conn.execute(
        "SELECT image_path FROM products WHERE image_path IS NOT NULL")
        if not (ROOT / r["image_path"]).exists()]
    check(not missing, "Every referenced photo exists on disk",
          f"missing: {missing[:3]}" if missing else "")

    # ---------------------------------------------------------- import check

    if args.expect_import:
        check(q("SELECT COUNT(*) FROM products") == EXPECTED_PRODUCTS,
              f"Product count is {EXPECTED_PRODUCTS}")
        check(q("SELECT COUNT(*) FROM batches") == EXPECTED_BATCHES,
              f"Batch count is {EXPECTED_BATCHES}")
        check(q("SELECT COUNT(*) FROM batches WHERE note LIKE '%not verified%'")
              == EXPECTED_PRE_EXPIRED,
              f"{EXPECTED_PRE_EXPIRED} pre-migration expired batches are noted")
        check(q("SELECT COUNT(*) FROM batches WHERE status = 'pulled' "
                "AND resolved_by IS NOT NULL") == 0,
              "No name is attached to unverified pre-migration rows")

    # ---------------------------------------------------------------- output

    width = max(len(label) for _, label, _ in results) + 2
    print()
    for passed, label, detail in results:
        mark = "PASS" if passed else "FAIL"
        print(f"  {mark}  {label:<{width}}{detail if not passed else ''}")

    failed = [r for r in results if not r[0]]
    window = int(q("SELECT value FROM settings WHERE key = 'expiry_window_days'") or 7)
    due = q("SELECT COUNT(*) FROM batches WHERE status = 'active' AND expiry_date <= ?",
            (today + dt.timedelta(days=window)).isoformat())

    print(f"\n  {q('SELECT COUNT(*) FROM products')} products, "
          f"{q('SELECT COUNT(*) FROM batches')} batches, "
          f"{q('SELECT COUNT(*) FROM categories')} categories, "
          f"{q('SELECT COUNT(*) FROM users')} staff")
    print(f"  {due} items due within {window} days as at {today:%d %b %Y}")
    print(f"  {overdue} past their date and not yet resolved "
          f"({'normal — staff clear these as they go' if overdue else 'nothing overdue'})")
    print(f"  {q('SELECT COUNT(*) FROM products WHERE category_id IS NULL')} products "
          f"still uncategorised (expected to fall over time)")
    print(f"  {q('SELECT COUNT(*) FROM products WHERE image_path IS NULL')} products "
          f"still without a photo\n")

    conn.close()

    if failed:
        print(f"  {len(failed)} check(s) FAILED\n")
        return 1
    print(f"  All {len(results)} checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
