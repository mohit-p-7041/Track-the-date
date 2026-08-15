"""Bring the app up. This is what `start.bat` double-clicks into.

    python scripts/serve.py             # https on 8443 if certs exist, http on 8000 if not
    python scripts/serve.py --http      # force plain http, for when a certificate is the problem
    python scripts/serve.py --port 443  # a different port, if 8443 is ever taken

The address staff type must never change, so everything that decides it lives
here rather than in a batch file: one port for http, one for https, and both
fixed. `start.bat` passes its arguments straight through and does nothing else.

Why this exists at all, given start.bat used to call uvicorn directly:

  - **It refuses to start twice.** Double-clicking the icon a second time used
    to end in a red `[Errno 10048] address already in use` traceback, which
    reads like the app is broken when in fact it is already running.
  - **It writes a log.** A shop session happens with nobody watching the
    console. `data/logs/` is the only way to answer "what went wrong on
    Saturday" on the Monday.
  - **It checks the certificate still matches this machine's address.** If the
    laptop's IP moves, every iPad refuses to connect with a message that names
    neither the cause nor the fix. Cheap to detect here, and the fix is printed.
  - Batch is a poor language for conditionals and cannot be tested. This can:
    see tests/test_serve.py.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import logging
import os
import re
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import backup  # noqa: E402  (stdlib only, so a missing pip install can't break it)
from scripts.show_address import lan_ip, local_name  # noqa: E402,F401  (re-exported)

CERT = ROOT / "certs" / "cert.pem"
KEY = ROOT / "certs" / "key.pem"
DB = ROOT / "data" / "tecoma.db"
LOG_DIR = ROOT / "data" / "logs"

# Fixed, and the whole point. An iPad's home screen icon holds a URL including
# the port; change either number and every icon in the shop stops working.
HTTPS_PORT = 8443
HTTP_PORT = 8000

# A Saturday session writes a few thousand access lines, so a fortnight of them
# is well under a megabyte. Long enough to still have last weekend's when
# somebody mentions it on the Tuesday.
LOG_KEEP_DAYS = 14

# Backing up only at startup means a session that runs nine until three is
# backed up as it stood at nine. Two hours suits the shape of a scan session:
# a snapshot as it opens, another mid-session, and with backup.KEEP at two that
# is exactly what survives.
BACKUP_EVERY_SECONDS = 2 * 60 * 60


# --------------------------------------------------------------------------
# The address
# --------------------------------------------------------------------------

def port_free(port: int) -> bool:
    """Can we bind this port, or is the app already running?

    Deliberately no SO_REUSEADDR: on Windows that option lets a second bind
    succeed on a port already in use, which is the exact opposite of what is
    being asked here.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


# --------------------------------------------------------------------------
# The certificate
# --------------------------------------------------------------------------

def cert_names(path: Path) -> bytes | None:
    """The first certificate in a PEM file, as DER bytes.

    Read by hand rather than through `ssl` so this works on a file holding a
    chain, and so a malformed file is a `None` rather than an exception on the
    one code path that has to start the app.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(
        r"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", text, re.S
    )
    if not match:
        return None
    try:
        return base64.b64decode(match.group(1))
    except ValueError:
        return None


def cert_covers(der: bytes | None, name: str) -> bool:
    """Is `name` one of the addresses this certificate was issued for?

    A subjectAltName entry is a tag byte, a length byte and the value, so a
    hostname is `\\x82<len>tecoma.local` and an IPv4 address is `\\x87\\x04`
    plus its four bytes. Searching the DER for that is not a parser and does
    not pretend to be one — the answer only ever drives a printed warning, so a
    chance match costs a warning nobody sees rather than anything breaking.
    Parsing ASN.1 properly would mean a dependency, and the rule is that every
    dependency is a thing that can break on a shop laptop.
    """
    if not der:
        return False
    octets = name.split(".")
    if len(octets) == 4 and all(o.isdigit() and 0 <= int(o) < 256 for o in octets):
        return b"\x87\x04" + bytes(int(o) for o in octets) in der
    raw = name.encode()
    return len(raw) < 128 and b"\x82" + bytes([len(raw)]) + raw in der


def cert_warning(der: bytes | None, ip: str | None, host: str) -> str | None:
    """The line to print when the certificate no longer matches this laptop.

    This is the failure that costs a Saturday: the laptop picks up a different
    address, the certificate still names the old one, and every iPad refuses
    the connection without saying why. Detected in the two seconds before the
    server starts, with the command that fixes it.
    """
    missing = [n for n in (ip, host) if n and not cert_covers(der, n)]
    if not missing:
        return None
    names = " ".join(n for n in (host, ip, "localhost", "127.0.0.1") if n)
    return (
        "   WARNING: the certificate does not cover " + ", ".join(missing) + ".\n"
        "   Devices will refuse to connect on that address. Reissue it with:\n"
        "     mkcert -key-file certs\\key.pem -cert-file certs\\cert.pem " + names
    )


# --------------------------------------------------------------------------
# What to run
# --------------------------------------------------------------------------

def choose(force_http: bool = False, port: int | None = None) -> tuple[str, int]:
    """The scheme and port for this run.

    HTTPS whenever both certificate files are there, because the iPad camera
    needs it and nothing else cares. `--http` exists for the morning when the
    certificate is the thing that is broken and the shop still has to work.
    """
    https = not force_http and CERT.exists() and KEY.exists()
    scheme = "https" if https else "http"
    return scheme, port or (HTTPS_PORT if https else HTTP_PORT)


def snapshot(when: str) -> None:
    """Take one backup. Never raises, whatever happens.

    A missing backup is not a reason to keep the shop from working, so every
    failure here is reported and stepped over.

    `when` decides only where it is reported. At startup nothing is configured
    to log yet, so a problem is printed for whoever is standing at the laptop;
    once the server is up the log file is the right place for a routine
    snapshot, and the console belongs to the address.
    """
    try:
        result = backup.run()
    except Exception as exc:                              # noqa: BLE001
        message = f"Backup failed at {when}: {exc}. The app is still running."
        print(f"   {message}")
        logging.getLogger("uvicorn.error").warning(message)
        return
    if when != "startup":
        logging.getLogger("uvicorn.error").info(
            "Backup taken: %s (%.0f KB), %d old snapshot(s) removed",
            result["file"].name, result["size"] / 1024, result["removed"],
        )


def start_periodic_backup(
    seconds: float | None = None,
    stop: threading.Event | None = None,
) -> threading.Thread:
    """Keep snapshotting while the app is up.

    A backup only at startup means a session that runs from nine until three is
    backed up as it was at nine. This adds one every couple of hours, which
    with `backup.KEEP` at two leaves the shop with the current state and the
    one before it.

    A daemon thread on purpose: closing the console window has to stop the app
    dead, and a non-daemon thread sleeping on a two-hour timer would keep the
    process alive after uvicorn had gone.

    It waits on an event rather than sleeping, so it can be stopped on demand.
    Nothing in the app ever sets it — the process ending is what stops this in
    the shop — but a test that could not stop the loop would be a test leaving
    a thread behind it, backing up the real database every few milliseconds for
    the rest of the run.
    """
    # Read here rather than as a default argument, which would freeze the
    # interval at import and quietly ignore anything that set it afterwards.
    every = BACKUP_EVERY_SECONDS if seconds is None else seconds
    stopping = stop or threading.Event()

    def loop() -> None:
        while not stopping.wait(every):
            snapshot("the two-hourly backup")

    thread = threading.Thread(target=loop, daemon=True, name="ttd-backup")
    thread.start()
    return thread


def log_file() -> Path:
    """Today's log, with anything older than a fortnight cleared out."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = dt.date.today() - dt.timedelta(days=LOG_KEEP_DAYS)
    for old in LOG_DIR.glob("ttd-*.log"):
        try:
            stamp = dt.date.fromisoformat(old.stem[4:])
        except ValueError:
            continue
        if stamp < cutoff:
            old.unlink(missing_ok=True)
    return LOG_DIR / f"ttd-{dt.date.today().isoformat()}.log"


def logging_config(path: Path) -> dict:
    """uvicorn's own logging, with everything also written to a file.

    The console stays exactly as it was — someone standing at the laptop reads
    that. The file is for the conversation three days later.
    """
    from uvicorn.config import LOGGING_CONFIG

    config = copy.deepcopy(LOGGING_CONFIG)
    config["formatters"]["file"] = {
        "format": "%(asctime)s %(levelname)s %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }
    config["handlers"]["file"] = {
        "class": "logging.FileHandler",
        "filename": str(path),
        "formatter": "file",
        "encoding": "utf-8",
    }
    for name in ("uvicorn", "uvicorn.access"):
        config["loggers"][name]["handlers"].append("file")
    # Anything the app itself logs, including a traceback out of a route, which
    # is the thing most worth having on the Monday.
    config["root"] = {"handlers": ["file"], "level": "WARNING"}
    return config


def banner(scheme: str, port: int, ip: str | None, host: str, warning: str | None) -> str:
    lines = [
        "",
        # ASCII only in anything printed: a Windows console renders the rest
        # by code page, and an em dash can arrive as garbage.
        "   ======================================================",
        "     Track the Date  -  Tecoma",
        "   ======================================================",
        "",
        f"   On this laptop:   {scheme}://localhost:{port}",
    ]
    if ip:
        lines.append(f"   On the iPads:     {scheme}://{host}:{port}")
        lines.append(f"   By address:       {scheme}://{ip}:{port}")
        lines.append("")
        lines.append("   The Android scanner phone uses the address, not the name.")
    else:
        lines += [
            "",
            "   No network address. This laptop is not on the shop WiFi, so",
            "   nothing else can reach it. Connect it and start this again.",
        ]
    if scheme == "http":
        lines += [
            "",
            "   No certificates, so this is plain http. Everything works except",
            "   the camera on an iPad or phone. See docs/WINDOWS-SETUP.md.",
        ]
    if warning:
        lines += ["", warning]
    lines += [
        "",
        "   Leave this window open while staff are using the app.",
        "   Closing it, or Ctrl+C, stops it. Everything saved is on the disk.",
        "   ======================================================",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Start Track the Date.")
    ap.add_argument("--http", action="store_true", help="plain http, ignore any certificates")
    ap.add_argument("--port", type=int, help="override the port (rarely a good idea)")
    ap.add_argument("--no-backup", action="store_true", help="skip the startup snapshot")
    args = ap.parse_args(argv)

    if not DB.exists():
        print("\n   No database yet. Run setup.bat first, or:\n")
        print("     python scripts\\init_db.py")
        print("     python scripts\\import_beep.py data\\imports\\beep_2026-08-10.xlsx\n")
        return 1

    scheme, port = choose(force_http=args.http, port=args.port)
    ip, host = lan_ip(), local_name()

    if not port_free(port):
        print("\n   Track the Date is already running on this laptop.")
        print("   There is nothing to do - use the address below.\n")
        print(f"     On this laptop:  {scheme}://localhost:{port}")
        if ip:
            print(f"     On the iPads:    {scheme}://{host}:{port}")
        print("\n   If you are sure it is not running, something else has taken")
        print(f"   port {port}. Restart the laptop and try again.\n")
        return 0

    if not args.no_backup:
        snapshot("startup")

    warning = cert_warning(cert_names(CERT), ip, host) if scheme == "https" else None
    # flush: uvicorn's logging writes to the same stream through its own
    # handler, and without this the address ends up *below* the startup lines
    # whenever output is redirected to a file.
    print(banner(scheme, port, ip, host, warning), flush=True)

    try:
        import uvicorn
    except ImportError:
        print("   The app's dependencies are not installed. Run setup.bat, or:\n")
        print("     pip install -r requirements.txt\n")
        return 1

    # Started after the import above, so a laptop with no dependencies installed
    # exits on the message rather than leaving a thread behind it.
    if not args.no_backup:
        start_periodic_backup()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_config=logging_config(log_file()),
        ssl_certfile=str(CERT) if scheme == "https" else None,
        ssl_keyfile=str(KEY) if scheme == "https" else None,
    )
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
