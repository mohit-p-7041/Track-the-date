"""Bring the laptop up to date, then start it. This is what `update.bat` runs.

    python scripts/update.py              # pull, then start the app
    python scripts/update.py --check      # say what would happen, change nothing
    python scripts/update.py --no-start   # pull only, don't start the app

The shop's update procedure used to be a PowerShell session and three commands
remembered correctly. This is the same thing as one double-click, and it knows
the four ways it goes wrong on this particular laptop.

**It refuses to run as administrator.** That is not caution, it is the finding
from 6 Sep: an elevated prompt on the shop laptop cannot write into
`.git\\objects` and the pull dies half way with `Permission denied`, while the
same command as the normal user succeeds. The ACLs are clean, Controlled Folder
Access is off and the disk is empty enough, so the cause is something on that
machine hooking elevated processes - not worth chasing when the plain window
works. `setup.bat` still needs administrator, for the firewall. This does not.

The other three: the app is already running and would hold the port; the
working tree has local edits and a pull would either fail or silently merge;
and a pull that brings a new dependency or a schema change needs a step doing
before the app comes back up. Each is checked and named rather than discovered.

Batch is a poor language for any of that and cannot be tested. This can - see
tests/test_update.py.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.serve import choose, port_free  # noqa: E402

WINDOWS = os.name == "nt"

# The branch the shop runs. A laptop on anything else is a laptop somebody left
# mid-investigation, and pulling would hide that rather than fix it.
BRANCH = "main"

# Nothing here prints as anything but ASCII: a Windows console renders the rest
# by code page, and an em dash can arrive as garbage.
OK, SKIP, FAIL = "[ ok ]", "[skip]", "[FAIL]"


# --------------------------------------------------------------------------
# What a pull brought with it
# --------------------------------------------------------------------------

def needs_dependencies(paths: list[str]) -> bool:
    """Did the pull change what has to be installed?

    Cheap to check and expensive to miss: the app comes up, and the first
    screen that touches the new library is a traceback in front of staff.
    """
    return "requirements.txt" in paths


def needs_attention(paths: list[str]) -> list[str]:
    """Anything that must be done by a person before the app comes back up.

    A schema change or a new migration script means the code that is about to
    start expects a database that does not exist yet. Starting anyway would put
    a broken app in front of the shop, so this stops instead and says so. Both
    are rare, and both have been wanted exactly when they happened.
    """
    reasons = []
    if "app/schema.sql" in paths:
        reasons.append(
            "app/schema.sql changed - the database on this laptop may need a "
            "migration before the new code will run against it"
        )
    migrations = sorted(
        p for p in paths if p.startswith("scripts/migrate_") and p.endswith(".py")
    )
    for path in migrations:
        reasons.append(f"{path} is new - a migration that has probably not been run here")
    return reasons


def is_elevated() -> bool:
    """Is this an administrator prompt?

    Windows only; everywhere else there is nothing to refuse. Wrapped because
    `windll` does not exist off Windows and the call itself can fail.
    """
    if not WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False


# --------------------------------------------------------------------------
# The update
# --------------------------------------------------------------------------

class Update:
    """Runs the steps, in order, stopping at the first one that should stop it."""

    def __init__(self, check_only: bool = False) -> None:
        self.check_only = check_only

    # -- reporting ---------------------------------------------------------

    def step(self, title: str) -> None:
        print(f"\n{title}")

    def ok(self, msg: str) -> None:
        print(f"  {OK} {msg}")

    def skip(self, msg: str) -> None:
        print(f"  {SKIP} {msg}")

    def fail(self, msg: str) -> None:
        print(f"  {FAIL} {msg}")

    # -- running things ----------------------------------------------------

    def run(self, cmd: list[str]) -> subprocess.CompletedProcess | None:
        """Run a command and hand back the result. None if it could not start.

        `encoding` and `errors` are pinned rather than left to the locale, for
        the reason written up in setup_laptop.Setup.run: with `text=True` alone
        Python decodes the child using the console code page, and a byte it has
        no mapping for raises inside the reader thread - a traceback over a
        step that actually worked.
        """
        try:
            return subprocess.run(
                cmd, cwd=ROOT, capture_output=True, text=True, timeout=600,
                encoding="utf-8", errors="replace",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.fail(f"could not run {cmd[0]}: {exc}")
            return None

    def git(self, *args: str) -> subprocess.CompletedProcess | None:
        return self.run(["git", *args])

    def git_out(self, *args: str) -> str:
        """A git command's output, or "" if it failed. For the questions."""
        result = self.git(*args)
        if result is None or result.returncode:
            return ""
        return result.stdout.strip()

    # -- the checks --------------------------------------------------------

    def not_elevated(self) -> bool:
        """Refuse an administrator prompt. See this module's docstring."""
        self.step("Administrator")
        if is_elevated():
            self.fail("this is an administrator window, and git cannot write here from one")
            print()
            print("   Close it and run update.bat by double-clicking it instead.")
            print("   Only setup.bat needs administrator, and only for the firewall.")
            return False
        self.ok("running as the normal user, which is what git needs")
        return True

    def app_not_running(self) -> bool:
        """A running app holds the port, and its code is about to change."""
        self.step("The app")
        scheme, port = choose()
        if not port_free(port):
            self.fail("Track the Date is already running on this laptop")
            print()
            print("   Close the black app window first, then run this again.")
            print(f"   (Something is answering on port {port}, which is the app.)")
            return False
        self.ok("not running, so it is safe to update")
        return True

    def repository_ready(self) -> bool:
        """A clean tree, on the branch the shop runs, with git available."""
        self.step("The code")
        if self.git("rev-parse", "--git-dir") is None:
            print()
            print("   Git is not installed, or not on PATH. See docs/WINDOWS-SETUP.md.")
            return False
        if not (ROOT / ".git").exists():
            self.fail(f"{ROOT} is not a git checkout, so there is nothing to pull")
            return False

        branch = self.git_out("rev-parse", "--abbrev-ref", "HEAD")
        if branch != BRANCH:
            self.fail(f"this checkout is on '{branch}', not '{BRANCH}'")
            print()
            print(f"   The shop runs {BRANCH}. Somebody left this mid-investigation.")
            print(f"   Switch back with:  git checkout {BRANCH}")
            return False

        dirty = self.git_out("status", "--porcelain")
        if dirty:
            self.fail("there are local changes to the code on this laptop")
            print()
            for line in dirty.splitlines()[:10]:
                print(f"     {line}")
            print()
            print("   A pull would either refuse or merge them. Neither should happen")
            print("   without somebody looking, so nothing has been changed. Send that")
            print("   list to whoever maintains this.")
            return False

        self.ok(f"on {branch}, nothing changed locally")
        return True

    # -- the pull ----------------------------------------------------------

    def pull(self) -> tuple[bool, list[str]]:
        """Fast-forward to what is on GitHub. (worked, files that changed)

        `--ff-only` on purpose. A merge commit made on the shop laptop is a
        thing nobody will ever see or push, and it turns the next pull into a
        conflict in a shop with no one to resolve it.
        """
        self.step("Update")
        before = self.git_out("rev-parse", "HEAD")

        if self.check_only:
            self.skip("would run: git pull --ff-only")
            # A fetch, because "what is waiting" cannot be answered from a
            # stale copy of the remote - `@{u}` without one is whatever this
            # laptop last heard, which on a machine updated by double-click is
            # the previous update. It writes only into .git and leaves both the
            # working tree and the branch exactly where they were.
            self.git("fetch", "--quiet")
            behind = self.git_out("rev-list", "--count", "HEAD..@{u}")
            if behind and behind != "0":
                self.ok(f"{behind} commit(s) waiting to come down")
            elif behind == "0":
                self.ok("already up to date")
            return True, []

        result = self.git("pull", "--ff-only")
        if result is None:
            return False, []
        if result.returncode:
            self.fail("git pull failed:")
            print((result.stderr or result.stdout).strip()[-1500:])
            print()
            print("   Nothing has been changed. If it says 'Permission denied' writing")
            print("   to .git, check this is not an administrator window - see")
            print("   docs/LAPTOP-NOTES.md.")
            return False, []

        after = self.git_out("rev-parse", "HEAD")
        if after == before:
            self.ok("already up to date - nothing new to install")
            return True, []

        changed = self.git_out("diff", "--name-only", before, after)
        paths = [p for p in changed.splitlines() if p]
        self.ok(f"updated, {len(paths)} file(s) changed")
        for line in self.git_out("log", "--oneline", "--no-merges", f"{before}..{after}").splitlines():
            print(f"     {line}")
        return True, paths

    def dependencies(self, paths: list[str]) -> bool:
        """Install anything new, but only when requirements.txt actually moved.

        pip on every update would be a minute of network on a laptop that is
        about to be used, for nothing, most of the time.
        """
        self.step("Dependencies")
        if not needs_dependencies(paths):
            self.skip("requirements.txt did not change")
            return True
        if self.check_only:
            self.skip("would run: pip install -r requirements.txt")
            return True
        result = self.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt",
             "--disable-pip-version-check", "--quiet"]
        )
        if result is None:
            return False
        if result.returncode:
            self.fail("pip install failed:")
            print((result.stderr or result.stdout).strip()[-1500:])
            print()
            print("   The code is updated but its dependencies are not, so the app")
            print("   may not start. Run setup.bat, or send this message on.")
            return False
        self.ok("installed")
        return True

    # -- handing over ------------------------------------------------------

    def run_server(self) -> int:
        """Start the app, in a fresh process.

        A new process rather than importing serve and calling it: serve.py may
        have been one of the files the pull just changed, and this process is
        already holding the copy it started with.
        """
        try:
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "serve.py")], cwd=ROOT
            ).returncode
        except (OSError, subprocess.SubprocessError) as exc:
            self.fail(f"could not start the app: {exc}")
            print("\n   The update worked. Double-click the Track the Date icon.")
            return 1


def summary(started: bool) -> None:
    print()
    print("=" * 64)
    if started:
        print("  Up to date. Starting the app...")
    else:
        print("  Up to date. Double-click the Track the Date icon to start it.")
    print("=" * 64)


def update(u: Update, start: bool) -> int:
    """The whole run, in order. Every step either passes or says why it didn't.

    Kept separate from main() so a test can drive it without argparse, and so
    the order of the checks is one readable list rather than something to
    reconstruct from nesting.
    """
    if not u.not_elevated():
        return 1
    if not u.app_not_running():
        return 1
    if not u.repository_ready():
        return 1

    worked, paths = u.pull()
    if not worked:
        return 1
    if not u.dependencies(paths):
        return 1

    reasons = needs_attention(paths)
    if reasons:
        u.step("Stop here")
        for reason in reasons:
            u.fail(reason)
        print()
        print("   The code is updated. The app has NOT been started, because it")
        print("   would run against a database it does not match. Send the lines")
        print("   above to whoever maintains this before starting it.")
        return 1

    if not start:
        summary(started=False)
        return 0

    summary(started=True)
    return u.run_server()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Update this laptop, then start the app.")
    ap.add_argument("--check", action="store_true", help="say what would happen, change nothing")
    ap.add_argument("--no-start", action="store_true", help="update only, do not start the app")
    args = ap.parse_args(argv)

    print("=" * 64)
    print("  Track the Date - updating this laptop")
    if args.check:
        print("  CHECK ONLY - nothing will be changed")
    print("=" * 64)

    return update(
        Update(check_only=args.check),
        start=not (args.check or args.no_start),
    )


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
