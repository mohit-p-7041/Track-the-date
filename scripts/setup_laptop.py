"""One-time setup on the shop laptop. This is what `setup.bat` runs.

    python scripts/setup_laptop.py
    python scripts/setup_laptop.py --dry-run      # say what it would do, change nothing
    python scripts/setup_laptop.py --autostart    # also start the app when Windows starts
    python scripts/setup_laptop.py --no-autostart # and take that back off again

Safe to run again at any time: every step checks whether it is already done.
Run it after a `git pull` too — it will pick up a new dependency and reissue a
certificate for an address that has moved.

Each step is independent and a failure in one does not stop the rest, because
the common case is "four of six already done" and the two that matter should
still be reported clearly. What it does:

  1. checks Python is new enough
  2. installs what's in requirements.txt
  3. creates the database if there isn't one
  4. issues the HTTPS certificate for this laptop's name and address (mkcert)
  5. opens the two ports on the Windows firewall, for private networks
  6. puts a "Track the Date" icon on the desktop

Steps 5 and 6 are Windows-only and skipped elsewhere, so this can be tested on
the machine it was written on. See docs/WINDOWS-SETUP.md for what to do with
the result, and tests/test_serve.py for what is covered.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.serve import CERT, DB, HTTP_PORT, HTTPS_PORT, KEY, cert_covers, cert_names  # noqa: E402
from scripts.serve import local_name  # noqa: E402
from scripts.show_address import lan_ip  # noqa: E402

WINDOWS = os.name == "nt"
MIN_PYTHON = (3, 10)
SHORTCUT = "Track the Date.lnk"

# Nothing here is ever printed as anything but ASCII: a Windows console renders
# by code page and an em dash can land as garbage.
OK, SKIP, FAIL = "[ ok ]", "[skip]", "[FAIL]"


class Setup:
    """Runs the steps and remembers what went wrong, so the last line can say."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.failures: list[str] = []
        self.notes: list[str] = []

    # -- reporting ---------------------------------------------------------

    def step(self, title: str) -> None:
        print(f"\n{title}")

    def ok(self, msg: str) -> None:
        print(f"  {OK} {msg}")

    def skip(self, msg: str) -> None:
        print(f"  {SKIP} {msg}")

    def fail(self, msg: str) -> None:
        print(f"  {FAIL} {msg}")
        self.failures.append(msg)

    def note(self, msg: str) -> None:
        """Something the person has to do by hand, collected for the summary."""
        print(f"        {msg}")
        self.notes.append(msg)

    # -- running things ----------------------------------------------------

    def run(self, cmd: list[str], **kw) -> subprocess.CompletedProcess | None:
        """Run a command, quietly unless it fails. None if --dry-run."""
        if self.dry_run:
            print(f"  {SKIP} would run: {' '.join(cmd)}")
            return None
        try:
            return subprocess.run(
                cmd, cwd=ROOT, capture_output=True, text=True, timeout=600, **kw
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.fail(f"could not run {cmd[0]}: {exc}")
            return None

    def powershell(self, script: str) -> subprocess.CompletedProcess | None:
        return self.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
        )

    # -- the steps ---------------------------------------------------------

    def python_version(self) -> None:
        self.step("Python")
        v = sys.version_info
        if v[:2] < MIN_PYTHON:
            self.fail(
                f"Python {v.major}.{v.minor} is too old - install "
                f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer from python.org"
            )
        else:
            self.ok(f"Python {v.major}.{v.minor}.{v.micro}")

    def dependencies(self) -> None:
        self.step("Dependencies")
        result = self.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt",
             "--disable-pip-version-check", "--quiet"]
        )
        if result is None:
            return
        if result.returncode:
            self.fail("pip install failed:")
            print((result.stderr or result.stdout).strip()[-1500:])
        else:
            self.ok("installed from requirements.txt")

    def database(self) -> None:
        self.step("Database")
        if DB.exists():
            size = DB.stat().st_size / 1024
            self.ok(f"{DB.relative_to(ROOT)} ({size:.0f} KB) - left alone")
            return
        result = self.run([sys.executable, str(ROOT / "scripts" / "init_db.py")])
        if result is None:
            return
        if result.returncode:
            self.fail("could not create the database:")
            print((result.stderr or result.stdout).strip()[-1500:])
            return
        self.ok("created an empty database")
        self.note("import the old data:  python scripts\\import_beep.py "
                  "data\\imports\\beep_2026-08-10.xlsx")
        self.note("then add yourself:     python scripts\\add_user.py \"Your Name\" 1234")

    def certificates(self, ip: str | None, host: str) -> None:
        """Issue the HTTPS certificate, which is what the cameras need.

        Reissued whenever it stops covering this laptop's current address,
        because that is the failure that silently takes every iPad offline.
        """
        self.step("HTTPS certificate")
        if not ip:
            self.skip("not on a network - connect to the shop WiFi and run this again")
            return

        der = cert_names(CERT) if CERT.exists() and KEY.exists() else None
        if der and cert_covers(der, ip) and cert_covers(der, host):
            self.ok(f"already covers {host} and {ip}")
            return

        if not shutil.which("mkcert"):
            self.skip("mkcert is not installed")
            self.note("install it:  winget install FiloSottile.mkcert")
            self.note("then run setup.bat again. Until then the app runs on plain")
            self.note("http and the camera will not open on an iPad or phone.")
            return

        (ROOT / "certs").mkdir(exist_ok=True)
        install = self.run(["mkcert", "-install"])
        if install is not None and install.returncode:
            self.fail("mkcert -install failed:")
            print((install.stderr or install.stdout).strip()[-800:])
            return

        made = self.run([
            "mkcert",
            "-key-file", str(KEY.relative_to(ROOT)),
            "-cert-file", str(CERT.relative_to(ROOT)),
            host, ip, "localhost", "127.0.0.1",
        ])
        if made is None:
            return
        if made.returncode:
            self.fail("mkcert could not issue the certificate:")
            print((made.stderr or made.stdout).strip()[-800:])
            return
        self.ok(f"issued for {host}, {ip}, localhost")
        self.note("every iPad and phone must trust it - see docs/DEVICE-SETUP.md")

    # -- Windows only ------------------------------------------------------

    def is_admin(self) -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            return False

    def firewall(self) -> None:
        """Let other devices reach the two ports.

        Private profile only. A rule that also covered public networks would
        follow the laptop to any WiFi it ever joins, and the shop network being
        classified Public is a thing to fix rather than to work around - it is
        checked below and named if it is wrong.
        """
        self.step("Windows firewall")
        if not WINDOWS:
            self.skip("not Windows")
            return
        if not self.is_admin() and not self.dry_run:
            self.skip("needs administrator")
            self.note("right-click setup.bat and choose Run as administrator to do")
            self.note("this bit, or tick Private when Windows asks on first start.")
            return

        for port in (HTTPS_PORT, HTTP_PORT):
            name = f"Track the Date ({port})"
            existing = self.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"])
            if existing is not None and existing.returncode == 0:
                self.ok(f"port {port} already allowed")
                continue
            added = self.run([
                "netsh", "advfirewall", "firewall", "add", "rule", f"name={name}",
                "dir=in", "action=allow", "protocol=TCP", f"localport={port}",
                "profile=private",
            ])
            if added is None:
                continue
            if added.returncode:
                self.fail(f"could not open port {port}: {added.stdout.strip()[:200]}")
            else:
                self.ok(f"port {port} allowed on private networks")

    def network_category(self) -> None:
        """Warn if the shop WiFi is classified Public.

        The firewall rules above are for private networks, so a network Windows
        thinks is public blocks every iPad while looking, from the laptop,
        exactly like a working app.
        """
        if not WINDOWS:
            return
        result = self.powershell(
            "(Get-NetConnectionProfile | Where-Object {$_.IPv4Connectivity -ne 'Disconnected'} "
            "| Select-Object -First 1 -ExpandProperty NetworkCategory)"
        )
        if result is None or result.returncode or not result.stdout.strip():
            return
        category = result.stdout.strip()
        if category.lower().startswith("public"):
            self.fail(f"this network is set to {category} - iPads will be blocked")
            self.note("Settings > Network & internet > WiFi > (the shop network)")
            self.note("> set Network profile type to Private. Then run this again.")
        else:
            self.ok(f"network profile is {category}")

    def shortcut(self, folder: str, label: str) -> None:
        """Put start.bat somewhere double-clickable, with the app's icon."""
        if not WINDOWS:
            self.skip(f"{label}: not Windows")
            return
        icon = ROOT / "app" / "static" / "icons" / "app.ico"
        script = (
            f"$p = [Environment]::GetFolderPath('{folder}');"
            f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
            f"(Join-Path $p '{SHORTCUT}'));"
            f"$s.TargetPath = '{ROOT / 'start.bat'}';"
            f"$s.WorkingDirectory = '{ROOT}';"
            f"$s.IconLocation = '{icon}';"
            f"$s.Description = 'Start Track the Date';"
            f"$s.Save(); Write-Output $p"
        )
        result = self.powershell(script)
        if result is None:
            return
        if result.returncode:
            self.fail(f"could not create the {label} shortcut: {result.stderr.strip()[:200]}")
        else:
            self.ok(f"{label}: {result.stdout.strip()}\\{SHORTCUT}")

    def remove_autostart(self) -> None:
        self.step("Start with Windows")
        if not WINDOWS:
            self.skip("not Windows")
            return
        result = self.powershell(
            f"$f = Join-Path ([Environment]::GetFolderPath('Startup')) '{SHORTCUT}';"
            f"if (Test-Path $f) {{ Remove-Item $f; Write-Output 'removed' }} "
            f"else {{ Write-Output 'was not set' }}"
        )
        if result is not None and result.returncode == 0:
            self.ok(f"autostart {result.stdout.strip()}")

    # -- the summary -------------------------------------------------------

    def summary(self, ip: str | None, host: str) -> int:
        scheme = "https" if CERT.exists() and KEY.exists() else "http"
        port = HTTPS_PORT if scheme == "https" else HTTP_PORT

        print("\n" + "=" * 64)
        if self.failures:
            print(f"  {len(self.failures)} thing(s) need attention:")
            for f in self.failures:
                print(f"    - {f}")
        else:
            print("  Setup finished. Nothing is broken.")

        print("\n  The address, once it is running:")
        print(f"    On this laptop:   {scheme}://localhost:{port}")
        if ip:
            print(f"    On the iPads:     {scheme}://{host}:{port}")
            print(f"    By address:       {scheme}://{ip}:{port}")

        print("\n  Next: double-click the Track the Date icon on the desktop.")
        print("  Then docs\\DEVICE-SETUP.md for the iPads and the scanner phone.")
        print("=" * 64 + "\n")
        return 1 if self.failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Set this laptop up to run Track the Date.")
    ap.add_argument("--dry-run", action="store_true", help="say what it would do, change nothing")
    ap.add_argument("--autostart", action="store_true", help="also start the app when Windows starts")
    ap.add_argument("--no-autostart", action="store_true", help="stop it starting with Windows")
    ap.add_argument("--skip-deps", action="store_true", help="do not touch pip")
    args = ap.parse_args(argv)

    s = Setup(dry_run=args.dry_run)
    ip, host = lan_ip(), local_name()

    print("=" * 64)
    print("  Track the Date - setting up this laptop")
    if args.dry_run:
        print("  DRY RUN - nothing will be changed")
    print("=" * 64)

    s.python_version()
    if not args.skip_deps:
        s.dependencies()
    s.database()
    s.certificates(ip, host)
    s.firewall()
    s.network_category()

    s.step("Desktop icon")
    s.shortcut("Desktop", "desktop")

    if args.no_autostart:
        s.remove_autostart()
    elif args.autostart:
        s.step("Start with Windows")
        s.shortcut("Startup", "startup folder")

    return s.summary(ip, host)


if __name__ == "__main__":
    sys.exit(main())
