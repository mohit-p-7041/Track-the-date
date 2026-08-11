"""The locked decisions from CLAUDE.md, as tests.

`scripts/check_db.py` asserts these hold in the *current* database. These
assert the database *cannot be made* to break them — the difference between
"nobody has done this yet" and "this is impossible".

If one of these fails, don't loosen it. Either the change was wrong, or the
decision genuinely moved and should be changed here deliberately, in a commit
that says so.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.main import au_date
from app.views import au_when
from app.security import hash_pin, verify_pin
from conftest import days


# ------------------------------------------------------- the duplication guard

def test_duplicate_live_batch_is_refused(db, sample):
    """The whole data model. Same product, same date, both live — impossible."""
    product = sample["products"]["monster"]
    date = days(60)
    db.execute("INSERT INTO batches (product_id, expiry_date) VALUES (?, ?)",
               (product, date))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO batches (product_id, expiry_date) VALUES (?, ?)",
                   (product, date))


def test_discounted_still_counts_as_live(db, sample):
    """A discounted batch is still on the shelf. Don't let a twin in behind it."""
    product = sample["products"]["monster"]
    date = days(61)
    db.execute("INSERT INTO batches (product_id, expiry_date, status) VALUES (?, ?, ?)",
               (product, date, "discounted"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO batches (product_id, expiry_date) VALUES (?, ?)",
                   (product, date))


def test_a_date_can_repeat_once_resolved(db, sample):
    """Stock cleared in March can legitimately recur in September."""
    product = sample["products"]["monster"]
    date = days(62)
    db.execute("INSERT INTO batches (product_id, expiry_date, status) VALUES (?, ?, ?)",
               (product, date, "pulled"))
    db.execute("INSERT INTO batches (product_id, expiry_date) VALUES (?, ?)",
               (product, date))  # must not raise


def test_same_date_different_products_is_fine(db, sample):
    date = days(63)
    db.execute("INSERT INTO batches (product_id, expiry_date) VALUES (?, ?)",
               (sample["products"]["monster"], date))
    db.execute("INSERT INTO batches (product_id, expiry_date) VALUES (?, ?)",
               (sample["products"]["curly"], date))


# ------------------------------------------------------------------ categories

def test_categories_are_case_insensitively_unique(db, sample):
    """Ten people typing freely produce Drinks/drinks/DRINKS within a week."""
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO categories (name) VALUES (?)", ("ENERGY DRINKS",))


def test_a_product_may_have_no_category(db, sample):
    """NULL is a normal state, not a missing value to be filled in."""
    db.execute("INSERT INTO products (barcode, name) VALUES (?, ?)",
               ("9300602222222", "Something nobody categorised"))
    db.commit()
    assert db.execute(
        "SELECT category_id FROM products WHERE barcode = '9300602222222'"
    ).fetchone()[0] is None


def test_deleting_a_category_does_not_delete_products(db, sample):
    """ON DELETE SET NULL. Losing a category must never lose the catalogue."""
    db.execute("DELETE FROM categories WHERE id = ?", (sample["cat_id"],))
    db.commit()
    row = db.execute("SELECT category_id FROM products WHERE id = ?",
                     (sample["products"]["monster"],)).fetchone()
    assert row is not None and row[0] is None


# ----------------------------------------------------------------- no counting

def test_quantity_cannot_be_zero_or_negative(db, sample):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO batches (product_id, expiry_date, quantity) "
                   "VALUES (?, ?, ?)", (sample["products"]["monster"], days(64), 0))


def test_quantity_defaults_to_one(db, sample):
    batch_id = db.execute("INSERT INTO batches (product_id, expiry_date) VALUES (?, ?)",
                          (sample["products"]["monster"], days(65))).lastrowid
    assert db.execute("SELECT quantity FROM batches WHERE id = ?",
                      (batch_id,)).fetchone()[0] == 1


def test_quantity_is_never_rendered(client, sample):
    """The column exists for a possible future. It must not reach the UI."""
    assert "quantity" not in client.get("/").text.lower()


# ------------------------------------------------------------- no roles, PINs

def test_users_have_no_role_column(db):
    columns = [c[1] for c in db.execute("PRAGMA table_info(users)")]
    assert "role" not in columns


def test_pin_round_trips(db):
    pin_hash, pin_salt = hash_pin("4821")
    assert verify_pin("4821", pin_hash, pin_salt)
    assert not verify_pin("4822", pin_hash, pin_salt)


def test_pin_must_be_four_digits(db):
    for bad in ("123", "12345", "abcd", "", "12a4"):
        with pytest.raises(ValueError):
            hash_pin(bad)


def test_same_pin_gets_different_hashes(db):
    """Per-user salt. Two staff picking 1234 must not look identical in the table."""
    assert hash_pin("1234")[0] != hash_pin("1234")[0]


# ----------------------------------------------------------------------- dates

def test_au_date_is_australian():
    assert au_date("2026-09-04") == "4 Sep 2026"


def test_au_date_has_no_leading_zero():
    """The Windows trap. strftime('%-d') does not exist there — au_date builds
    the day by hand, and this test is what stops someone 'simplifying' it."""
    assert au_date("2026-01-01") == "1 Jan 2026"
    assert not au_date("2026-01-01").startswith("01")


def test_au_date_handles_two_digit_days():
    assert au_date("2026-12-25") == "25 Dec 2026"


def test_au_date_is_never_us_format():
    """4 Sep 2026, never 9/4/2026 — the failure mode is silent and dangerous."""
    assert "/" not in au_date("2026-09-04")


def test_au_when_is_australian_and_local():
    """Stamps are stored UTC by datetime('now'); the shop reads GMT+10."""
    assert au_when("2026-09-04 03:11:06") == "4 Sep 2026, 1:11 pm"
    assert au_when("2026-01-01 14:05:00") == "2 Jan 2026, 12:05 am"


def test_au_when_has_no_leading_zero_hour():
    """The Windows trap again — '%-I' does not exist there either."""
    assert au_when("2026-09-04 22:30:00").endswith("8:30 am")
    assert ", 08:" not in au_when("2026-09-04 22:30:00")


def test_au_when_survives_an_empty_stamp():
    """resolved_at is NULL for everything nobody has resolved."""
    assert au_when(None) == ""


# ------------------------------------------------------------------- integrity

def test_foreign_keys_are_enforced(db, sample):
    """A raw sqlite3.connect() silently drops this pragma. connect() must not."""
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO batches (product_id, expiry_date) VALUES (?, ?)",
                   (999999, days(66)))


def test_synchronous_is_full(db):
    """What makes a closed lid safe. FULL is 2."""
    assert db.execute("PRAGMA synchronous").fetchone()[0] == 2


def test_barcodes_are_unique(db, sample):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO products (barcode, name) VALUES (?, ?)",
                   ("9300601234567", "A different product, same barcode"))


def test_batch_status_is_constrained(db, sample):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO batches (product_id, expiry_date, status) "
                   "VALUES (?, ?, ?)", (sample["products"]["monster"], days(67), "gone"))


def test_deleting_a_product_removes_its_batches(db, sample):
    """ON DELETE CASCADE — no orphan batches, which check_db.py also asserts."""
    db.execute("DELETE FROM products WHERE id = ?", (sample["products"]["monster"],))
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM batches WHERE product_id = ?",
                      (sample["products"]["monster"],)).fetchone()[0] == 0


def test_no_categories_are_seeded(db):
    """seed.sql must stay settings-only. The list grows by itself."""
    assert db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0


def test_the_window_is_a_setting_not_a_constant(db):
    assert db.execute(
        "SELECT value FROM settings WHERE key = 'expiry_window_days'"
    ).fetchone()[0] == "7"
