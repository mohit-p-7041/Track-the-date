"""Track the Date — Tecoma.

The FastAPI application: wiring only. Every screen lives in app/routes/, the
templates and helpers in app/views.py, and who's signed in in app/auth.py.

See SPEC.md for the design and CLAUDE.md for the working rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import photos  # noqa: E402
from app.auth import session_middleware  # noqa: E402
from app.routes import home, login, products, scan, settings, sheet  # noqa: E402
from app.views import au_date, templates  # noqa: E402,F401  (au_date re-exported: tests import it from here)

app = FastAPI(title="Track the Date — Tecoma", docs_url=None, redoc_url=None)

# Signed-in-or-redirect, applied to everything. Routes never re-check.
app.middleware("http")(session_middleware)


# How long a browser may keep an asset. A URL carrying `?v=` was built by
# asset_url() or photo_url(), which stamp the file's own modification time into
# it — so that URL's bytes can never change, and it is safe to keep for a year.
# Editing the file produces a different URL, which is the whole point of the
# stamp (see app/views.py). Anything unstamped gets five minutes instead: the
# icons and manifest.json are referenced by plain path from base.html, and
# caching those forever would mean a redrawn icon never reaching a device.
VERSIONED = "max-age=31536000, immutable"
UNVERSIONED = "max-age=300"


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    """Let devices keep assets instead of re-asking for them every page.

    Without this the shop's iPads revalidate the stylesheet, three scripts and
    every thumbnail on *every* navigation. Each one comes back "304 Not
    Modified" — the bytes are saved but the round trip is not, and on shop WiFi
    the round trips are the slow part.

    Photos are marked private rather than public: they sit behind the PIN, and
    while a LAN has no shared proxy to leak them to, saying so costs nothing.
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") or path.startswith("/data/photos/"):
        scope = "private" if path.startswith("/data/photos/") else "public"
        freshness = VERSIONED if request.query_params.get("v") else UNVERSIONED
        response.headers["Cache-Control"] = f"{scope}, {freshness}"
    return response


# Compression, and it is the single biggest thing on this list. The Due screen
# is the first page of every session and renders every live batch: 485 KB of
# HTML on the shop's data, which is ~2.6s of a weak WiFi link before anything
# appears. Gzipped it is 20 KB. Measured, not guessed.
#
# Level 6, not the library's default 9: on this HTML the two are within about
# one percent of each other and 9 costs several times the CPU, on a laptop that
# is also serving everything else.
#
# Added last, so it wraps everything else and compresses the finished response.
# It has no content-type opinion, so it also spends about a millisecond failing
# to compress each JPEG — which the cache headers above turn into a once-per-
# photo cost rather than a once-per-page one.
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)

photos.photo_dir().mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")


# Photos are files on disk, not rows — see SPEC §5. Served from the path stored on
# the product, so a template can use src="/{{ image_path }}".
#
# A route rather than a StaticFiles mount, and that is the whole point. Punch list
# item 8: this was a mount over a hardcoded ROOT / "data" / "photos" while
# photos.py honoured TTD_PHOTO_DIR, so with the variable set — which the LAN test
# server does — uploads were written to one directory and served from another and
# every photo rendered broken. Production had the variable unset, both hardcoded
# paths agreed, and it took an iPad session to notice.
#
# Asking photos.photo_dir() at import would fix production and leave the bug
# untestable, because a mount binds its directory once and the suite points each
# test at a fresh temp folder. Resolved per request, the two halves cannot
# disagree and a broken photo URL finally fails a test.
@app.get("/data/photos/{filename}")
def photo_file(filename: str):
    root = photos.photo_dir().resolve()
    path = (root / filename).resolve()
    # A filename is a barcode plus .jpg. Anything that climbs out of the folder
    # is not one, and this is the one place a request names a file on disk.
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)

app.include_router(login.router)
app.include_router(home.router)
app.include_router(scan.router)
app.include_router(products.router)
app.include_router(sheet.router)
app.include_router(settings.router)


# ---------------------------------------------------------------- error pages
#
# A stale bookmark, a product another iPad deleted a minute ago, or a typo in
# the address used to reach staff as `{"detail":"Not Found"}` in the middle of
# a blank page. That is not a message, and on an iPad it reads as the whole app
# being broken rather than one link being out of date.
#
# What each of these has to preserve is the redirect. `current_user` raises a
# 303 carrying a Location header to bounce an account that has been taken off
# the sign-in list, and the sign-in middleware depends on that still being a
# redirect and not a page saying "303". So anything with a Location goes back
# out as one, untouched.

WORDS = {
    404: ("Not found", "That page or product is not here. It may have been deleted."),
    403: ("Not allowed", "That is not something this account can do."),
    405: ("Not found", "That page or product is not here. It may have been deleted."),
}
GENERIC = ("Something went wrong", "The app hit a problem and could not finish that.")


def _error_page(request: Request, status_code: int):
    heading, detail = WORDS.get(status_code, GENERIC)
    return templates.TemplateResponse(
        request,
        "error.html",
        {"heading": heading, "detail": detail},
        status_code=status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_page(request: Request, exc: StarletteHTTPException):
    location = (exc.headers or {}).get("Location") or (exc.headers or {}).get("location")
    if location:
        # A redirect wearing an exception's clothes — see the note above.
        return RedirectResponse(location, status_code=exc.status_code)
    if exc.status_code < 400:
        return await http_exception_handler(request, exc)
    return _error_page(request, exc.status_code)


@app.exception_handler(Exception)
async def server_error_page(request: Request, exc: Exception):
    """A crash, shown as a sentence instead of a blank page.

    Starlette re-raises after this returns, so the traceback still reaches the
    log that scripts/serve.py writes — the person gets the sentence, and the
    detail is still there to debug from. Nothing about the error is put on the
    screen: it would mean nothing to whoever is holding the iPad.
    """
    return _error_page(request, 500)
