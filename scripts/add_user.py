"""Add a member of staff, or reset an existing PIN.

    python scripts/add_user.py "Mohit" 4821
    python scripts/add_user.py "Mohit" 4821 --reset     # existing name, new PIN

Settings has the same thing with a screen around it (backlog item 8). This is
for the first person on a fresh database, when nobody can sign in yet.

There are no roles. Everyone added here can do everything.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.security import hash_pin  # noqa: E402
from scripts.init_db import DB_PATH, connect  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("pin", help="exactly 4 digits")
    ap.add_argument("--reset", action="store_true",
                    help="the name already exists; set a new PIN for it")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    args = ap.parse_args()

    name = args.name.strip()
    if not name:
        sys.exit("A name is required.")
    try:
        pin_hash, pin_salt = hash_pin(args.pin)
    except ValueError as exc:
        sys.exit(str(exc))
    if not args.db.exists():
        sys.exit(f"No database at {args.db}. Run: python scripts/init_db.py")

    conn = connect(args.db)
    existing = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()

    if existing and not args.reset:
        conn.close()
        sys.exit(f"{name} already exists. Use --reset to set a new PIN.")

    if existing:
        conn.execute(
            "UPDATE users SET pin_hash = ?, pin_salt = ?, active = 1 WHERE id = ?",
            (pin_hash, pin_salt, existing["id"]),
        )
        print(f"Reset the PIN for {name}.")
    else:
        conn.execute(
            "INSERT INTO users (name, pin_hash, pin_salt) VALUES (?, ?, ?)",
            (name, pin_hash, pin_salt),
        )
        print(f"Added {name}.")

    conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
