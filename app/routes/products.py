"""Product list and detail. Backlog item 6, SPEC §3.4 and §3.5.

Search has to cope with the names that are actually in the database rather
than the ones anyone would design: inconsistent case, trailing whitespace,
curly apostrophes, abbreviations like `C/RIDGE WATER 1L`. Fix the search, not
the data — staff recognise those names.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from app import photos
from app.auth import current_user
from app.catalogue import (
    categories,
    clean_name,
    live_batch,
    parse_expiry,
    resolve_category,
)
from app.db import get_conn
from app.views import au_date, render, setting

router = APIRouter()

# 952 products render in one page happily on a laptop and sluggishly on an old
# iPad. Show the soonest by default; the count line says what is being held
# back and links to the rest.
PAGE = 100

# Two endings, not four. Amended 13 Aug — see CLAUDE.md. A batch gets a
# discount sticker, or it is deleted for real. 'pulled' and 'sold' were never
# used once by the shop.
RESOLUTIONS = {
    "discounted": "Discounted",
}

# Straight and curly apostrophes are the same character to a person typing.
NORMALISED_NAME = "REPLACE(p.name, '’', '''')"

# Where the Due screen's rows post back to, so acting on a batch from there
# returns there instead of jumping to the product.
RETURN_PATHS = ("/", "/products")


def _back(next: str, product_id: int) -> str:
    """Where to send someone after they act on a batch.

    Only a known path is honoured. `next` arrives in a form field, and a route
    that redirects to whatever it is handed is an open redirect — worth
    refusing even on a LAN app, because it costs one comparison.
    """
    return next if next in RETURN_PATHS else f"/products/{product_id}"


def _tokens(query: str) -> list[str]:
    """The search words, tidied the same way the stored names get tidied.

    Whitespace-tolerant because the export has trailing spaces in it, and
    case-insensitive because SQLite's LIKE already is for ASCII.
    """
    return (query or "").replace("’", "'").split()


@router.get("/products")
def product_list(
    request: Request,
    q: str = "",
    category: str | None = None,
    all: str = "",
    conn: sqlite3.Connection = Depends(get_conn),
):
    tokens = _tokens(q)

    # One point per word found in the name or the barcode. Everything that
    # matches at least one word is shown, best first — so "cool ridge" still
    # surfaces C/RIDGE WATER 1L on the strength of "ridge", which an
    # all-words-must-match search would drop entirely.
    if tokens:
        score = " + ".join(
            [f"(CASE WHEN {NORMALISED_NAME} LIKE ? OR p.barcode LIKE ? THEN 1 ELSE 0 END)"]
            * len(tokens)
        )
    else:
        score = "0"

    params: list = []
    for token in tokens:
        params += [f"%{token}%", f"%{token}%"]

    where = ["1 = 1"]
    if category == "none":
        where.append("p.category_id IS NULL")
    elif category:
        where.append("p.category_id = ?")
        params.append(category)

    sql = f"""
        SELECT * FROM (
            SELECT p.id, p.name, p.barcode, p.image_path,
                   c.name AS category,
                   (SELECT MIN(expiry_date) FROM batches b
                     WHERE b.product_id = p.id
                       AND b.status IN ('active','discounted')) AS next_expiry,
                   (SELECT COUNT(*) FROM batches b
                     WHERE b.product_id = p.id
                       AND b.status IN ('active','discounted')) AS live_count,
                   {score} AS score
              FROM products p
         LEFT JOIN categories c ON c.id = p.category_id
             WHERE {' AND '.join(where)}
        )
        WHERE score > 0 OR ? = 0
        ORDER BY score DESC, next_expiry IS NULL, next_expiry, name COLLATE NOCASE
    """
    params.append(len(tokens))

    rows = conn.execute(sql, params).fetchall()
    shown = rows if all else rows[:PAGE]

    return render(
        request,
        conn,
        "products.html",
        rows=shown,
        total=len(rows),
        truncated=len(rows) - len(shown),
        q=q,
        categories=categories(conn),
        selected=category or "",
    )


@router.get("/products/{product_id}")
def product_detail(
    request: Request,
    product_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
):
    return _detail_page(request, conn, product_id)


def _detail_page(request: Request, conn: sqlite3.Connection, product_id: int,
                 message: str = "", editing: bool = False):
    product = conn.execute(
        """SELECT p.*, c.name AS category_name
             FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?""",
        (product_id,),
    ).fetchone()
    if product is None:
        raise HTTPException(status_code=404)

    batches = conn.execute(
        """SELECT b.*,
                  a.name AS added_by_name,
                  r.name AS resolved_by_name,
                  e.name AS edited_by_name
             FROM batches b
        LEFT JOIN users a ON a.id = b.added_by
        LEFT JOIN users r ON r.id = b.resolved_by
        LEFT JOIN users e ON e.id = b.edited_by
            WHERE b.product_id = ?
         ORDER BY b.expiry_date""",
        (product_id,),
    ).fetchall()

    return render(
        request,
        conn,
        "product.html",
        product=product,
        batches=batches,
        categories=categories(conn),
        resolutions=RESOLUTIONS,
        today=dt.date.today().isoformat(),
        message=message,
        editing=editing,
    )


@router.post("/products/{product_id}/edit")
def edit_product(
    request: Request,
    product_id: int,
    name: str = Form(""),
    category: str = Form(""),
    photo: UploadFile | None = File(None),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Everything editable about a product, in one form.

    Replaced the separate category and photo routes on 13 Aug. The screen used
    to show both pickers permanently, so after saving a category the picker sat
    there redisplaying the value and read like unfinished work rather than a
    saved fact. One Edit toggle, one form, one Save.

    **Renaming is deliberate**, and this is where iteration 1's open question got
    settled: staff can rename a product. The imported names stay as they are by
    default because staff recognise them, nothing renames automatically, and
    there is no bulk tidy-up — but a name typed wrong at 7am can be corrected.
    The barcode is not editable: that is the product's identity, and a wrong one
    is a different product.
    """
    product = conn.execute(
        "SELECT id, barcode, image_path FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if product is None:
        raise HTTPException(status_code=404)

    name = clean_name(name)
    if not name:
        return _detail_page(request, conn, product_id, editing=True,
                            message="Give the product a name.")

    # One category per barcode, so this reaches every batch of it at once.
    category_id = resolve_category(conn, category, user["id"])
    conn.execute(
        "UPDATE products SET name = ?, category_id = ? WHERE id = ?",
        (name, category_id, product_id),
    )

    # Read synchronously: this route resizes an image, and a sync route runs in
    # the threadpool instead of blocking the event loop while it does.
    data = photo.file.read() if photo is not None else b""
    if data:
        if len(data) > photos.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="That image is too big")
        try:
            stored, _size = photos.save(
                data,
                product["barcode"],
                max_px=int(setting(conn, "image_max_px", "800")),
                quality=int(setting(conn, "image_quality", "72")),
            )
        except OSError:
            # Not an image, or one Pillow cannot read. Say so on the page rather
            # than showing a stack trace to somebody holding an iPad.
            #
            # The name and category go with it: one form, one save. The rollback
            # is explicit rather than load-bearing — get_conn closes without
            # committing, which discards them anyway — but it says so, and it is
            # what keeps this correct if a commit is ever added above.
            conn.rollback()
            return _detail_page(request, conn, product_id, editing=True,
                                message="That file was not an image.")
        conn.execute("UPDATE products SET image_path = ? WHERE id = ?", (stored, product_id))

    conn.commit()
    return RedirectResponse(f"/products/{product_id}", status_code=303)


@router.post("/products/{product_id}/batches/{batch_id}")
def resolve_batch(
    request: Request,
    product_id: int,
    batch_id: int,
    status: str = Form(...),
    next: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Mark a batch discounted — the only resolution there is.

    The other ending is deletion, which is `delete_batch` below. 'pulled' and
    'sold' were removed on 13 Aug; a status this does not recognise is refused
    rather than written, and the CHECK constraint is the backstop.
    """
    if status not in RESOLUTIONS:
        raise HTTPException(status_code=400, detail="Unknown status")

    conn.execute(
        "UPDATE batches SET status = ?, resolved_by = ?, resolved_at = datetime('now') "
        "WHERE id = ? AND product_id = ?",
        (status, user["id"], batch_id, product_id),
    )
    conn.commit()
    return RedirectResponse(_back(next, product_id), status_code=303)


@router.post("/products/{product_id}/batches/{batch_id}/date")
def edit_batch_date(
    request: Request,
    product_id: int,
    batch_id: int,
    expiry_date: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Correct a date that was saved wrong.

    Deleting and rescanning already recovered from this, so what editing buys is
    the history that a delete throws away: who first recorded the batch, and
    when. Those stay, and the correction is attributed on top with
    `edited_by` / `edited_at`.

    It goes through the same two checks an add does, from app/catalogue.py, so
    there is one implementation of each:

      - `parse_expiry` — no US format, and an implausible year is refused
      - `live_batch` — moving a date onto one the product already has live is
        refused exactly as adding it would be, and `idx_batches_unique_live` is
        still the backstop underneath
    """
    batch = conn.execute(
        "SELECT id, expiry_date FROM batches WHERE id = ? AND product_id = ?",
        (batch_id, product_id),
    ).fetchone()
    if batch is None:
        raise HTTPException(status_code=404)

    expiry, problem = parse_expiry(expiry_date)
    if problem:
        return _detail_page(request, conn, product_id, message=problem)

    # Excluding this batch: saving the date it already has is a no-op, not a
    # clash with itself.
    clash = live_batch(conn, product_id, expiry.isoformat(), exclude_id=batch_id)
    if clash:
        return _detail_page(
            request, conn, product_id,
            message=f"Already tracked — expires {au_date(clash['expiry_date'])}.",
        )

    try:
        conn.execute(
            "UPDATE batches SET expiry_date = ?, edited_by = ?, edited_at = datetime('now') "
            "WHERE id = ? AND product_id = ?",
            (expiry.isoformat(), user["id"], batch_id, product_id),
        )
    except sqlite3.IntegrityError:
        # The index caught it. Same words either way — nobody needs to know
        # which layer noticed.
        conn.rollback()
        return _detail_page(
            request, conn, product_id,
            message=f"Already tracked — expires {au_date(expiry)}.",
        )

    conn.commit()
    return RedirectResponse(f"/products/{product_id}", status_code=303)


@router.post("/products/{product_id}/batches/{batch_id}/delete")
def delete_batch(
    request: Request,
    product_id: int,
    batch_id: int,
    next: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Really delete the batch. The row goes.

    This is the second of a batch's two endings, and it is a hard delete by
    decision: keeping a record of everything ever removed only grows, on a
    laptop nobody prunes, and the shop never used the statuses that did it.
    Take the Excel export if a snapshot of history is wanted.

    The product is never deleted, not even when this was its last batch.

    Whether staff were asked to confirm first is a question for the screen, not
    for here — see `needs_confirmation`. By the time this route runs, the
    decision has been made.
    """
    conn.execute(
        "DELETE FROM batches WHERE id = ? AND product_id = ?", (batch_id, product_id)
    )
    conn.commit()
    return RedirectResponse(_back(next, product_id), status_code=303)
