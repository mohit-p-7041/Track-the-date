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
    "staff-renamed": "Name changed.",
    "staff-off": "Taken off the sign-in list. Their past entries keep their name.",
    "staff-back": "Back on the sign-in list.",
    "staff-last": "That is the only person left who can sign in.",
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
        # Everyone, not just the active ones, so someone taken off the list by
        # accident can be put back. The entry count is here because renaming
        # an account renames every entry it ever made: the two imported
        # accounts hold 2,290 and 50 batches between them, and whoever is
        # about to rename one should see that number before they do.
        staff=conn.execute(
            """SELECT u.id, u.name, u.active,
                      (SELECT COUNT(*) FROM batches b WHERE b.added_by = u.id) AS entries
                 FROM users u
             ORDER BY u.name COLLATE NOCASE"""
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


def _name_taken(conn: sqlite3.Connection, name: str, exclude_id: int = 0) -> bool:
    """Is somebody else already called this, ignoring case?

    `users.name` is UNIQUE, but that is case-sensitive — the database would
    happily hold Sarah and sarah, and the sign-in list would then show two
    Sarahs with no way to tell which is yours. Categories have a NOCASE unique
    index for the same reason; ten people typing names freely is the same
    problem in both places.
    """
    return conn.execute(
        "SELECT 1 FROM users WHERE name = ? COLLATE NOCASE AND id != ?",
        (name, exclude_id),
    ).fetchone() is not None


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
    if _name_taken(conn, name):
        return _back("staff-exists")
    try:
        conn.execute("INSERT INTO users (name, pin_hash, pin_salt) VALUES (?, ?, ?)",
                     (name, pin_hash, pin_salt))
    except sqlite3.IntegrityError:
        return _back("staff-exists")
    conn.commit()
    return _back("staff-added")


@router.post("/settings/staff/{user_id}/name")
def rename_staff(
    user_id: int,
    name: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Fix a name — a typo, a shorthand, or a married name.

    This does not move any history. `batches.added_by` points at the row, so
    every entry this account ever made now reads under the new name. That is
    right when it is the same person under a tidier name, and wrong when it is
    the old app's shared `BP TECOMA` login being turned into a real person —
    2,290 entries would start claiming somebody made them. Retiring that one
    is what the button below is for. See docs/STAFF-SETUP.md.
    """
    name = " ".join(name.split())
    if not name:
        return _back("staff-blank")
    if _name_taken(conn, name, exclude_id=user_id):
        return _back("staff-exists")
    try:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
    except sqlite3.IntegrityError:
        return _back("staff-exists")
    conn.commit()
    return _back("staff-renamed")


@router.post("/settings/staff/{user_id}/active")
def set_staff_active(
    user_id: int,
    active: int = Form(...),
    conn: sqlite3.Connection = Depends(get_conn),
    user: dict = Depends(current_user),
):
    """Take somebody off the sign-in list, or put them back.

    Nothing is deleted: the row stays, so every batch they added keeps saying
    who added it. This is how somebody who has left the shop stops appearing
    on the keypad screen, and how the two imported accounts get retired
    without rewriting the history they carry.

    Taking yourself off is allowed. It has to be — on the day the real staff
    are set up, whoever is doing it is signed in as `BP TECOMA`, and that is
    the account being retired. There are no roles here; the only thing guarded
    is emptying the list completely, which would lock the shop out of its own
    laptop.
    """
    wanted = 1 if active else 0
    if not wanted:
        others = conn.execute(
            "SELECT COUNT(*) FROM users WHERE active = 1 AND id != ?", (user_id,)
        ).fetchone()[0]
        if not others:
            return _back("staff-last")
    conn.execute("UPDATE users SET active = ? WHERE id = ?", (wanted, user_id))
    conn.commit()
    return _back("staff-back" if wanted else "staff-off")


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
