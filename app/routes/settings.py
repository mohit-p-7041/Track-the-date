"""Settings. Backlog item 8, SPEC §3.7.

Open to everyone. There are no roles, no admin tier and no manager PIN — about
ten people share one shop, and gating this behind a tier would only mean
waiting for whoever holds the tier.

Everything here is small: the expiry window, the category names, who can sign
in, and a backup button for before something risky.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.auth import current_user
from app.db import get_conn
from app.photos import photo_dir
from app.security import hash_pin
from app.views import render, window_days
from scripts import backup as backup_script

router = APIRouter()

# Short codes rather than free text in the URL: the message shown always comes
# from this file, not from whatever someone puts in the address bar.
MESSAGES = {
    "window": "Expiry window saved.",
    "category-added": "Category added.",
    "category-renamed": "Category renamed.",
    "category-exists": "There is already a category with that name.",
    "category-blank": "Give the category a name.",
    "staff-added": "Staff member added.",
    "staff-blank": "Give the person a name.",
    "staff-exists": "Somebody already has that name.",
    "staff-bad-pin": "A PIN is exactly 4 digits.",
    "pin-reset": "PIN reset.",
    "backed-up": "Backed up.",
    "backup-failed": "The backup did not finish. Check the laptop's disk space.",
}


def _db_path(conn: sqlite3.Connection) -> Path:
    """The file this connection is actually attached to.

    Asking the connection rather than assuming data/tecoma.db means a backup
    started from this screen follows the database the app is serving — which
    is what stops a test run from snapshotting the shop's real data.
    """
    for _seq, name, file in conn.execute("PRAGMA database_list"):
        if name == "main" and file:
            return Path(file)
    raise RuntimeError("this connection has no file behind it")


def _backup_dir(conn: sqlite3.Connection) -> Path:
    return _db_path(conn).parent / "backups"


@router.get("/settings")
def settings_page(
    request: Request,
    message: str = "",
    conn: sqlite3.Connection = Depends(get_conn),
):
    last = backup_script.last_backup(_backup_dir(conn))
    return render(
        request,
        conn,
        "settings.html",
        window=window_days(conn),
        categories=conn.execute(
            """SELECT c.id, c.name,
                      (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id) AS products
                 FROM categories c
             ORDER BY c.sort_order, c.name COLLATE NOCASE"""
        ).fetchall(),
        staff=conn.execute(
            "SELECT id, name FROM users WHERE active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall(),
        last_backup=last.name if last else None,
        backup_count=len(list(_backup_dir(conn).glob("tecoma-*.db")))
        if _backup_dir(conn).exists() else 0,
        message=MESSAGES.get(message, ""),
    )


def _back(code: str = "") -> RedirectResponse:
    return RedirectResponse(f"/settings?message={code}" if code else "/settings",
                            status_code=303)


@router.post("/settings/window")
def set_window(
    days: int = Form(...),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """One window, not a set of bands — this changes its length, nothing else."""
    days = max(1, min(days, 90))
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('expiry_window_days', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(days),),
    )
    conn.commit()
    return _back("window")


@router.post("/settings/categories")
def add_category(
    name: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    name = " ".join(name.split())
    if not name:
        return _back("category-blank")
    try:
        conn.execute("INSERT INTO categories (name, created_by) VALUES (?, ?)",
                     (name, user["id"]))
    except sqlite3.IntegrityError:
        return _back("category-exists")     # case-insensitive index caught it
    conn.commit()
    return _back("category-added")


@router.post("/settings/categories/{category_id}")
def rename_category(
    category_id: int,
    name: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Renaming reaches every product in it — the category is one row."""
    name = " ".join(name.split())
    if not name:
        return _back("category-blank")
    try:
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
    except sqlite3.IntegrityError:
        return _back("category-exists")
    conn.commit()
    return _back("category-renamed")


@router.post("/settings/staff")
def add_staff(
    name: str = Form(""),
    pin: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    name = " ".join(name.split())
    if not name:
        return _back("staff-blank")
    try:
        pin_hash, pin_salt = hash_pin(pin.strip())
    except ValueError:
        return _back("staff-bad-pin")
    try:
        conn.execute("INSERT INTO users (name, pin_hash, pin_salt) VALUES (?, ?, ?)",
                     (name, pin_hash, pin_salt))
    except sqlite3.IntegrityError:
        return _back("staff-exists")
    conn.commit()
    return _back("staff-added")


@router.post("/settings/staff/{user_id}/pin")
def reset_pin(
    user_id: int,
    pin: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Anyone can reset anyone's PIN. That is the decision — see SPEC §2."""
    try:
        pin_hash, pin_salt = hash_pin(pin.strip())
    except ValueError:
        return _back("staff-bad-pin")
    conn.execute("UPDATE users SET pin_hash = ?, pin_salt = ? WHERE id = ?",
                 (pin_hash, pin_salt, user_id))
    conn.commit()
    return _back("pin-reset")


@router.post("/settings/backup")
def backup_now(
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """The same backup start.bat runs, for before doing something risky."""
    try:
        backup_script.run(
            db_path=_db_path(conn),
            backup_dir=_backup_dir(conn),
            photo_dir=photo_dir(),
        )
    except Exception:                              # noqa: BLE001
        return _back("backup-failed")
    return _back("backed-up")
