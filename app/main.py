"""Track the Date — Tecoma.

The FastAPI application: wiring only. Every screen lives in app/routes/, the
templates and helpers in app/views.py, and who's signed in in app/auth.py.

See SPEC.md for the design and CLAUDE.md for the working rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import photos  # noqa: E402
from app.auth import session_middleware  # noqa: E402
from app.routes import home, login, products, scan, settings, sheet  # noqa: E402
from app.views import au_date  # noqa: E402,F401  (re-exported: the tests import it from here)

app = FastAPI(title="Track the Date — Tecoma", docs_url=None, redoc_url=None)

# Signed-in-or-redirect, applied to everything. Routes never re-check.
app.middleware("http")(session_middleware)

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
