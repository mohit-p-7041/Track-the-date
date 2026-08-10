"""Back up the database and photos.

    python scripts/backup.py              # run a backup, print what happened
    python scripts/backup.py --quiet      # only speak up if something is wrong

Called automatically by start.bat every time the app comes up. That timing is
deliberate: the shop laptop is not on overnight, so a scheduled 2am backup
would simply never run.

The database is copied with SQLite's own backup API rather than a file copy,
so it is safe to run even while the app is serving requests. Photos are copied
only when new or changed, so a backup costs almost nothing after the first.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.init_db import DB_PATH, connect  # noqa: E402

BACKUP_DIR = ROOT / "data" / "backups"
PHOTO_DIR = ROOT / "data" / "photos"
KEEP = 7


def backup_database(stamp: str) -> Path:
    """Consistent snapshot of the database, safe to take while the app runs."""
    target = BACKUP_DIR / f"tecoma-{stamp}.db"
    src = connect(DB_PATH)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def backup_photos() -> tuple[int, int]:
    """Copy photos that are new or newer than the backed-up copy."""
    mirror = BACKUP_DIR / "photos"
    mirror.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for photo in PHOTO_DIR.glob("*"):
        if not photo.is_file() or photo.suffix.lower() not in PHOTO_SUFFIXES:
            continue
        dest = mirror / photo.name
        if dest.exists() and dest.stat().st_mtime >= photo.stat().st_mtime:
            skipped += 1
            continue
        shutil.copy2(photo, dest)
        copied += 1
    return copied, skipped


def prune(keep: int = KEEP) -> int:
    """Keep the most recent N database snapshots."""
    snaps = sorted(BACKUP_DIR.glob("tecoma-*.db"), key=lambda p: p.stat().st_mtime)
    removed = 0
    for old in snaps[:-keep] if len(snaps) > keep else []:
        old.unlink()
        removed += 1
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="only report problems")
    ap.add_argument("--keep", type=int, default=KEEP)
    args = ap.parse_args()

    if not DB_PATH.exists():
        if not args.quiet:
            print("No database to back up yet.")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")

    try:
        db_file = backup_database(stamp)
        copied, skipped = backup_photos()
        removed = prune(args.keep)
    except Exception as exc:                      # noqa: BLE001
        # Never stop the app starting because a backup failed — but be loud.
        print(f"  WARNING: backup failed — {exc}")
        print("  The app will still start. Fix this before you rely on it.")
        return 1

    if not args.quiet:
        size = db_file.stat().st_size / 1024
        print(f"  Backed up to {db_file.relative_to(ROOT)} ({size:.0f} KB)")
        print(f"  Photos: {copied} copied, {skipped} already current")
        if removed:
            print(f"  Removed {removed} old snapshot(s), keeping {args.keep}")
        print()
        print("  These live on the same disk as the original. Copy data/backups")
        print("  to OneDrive or a USB stick, or a dead laptop takes both.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
