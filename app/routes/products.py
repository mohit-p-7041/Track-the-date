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
from app.catalogue import categories, resolve_category
from app.db import get_conn
from app.views import render, setting

router = APIRouter()

# 952 products render in one page happily on a laptop and sluggishly on an old
# iPad. Show the soonest by default; the count line says what is being held
# back and links to the rest.
PAGE = 100

RESOLUTIONS = {
    "discounted": "Discounted",
    "pulled": "Pulled",
    "sold": "Sold",
}

# Straight and curly apostrophes are the same character to a person typing.
NORMALISED_NAME = "REPLACE(p.name, '’', '''')"


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


def _detail_page(request: Request, conn: sqlite3.Connection, product_id: int, message: str = ""):
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
                  r.name AS resolved_by_name
             FROM batches b
        LEFT JOIN users a ON a.id = b.added_by
        LEFT JOIN users r ON r.id = b.resolved_by
            WHERE b.product_id = ?
         ORDER BY b.status IN ('pulled','sold'), b.expiry_date""",
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
    )


@router.post("/products/{product_id}/category")
def set_category(
    request: Request,
    product_id: int,
    category: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """One category per barcode, so this reaches every batch of it at once."""
    category_id = resolve_category(conn, category, user["id"])
    conn.execute("UPDATE products SET category_id = ? WHERE id = ?", (category_id, product_id))
    conn.commit()
    return RedirectResponse(f"/products/{product_id}", status_code=303)


@router.post("/products/{product_id}/photo")
def set_photo(
    request: Request,
    product_id: int,
    photo: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Attach a photo to the barcode. Never required, and it backfills.

    The browser has usually shrunk this already (see static/js/photo.js), so
    what arrives is normally well under a megabyte. Pillow runs regardless —
    the resize is the guarantee, the browser side is only there to keep four
    megabytes off the shop WiFi.
    """
    product = conn.execute(
        "SELECT id, barcode, image_path FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if product is None:
        raise HTTPException(status_code=404)

    # Read synchronously: this route resizes an image, and a sync route runs
    # in the threadpool instead of blocking the event loop while it does.
    data = photo.file.read()
    if not data:
        return RedirectResponse(f"/products/{product_id}", status_code=303)
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
        # than showing a stack trace to someone holding an iPad.
        return _detail_page(request, conn, product_id, message="That file was not an image.")

    conn.execute("UPDATE products SET image_path = ? WHERE id = ?", (stored, product_id))
    conn.commit()
    return RedirectResponse(f"/products/{product_id}", status_code=303)


@router.post("/products/{product_id}/batches/{batch_id}")
def resolve_batch(
    request: Request,
    product_id: int,
    batch_id: int,
    status: str = Form(...),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Mark a batch discounted, pulled or sold.

    An update, never a delete: waste has to stay reviewable, and the row keeps
    who resolved it and when.
    """
    if status not in RESOLUTIONS:
        raise HTTPException(status_code=400, detail="Unknown status")

    conn.execute(
        "UPDATE batches SET status = ?, resolved_by = ?, resolved_at = datetime('now') "
        "WHERE id = ? AND product_id = ?",
        (status, user["id"], batch_id, product_id),
    )
    conn.commit()
    return RedirectResponse(f"/products/{product_id}", status_code=303)
