"""PIN hashing.

Deliberately stdlib-only — no bcrypt/argon2 dependency to install on a shop
laptop. PBKDF2 with a per-user salt is well beyond what a 4-digit PIN on a
LAN-only app needs.

Note: a 4-digit PIN has 10,000 possible values, so this is an accountability
mechanism, not a security boundary. That is the intended design. Anyone on the
shop WiFi who wants in, gets in. The point is knowing who added what.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 100_000


def hash_pin(pin: str, salt: str | None = None) -> tuple[str, str]:
    """Return (hash_hex, salt_hex) for a PIN."""
    if not pin.isdigit() or len(pin) != 4:
        raise ValueError("PIN must be exactly 4 digits")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), _ITERATIONS)
    return digest.hex(), salt


def verify_pin(pin: str, pin_hash: str, pin_salt: str) -> bool:
    """Constant-time check of a PIN against a stored hash."""
    if not pin.isdigit() or len(pin) != 4:
        return False
    candidate, _ = hash_pin(pin, pin_salt)
    return hmac.compare_digest(candidate, pin_hash)
