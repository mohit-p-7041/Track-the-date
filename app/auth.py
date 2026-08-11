"""Who is signed in.

PINs are accountability, not security — see CLAUDE.md. This is a LAN-only app
and a 4-digit PIN has ten thousand values. The point is that every batch can
say who added it and who resolved it, not to keep anyone out.

So: a signed cookie holding the user's id and name, checked by one middleware,
and no lockouts, no complexity rules, no roles.

The signing key lives in `data/session.key` rather than in the settings table
on purpose. The middleware runs before routing and has no `Depends(get_conn)`
to take a connection from, and a middleware that called connect() itself would
read the shop's real database during a test run — the exact thing app/db.py
exists to prevent. A file keeps the middleware away from the database
entirely.
"""

from __future__ import annotations

import secrets
import sqlite3
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.db import get_conn

ROOT = Path(__file__).resolve().parent.parent
KEY_FILE = ROOT / "data" / "session.key"

COOKIE_NAME = "ttd_session"

# Long enough that staff are not re-entering PINs all weekend, short enough
# that a forgotten iPad in a drawer eventually signs itself out.
MAX_AGE_SECONDS = 30 * 24 * 60 * 60

# Everything else needs a signed-in user. /static is here because the login
# page itself needs its stylesheet.
PUBLIC_PREFIXES = ("/login", "/logout", "/static/", "/favicon.ico")

_serializer: URLSafeTimedSerializer | None = None


def _secret() -> str:
    """The signing key, created on first use and reused after that.

    Rotating it signs everyone out, which is a mild inconvenience and never a
    data problem — so a lost key file is not an incident.
    """
    if not KEY_FILE.exists():
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
        KEY_FILE.chmod(0o600)
    return KEY_FILE.read_text(encoding="utf-8").strip()


def serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(_secret(), salt="ttd-session")
    return _serializer


def sign_in(response, user_id: int, name: str) -> None:
    """Attach the session cookie to a response."""
    token = serializer().dumps({"id": user_id, "name": name})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


def sign_out(response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def read_session(request: Request) -> dict | None:
    """The signed-in user from the cookie, or None if there isn't a valid one."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = serializer().loads(token, max_age=MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or "id" not in data:
        return None
    return {"id": int(data["id"]), "name": str(data.get("name", ""))}


def is_public(path: str) -> bool:
    return path == "/login" or path.startswith(PUBLIC_PREFIXES)


async def session_middleware(request: Request, call_next):
    """Put the signed-in user on the request, or send them to sign in.

    Every route can then read `request.state.user` — no route re-checks the
    cookie, and no route can accidentally be left unprotected.
    """
    request.state.user = read_session(request)
    if request.state.user is None and not is_public(request.url.path):
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


def is_active(conn: sqlite3.Connection, user_id: int) -> bool:
    """Is this account still on the sign-in list?"""
    row = conn.execute("SELECT active FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["active"])


def current_user(
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Dependency: the signed-in user. Guaranteed by the middleware.

    Every route that writes takes this, so this is where an account taken off
    the sign-in list stops being able to add anything. The middleware cannot
    do it — it runs before routing and has no connection, deliberately (see
    the note at the top of this file), so it trusts the cookie alone. That
    cookie lasts thirty days, which is long enough for an iPad still holding
    a retired account's session to keep stamping batches with it. Checking
    here closes that: taking someone off the list takes effect on the next
    thing they try to save, not thirty days later.

    Reading is left alone. Browsing as a retired account writes nothing and
    misattributes nothing, and bouncing someone out of a page they are only
    looking at would be noise.
    """
    user = getattr(request.state, "user", None)
    if user is None:  # pragma: no cover — the middleware redirects first
        raise RuntimeError("current_user used on a public route")
    if not is_active(conn, user["id"]):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user
