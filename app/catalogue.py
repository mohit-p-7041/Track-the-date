"""Shared reads and writes over products, categories and batches.

The scan screen, the product screens and settings all touch the same three
tables in the same few ways. Keeping those here means the duplicate rule and
the category rule have one implementation each, not one per screen.
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3

LIVE = ("active", "discounted")

# A typo in the year of a hand-typed date is silent and poisons the due list
# for years. Past dates are legitimate — staff record things already expired —
# so only implausible years are refused.
YEARS_BACK = 1
YEARS_FORWARD = 10

# A barcode is digits only, 6 to 18 of them. Decided 13 Aug: typed words are
# the thing this rule exists to stop, and because a product is never deleted,
# one junk row is permanent. See docs/ITERATION-2.md punch list item 1.
BARCODE_MIN = 6
BARCODE_MAX = 18

# The gun announces the symbology first, as an AIM identifier — ']' and two
# characters — ahead of the code itself. That is transport noise rather than
# part of the barcode, so it is stripped instead of refused.
AIM_PREFIX = re.compile(r"^\].{2}")

# Explicitly ASCII 0-9. str.isdigit() also accepts '²' and '٣', which the
# CHECK constraint in schema.sql refuses — and a rule whose two halves
# disagree surfaces an IntegrityError instead of a sentence staff can read.
ASCII_DIGITS = re.compile(r"[0-9]+\Z")


def clean_barcode(value: str) -> str:
    """Normalise what the gun or the keyboard produced. Does not validate.

    Used on the lookup path too, so a gun-prefixed scan of a barcode the shop
    already knows finds the existing product rather than inventing a new one.
    """
    return AIM_PREFIX.sub("", (value or "").strip())


def parse_barcode(value: str) -> tuple[str, str]:
    """Normalised barcode, or ("", reason). Same shape as parse_expiry.

    `schema.sql` carries this rule again as a CHECK constraint, the way
    idx_batches_unique_live backstops the duplicate rule: this is the check,
    that is the backstop, and the message comes from here.
    """
    barcode = clean_barcode(value)
    if not barcode:
        return "", "Scan a barcode."
    if not ASCII_DIGITS.match(barcode):
        return "", "A barcode is digits only — scan it, or type the digits under it."
    if len(barcode) < BARCODE_MIN or len(barcode) > BARCODE_MAX:
        return "", (
            f"A barcode is {BARCODE_MIN} to {BARCODE_MAX} digits. "
            f"That one is {len(barcode)}."
        )
    return barcode, ""


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


def _as_date(value) -> dt.date | None:
    """A date from either ISO text or a date. Templates hand over both."""
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def days_until(expiry, today=None) -> int | None:
    """Whole days from today to the expiry date. Negative once it is past."""
    expiry_date, today_date = _as_date(expiry), _as_date(today) or dt.date.today()
    return None if expiry_date is None else (expiry_date - today_date).days


def needs_confirmation(status: str, expiry, today=None) -> bool:
    """Whether deleting this batch should ask first.

    Only when the item is still good *and* still full price. Past its date, or
    already discounted, and a decision about that item has been made — staff are
    standing at the shelf holding it, and asking again is friction on the most
    common case there is.

    Two screens ask this question, so it lives here rather than in either of
    them, and it is registered as a template global in app/views.py.
    """
    remaining = days_until(expiry, today)
    return status == "active" and remaining is not None and remaining >= 0


def live_batch(
    conn: sqlite3.Connection,
    product_id: int,
    expiry: str,
    exclude_id: int | None = None,
) -> sqlite3.Row | None:
    """The batch that makes this a duplicate, if there is one.

    Checked before insert so the person is told "already tracked, expires
    such-and-such" instead of meeting an IntegrityError. The partial unique
    index idx_batches_unique_live is the backstop, not the check.

    `exclude_id` is for editing an existing batch: without it a batch saved onto
    the date it already has would find itself and be refused as its own
    duplicate. Adding a batch passes nothing, and nothing is excluded.
    """
    sql = ("SELECT id, expiry_date FROM batches "
           "WHERE product_id = ? AND expiry_date = ? AND status IN ('active','discounted')")
    params: list = [product_id, expiry]
    if exclude_id is not None:
        sql += " AND id != ?"
        params.append(exclude_id)
    return conn.execute(sql, params).fetchone()
