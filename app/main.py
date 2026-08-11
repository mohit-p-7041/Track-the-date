"""Track the Date — Tecoma.

The FastAPI application: wiring only. Every screen lives in app/routes/, the
templates and helpers in app/views.py, and who's signed in in app/auth.py.

See SPEC.md for the design and CLAUDE.md for the working rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.auth import session_middleware  # noqa: E402
from app.routes import home, login, products, scan, settings, sheet  # noqa: E402
from app.views import au_date  # noqa: E402,F401  (re-exported: the tests import it from here)

app = FastAPI(title="Track the Date — Tecoma", docs_url=None, redoc_url=None)

# Signed-in-or-redirect, applied to everything. Routes never re-check.
app.middleware("http")(session_middleware)

PHOTOS = ROOT / "data" / "photos"
PHOTOS.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
# Photos are files on disk, not rows — see SPEC §5. Served from the same path
# that is stored on the product, so a template can use src="/{{ image_path }}".
app.mount("/data/photos", StaticFiles(directory=PHOTOS), name="photos")

app.include_router(login.router)
app.include_router(home.router)
app.include_router(scan.router)
app.include_router(products.router)
app.include_router(sheet.router)
app.include_router(settings.router)
