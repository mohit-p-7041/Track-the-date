"""The home screen: what's due. SPEC §3.2.

Past-date items sit at the top because someone has to deal with them, not
because anything has gone wrong — 583 batches arrived from the old app already
expired and that is a normal Monday.

Below them, one band per day: Today, Tomorrow, 3 days left, and so on to the
edge of the window, then a single group for everything beyond it. Replaced the
one "Due within N days" heading on 16 Aug, to match the app this is standing in
for; see days_left_label() in app/catalogue.py.

Two consequences of that worth knowing, because both changed behaviour:

  - `expiry_window_days` no longer decides what appears on this screen. It
    decides where the per-day bands stop and the "More than a week" group
    starts. Nothing live is hidden from this page any more.
  - so the query has no date ceiling, and the shop's data puts 1644 batches
    past the window. Those are cut to PAGE with a "show all" link, the same way
    the products screen handles its 944 — a Chrome 50 handheld should not be
    handed a megabyte of HTML to scroll past on its way to what is due today.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, Request

from app.db import get_conn
from app.views import render, window_days

router = APIRouter()

# Matches products.py. The group past the window holds 1644 batches in the
# shop's data and almost none of them are anybody's business today.
PAGE = 100


@router.get("/")
def home(
    request: Request,
    category: str | None = None,
    later: str | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    window = window_days(conn)
    today = dt.date.today()

    sql = """SELECT b.id, b.expiry_date, b.status,
                    p.id AS product_id, p.name, p.barcode, p.image_path,
                    c.name AS category
               FROM batches b
               JOIN products p ON p.id = b.product_id
          LEFT JOIN categories c ON c.id = p.category_id
              WHERE b.status IN ('active', 'discounted')"""
    params: list = []

    # 'none' is the filter for uncategorised, which is a normal state and not
    # a category — there is no 'Uncategorised' row to select instead.
    if category == "none":
        sql += " AND p.category_id IS NULL"
    elif category:
        sql += " AND p.category_id = ?"
        params.append(category)

    rows = conn.execute(sql + " ORDER BY b.expiry_date, p.name", params).fetchall()

    today_iso = today.isoformat()
    cutoff_iso = (today + dt.timedelta(days=window)).isoformat()

    overdue = [r for r in rows if r["expiry_date"] < today_iso]
    beyond = [r for r in rows if r["expiry_date"] > cutoff_iso]

    # One band per day, and only for days that have something in them: an empty
    # "5 days left" heading is a line of furniture between the person and the
    # next thing they have to do. `rows` is already ordered by date, so each
    # day's run is contiguous and this stays a single pass.
    days: list[tuple[int, list]] = []
    for row in rows:
        if not (today_iso <= row["expiry_date"] <= cutoff_iso):
            continue
        left = (dt.date.fromisoformat(row["expiry_date"]) - today).days
        if not days or days[-1][0] != left:
            days.append((left, []))
        days[-1][1].append(row)

    later_shown = beyond if later == "all" else beyond[:PAGE]

    return render(
        request,
        conn,
        "home.html",
        window=window,
        today=today,
        overdue=overdue,
        days=days,
        later=later_shown,
        later_total=len(beyond),
        later_truncated=len(beyond) - len(later_shown),
        categories=conn.execute(
            "SELECT id, name FROM categories WHERE active = 1 "
            "ORDER BY sort_order, name COLLATE NOCASE"
        ).fetchall(),
        selected=category or "",
        total_products=conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        total_live=conn.execute(
            "SELECT COUNT(*) FROM batches WHERE status IN ('active','discounted')"
        ).fetchone()[0],
    )
