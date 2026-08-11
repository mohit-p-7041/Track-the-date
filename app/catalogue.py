"""Shared reads and writes over products, categories and batches.

The scan screen, the product screens and settings all touch the same three
tables in the same few ways. Keeping those here means the duplicate rule and
the category rule have one implementation each, not one per screen.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

LIVE = ("active", "discounted")

# A typo in the year of a hand-typed date is silent and poisons the due list
# for years. Past dates are legitimate — staff record things already expired —
# so only implausible years are refused.
YEARS_BACK = 1
YEARS_FORWARD = 10


def clean_barcode(value: str) -> str:
    return (value or "").strip()


def clean_name(value: str) -> str:
    """Trim the ends only.

    Names are deliberately not otherwise tidied: the export is full of
    inconsistent case and odd punctuation and staff recognise them as they
    are. See docs/DATA-NOTES.md.
    """
    return (value or "").strip()


def parse_expiry(value: str, today: dt.date | None = None) -> tuple[dt.date | None, str]:
    """ISO text -> a date, or (None, reason).

    Only ISO YYYY-MM-DD is accepted, which is what <input type="date"> posts in
    every browser regardless of how it displays. Nothing here will ever read
    09/04/2026 as the fourth of September or the ninth of April, because
    nothing here reads that shape at all.
    """
    today = today or dt.date.today()
    try:
        date = dt.date.fromisoformat((value or "").strip())
    except ValueError:
        return None, "Enter the expiry date."
    if not (today.year - YEARS_BACK <= date.year <= today.year + YEARS_FORWARD):
        return None, "Check the year on that date."
    return date, ""


def get_product_by_barcode(conn: sqlite3.Connection, barcode: str) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT p.*, c.name AS category_name
             FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.barcode = ?""",
        (barcode,),
    ).fetchone()


def categories(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name FROM categories WHERE active = 1 "
        "ORDER BY sort_order, name COLLATE NOCASE"
    ).fetchall()


def resolve_category(conn: sqlite3.Connection, name: str, user_id: int) -> int | None:
    """Find a category by name, or create it. Blank means no category.

    Matching is case-insensitive, so typing "energy drinks" picks up the
    existing "Energy Drinks" rather than colliding with it. Blank is a normal
    answer and never a warning — `products.category_id IS NULL` is how
    uncategorised is stored, and there is no 'Uncategorised' row.
    """
    name = " ".join((name or "").split())
    if not name:
        return None

    row = conn.execute(
        "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if row:
        return row["id"]

    try:
        return conn.execute(
            "INSERT INTO categories (name, created_by) VALUES (?, ?)", (name, user_id)
        ).lastrowid
    except sqlite3.IntegrityError:
        # Two people typed the same new category at once. The unique index
        # caught it; take theirs rather than showing a database error.
        row = conn.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        return row["id"] if row else None


def live_batch(conn: sqlite3.Connection, product_id: int, expiry: str) -> sqlite3.Row | None:
    """The batch that makes this a duplicate, if there is one.

    Checked before insert so the person is told "already tracked, expires
    such-and-such" instead of meeting an IntegrityError. The partial unique
    index idx_batches_unique_live is the backstop, not the check.
    """
    return conn.execute(
        "SELECT id, expiry_date FROM batches "
        "WHERE product_id = ? AND expiry_date = ? AND status IN ('active','discounted')",
        (product_id, expiry),
    ).fetchone()
