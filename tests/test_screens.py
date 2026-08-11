"""Does the app actually render?

`scripts/check_db.py` proves the data is sound. It cannot tell you that a
template throws, that a query returns the wrong rows, or that a route 500s.
This file is that half of the check.

Add a test here for every screen as it gets built — see docs/BACKLOG.md, which
lists the acceptance criteria each one has to meet.
"""

from __future__ import annotations

from conftest import days


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
