"""Does the app actually render?

`scripts/check_db.py` proves the data is sound. It cannot tell you that a
template throws, that a query returns the wrong rows, or that a route 500s.
This file is that half of the check.

Add a test here for every screen as it gets built — see docs/BACKLOG.md, which
lists the acceptance criteria each one has to meet.
"""

from __future__ import annotations

from conftest import STAFF_NAME, STAFF_PIN, days


# --------------------------------------------------------------- signing in

def test_login_lists_active_staff(anon_client, staff):
    body = anon_client.get("/login").text
    assert STAFF_NAME in body


def test_login_hides_inactive_staff(anon_client, staff, db):
    db.execute("UPDATE users SET active = 0 WHERE id = ?", (staff["id"],))
    db.commit()
    assert STAFF_NAME not in anon_client.get("/login").text


def test_login_shows_a_keypad(anon_client, staff):
    """Big targets, no keyboard needed — one-handed on an iPad."""
    body = anon_client.get(f"/login?user={staff['id']}").text
    for digit in "0123456789":
        assert f'data-digit="{digit}"' in body


def test_correct_pin_signs_in_and_lands_on_due(anon_client, staff):
    response = anon_client.post(
        "/login", data={"user_id": staff["id"], "pin": STAFF_PIN}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert anon_client.get("/").status_code == 200


def test_wrong_pin_says_so_plainly(anon_client, staff):
    response = anon_client.post(
        "/login", data={"user_id": staff["id"], "pin": "9999"}, follow_redirects=False
    )
    assert response.status_code == 200            # re-rendered, not redirected
    assert "did not match" in response.text
    # Must not leak which half was wrong, and must never echo the PIN back.
    assert "9999" not in response.text
    assert anon_client.get("/", follow_redirects=False).status_code == 303


def test_wrong_pin_does_not_lock_anybody_out(anon_client, staff):
    """PINs are accountability, not security. No lockout, by decision."""
    for _ in range(5):
        anon_client.post("/login", data={"user_id": staff["id"], "pin": "0000"})
    response = anon_client.post(
        "/login", data={"user_id": staff["id"], "pin": STAFF_PIN}, follow_redirects=False
    )
    assert response.status_code == 303


def test_no_session_redirects_to_login(anon_client):
    for path in ("/", "/scan", "/products", "/sheet", "/settings"):
        response = anon_client.get(path, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == "/login", path


def test_login_and_static_are_reachable_signed_out(anon_client):
    assert anon_client.get("/login").status_code == 200
    assert anon_client.get("/static/css/app.css").status_code == 200


def test_signed_in_name_is_on_every_page(client):
    """Proof the user reached the route: writes stamp this id, so it has to be
    there without the route re-reading the cookie."""
    assert STAFF_NAME in client.get("/").text


def test_logout_clears_the_session(client):
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/", follow_redirects=False).status_code == 303


def test_login_page_works_with_no_staff_at_all(anon_client):
    """A fresh database has nobody in it. The page must still explain itself."""
    response = anon_client.get("/login")
    assert response.status_code == 200
    assert "add_user.py" in response.text


# ------------------------------------------------------------------- home

def test_home_renders_when_empty(client):
    """A fresh database is a valid state. The home screen must not need data."""
    response = client.get("/")
    assert response.status_code == 200
    assert "BP Tecoma" in response.text
    assert "Nothing due in the next 7 days" in response.text


def test_home_shows_due_items(client, sample):
    response = client.get("/")
    assert response.status_code == 200
    assert "C/RIDGE WATER 1L" in response.text          # due in 2 days
    assert "Monster Ultra Zero 500ml" in response.text  # 4 days overdue


def test_home_hides_items_beyond_the_window(client, sample, db):
    """The 30-day batch exists but must not appear. Only its product's other
    batch puts that name on the page, so check the date instead."""
    far_off = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["outside"],)
    ).fetchone()[0]
    body = client.get("/").text
    assert _au(far_off) not in body


def test_home_hides_resolved_batches(client, sample, db):
    resolved = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["resolved"],)
    ).fetchone()[0]
    assert _au(resolved) not in client.get("/").text


def test_home_includes_the_window_edge(client, sample, db):
    """Exactly 7 days out is inside the window, not outside it. Off-by-one here
    silently hides a day's worth of stock."""
    edge = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["due_edge"],)
    ).fetchone()[0]
    assert _au(edge) in client.get("/").text


def test_home_puts_overdue_first(client, sample):
    """Past-date items sit above upcoming ones. Normal state, top of the page."""
    body = client.get("/").text
    assert body.index("Past date") < body.index("Due within")


def test_overdue_is_not_an_error(client, sample):
    """583 batches imported already expired. Overdue is expected, not a warning."""
    body = client.get("/").text
    for alarm in ("Error", "error", "Warning", "warning"):
        assert alarm not in body


def test_uncategorised_product_renders_blank(client, sample):
    """category_id IS NULL is normal. No 'Uncategorised' label anywhere."""
    body = client.get("/").text
    assert "Uncategorised" not in body
    assert "None" not in body  # a NULL leaking into the template


def test_home_counts_only_live_batches(client, sample):
    """3 products; 4 live batches (the pulled one does not count)."""
    body = client.get("/").text
    assert "3 products, 4 being tracked" in body


def test_photo_placeholder_when_no_image(client, sample):
    """Lists must not reflow when photos are backfilled months later."""
    assert "thumb-empty" in client.get("/").text


def test_dates_are_australian_on_the_page(client, sample):
    """Never US format. 4 Sep, not Sep 4 or 09/04."""
    body = client.get("/").text
    assert _au(days(2)) in body


def test_home_filters_by_category(client, sample):
    body = client.get(f"/?category={sample['cat_id']}").text
    assert "Monster Ultra Zero 500ml" in body
    assert "C/RIDGE WATER 1L" not in body


def test_home_filters_to_the_uncategorised(client, sample):
    """A normal state with a filter of its own — and still no 'Uncategorised'
    row anywhere, because NULL is how it is stored."""
    body = client.get("/?category=none").text
    assert "C/RIDGE WATER 1L" in body
    assert "Monster Ultra Zero 500ml" not in body
    assert "Uncategorised" not in body


def test_home_shows_no_filter_bar_until_a_category_exists(client, db):
    """The list starts empty and grows by itself. No empty chrome before then."""
    assert 'class="filters"' not in client.get("/").text


def test_home_rows_link_to_the_product(client, sample):
    assert f'href="/products/{sample["products"]["monster"]}"' in client.get("/").text


# ------------------------------------------------------------ scan and add

def test_scan_opens_with_the_cursor_in_the_barcode_field(client):
    body = client.get("/scan").text
    assert 'id="barcode"' in body
    assert "autofocus" in body.split('id="barcode"')[1].split(">")[0]


def test_known_barcode_shows_the_product_and_focuses_the_date(client, sample):
    body = client.get("/scan?barcode=9300601234567").text
    assert "Monster Ultra Zero 500ml" in body
    assert 'id="expiry"' in body
    assert "autofocus" in body.split('id="expiry"')[1].split(">")[0]
    assert 'id="name"' not in body            # nothing to re-type for a known product


def test_unknown_barcode_asks_for_a_name(client, sample):
    body = client.get("/scan?barcode=9999999999999").text
    assert 'id="name"' in body
    assert 'id="expiry"' in body


def test_a_typed_word_is_refused_and_creates_nothing(client, db):
    """The punch-list bug itself. Products are never deleted, so junk is forever."""
    before = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    response = client.post(
        "/scan/add",
        data={"barcode": "cool ridge water", "name": "Cool Ridge Water 600ml",
              "expiry_date": days(10)},
        follow_redirects=False,
    )
    assert response.status_code == 200            # re-rendered with the reason
    assert "digits only" in response.text
    assert db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == before
    assert db.execute("SELECT COUNT(*) FROM batches").fetchone()[0] == 0


def test_an_invalid_barcode_never_opens_the_new_product_form(client):
    """Nobody should type a name for something that will be refused on save."""
    body = client.get("/scan?barcode=cool ridge water").text
    assert "digits only" in body
    assert 'id="name"' not in body
    assert 'id="barcode"' in body                 # back to step one, ready to rescan


def test_a_barcode_of_the_wrong_length_says_the_length(client, db):
    response = client.post(
        "/scan/add", data={"barcode": "12345", "name": "Too Short", "expiry_date": days(10)}
    )
    assert "6 to 18 digits" in response.text
    assert "That one is 5" in response.text
    assert db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0


def test_a_gun_prefixed_new_barcode_is_stored_without_the_prefix(client, db, staff):
    """The stored barcode is the code, not the gun's announcement of it."""
    client.post(
        "/scan/add",
        data={"barcode": "]C10118721274620198", "name": "Golden Gay Time Lamington",
              "expiry_date": days(12)},
    )
    row = db.execute(
        "SELECT barcode FROM products WHERE name = 'Golden Gay Time Lamington'"
    ).fetchone()
    assert row is not None, "the add was refused"
    assert row["barcode"] == "0118721274620198"


def test_adding_writes_a_batch_stamped_with_the_signed_in_user(client, sample, db, staff):
    response = client.post(
        "/scan/add",
        data={"barcode": "9300601234567", "expiry_date": days(45)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.execute(
        "SELECT b.added_by, b.status, b.quantity FROM batches b "
        "WHERE b.product_id = ? AND b.expiry_date = ?",
        (sample["products"]["monster"], days(45)),
    ).fetchone()
    assert row is not None
    assert row["added_by"] == staff["id"]
    assert row["status"] == "active"
    assert row["quantity"] == 1


def test_adding_an_unknown_barcode_creates_the_product_too(client, db, staff):
    client.post(
        "/scan/add",
        data={"barcode": "9300600000123", "name": "Solo Energy Lemon 500ml",
              "expiry_date": days(20)},
    )
    product = db.execute(
        "SELECT id, name, category_id, created_by FROM products WHERE barcode = ?",
        ("9300600000123",),
    ).fetchone()
    assert product is not None
    assert product["name"] == "Solo Energy Lemon 500ml"
    assert product["category_id"] is None      # no category is a normal state
    assert product["created_by"] == staff["id"]
    assert db.execute(
        "SELECT COUNT(*) FROM batches WHERE product_id = ?", (product["id"],)
    ).fetchone()[0] == 1


def test_duplicate_is_caught_before_insert_with_the_date(client, sample, db):
    """The core rule. Not a database error, and no offer to raise a quantity."""
    existing = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["overdue"],)
    ).fetchone()[0]

    response = client.post(
        "/scan/add", data={"barcode": "9300601234567", "expiry_date": existing}
    )
    assert response.status_code == 200
    assert f"Already tracked — expires {_au(existing)}" in response.text
    assert "quantity" not in response.text.lower()
    assert "IntegrityError" not in response.text

    assert db.execute(
        "SELECT COUNT(*) FROM batches WHERE product_id = ? AND expiry_date = ?",
        (sample["products"]["monster"], existing),
    ).fetchone()[0] == 1


def test_a_duplicate_still_keeps_the_category_that_was_typed(client, sample, db):
    """Proof the app checks before inserting rather than letting the index
    raise: an IntegrityError would roll the category back with it."""
    duplicate_date = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["due_soon"],)
    ).fetchone()[0]

    response = client.post(
        "/scan/add",
        data={"barcode": "9300609876543", "category": "Water", "expiry_date": duplicate_date},
    )
    assert "Already tracked" in response.text
    assert db.execute(
        """SELECT c.name FROM products p JOIN categories c ON c.id = p.category_id
            WHERE p.barcode = ?""",
        ("9300609876543",),
    ).fetchone()[0] == "Water"


def test_a_date_freed_up_by_a_resolved_batch_is_accepted(client, sample, db):
    """The pulled batch on that date is history. The date can come round again."""
    freed = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["resolved"],)
    ).fetchone()[0]

    response = client.post(
        "/scan/add",
        data={"barcode": "9300601111111", "expiry_date": freed},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db.execute(
        "SELECT COUNT(*) FROM batches WHERE product_id = ? AND expiry_date = ? "
        "AND status = 'active'",
        (sample["products"]["curly"], freed),
    ).fetchone()[0] == 1


def test_after_saving_the_form_is_back_at_the_barcode_field(client, sample):
    response = client.post(
        "/scan/add",
        data={"barcode": "9300601234567", "expiry_date": days(46)},
        follow_redirects=True,
    )
    body = response.text
    assert "Saved" in body
    assert 'id="barcode"' in body
    assert 'id="expiry"' not in body          # nothing half-finished left on screen


def test_a_rejected_date_does_not_lose_the_typed_name(client):
    body = client.post(
        "/scan/add",
        data={"barcode": "9300600000999", "name": "Chobani Greek Yoghurt 170g",
              "expiry_date": ""},
    ).text
    assert "Chobani Greek Yoghurt 170g" in body
    assert "Enter the expiry date." in body


def test_a_mistyped_year_is_refused(client, sample):
    body = client.post(
        "/scan/add", data={"barcode": "9300601234567", "expiry_date": "0226-09-14"}
    ).text
    assert "Check the year" in body


def test_scan_never_renders_a_us_date(client, sample, db):
    existing = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["overdue"],)
    ).fetchone()[0]
    body = client.post(
        "/scan/add", data={"barcode": "9300601234567", "expiry_date": existing}
    ).text
    assert "/" not in body.split("Already tracked")[1].split("<")[0]


# ------------------------------------------------------- inline categories

def test_category_input_suggests_the_existing_ones(client, sample):
    body = client.get("/scan?barcode=9300609876543").text
    assert '<datalist id="category-list">' in body
    assert '<option value="Energy Drinks">' in body


def test_typing_a_new_category_creates_it_against_the_product(client, db, staff):
    client.post(
        "/scan/add",
        data={"barcode": "9300600000456", "name": "Bulla Ice Cream 2L",
              "category": "Frozen", "expiry_date": days(30)},
    )
    category = db.execute(
        "SELECT id, created_by FROM categories WHERE name = 'Frozen'"
    ).fetchone()
    assert category is not None
    assert category["created_by"] == staff["id"]
    assert db.execute(
        "SELECT category_id FROM products WHERE barcode = ?", ("9300600000456",)
    ).fetchone()[0] == category["id"]


def test_a_case_variant_picks_the_existing_category(client, sample, db):
    """Typing 'energy drinks' must find 'Energy Drinks', not collide with it."""
    client.post(
        "/scan/add",
        data={"barcode": "9300609876543", "category": "energy drinks",
              "expiry_date": days(31)},
    )
    assert db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 1
    assert db.execute(
        "SELECT category_id FROM products WHERE barcode = ?", ("9300609876543",)
    ).fetchone()[0] == sample["cat_id"]


def test_a_category_covers_batches_recorded_earlier(client, sample, db):
    """It attaches to the barcode, so it reaches back over old batches."""
    client.post(
        "/scan/add",
        data={"barcode": "9300601111111", "category": "Biscuits", "expiry_date": days(32)},
    )
    rows = db.execute(
        """SELECT c.name FROM batches b
             JOIN products p ON p.id = b.product_id
             JOIN categories c ON c.id = p.category_id
            WHERE b.product_id = ?""",
        (sample["products"]["curly"],),
    ).fetchall()
    assert len(rows) == 3                       # every batch of that barcode, old ones too
    assert all(r["name"] == "Biscuits" for r in rows)


def test_a_blank_category_is_never_complained_about(client, sample, db):
    response = client.post(
        "/scan/add",
        data={"barcode": "9300609876543", "category": "  ", "expiry_date": days(33)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db.execute(
        "SELECT category_id FROM products WHERE barcode = ?", ("9300609876543",)
    ).fetchone()[0] is None


def test_no_uncategorised_option_is_offered(client, sample):
    assert "Uncategorised" not in client.get("/scan?barcode=9300609876543").text


# ------------------------------------------------- product list and detail

def test_product_list_shows_everything_by_default(client, sample):
    body = client.get("/products").text
    assert "Monster Ultra Zero 500ml" in body
    assert "C/RIDGE WATER 1L" in body
    assert "Arnott" in body


def test_search_is_case_insensitive(client, sample):
    assert "Monster Ultra Zero 500ml" in client.get("/products?q=MONSTER").text
    assert "Monster Ultra Zero 500ml" in client.get("/products?q=monster").text


def test_search_tolerates_surrounding_whitespace(client, sample):
    """Stored names have trailing spaces; typed queries have stray ones."""
    body = client.get("/products?q=%20%20water%20%20").text
    assert "C/RIDGE WATER 1L" in body


def test_search_finds_the_abbreviated_name(client, sample):
    """'cool ridge' cannot substring-match 'C/RIDGE WATER 1L' — the shop's
    abbreviation is not derivable — so the word that does match carries it."""
    body = client.get("/products?q=cool+ridge").text
    assert "C/RIDGE WATER 1L" in body


def test_search_handles_a_curly_apostrophe_either_way(client, sample):
    """The export has Arnott’s with a curly one. Nobody types that."""
    assert "Tim Tam" in client.get("/products?q=arnott%27s").text
    assert "Tim Tam" in client.get("/products?q=arnott%E2%80%99s").text


def test_search_by_barcode(client, sample):
    body = client.get("/products?q=9300609876543").text
    assert "C/RIDGE WATER 1L" in body
    assert "Monster Ultra Zero 500ml" not in body


def test_search_that_matches_nothing_says_so(client, sample):
    assert "Nothing matches that." in client.get("/products?q=zzzzzz").text


def test_product_list_filters_by_category(client, sample):
    body = client.get(f"/products?category={sample['cat_id']}").text
    assert "Monster Ultra Zero 500ml" in body
    assert "C/RIDGE WATER 1L" not in body


def test_product_list_sorts_by_soonest_expiry(client, sample):
    """Monster is 4 days overdue, the water is due in 2, the Tim Tams in 7."""
    body = client.get("/products").text
    assert body.index("Monster Ultra Zero") < body.index("C/RIDGE WATER") < body.index("Tim Tam")


def test_product_detail_shows_every_batch_and_who_added_them(client, sample):
    body = client.get(f"/products/{sample['products']['curly']}").text
    assert _au(days(7)) in body        # live
    assert _au(days(1)) in body        # pulled — history stays visible
    assert "Mohit" in body             # the audit trail, not the signed-in user


def test_product_detail_404s_for_an_unknown_id(client, sample):
    assert client.get("/products/999999").status_code == 404


def test_resolving_a_batch_records_who_and_when(client, sample, db, staff):
    batch = sample["batches"]["due_soon"]
    response = client.post(
        f"/products/{sample['products']['shouty']}/batches/{batch}",
        data={"status": "pulled"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.execute(
        "SELECT status, resolved_by, resolved_at FROM batches WHERE id = ?", (batch,)
    ).fetchone()
    assert row["status"] == "pulled"
    assert row["resolved_by"] == staff["id"]
    assert row["resolved_at"] is not None


def test_a_resolved_batch_leaves_the_due_list(client, sample):
    batch = sample["batches"]["due_soon"]
    client.post(f"/products/{sample['products']['shouty']}/batches/{batch}",
                data={"status": "sold"})
    assert "C/RIDGE WATER 1L" not in client.get("/").text


def test_a_discounted_batch_is_still_on_the_shelf(client, sample, db):
    """Discounted is a resolution but not a removal — it still shows as due."""
    batch = sample["batches"]["due_soon"]
    client.post(f"/products/{sample['products']['shouty']}/batches/{batch}",
                data={"status": "discounted"})
    assert "C/RIDGE WATER 1L" in client.get("/").text


def test_nothing_is_hard_deleted(client, sample, db):
    before = db.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
    client.post(f"/products/{sample['products']['shouty']}/batches/"
                f"{sample['batches']['due_soon']}", data={"status": "pulled"})
    assert db.execute("SELECT COUNT(*) FROM batches").fetchone()[0] == before


def test_an_unknown_resolution_is_refused(client, sample):
    response = client.post(
        f"/products/{sample['products']['shouty']}/batches/{sample['batches']['due_soon']}",
        data={"status": "binned"},
    )
    assert response.status_code == 400


def test_category_can_be_set_from_the_product_screen(client, sample, db):
    client.post(f"/products/{sample['products']['shouty']}/category",
                data={"category": "Water"})
    assert db.execute(
        """SELECT c.name FROM products p JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?""",
        (sample["products"]["shouty"],),
    ).fetchone()[0] == "Water"


def test_clearing_the_category_is_allowed(client, sample, db):
    client.post(f"/products/{sample['products']['monster']}/category", data={"category": ""})
    assert db.execute(
        "SELECT category_id FROM products WHERE id = ?", (sample["products"]["monster"],)
    ).fetchone()[0] is None


# ----------------------------------------------------------------- photos

def _photo_bytes(width=2000, height=1500, orientation=None) -> bytes:
    """A JPEG the size an iPad actually produces, optionally rotated by EXIF."""
    import io

    from PIL import Image

    image = Image.new("RGB", (width, height), (180, 40, 40))
    for x in range(0, width, 40):           # some detail, so it isn't a flat block
        for y in range(0, height, 40):
            image.putpixel((x, y), (20, 90, 200))
    buffer = io.BytesIO()
    if orientation:
        exif = image.getexif()
        exif[274] = orientation
        image.save(buffer, "JPEG", exif=exif, quality=95)
    else:
        image.save(buffer, "JPEG", quality=95)
    return buffer.getvalue()


def test_uploading_a_photo_attaches_it_to_the_product(client, sample, db, photo_dir):
    response = client.post(
        f"/products/{sample['products']['monster']}/photo",
        files={"photo": ("counter.jpg", _photo_bytes(), "image/jpeg")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    stored = db.execute(
        "SELECT image_path FROM products WHERE id = ?", (sample["products"]["monster"],)
    ).fetchone()[0]
    assert stored == "data/photos/9300601234567.jpg"     # keyed to the barcode
    assert (photo_dir / "9300601234567.jpg").exists()


def test_a_photo_is_resized_and_stripped(client, sample, photo_dir):
    from PIL import Image

    client.post(
        f"/products/{sample['products']['monster']}/photo",
        files={"photo": ("counter.jpg", _photo_bytes(orientation=6), "image/jpeg")},
    )
    saved = Image.open(photo_dir / "9300601234567.jpg")

    assert saved.format == "JPEG"
    assert max(saved.size) == 800                        # long edge, SPEC §5
    assert saved.size == (600, 800), "EXIF orientation 6 means this is portrait"
    assert not dict(saved.getexif()), "EXIF is stripped — an iPad photo carries GPS"
    assert (photo_dir / "9300601234567.jpg").stat().st_size < 80 * 1024


def test_a_photo_appears_on_batches_recorded_months_ago(client, sample):
    """It hangs off the barcode, so it backfills everything already recorded."""
    assert "thumb-empty" in client.get("/").text
    client.post(
        f"/products/{sample['products']['monster']}/photo",
        files={"photo": ("counter.jpg", _photo_bytes(), "image/jpeg")},
    )
    body = client.get("/").text
    assert "/data/photos/9300601234567.jpg" in body


def test_replacing_a_photo_leaves_no_orphan(client, sample, photo_dir):
    for _ in range(3):
        client.post(
            f"/products/{sample['products']['monster']}/photo",
            files={"photo": ("counter.jpg", _photo_bytes(), "image/jpeg")},
        )
    files = [p for p in photo_dir.iterdir() if p.is_file()]
    assert len(files) == 1, files


def test_the_photo_url_changes_when_the_photo_does(client, sample):
    """Same filename every time, so without a stamp an iPad shows a stale one."""
    client.post(
        f"/products/{sample['products']['monster']}/photo",
        files={"photo": ("counter.jpg", _photo_bytes(), "image/jpeg")},
    )
    body = client.get(f"/products/{sample['products']['monster']}").text
    assert "9300601234567.jpg?v=" in body
    assert "?v=0" not in body


def test_a_file_that_is_not_an_image_is_refused_politely(client, sample, db):
    response = client.post(
        f"/products/{sample['products']['monster']}/photo",
        files={"photo": ("notes.txt", b"this is not a photograph", "text/plain")},
    )
    assert response.status_code == 200
    assert "not an image" in response.text
    assert db.execute(
        "SELECT image_path FROM products WHERE id = ?", (sample["products"]["monster"],)
    ).fetchone()[0] is None


def test_the_photo_form_offers_a_file_and_a_camera(client, sample):
    """The file input covers uploads and Take Photo on iOS; the camera button
    is unhidden by script only where getUserMedia can actually work."""
    body = client.get(f"/products/{sample['products']['monster']}").text
    assert 'type="file"' in body and 'accept="image/*"' in body
    assert 'id="camera"' in body
    js = client.get("/static/js/photo.js").text
    assert "getUserMedia" in js
    assert "canvas" in js               # shrunk in the browser before upload


def test_a_product_with_no_photo_is_a_normal_state(client, sample):
    """Nothing in the add path waits for a camera."""
    for path in ("/", "/products", f"/products/{sample['products']['curly']}"):
        assert "thumb-empty" in client.get(path).text


# --------------------------------------------------- weekly discount sheet

def test_sheet_lists_what_is_due_in_the_window(client, sample, db):
    body = client.get("/sheet").text
    assert "C/RIDGE WATER 1L" in body                  # due in 2 days
    far_off = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["outside"],)
    ).fetchone()[0]
    assert _au(far_off) not in body                    # 30 days out, not this week


def test_sheet_range_is_adjustable(client, sample, db):
    far_off = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["outside"],)
    ).fetchone()[0]
    assert _au(far_off) in client.get("/sheet?days=45").text


def test_sheet_groups_by_category_with_uncategorised_last(client, sample, db):
    """The categorised item needs an in-window date now the range is bounded."""
    db.execute(
        "INSERT INTO batches (product_id, expiry_date, status, added_by) "
        "VALUES (?, ?, 'active', ?)",
        (sample["products"]["monster"], days(3), sample["user_id"]),
    )
    db.commit()
    body = client.get("/sheet").text
    assert body.index("Energy Drinks") < body.index("No category")
    assert "Uncategorised" not in body


def test_sheet_sorts_by_date_within_a_group(client, sample, db):
    """Two uncategorised items: the water in 2 days, the Tim Tams in 7."""
    body = client.get("/sheet").text
    assert body.index("C/RIDGE WATER 1L") < body.index("Tim Tam")


def test_sheet_has_a_tick_box_and_a_blank_price_column(client, sample):
    body = client.get("/sheet").text
    assert 'class="tick"' in body
    assert "Price" in body
    assert '<td class="col-price"></td>' in body       # blank, for a pen


def test_sheet_shows_the_barcode_on_every_line(client, sample):
    body = client.get("/sheet").text
    assert "9300609876543" in body


def test_sheet_hides_resolved_batches(client, sample, db):
    resolved = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["resolved"],)
    ).fetchone()[0]
    assert _au(resolved) not in client.get("/sheet").text


def test_sheet_leaves_out_past_date_items(client, sample, db):
    """Amended 13 Aug: the sheet is a pricing list, not the worklist.

    A past-date item is not discounted, it is pulled off the shelf. Before this
    the shop's real sheet opened with 27 of them ahead of the week's work.
    """
    overdue = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["overdue"],)
    ).fetchone()[0]
    body = client.get("/sheet").text
    assert _au(overdue) not in body
    assert "Monster Ultra Zero 500ml" not in body   # its only other date is 30 days out
    assert "(past)" not in body                     # the marker has nothing left to mark


def test_the_due_screen_still_shows_the_past_date_backlog(client, sample, db):
    """The two screens diverge deliberately — this is the half that must not.

    One definition of "due" survives: the Due screen is the worklist, and a
    past-date item is the most urgent thing on it. If bounding the sheet ever
    gets copied into home.py, this goes red.
    """
    overdue = db.execute(
        "SELECT expiry_date FROM batches WHERE id = ?", (sample["batches"]["overdue"],)
    ).fetchone()[0]
    body = client.get("/").text
    assert _au(overdue) in body
    assert "Monster Ultra Zero 500ml" in body


def test_sheet_includes_an_item_expiring_today(client, sample, db):
    """The lower bound is inclusive: today's stock still wants a sticker.

    Asserted on a product name rather than on today's date, because the sheet
    title prints today either way — checking the date alone passes against a
    sheet bounded with `>` and catches nothing.
    """
    product_id = db.execute(
        "INSERT INTO products (barcode, name) VALUES ('9300602222222', ?)",
        ("Dies Today Yoghurt 170g",),
    ).lastrowid
    db.execute(
        "INSERT INTO batches (product_id, expiry_date, status, added_by) "
        "VALUES (?, ?, 'active', ?)",
        (product_id, days(0), sample["user_id"]),
    )
    db.commit()
    assert "Dies Today Yoghurt 170g" in client.get("/sheet").text


def test_sheet_survives_an_absurd_range(client, sample):
    assert client.get("/sheet?days=99999").status_code == 200
    assert client.get("/sheet?days=0").status_code == 200


def test_sheet_prints_without_the_navigation(client, sample):
    """A4 print CSS: no nav, no chrome, no toner-eating backgrounds."""
    css = client.get("/static/css/app.css").text
    assert "@page" in css and "size: A4" in css
    assert ".bar, .no-print" in css


# --------------------------------------------------------------- settings

def test_settings_opens_for_anyone_signed_in(client):
    """No admin tier, no manager PIN — everyone gets the same app."""
    response = client.get("/settings")
    assert response.status_code == 200
    for word in ("Expiry window", "Categories", "Staff", "Backup"):
        assert word in response.text


def test_the_expiry_window_can_be_changed_and_the_screens_follow(client, sample, db):
    """It is a setting precisely so this does not need a code change."""
    assert "Arnott" in client.get("/").text            # 7 days out, inside the window
    client.post("/settings/window", data={"days": 3})
    assert db.execute(
        "SELECT value FROM settings WHERE key = 'expiry_window_days'"
    ).fetchone()[0] == "3"
    assert "Arnott" not in client.get("/").text
    assert "Due within 3 days" in client.get("/").text


def test_an_absurd_window_is_clamped_not_crashed(client, db):
    client.post("/settings/window", data={"days": 100000})
    assert client.get("/").status_code == 200


def test_a_category_can_be_added_here(client, db, staff):
    client.post("/settings/categories", data={"name": "Chocolate"})
    row = db.execute("SELECT created_by FROM categories WHERE name = 'Chocolate'").fetchone()
    assert row is not None and row["created_by"] == staff["id"]


def test_adding_a_case_variant_category_is_refused_politely(client, sample):
    body = client.post(
        "/settings/categories", data={"name": "ENERGY DRINKS"}, follow_redirects=True
    ).text
    assert "already a category with that name" in body
    assert "IntegrityError" not in body


def test_renaming_a_category_reaches_every_product_in_it(client, sample, db):
    client.post(f"/settings/categories/{sample['cat_id']}", data={"name": "Energy"})
    assert db.execute(
        """SELECT c.name FROM products p JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?""",
        (sample["products"]["monster"],),
    ).fetchone()[0] == "Energy"


def test_staff_can_be_added_and_can_then_sign_in(client, anon_client, db):
    client.post("/settings/staff", data={"name": "Sarah", "pin": "4821"})
    new_id = db.execute("SELECT id FROM users WHERE name = 'Sarah'").fetchone()[0]

    client.get("/logout")
    response = anon_client.post(
        "/login", data={"user_id": new_id, "pin": "4821"}, follow_redirects=False
    )
    assert response.status_code == 303


def test_a_pin_that_is_not_four_digits_is_refused(client, db):
    body = client.post(
        "/settings/staff", data={"name": "Bad PIN", "pin": "12"}, follow_redirects=True
    ).text
    assert "exactly 4 digits" in body
    assert db.execute("SELECT COUNT(*) FROM users WHERE name = 'Bad PIN'").fetchone()[0] == 0


def test_resetting_a_pin_changes_which_one_works(client, anon_client, staff):
    client.post(f"/settings/staff/{staff['id']}/pin", data={"pin": "5150"})
    client.get("/logout")

    assert anon_client.post(
        "/login", data={"user_id": staff["id"], "pin": STAFF_PIN}, follow_redirects=False
    ).status_code == 200                                  # the old one no longer works
    assert anon_client.post(
        "/login", data={"user_id": staff["id"], "pin": "5150"}, follow_redirects=False
    ).status_code == 303


# ------------------------------------------------------ camera scanning
# Iteration 2 item 3. The aisle half of scanning. The counter gun is the path
# used hundreds of times a week and must come out of this untouched.

def test_the_camera_button_ships_hidden(client):
    """It is revealed by JS only where getUserMedia exists.

    Anywhere a camera could not be opened — the shop's http address before the
    certificates go on — it stays hidden rather than appearing and failing.
    """
    body = client.get("/scan").text
    tag = body.split('id="scan-camera"')[1].split(">")[0]
    assert "hidden" in tag


def test_the_camera_fills_the_same_field_and_submits_the_same_form(client):
    """One route, one lookup, one duplicate check — however the barcode arrived."""
    body = client.get("/scan").text
    assert 'id="barcode-form"' in body
    assert 'action="/scan"' in body
    assert 'method="get"' in body
    # The button is inside that form and is type=button, so it cannot itself
    # submit a blank lookup before anything has been decoded.
    tag = body.split('id="scan-camera"')[1].split(">")[0]
    assert 'type="button"' in tag


def test_a_decoded_barcode_takes_the_ordinary_path(client, sample, db, staff):
    """Whatever the camera fills in is just a barcode in the query string."""
    body = client.get("/scan?barcode=9300601234567").text
    assert "Monster Ultra Zero 500ml" in body

    # ...and the duplicate rule still applies to it, exactly as when typed.
    client.post("/scan/add", data={"barcode": "9300601234567", "expiry_date": days(50)})
    body = client.post(
        "/scan/add", data={"barcode": "9300601234567", "expiry_date": days(50)},
        follow_redirects=True,
    ).text
    assert "Already tracked" in body
    assert db.execute(
        "SELECT COUNT(*) FROM batches WHERE product_id = ? AND expiry_date = ?",
        (sample["products"]["monster"], days(50)),
    ).fetchone()[0] == 1


def test_the_scanner_library_is_served_from_static_vendor(client):
    response = client.get("/static/vendor/zxing-0.21.3.min.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "ZXing" in response.text[:400]


def test_the_scanner_script_is_absent_from_the_date_step(client, sample):
    """The counter path is scan, type date, Enter. It carries no scanner code."""
    body = client.get("/scan?barcode=9300601234567").text
    assert "scanner.js" not in body
    assert 'id="scan-camera"' not in body


def test_the_heavy_library_is_not_loaded_up_front(client):
    """336 KB must not land on the gun path. scanner.js injects it on demand."""
    body = client.get("/scan").text
    assert "scanner.js" in body
    assert "zxing" not in body.lower()


def test_the_counter_flow_is_unchanged(client, sample, db, staff):
    """Scan, type date, Enter — no mouse, and nothing new in the way."""
    body = client.get("/scan").text
    assert "autofocus" in body.split('id="barcode"')[1].split(">")[0]

    body = client.get("/scan?barcode=9300601234567").text
    assert "autofocus" in body.split('id="expiry"')[1].split(">")[0]

    response = client.post(
        "/scan/add", data={"barcode": "9300601234567", "expiry_date": days(55)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db.execute(
        "SELECT added_by FROM batches WHERE expiry_date = ?", (days(55),)
    ).fetchone()[0] == staff["id"]


# ------------------------------------------------- renaming and retiring staff
# Iteration 2 item 1. The two imported accounts are `BP TECOMA` and `sar ob`,
# both still on the placeholder PIN, and until they are dealt with the audit
# trail says BP TECOMA for everybody.

def test_somebody_can_be_renamed(client, anon_client, db, staff):
    """`sar ob` becoming a real name is the whole point of this."""
    client.post(f"/settings/staff/{staff['id']}/name", data={"name": "Sarah O’Brien"})
    assert db.execute(
        "SELECT name FROM users WHERE id = ?", (staff["id"],)
    ).fetchone()[0] == "Sarah O’Brien"

    client.get("/logout")
    assert "Sarah O’Brien" in anon_client.get("/login").text
    assert STAFF_NAME not in anon_client.get("/login").text


def test_a_rename_carries_every_entry_that_person_ever_made(client, sample):
    """added_by points at the row, so the history follows the name.

    This is the behaviour that makes renaming the shared `BP TECOMA` login
    into a person wrong, and it is why the screen shows the entry count.
    """
    client.post(f"/settings/staff/{sample['user_id']}/name", data={"name": "Mohit Pandya"})
    body = client.get(f"/products/{sample['products']['monster']}").text
    assert "Added by Mohit Pandya" in body


def test_a_rename_does_not_move_any_history(client, sample, db):
    """Renaming must not touch the batches themselves — same rows, same ids."""
    before = db.execute(
        "SELECT COUNT(*) FROM batches WHERE added_by = ?", (sample["user_id"],)
    ).fetchone()[0]
    client.post(f"/settings/staff/{sample['user_id']}/name", data={"name": "Mohit Pandya"})
    assert db.execute(
        "SELECT COUNT(*) FROM batches WHERE added_by = ?", (sample["user_id"],)
    ).fetchone()[0] == before
    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2


def test_the_header_shows_the_new_name_without_signing_in_again(client, staff):
    """The cookie still holds the old name; the page must not."""
    client.post(f"/settings/staff/{staff['id']}/name", data={"name": "Sarah O’Brien"})
    body = client.get("/").text
    assert "Sarah O’Brien" in body
    assert STAFF_NAME not in body


def test_renaming_somebody_to_a_case_variant_of_somebody_else_is_refused(client, db, staff):
    """Two Sarahs on the keypad screen and nobody knows which one is theirs."""
    client.post("/settings/staff", data={"name": "Sarah", "pin": "4821"})
    body = client.post(
        f"/settings/staff/{staff['id']}/name", data={"name": "SARAH"}, follow_redirects=True
    ).text
    assert "already has that name" in body
    assert "IntegrityError" not in body
    assert db.execute(
        "SELECT name FROM users WHERE id = ?", (staff["id"],)
    ).fetchone()[0] == STAFF_NAME


def test_adding_a_case_variant_of_an_existing_person_is_refused(client, db, staff):
    body = client.post(
        "/settings/staff", data={"name": STAFF_NAME.lower(), "pin": "4821"},
        follow_redirects=True,
    ).text
    assert "already has that name" in body
    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_somebody_can_be_recased_without_colliding_with_themselves(client, db, staff):
    """`sar ob` -> `Sar Ob` is a rename, not a duplicate."""
    client.post(f"/settings/staff/{staff['id']}/name", data={"name": STAFF_NAME.upper()})
    assert db.execute(
        "SELECT name FROM users WHERE id = ?", (staff["id"],)
    ).fetchone()[0] == STAFF_NAME.upper()


def test_a_blank_staff_name_is_refused(client, db, staff):
    body = client.post(
        f"/settings/staff/{staff['id']}/name", data={"name": "   "}, follow_redirects=True
    ).text
    assert "Give the person a name" in body
    assert db.execute(
        "SELECT name FROM users WHERE id = ?", (staff["id"],)
    ).fetchone()[0] == STAFF_NAME


def test_somebody_taken_off_the_list_cannot_sign_in(client, anon_client, staff):
    client.post("/settings/staff", data={"name": "Sarah", "pin": "4821"})
    client.post(f"/settings/staff/{staff['id']}/active", data={"active": "0"})
    client.get("/logout")

    assert STAFF_NAME not in anon_client.get("/login").text
    assert anon_client.post(
        "/login", data={"user_id": staff["id"], "pin": STAFF_PIN}, follow_redirects=False
    ).status_code == 200                                  # re-rendered, not signed in


def test_taking_somebody_off_the_list_deletes_nothing(client, sample, db):
    """Their entries have to stay readable — that is the whole reason for it."""
    client.post("/settings/staff", data={"name": "Sarah", "pin": "4821"})
    client.post(f"/settings/staff/{sample['user_id']}/active", data={"active": "0"})

    assert db.execute(
        "SELECT COUNT(*) FROM batches WHERE added_by = ?", (sample["user_id"],)
    ).fetchone()[0] == 5
    assert "Added by Mohit" in client.get(
        f"/products/{sample['products']['monster']}"
    ).text


def test_somebody_taken_off_the_list_can_be_put_back(client, anon_client, db):
    """A misclick has to be undoable, so there is no confirm step on the way in."""
    client.post("/settings/staff", data={"name": "Sarah", "pin": "4821"})
    sarah = db.execute("SELECT id FROM users WHERE name = 'Sarah'").fetchone()[0]

    client.post(f"/settings/staff/{sarah}/active", data={"active": "0"})
    assert "Off the sign-in list" in client.get("/settings").text
    assert db.execute("SELECT active FROM users WHERE id = ?", (sarah,)).fetchone()[0] == 0

    client.post(f"/settings/staff/{sarah}/active", data={"active": "1"})
    assert "Off the sign-in list" not in client.get("/settings").text

    client.get("/logout")                      # the sign-in list needs a signed-out client
    assert "Sarah" in anon_client.get("/login").text


def test_the_staff_list_shows_how_many_entries_each_person_has(client, sample, staff):
    """So nobody renames a 2,290-entry shared login without seeing the 2,290."""
    body = client.get("/settings").text
    assert "5 entries" in body                            # sample's user
    assert "0 entries" in body                            # the signed-in one


def test_the_off_the_list_card_is_absent_when_everyone_is_on_it(client, staff):
    assert "Off the sign-in list" not in client.get("/settings").text


def test_backup_runs_on_demand_and_is_reported(client, db_path):
    body = client.get("/settings").text
    assert "No backup has been taken yet" in body

    client.post("/settings/backup")
    snapshots = list((db_path.parent / "backups").glob("tecoma-*.db"))
    assert len(snapshots) == 1
    assert "Last backup:" in client.get("/settings").text


def test_backup_snapshots_the_database_the_app_is_using(client, db_path, sample):
    """Never data/tecoma.db while a test is running — it follows the connection."""
    from scripts.init_db import DB_PATH, connect

    client.post("/settings/backup")
    snapshot = next((db_path.parent / "backups").glob("tecoma-*.db"))
    assert snapshot.parent != DB_PATH.parent

    copy = connect(snapshot)
    assert copy.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 3
    copy.close()


# ----------------------------------------------------------- the Excel export

def _sheet(response):
    """The one worksheet in a downloaded export."""
    from io import BytesIO

    from openpyxl import load_workbook

    return load_workbook(BytesIO(response.content)).active


def test_settings_offers_the_export(client, sample):
    body = client.get("/settings").text
    assert "/settings/export.xlsx" in body
    assert "Export to Excel" in body
    assert "5 of them" in body                    # sample has five batches


def test_the_export_downloads_as_a_spreadsheet(client, sample):
    import datetime as dt

    response = client.get("/settings/export.xlsx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert f"tecoma-{dt.date.today().isoformat()}.xlsx" in disposition


def test_the_export_has_one_row_per_batch_and_a_header(client, sample):
    sheet = _sheet(client.get("/settings/export.xlsx"))
    assert sheet.max_row == 6                      # header + five batches
    headings = [c.value for c in sheet[1]]
    assert headings[:6] == ["Product", "Barcode", "Category", "Expiry",
                            "Days left", "Status"]


def test_the_export_includes_resolved_batches(client, sample):
    """Pulled rows are kept so waste can be reviewed — the export is where."""
    sheet = _sheet(client.get("/settings/export.xlsx"))
    statuses = [row[5].value for row in sheet.iter_rows(min_row=2)]
    assert "pulled" in statuses
    assert statuses.count("active") == 4


def test_the_export_opens_on_what_is_still_on_the_shelf(client, sample):
    """Live rows first, soonest first. Sorted by date alone, the shop's 583
    pulled rows sit above everything that still matters."""
    statuses = [row[5].value for row in _sheet(client.get("/settings/export.xlsx"))
                .iter_rows(min_row=2)]
    assert statuses[0] == "active"
    assert statuses[-1] == "pulled"
    assert statuses.index("pulled") == 4, "a resolved row is mixed in among the live ones"


def test_the_export_shows_uncategorised_as_blank_not_a_word(client, sample):
    """There is no 'Uncategorised' category and the export must not invent one."""
    sheet = _sheet(client.get("/settings/export.xlsx"))
    categories = [row[2].value for row in sheet.iter_rows(min_row=2)]
    assert None in categories
    assert "Uncategorised" not in str(categories)


def test_the_export_counts_days_from_today(client, sample):
    sheet = _sheet(client.get("/settings/export.xlsx"))
    by_days = {row[4].value for row in sheet.iter_rows(min_row=2)}
    assert -4 in by_days                            # sample's overdue batch
    assert 7 in by_days                             # the one on the window edge


def test_the_export_names_who_added_each_row(client, sample):
    sheet = _sheet(client.get("/settings/export.xlsx"))
    assert {row[7].value for row in sheet.iter_rows(min_row=2)} == {"Mohit"}


def test_the_export_is_behind_the_pin(anon_client, sample):
    response = anon_client.get("/settings/export.xlsx", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_settings_has_no_role_or_admin_anything(client):
    body = client.get("/settings").text.lower()
    for word in ("admin", "manager", "role", "permission"):
        assert word not in body


def test_static_assets_are_served(client):
    response = client.get("/static/css/app.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_no_api_docs_exposed(client):
    """docs_url=None — staff should never land on FastAPI's Swagger page."""
    assert client.get("/docs").status_code == 404


def test_unknown_route_is_not_a_crash(client):
    assert client.get("/does-not-exist").status_code == 404


def _au(iso: str) -> str:
    """Mirror of the au_date filter, so page assertions read naturally."""
    from app.main import au_date

    return au_date(iso)
