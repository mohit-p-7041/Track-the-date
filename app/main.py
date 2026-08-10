"""Track the Date — Tecoma.

The FastAPI application. This is deliberately a small starting point, not the
finished app: it proves the whole stack works together (Python -> SQLite ->
Jinja2 -> browser) and gives the home screen something real to grow from.

Build the rest one screen at a time. See SPEC.md section 3 for the list, and
CLAUDE.md for the rules. Route modules go in app/routes/ as they appear.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.init_db import connect  # noqa: E402

app = FastAPI(title="Track the Date — Tecoma", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "app" / "templates")


def au_date(value: str | dt.date) -> str:
    """'2026-08-14' -> '14 Aug 2026'. Australian format, never US.

    Built by hand rather than with strftime('%-d'), which is not portable —
    that format code does not exist on Windows, and this runs on Windows.
    """
    d = dt.date.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(d, dt.date):
        return str(value)
    return f"{d.day} {d:%b %Y}"


templates.env.filters["au_date"] = au_date


def setting(conn, key: str, default: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


@app.get("/")
def home(request: Request):
    """What's due. The first thing anyone sees."""
    conn = connect()
    try:
        window = int(setting(conn, "expiry_window_days", "7"))
        today = dt.date.today()
        cutoff = (today + dt.timedelta(days=window)).isoformat()

        rows = conn.execute(
            """SELECT b.id, b.expiry_date, b.status,
                      p.name, p.barcode, p.image_path,
                      c.name AS category
                 FROM batches b
                 JOIN products p ON p.id = b.product_id
            LEFT JOIN categories c ON c.id = p.category_id
                WHERE b.status IN ('active', 'discounted')
                  AND b.expiry_date <= ?
             ORDER BY b.expiry_date, p.name""",
            (cutoff,),
        ).fetchall()

        today_iso = today.isoformat()
        overdue = [r for r in rows if r["expiry_date"] < today_iso]
        due = [r for r in rows if r["expiry_date"] >= today_iso]

        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "shop_name": setting(conn, "shop_name", "BP Tecoma"),
                "window": window,
                "today": today,
                "overdue": overdue,
                "due": due,
                "total_products": conn.execute(
                    "SELECT COUNT(*) FROM products").fetchone()[0],
                "total_live": conn.execute(
                    "SELECT COUNT(*) FROM batches WHERE status IN "
                    "('active','discounted')").fetchone()[0],
            },
        )
    finally:
        conn.close()
