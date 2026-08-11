"""The home screen: what's due. SPEC §3.2.

Two groups, one window. Past-date items sit at the top because someone has to
deal with them, not because anything has gone wrong — 583 batches arrived from
the old app already expired and that is a normal Monday.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, Request

from app.db import get_conn
from app.views import render, window_days

router = APIRouter()


@router.get("/")
def home(
    request: Request,
    category: str | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    window = window_days(conn)
    today = dt.date.today()
    cutoff = (today + dt.timedelta(days=window)).isoformat()

    sql = """SELECT b.id, b.expiry_date, b.status,
                    p.id AS product_id, p.name, p.barcode, p.image_path,
                    c.name AS category
               FROM batches b
               JOIN products p ON p.id = b.product_id
          LEFT JOIN categories c ON c.id = p.category_id
              WHERE b.status IN ('active', 'discounted')
                AND b.expiry_date <= ?"""
    params: list = [cutoff]

    # 'none' is the filter for uncategorised, which is a normal state and not
    # a category — there is no 'Uncategorised' row to select instead.
    if category == "none":
        sql += " AND p.category_id IS NULL"
    elif category:
        sql += " AND p.category_id = ?"
        params.append(category)

    rows = conn.execute(sql + " ORDER BY b.expiry_date, p.name", params).fetchall()

    today_iso = today.isoformat()
    overdue = [r for r in rows if r["expiry_date"] < today_iso]
    due = [r for r in rows if r["expiry_date"] >= today_iso]

    return render(
        request,
        conn,
        "home.html",
        window=window,
        today=today,
        overdue=overdue,
        due=due,
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
