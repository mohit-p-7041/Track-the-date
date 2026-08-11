"""Signing in. Backlog item 1, SPEC §3.1.

Two steps on one screen and no browser state: pick your name, then type four
digits. Picking a name is a link (`/login?user=3`), so the keypad step is a
plain page the server rendered — nothing to lose if the laptop sleeps between
the two taps.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.auth import sign_in, sign_out
from app.db import get_conn
from app.security import verify_pin
from app.views import render

router = APIRouter()

# Deliberately the same message whichever part was wrong. Not for secrecy —
# there is none here — but because "no such user" is noise to someone who just
# mistyped a digit.
WRONG = "That did not match. Try again."


def _staff(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name FROM users WHERE active = 1 ORDER BY name COLLATE NOCASE"
    ).fetchall()


@router.get("/login")
def login_form(
    request: Request,
    user: int | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    if getattr(request.state, "user", None):
        return RedirectResponse("/", status_code=303)

    staff = _staff(conn)
    person = next((s for s in staff if s["id"] == user), None)
    return render(request, conn, "login.html", staff=staff, person=person)


@router.post("/login")
def login_submit(
    request: Request,
    user_id: int = Form(...),
    pin: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
):
    row = conn.execute(
        "SELECT id, name, pin_hash, pin_salt FROM users WHERE id = ? AND active = 1",
        (user_id,),
    ).fetchone()

    if row is None or not verify_pin(pin.strip(), row["pin_hash"], row["pin_salt"]):
        staff = _staff(conn)
        person = next((s for s in staff if s["id"] == user_id), None)
        return render(request, conn, "login.html", staff=staff, person=person, message=WRONG)

    response = RedirectResponse("/", status_code=303)
    sign_in(response, row["id"], row["name"])
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    sign_out(response)
    return response
