"""The weekly discount sheet. Backlog item 7, SPEC §4.

Printed on the weekend and carried round the aisles. Staff tick items off on
paper and mark them discounted in the app afterwards, so the page is a list to
write on rather than a screen to use: no navigation, no colour, and a blank
column for the price.

The range is bounded at both ends — today to the cutoff. Amended 13 Aug, after
the first iPad session found 27 past-date rows printing ahead of the week's
work. Iteration 1 had this show exactly what the home screen shows, on the
grounds that two definitions of "due" would disagree and the shelf would follow
the wrong one. They are not two definitions of the same thing:

- the Due screen is a worklist — everything unresolved, past included, because
  a past-date item is the most urgent thing there is
- this sheet is a pricing list — things still sellable that want a sticker this
  week. A past-date item is not discounted, it is pulled off the shelf

One definition of "due" survives; the sheet is a narrower question asked of it.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from itertools import groupby

from fastapi import APIRouter, Depends, Request

from app.db import get_conn
from app.views import render, window_days

router = APIRouter()

MAX_DAYS = 90


@router.get("/sheet")
def sheet(
    request: Request,
    days: int | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    window = window_days(conn) if days is None else max(1, min(days, MAX_DAYS))
    today = dt.date.today()
    cutoff = (today + dt.timedelta(days=window)).isoformat()

    # Bounded at both ends. An item expiring today still wants a sticker, so
    # the lower bound is inclusive; anything already past its date is a pull,
    # not a discount, and belongs on the Due screen instead.
    rows = conn.execute(
        """SELECT b.expiry_date, b.status, p.name, p.barcode,
                  c.name AS category
             FROM batches b
             JOIN products p ON p.id = b.product_id
        LEFT JOIN categories c ON c.id = p.category_id
            WHERE b.status IN ('active', 'discounted')
              AND b.expiry_date >= ?
              AND b.expiry_date <= ?
         ORDER BY c.name IS NULL, c.name COLLATE NOCASE, b.expiry_date,
                  p.name COLLATE NOCASE""",
        (today.isoformat(), cutoff),
    ).fetchall()

    # Uncategorised sorts last and is headed plainly. There is no
    # 'Uncategorised' category and this does not invent one.
    groups = [
        (name, list(items))
        for name, items in groupby(rows, key=lambda r: r["category"])
    ]

    return render(
        request,
        conn,
        "sheet.html",
        groups=groups,
        total=len(rows),
        window=window,
        today=today,
        cutoff=cutoff,
    )
