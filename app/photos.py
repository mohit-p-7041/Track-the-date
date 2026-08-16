"""Product photos. Backlog item 5, SPEC §5.

One photo per barcode, stored as a file rather than a row, so the database
stays small enough to snapshot on every startup. Because it hangs off the
product, adding one today makes it appear on batches recorded months ago.

The file name is the barcode, so replacing a photo overwrites the old one and
there is never an orphan to clean up.
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent

# Where the stored path points. Kept relative in the database so the value
# means the same thing on the shop laptop, on a dev machine and in a backup.
STORED_PREFIX = "data/photos"

MAX_UPLOAD_BYTES = 12 * 1024 * 1024


def photo_dir() -> Path:
    """The photo folder. Overridable so tests never write into the real one."""
    return Path(os.environ.get("TTD_PHOTO_DIR", str(ROOT / STORED_PREFIX)))


def fs_path(image_path: str | None) -> Path | None:
    """Stored path -> a file on this machine."""
    if not image_path:
        return None
    return photo_dir() / Path(image_path).name


def _file_name(barcode: str) -> str:
    """Barcodes are digits, but a typed one could be anything. Keep it a
    filename and nothing else — no directory separators, no surprises."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "", barcode) or "product"
    return f"{safe}.jpg"


def save(data: bytes, barcode: str, max_px: int = 800, quality: int = 72) -> tuple[str, int]:
    """Compress an upload and write it. Returns (stored path, bytes on disk).

    Pillow does the real work: honour the camera's rotation flag, then drop
    EXIF entirely (an iPad photo carries the shop's GPS position otherwise),
    long edge to max_px, JPEG at the configured quality.
    """
    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)      # apply the rotation...
    image = image.convert("RGB")                # ...then keep only pixels
    image.thumbnail((max_px, max_px))           # long edge, aspect kept

    directory = photo_dir()
    directory.mkdir(parents=True, exist_ok=True)
    name = _file_name(barcode)
    target = directory / name

    # Write beside it and move into place, so a photo taken while the laptop
    # is closing never leaves a half-written file behind the old one.
    staging = directory / f".{name}.part"
    image.save(staging, "JPEG", quality=quality, optimize=True, progressive=True)
    staging.replace(target)

    return f"{STORED_PREFIX}/{name}", target.stat().st_size


def store_upload(upload, barcode: str, max_px: int = 800, quality: int = 72):
    """Take an uploaded file off a form and store it, or say why not.

    Returns `(stored_path, error)`, and at most one of them is set. `(None,
    None)` means no file was offered — the normal case, because a photo is
    optional on every screen that accepts one and must never block an add.

    Extracted 16 Aug when the scan screen started accepting photos too. Both
    callers need the same four steps in the same order, and the interesting one
    is the last: Pillow raising on something that is not an image has to become
    a sentence on the page, not a stack trace in front of somebody standing at a
    shelf holding the item.

    Read synchronously — both callers are sync routes, so they run in the
    threadpool and this does not block the event loop while it decodes.
    """
    data = upload.file.read() if upload is not None else b""
    if not data:
        return None, None
    if len(data) > MAX_UPLOAD_BYTES:
        return None, "That photo is too big."
    try:
        stored, _size = save(data, barcode, max_px=max_px, quality=quality)
    except OSError:
        return None, "That file was not an image."
    return stored, None
