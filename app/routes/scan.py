"""Scan & add. Backlog item 2, SPEC §3.3.

The screen the app exists for — used hundreds of times a week, so it gets the
fussiest treatment and everything else can be plain.

Counted keystrokes for a barcode the shop already knows:

    1. the scanner gun fires the barcode and its own trailing Enter
    2. type the date          (the field already has focus)
    3. Enter

That is the floor. There is no mouse in it, nothing to confirm afterwards, and
no wizard state — each step is a page the server rendered, so a laptop that
sleeps between two of them loses nothing that was already saved.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.auth import current_user
from app.catalogue import (
    categories,
    clean_barcode,
    clean_name,
    get_product_by_barcode,
    live_batch,
    parse_barcode,
    parse_expiry,
    resolve_category,
)
from app import photos
from app.db import get_conn
from app.views import au_date, render, setting

router = APIRouter()


def _page(request, conn, **context):
    context.setdefault("product", None)
    context.setdefault("barcode", "")
    context.setdefault("message", "")
    context.setdefault("saved", None)
    # What was typed, handed back so a rejected date does not also lose the
    # name someone just entered for a new product.
    context.setdefault("typed", {"name": "", "category": ""})
    return render(request, conn, "scan.html", categories=categories(conn), **context)


@router.get("/scan")
def scan(
    request: Request,
    barcode: str = "",
    added: int | None = None,
    photo_problem: str = "",
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Step one: the barcode. Step two if a barcode came with the request."""
    # Refused here as well as on the write path, so a typed word never opens
    # the new-product form and nobody fills in a name for something that will
    # be rejected on save. A rejected barcode falls back to step one, where
    # the field is focused and ready for another scan.
    # A photo that Pillow refused on the previous add. The batch itself saved —
    # that is the whole point of reporting it here rather than failing the add —
    # so this says what did not happen, next to the confirmation of what did.
    # Says which of the two things happened, in that order: the date is the
    # point of the screen, so it is reported first and the photo second. The
    # reason travels as a code (see app/photos.py) rather than being assumed —
    # it used to always read "it was not an image", which is the wrong sentence
    # for a picture that was a perfectly good image and merely too big.
    message = (
        f"The date saved, but the photo did not. {photos.problem_message(photo_problem)}"
        if photo_problem else ""
    )
    barcode = clean_barcode(barcode)
    if barcode:
        barcode, message = parse_barcode(barcode)

    # What the last add saved, read back from the database rather than carried
    # in the browser — there is no client-side state between entries.
    saved = None
    if added:
        saved = conn.execute(
            """SELECT b.expiry_date, p.name
                 FROM batches b JOIN products p ON p.id = b.product_id
                WHERE b.id = ?""",
            (added,),
        ).fetchone()

    product = get_product_by_barcode(conn, barcode) if barcode else None
    return _page(
        request, conn, barcode=barcode, product=product, saved=saved, message=message
    )


@router.post("/scan/add")
def add(
    request: Request,
    barcode: str = Form(""),
    name: str = Form(""),
    category: str = Form(""),
    expiry_date: str = Form(""),
    photo: UploadFile | None = File(None),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    barcode, bad_barcode = parse_barcode(barcode)
    name = clean_name(name)
    product = get_product_by_barcode(conn, barcode) if barcode else None

    def again(message: str):
        """Back to the same step, with the reason and nothing lost."""
        return _page(
            request,
            conn,
            barcode=barcode,
            product=product,
            message=message,
            typed={"name": name, "category": category},
        )

    # Covers the empty field too — parse_barcode says "Scan a barcode." for it.
    if bad_barcode:
        return again(bad_barcode)

    expiry, problem = parse_expiry(expiry_date)
    if problem:
        return again(problem)

    if product is None and not name:
        return again("This barcode is new — give it a name.")

    category_id = resolve_category(conn, category, user["id"])

    if product is None:
        product_id = conn.execute(
            "INSERT INTO products (barcode, name, category_id) VALUES (?, ?, ?)",
            (barcode, name, category_id),
        ).lastrowid
    else:
        product_id = product["id"]
        # A category typed against a known product attaches to the product, so
        # it covers every batch of that barcode, past and future.
        if category_id and category_id != product["category_id"]:
            conn.execute(
                "UPDATE products SET category_id = ? WHERE id = ?", (category_id, product_id)
            )

    existing = live_batch(conn, product_id, expiry.isoformat())
    if existing:
        conn.commit()   # keep the category or product edit; the batch is the duplicate
        return again(f"Already tracked — expires {au_date(existing['expiry_date'])}.")

    try:
        batch_id = conn.execute(
            "INSERT INTO batches (product_id, expiry_date, added_by) VALUES (?, ?, ?)",
            (product_id, expiry.isoformat(), user["id"]),
        ).lastrowid
    except sqlite3.IntegrityError:
        # The index did the catching. Same words either way — nobody needs to
        # know which layer noticed, and there is no quantity to offer to raise.
        conn.rollback()
        return again(f"Already tracked — expires {au_date(expiry)}.")

    # The photo, last, and never in the way of the date.
    #
    # Added 16 Aug. 944 of the shop's 945 products had no picture, because the
    # only place to attach one was behind the Edit toggle on the product screen
    # — a trip nobody makes later, for an item they are no longer holding. This
    # is the moment it is in a hand.
    #
    # It is deliberately not allowed to fail the add: the batch is already
    # written above, and a rejected image says so on the next screen rather than
    # throwing away a date that was typed correctly. That is the same order of
    # priorities as everything else here — the date is the point, the photo is a
    # bonus.
    stored, problem = photos.store_upload(
        photo,
        barcode,
        max_px=int(setting(conn, "image_max_px", "800")),
        quality=int(setting(conn, "image_quality", "72")),
    )
    if stored:
        conn.execute(
            "UPDATE products SET image_path = ? WHERE id = ?", (stored, product_id)
        )

    conn.commit()
    if problem:
        return RedirectResponse(
            f"/scan?added={batch_id}&photo_problem={problem}", status_code=303
        )
    return RedirectResponse(f"/scan?added={batch_id}", status_code=303)
