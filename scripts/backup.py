"""Back up the database and photos.

    python scripts/backup.py              # run a backup, print what happened
    python scripts/backup.py --quiet      # only speak up if something is wrong

Called automatically when the app comes up, and every two hours while it is up
— see `start_periodic_backup()` in scripts/serve.py. That timing is deliberate:
the shop laptop is not on overnight, so a scheduled 2am job would simply never
run, and the backup has to happen inside the session or not at all.

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

# Two, decided 15 Aug, down from seven: the shop wanted the folder not to pile
# up. Photos are mirrored into one shared folder rather than copied per
# snapshot, so this is only ever about the .db files — about 550 KB each.
#
# Know what it costs. Two snapshots plus the two-hourly rhythm in serve.py
# means the oldest one you can go back to is a couple of hours old, so a
# mistake noticed the next day has no snapshot from before it. That is the
# trade for a tidy folder, and it is a one-word change here if it ever bites.
KEEP = 2


def backup_database(stamp: str, db_path: Path = DB_PATH,
                    backup_dir: Path = BACKUP_DIR) -> Path:
    """Consistent snapshot of the database, safe to take while the app runs."""
    target = backup_dir / f"tecoma-{stamp}.db"
    src = connect(db_path)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def backup_photos(photo_dir: Path = PHOTO_DIR, backup_dir: Path = BACKUP_DIR) -> tuple[int, int]:
    """Copy photos that are new or newer than the backed-up copy."""
    mirror = backup_dir / "photos"
    mirror.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    if not photo_dir.exists():
        return 0, 0
    for photo in photo_dir.glob("*"):
        if not photo.is_file() or photo.suffix.lower() not in PHOTO_SUFFIXES:
            continue
        dest = mirror / photo.name
        if dest.exists() and dest.stat().st_mtime >= photo.stat().st_mtime:
            skipped += 1
            continue
        shutil.copy2(photo, dest)
        copied += 1
    return copied, skipped


def prune(keep: int = KEEP, backup_dir: Path = BACKUP_DIR) -> int:
    """Keep the most recent N database snapshots, and nothing else.

    A snapshot can leave a `-wal` and a `-shm` beside it — SQLite's backup API
    copies the journal mode across, and if the laptop is closed mid-write those
    two are still there next time. Deleting the `.db` and walking away from its
    sidecars is how a folder asked to hold two files ends up holding six, so
    they go with it, and any orphan left by an earlier run goes too.

    Only `.db` files are counted in the number returned. They are the backups;
    the rest is bookkeeping.
    """
    snaps = sorted(backup_dir.glob("tecoma-*.db"), key=lambda p: p.stat().st_mtime)
    removed = 0
    for old in snaps[:-keep] if len(snaps) > keep else []:
        old.unlink()
        removed += 1

    live = {p.name for p in backup_dir.glob("tecoma-*.db")}
    for suffix in ("-wal", "-shm"):
        for sidecar in backup_dir.glob(f"tecoma-*.db{suffix}"):
            # "tecoma-2026-08-13_1646.db-wal" -> "tecoma-2026-08-13_1646.db"
            if sidecar.name.rsplit("-", 1)[0] not in live:
                sidecar.unlink(missing_ok=True)
    return removed


def last_backup(backup_dir: Path = BACKUP_DIR) -> Path | None:
    """The most recent snapshot, or None if nothing has been backed up yet."""
    snaps = sorted(backup_dir.glob("tecoma-*.db"), key=lambda p: p.stat().st_mtime)
    return snaps[-1] if snaps else None


def run(db_path: Path = DB_PATH, backup_dir: Path = BACKUP_DIR,
        photo_dir: Path = PHOTO_DIR, keep: int = KEEP) -> dict:
    """Take a backup. Used by the CLI above and by the settings screen.

    The paths are arguments rather than constants so the app can back up
    whichever database it is actually serving — which is also what keeps a
    test run from snapshotting the shop's real data.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    db_file = backup_database(stamp, db_path, backup_dir)
    copied, skipped = backup_photos(photo_dir, backup_dir)
    removed = prune(keep, backup_dir)
    return {
        "file": db_file,
        "size": db_file.stat().st_size,
        "copied": copied,
        "skipped": skipped,
        "removed": removed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="only report problems")
    ap.add_argument("--keep", type=int, default=KEEP)
    args = ap.parse_args()

    if not DB_PATH.exists():
        if not args.quiet:
            print("No database to back up yet.")
        return 0

    try:
        result = run(keep=args.keep)
        db_file, copied = result["file"], result["copied"]
        skipped, removed = result["skipped"], result["removed"]
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
