"""The weekly discount sheet. Backlog item 7, SPEC §4.

Printed on the weekend and carried round the aisles. Staff tick items off on
paper and mark them discounted in the app afterwards, so the page is a list to
write on rather than a screen to use: no navigation, no colour, and a blank
column for the price.

It shows exactly what the home screen shows — the same window, and past-date
items included — because two definitions of "due" would eventually disagree
and the shelf would follow the wrong one.
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

    rows = conn.execute(
        """SELECT b.expiry_date, b.status, p.name, p.barcode,
                  c.name AS category
             FROM batches b
             JOIN products p ON p.id = b.product_id
        LEFT JOIN categories c ON c.id = p.category_id
            WHERE b.status IN ('active', 'discounted')
              AND b.expiry_date <= ?
         ORDER BY c.name IS NULL, c.name COLLATE NOCASE, b.expiry_date,
                  p.name COLLATE NOCASE""",
        (cutoff,),
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
