"""The locked decisions from CLAUDE.md, as tests.

`scripts/check_db.py` asserts these hold in the *current* database. These
assert the database *cannot be made* to break them — the difference between
"nobody has done this yet" and "this is impossible".

If one of these fails, don't loosen it. Either the change was wrong, or the
decision genuinely moved and should be changed here deliberately, in a commit
that says so.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

import pytest

from app.main import au_date
from app.views import au_when
from app.security import hash_pin, verify_pin
from conftest import days

ROOT = Path(__file__).resolve().parent.parent


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


def test_an_account_off_the_list_cannot_add_anything(client, sample, db, staff):
    """Retiring an account has to bite the sessions already holding it.

    The cookie lasts thirty days and the middleware never looks at the
    database, so without the check in current_user an iPad still signed in as
    `BP TECOMA` would go on stamping batches with it for a month after it was
    taken off the list. That is exactly the thing this iteration exists to
    stop.
    """
    client.post("/settings/staff", data={"name": "Sarah", "pin": "4821"})

    def add(expiry: str) -> int:
        """Add a date to a known barcode; how many batches now carry that date."""
        client.post(
            "/scan/add",
            data={"barcode": "9300601234567", "expiry_date": expiry},
            follow_redirects=False,
        )
        return db.execute(
            "SELECT COUNT(*) FROM batches WHERE expiry_date = ?", (expiry,)
        ).fetchone()[0]

    assert add(days(45)) == 1, "the control failed — this test proves nothing"

    client.post(f"/settings/staff/{staff['id']}/active", data={"active": "0"})
    assert add(days(46)) == 0


def test_somebody_off_the_list_can_still_reach_the_sign_in_screen(client, staff):
    """Otherwise retiring your own account locks you out of your own laptop.

    /login sends a signed-in person to the home screen. Somebody just taken
    off the list is still signed in as far as the cookie goes, so without the
    active check there they would bounce straight back and never get to sign
    in as themselves.
    """
    client.post("/settings/staff", data={"name": "Sarah", "pin": "4821"})
    client.post(f"/settings/staff/{staff['id']}/active", data={"active": "0"})

    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 200
    assert "Sarah" in response.text


def test_the_shop_cannot_empty_its_own_sign_in_list(client, db, staff):
    """No roles means anyone can retire anyone. Retiring the last one is a lockout."""
    body = client.post(
        f"/settings/staff/{staff['id']}/active", data={"active": "0"}, follow_redirects=True
    ).text
    assert "only person left" in body
    assert db.execute("SELECT COUNT(*) FROM users WHERE active = 1").fetchone()[0] == 1


# --------------------------------------------------------------- no CDN links

# The shop laptop has to work with the internet down. A CDN link is invisible
# until the day the connection drops, which is exactly the day someone is
# standing at the counter with a queue.

# Matches a URL only where the browser would actually go and fetch it, so
# prose in a comment ("a plain http:// address is not a secure context") does
# not trip it. That distinction matters: the rule is about requests, not text.
EXTERNAL = re.compile(
    r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//"""
    r"""|url\(\s*["']?\s*(?:https?:)?//"""
    r"""|@import\s+["']?\s*(?:https?:)?//"""
    r"""|(?:fetch|importScripts)\(\s*["']\s*(?:https?:)?//""",
    re.IGNORECASE,
)

SERVED = [
    *(ROOT / "app" / "templates").glob("*.html"),
    *(ROOT / "app" / "static" / "js").glob("*.js"),
    *(ROOT / "app" / "static" / "css").glob("*.css"),
]


def test_nothing_served_to_a_browser_links_out():
    """Every asset comes from this laptop. Vendored files go in static/vendor."""
    assert SERVED, "found no templates or assets to check — the globs are wrong"
    offenders = []
    for path in SERVED:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if EXTERNAL.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not offenders, "external requests found:\n" + "\n".join(offenders)


CSS = ROOT / "app" / "static" / "css" / "app.css"


def test_the_hidden_attribute_actually_hides():
    """A hidden element must not be on screen. This was not true.

    The browser's own rule is `[hidden] { display: none }` — one attribute
    selector, which any author rule setting `display` outranks. `.btn` sets
    `display: inline-block`, so the camera button shipped `hidden`, was left
    hidden on every device without a camera, and was drawn anyway: visible,
    and completely dead, because scanner.js returns before it binds a click.
    Found on an iPad over plain http, where it is the normal state.

    There is no browser in this suite, so this checks the mechanism rather
    than the pixels: the stylesheet has to re-assert `[hidden]` hard enough
    to win. Removing that rule brings the bug straight back.
    """
    # Comments stripped first: the rule is explained in a comment that quotes
    # the browser's weaker version of itself, and a plain search finds that.
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    rule = re.search(r"\[hidden\]\s*\{([^}]*)\}", css)
    assert rule, "nothing in app.css re-asserts [hidden]"
    body = rule.group(1)
    assert "display" in body and "none" in body, f"[hidden] does not hide: {body!r}"
    assert "!important" in body, "without !important a .btn display rule still wins"

    # The hazard has to still be there for the guard to be worth keeping. If
    # this ever fails, .btn stopped setting display and this test can go.
    assert re.search(r"\.btn\s*\{[^}]*display\s*:", css), \
        ".btn no longer sets display — re-check whether the guard is still needed"


def test_the_vendored_scanner_is_the_file_we_vetted():
    """Pinned by checksum, so a swapped or edited bundle is not silent.

    app/static/vendor/README.md records where this came from and what it
    hashes to. Nothing in that folder is edited by hand — if this fails, the
    file changed and the question is who changed it and to what.
    """
    vendor = ROOT / "app" / "static" / "vendor"
    library = vendor / "zxing-0.21.3.min.js"
    assert library.exists(), "the vendored scanner library is missing"

    recorded = re.search(
        r"SHA-256.*?`([0-9a-f]{64})`", (vendor / "README.md").read_text(encoding="utf-8")
    )
    assert recorded, "README.md no longer records a SHA-256 for the library"

    actual = hashlib.sha256(library.read_bytes()).hexdigest()
    assert actual == recorded.group(1), (
        f"the vendored library does not match README.md\n"
        f"  recorded {recorded.group(1)}\n  actual   {actual}"
    )


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


# ------------------------------------------------------------- the barcode rule
#
# Digits only, 6 to 18 of them, after stripping the gun's AIM identifier.
# Decided 13 Aug: a product is never deleted, so a barcode typed as a word is
# permanent. Two layers, and both are tested — app/catalogue.py produces the
# sentence staff read, the CHECK constraint makes it impossible by any route.

@pytest.mark.parametrize("value", [
    "cool ridge water",                  # the actual bug: a typed name
    "https://qrco.de/bdeRvm",            # a marketing QR, 5 of these are in the export
    "www.ausbev.com.au",
    "12345",                             # 5 digits, under the floor
    "1" * 19,                            # 19, over the ceiling
    "1930083008300830083008300830083008300830",   # the real 40-digit gun misfire
    "93006 01234567",                    # embedded space
    "9300601234567x",
    "",
    "   ",
])
def test_the_barcode_rule_refuses(value):
    from app.catalogue import parse_barcode

    barcode, problem = parse_barcode(value)
    assert barcode == "", f"{value!r} was accepted"
    assert problem, f"{value!r} was refused with no reason to show anybody"


@pytest.mark.parametrize("value,expected", [
    ("9300601234567", "9300601234567"),      # ordinary EAN-13
    ("0000001051117", "0000001051117"),      # leading zeros are significant
    ("123456", "123456"),                    # 6, the floor
    ("1" * 18, "1" * 18),                    # 18, the ceiling
    ("  9300601234567  ", "9300601234567"),  # whitespace from the gun
    ("9300601234567\r\n", "9300601234567"),  # the gun's trailing newline
    ("]C10118721274620198", "0118721274620198"),   # AIM identifier stripped
    ("]E09300601234567", "9300601234567"),
])
def test_the_barcode_rule_accepts_and_normalises(value, expected):
    """The prefix is the gun naming the symbology, not part of the code."""
    from app.catalogue import parse_barcode

    barcode, problem = parse_barcode(value)
    assert not problem, f"{value!r} was refused: {problem}"
    assert barcode == expected


def test_the_barcode_check_constraint_is_the_backstop(db, sample):
    """The app checks first; this is what makes it impossible another way."""
    for value in ("cool ridge water", "https://qrco.de/bdeRvm", "12345", "1" * 19):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO products (barcode, name) VALUES (?, ?)",
                       (value, "Should never exist"))


def test_the_two_barcode_layers_agree_on_unicode_digits(db, sample):
    """The subtle one. str.isdigit() is True for '٣' and '²'.

    Had the app used it, those would pass the app and then hit the CHECK
    constraint, so staff would get an IntegrityError page instead of a
    sentence. The rule has to refuse the same things in both halves.
    """
    from app.catalogue import parse_barcode

    for value in ("١٢٣٤٥٦٧٨", "9300601234567²", "½½½½½½"):
        barcode, problem = parse_barcode(value)
        assert problem, f"the app accepted {value!r}"
        # And the database would have refused it too, so they cannot disagree.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO products (barcode, name) VALUES (?, ?)",
                       (value, "Should never exist"))


def test_a_gun_prefixed_scan_finds_the_existing_product(client, sample):
    """Normalising on the lookup path too, or the gun invents a second product.

    `sample` already holds 9300601234567. Scanning it with the prefix attached
    must land on that product's date step, not the new-product form.
    """
    body = client.get("/scan?barcode=]C19300601234567").text
    assert "Monster Ultra Zero 500ml" in body
    assert "New barcode" not in body


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


# --------------------------------------------------------------- the export
#
# A spreadsheet is the one place this data leaves the app, and Excel rewrites
# anything it is allowed to interpret. These say it may not.

def _export(conn, **kwargs):
    from io import BytesIO

    from openpyxl import load_workbook

    from scripts.export_xlsx import build

    return load_workbook(BytesIO(build(conn, **kwargs))).active


def _row_for(sheet, product_name):
    """The one row for this product. Strict on purpose.

    A product can have several batches, and returning the first match would
    let a change in sort order quietly point a test at a different row —
    which is exactly what happened once. Target products with one batch.
    """
    rows = [row for row in sheet.iter_rows(min_row=2) if row[0].value == product_name]
    assert len(rows) == 1, f"{product_name!r} has {len(rows)} rows, expected 1"
    return rows[0]


# One batch, so a row lookup is unambiguous. Trailing spaces and all.
SINGLE = "C/RIDGE WATER 1L  "


def test_a_barcode_keeps_its_leading_zeros(db, sample):
    """0000001051117 is a real product. As a number it becomes 1051117."""
    db.execute("INSERT INTO products (barcode, name) VALUES (?, ?)",
               ("0000001051117", "Zero Lead Test Item"))
    db.execute("INSERT INTO batches (product_id, expiry_date) "
               "SELECT id, ? FROM products WHERE barcode = ?",
               (days(20), "0000001051117"))
    db.commit()

    cell = _row_for(_export(db), "Zero Lead Test Item")[1]
    assert cell.value == "0000001051117"
    assert isinstance(cell.value, str), "written as a number, the zeros are gone"
    assert cell.number_format == "@", "without a text format Excel re-reads it"


def test_a_long_barcode_is_not_turned_into_a_number(db, sample):
    """Rewritten 13 Aug, when the barcode rule made the old fixtures illegal.

    This used to insert ']C10118721274620198' and a QR-code URL, because both
    were in the real data. Neither can exist now — the CHECK constraint refuses
    them and the migration cleared the ones that were there.

    The risk it was guarding is not gone though, it moved: an 18-digit numeric
    barcode is exactly what Excel turns into 1.11E+17. So the case is now the
    longest barcode the rule allows, which is a stronger test than the old one
    — ']C1...' was safe from Excel precisely because it was not a number.
    """
    longest = "1" * 18
    db.execute("INSERT INTO products (barcode, name) VALUES (?, ?)",
               (longest, "Eighteen Digit Item"))
    db.execute("INSERT INTO batches (product_id, expiry_date) "
               "SELECT id, ? FROM products WHERE barcode = ?", (days(21), longest))
    db.commit()

    cell = _row_for(_export(db), "Eighteen Digit Item")[1]
    assert cell.value == longest
    assert isinstance(cell.value, str), "as a number this is 1.11E+17"
    assert cell.number_format == "@", "without a text format Excel re-reads it"


def test_expiry_is_a_real_date_never_a_us_string(db, sample):
    import datetime as dt

    cell = _row_for(_export(db), SINGLE)[3]
    assert isinstance(cell.value, (dt.date, dt.datetime)), "a string is Excel's to guess at"
    assert "mmm" in cell.number_format, "a numeric month can be read either way round"
    assert "mm/dd" not in cell.number_format


def test_the_export_carries_no_quantity(db, sample):
    """There is no counting. The column exists in the schema and stays there."""
    headings = [c.value for c in _export(db)[1]]
    assert not any("quantity" in str(h).lower() for h in headings)


def test_timestamps_are_shifted_to_shop_time(db, sample):
    """SQLite stores UTC. The shop is GMT+10 and reads these as local."""
    db.execute("UPDATE batches SET added_at = ? WHERE product_id = ?",
               ("2026-08-11 03:30:00", sample["products"]["shouty"]))
    db.commit()

    stamp = _row_for(_export(db), SINGLE)[8].value
    assert (stamp.hour, stamp.minute) == (13, 30), "still UTC"
    assert stamp.day == 11


def test_a_date_only_stamp_is_not_shifted_into_a_time(db, sample):
    """The 583 migrated rows carry a date, not a timestamp. +10h invents 10am."""
    import datetime as dt

    db.execute("UPDATE batches SET status = 'pulled', resolved_at = ? WHERE id = ?",
               ("2026-03-02", sample["batches"]["due_soon"]))
    db.commit()

    cell = _row_for(_export(db), SINGLE)[10]
    assert cell.value == dt.datetime(2026, 3, 2, 0, 0), "a time appeared from nowhere"
    assert cell.number_format == "d mmm yyyy"


def test_names_go_in_exactly_as_the_shop_has_them(db, sample):
    """Messy case, trailing space, curly apostrophe. Do not clean them."""
    products = {row[0].value for row in _export(db).iter_rows(min_row=2)}
    assert "C/RIDGE WATER 1L  " in products
    assert "Arnott’s Tim Tam 200g" in products


def test_a_name_starting_with_equals_is_not_a_formula(db, sample):
    db.execute("INSERT INTO products (barcode, name) VALUES (?, ?)",
               ("9300600000999", "=SUM(A1:A9) Mints"))
    db.execute("INSERT INTO batches (product_id, expiry_date) "
               "SELECT id, ? FROM products WHERE barcode = ?",
               (days(22), "9300600000999"))
    db.commit()

    cell = _row_for(_export(db), "=SUM(A1:A9) Mints")[0]
    assert cell.data_type == "s", "Excel would show #NAME? where the product should be"


def test_exporting_changes_nothing_in_the_database(db, sample):
    """It is a copy for reading. Nothing here is a write."""
    from scripts.export_xlsx import build

    before = "\n".join(db.iterdump())
    build(db)
    assert "\n".join(db.iterdump()) == before
