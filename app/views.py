"""Templates, the date filter, and the small helpers every screen needs.

This lives apart from app/main.py so route modules can import it without
importing the application object back the other way.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parent.parent

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


# The shop is GMT+10. SQLite's datetime('now') is UTC, so stamps need shifting
# before anyone reads them. These say "who did this, roughly when" — they are
# not read to the minute, and daylight saving is not worth a dependency here.
SHOP_OFFSET = dt.timedelta(hours=10)


def au_when(value: str | None) -> str:
    """'2024-12-22 20:11:06' -> '22 Dec 2024, 8:11 pm'.

    Timestamps are stored by SQLite's datetime('now'), which is UTC. The shop
    is GMT+10 and nobody there thinks in UTC, so shift before displaying.

    Built by hand for the same reason as au_date: '%-I' does not exist on
    Windows either.
    """
    if not value:
        return ""
    try:
        stamp = dt.datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return str(value)
    stamp = stamp + SHOP_OFFSET
    hour = stamp.hour % 12 or 12
    meridiem = "am" if stamp.hour < 12 else "pm"
    return f"{au_date(stamp.date())}, {hour}:{stamp:%M} {meridiem}"


def photo_url(image_path: str | None) -> str:
    """The src for a product photo, stamped with the file's own timestamp.

    Photos are keyed to the barcode, so replacing one reuses the same name.
    Without the stamp an iPad would keep showing the picture it cached weeks
    ago; with it, a replacement appears immediately and nothing is re-fetched
    unnecessarily in between.
    """
    from app.photos import fs_path  # local: keeps Pillow out of import order

    path = fs_path(image_path)
    stamp = int(path.stat().st_mtime) if path and path.exists() else 0
    return f"/{image_path}?v={stamp}"


templates.env.filters["au_date"] = au_date
templates.env.filters["au_when"] = au_when
templates.env.globals["photo_url"] = photo_url


def setting(conn: sqlite3.Connection, key: str, default: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def window_days(conn: sqlite3.Connection) -> int:
    """The one expiry window, read from settings rather than hard-coded."""
    try:
        return int(setting(conn, "expiry_window_days", "7"))
    except ValueError:
        return 7


def signed_in_name(request: Request, conn: sqlite3.Connection) -> dict | None:
    """The signed-in user, with the name the database holds right now.

    The cookie carries the name it was signed in with, which goes stale the
    moment somebody is renamed in Settings — the header would keep saying
    `BP TECOMA` until that person happened to sign in again. Writes were never
    affected (they stamp the id), but a screen showing a name that is no
    longer anyone's is the sort of thing that makes people distrust the rest
    of the page.
    """
    user = getattr(request.state, "user", None)
    if not user:
        return None
    row = conn.execute("SELECT name FROM users WHERE id = ?", (user["id"],)).fetchone()
    return {**user, "name": row["name"]} if row else user


def render(
    request: Request,
    conn: sqlite3.Connection,
    template: str,
    status_code: int = 200,
    **context,
) -> HTMLResponse:
    """Render a template with the things every page needs already in place.

    `shop_name` is in base.html and `user` is in the header, so putting them
    here means no route can forget them and render a page with a blank title
    or no way to sign out.
    """
    base = {
        "shop_name": setting(conn, "shop_name", "BP Tecoma"),
        "user": signed_in_name(request, conn),
        "today": dt.date.today(),
    }
    base.update(context)
    return templates.TemplateResponse(request, template, base, status_code=status_code)
