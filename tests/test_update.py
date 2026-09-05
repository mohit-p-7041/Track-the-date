"""The updater — what `update.bat` double-clicks into.

This one exists because the rollout on 6 Sep took twenty minutes it should not
have, and every minute of it was a thing a script can check.

The refusals are the point, not the pull. A pull that works is one line of git;
what earns a test is each way it goes wrong on the shop laptop, because every
one of them happens with nobody technical standing there:

  - an **administrator window**, which on that machine cannot write into
    .git\\objects and dies half way through with "Permission denied"
  - the **app still running**, holding the port and the code
  - **local edits** on the laptop, which a pull would refuse or silently merge
  - a pull that brings a **schema change or a migration**, where starting the
    app is the wrong thing to do next

The flow tests build a real repository and a real clone in a temp directory and
run real git against them. Mocking git would test the mock: the questions being
asked here are all "what does git actually do when...", and the answers are the
whole value.

Nothing here touches data/tecoma.db, and no test in this file starts a server.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import update  # noqa: E402


def git(cwd: Path, *args: str) -> str:
    """Real git, loudly, so a broken fixture fails as itself."""
    done = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


@pytest.fixture
def shop(tmp_path, monkeypatch):
    """A repository somewhere else, and this laptop's clone of it.

    `origin` stands in for GitHub. Committing into it and then pulling in the
    clone is exactly the shape of the real thing, without a network.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    git(origin, "config", "user.email", "shop@example.com")
    git(origin, "config", "user.name", "Shop")
    (origin / "app").mkdir()
    (origin / "requirements.txt").write_text("fastapi==0.115.0\n")
    (origin / "app" / "schema.sql").write_text("-- tables\n")
    (origin / "app" / "main.py").write_text("app = None\n")
    git(origin, "add", "-A")
    git(origin, "commit", "-qm", "first")

    clone = tmp_path / "laptop"
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    git(clone, "config", "user.email", "laptop@example.com")
    git(clone, "config", "user.name", "Laptop")

    # The three things the real laptop is, so each test only has to change the
    # one it is about.
    monkeypatch.setattr(update, "ROOT", clone)
    monkeypatch.setattr(update, "is_elevated", lambda: False)
    monkeypatch.setattr(update, "port_free", lambda port: True)

    def commit_upstream(path: str, text: str, message: str = "next") -> None:
        target = origin / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        git(origin, "add", "-A")
        git(origin, "commit", "-qm", message)

    return SimpleNamespace(origin=origin, clone=clone, commit_upstream=commit_upstream)


def run(check_only: bool = False, start: bool = False) -> int:
    return update.update(update.Update(check_only=check_only), start=start)


# ------------------------------------------------------------- the refusals

def test_it_refuses_an_administrator_window(shop, monkeypatch, capsys):
    """The finding from 6 Sep, as a check instead of twenty minutes.

    An elevated prompt on the shop laptop cannot write into .git\\objects. The
    ACLs are clean and Controlled Folder Access is off, so nothing about the
    error says "try it without administrator" - which is why this refuses
    before git is ever reached, and says which window to open instead.
    """
    monkeypatch.setattr(update, "is_elevated", lambda: True)
    before = git(shop.clone, "rev-parse", "HEAD")
    shop.commit_upstream("app/main.py", "app = 1\n")

    assert run() == 1

    out = capsys.readouterr().out
    assert "administrator" in out.lower()
    assert "double-clicking" in out
    # It stopped rather than trying and failing half way.
    assert git(shop.clone, "rev-parse", "HEAD") == before


def test_it_refuses_while_the_app_is_still_running(shop, monkeypatch, capsys):
    """Updating code that is in use, on Windows, is how you get a half-update."""
    monkeypatch.setattr(update, "port_free", lambda port: False)
    before = git(shop.clone, "rev-parse", "HEAD")
    shop.commit_upstream("app/main.py", "app = 1\n")

    assert run() == 1

    out = capsys.readouterr().out
    assert "already running" in out
    assert "Close the black app window" in out
    assert git(shop.clone, "rev-parse", "HEAD") == before


def test_it_refuses_a_checkout_with_local_changes(shop, capsys):
    """A pull would merge them, or refuse. Neither should happen unwatched.

    The local edit is deliberately to a *different* file than the one that
    changed upstream. Put both on the same file and git refuses the pull by
    itself, the run stops anyway, and this passes whether the check exists or
    not - which is how it was written the first time.
    """
    (shop.clone / "app" / "schema.sql").write_text("-- edited at the shop\n")
    shop.commit_upstream("app/main.py", "app = 1\n")
    before = git(shop.clone, "rev-parse", "HEAD")

    assert run() == 1

    out = capsys.readouterr().out
    assert "there are local changes to the code on this laptop" in out
    assert "app/schema.sql" in out
    # It stopped before pulling, and the edit is still there.
    assert git(shop.clone, "rev-parse", "HEAD") == before
    assert "edited at the shop" in (shop.clone / "app" / "schema.sql").read_text()


def test_it_refuses_a_checkout_on_another_branch(shop, capsys):
    """The shop runs main. Anything else is somebody's half-finished look."""
    git(shop.clone, "checkout", "-q", "-b", "investigating")

    assert run() == 1

    out = capsys.readouterr().out
    assert "investigating" in out
    assert "git checkout main" in out


# ------------------------------------------------------------------ the pull

def test_it_fast_forwards_and_names_what_came_down(shop, capsys):
    shop.commit_upstream("app/main.py", "app = 'new'\n", "Make the thing better")

    assert run() == 0

    assert (shop.clone / "app" / "main.py").read_text() == "app = 'new'\n"
    out = capsys.readouterr().out
    assert "Make the thing better" in out
    assert "Double-click the Track the Date icon" in out


def test_a_laptop_already_current_says_so_and_succeeds(shop, capsys):
    """The common case once somebody starts double-clicking it out of habit."""
    assert run() == 0
    assert "already up to date" in capsys.readouterr().out


def test_check_says_what_is_waiting_and_changes_nothing(shop, capsys):
    before = git(shop.clone, "rev-parse", "HEAD")
    shop.commit_upstream("app/main.py", "app = 'new'\n")

    assert run(check_only=True) == 0

    assert git(shop.clone, "rev-parse", "HEAD") == before
    assert (shop.clone / "app" / "main.py").read_text() == "app = None\n"
    out = capsys.readouterr().out
    assert "would run: git pull" in out
    assert "1 commit(s) waiting" in out


def test_a_merge_is_never_made_on_the_shop_laptop(shop, capsys):
    """--ff-only, so a diverged laptop stops instead of inventing a commit.

    A merge commit made here would never be pushed and would turn the next
    pull into a conflict, in a shop, with nobody to resolve it.

    The two sides touch different files on purpose, so they *would* merge
    cleanly. A conflict would stop a plain `git pull` too, and then this would
    pass with or without --ff-only.

    Confirmed red by making the code merge for real (`git pull --no-rebase`).
    A bare `git pull` leaves it green, because git itself refuses a divergent
    pull while `pull.rebase` is unset - but Git for Windows' installer offers
    to set that, so --ff-only is what makes the behaviour independent of how
    somebody clicked through it.
    """
    (shop.clone / "app" / "schema.sql").write_text("-- a change made at the shop\n")
    git(shop.clone, "commit", "-qam", "a commit made at the shop")
    shop.commit_upstream("app/main.py", "app = 'upstream'\n")

    assert run() == 1

    out = capsys.readouterr().out
    assert "git pull failed" in out
    assert "administrator window" in out
    # One parent, so no merge was made - the thing --ff-only is there to stop.
    assert len(git(shop.clone, "rev-list", "--parents", "-n", "1", "HEAD").split()) == 2


# ---------------------------------------------------- what a pull brings with it

def test_pip_runs_only_when_requirements_changed(shop, monkeypatch):
    """A minute of network on every update, for nothing, most of the time."""
    calls = []
    real = update.Update.run

    def spy(self, cmd):
        if cmd[0] == sys.executable:
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real(self, cmd)

    monkeypatch.setattr(update.Update, "run", spy)

    shop.commit_upstream("app/main.py", "app = 'new'\n")
    assert run() == 0
    assert calls == []

    shop.commit_upstream("requirements.txt", "fastapi==0.116.0\n")
    assert run() == 0
    assert len(calls) == 1
    assert "install" in calls[0] and "requirements.txt" in calls[0]


def test_needs_dependencies_only_for_the_file_that_decides_them():
    assert update.needs_dependencies(["requirements.txt"])
    assert not update.needs_dependencies(["requirements-dev.txt", "app/main.py"])


def test_a_schema_change_stops_it_before_the_app_starts(shop, monkeypatch, capsys):
    """New code against an unmigrated database is a broken app in front of staff."""
    monkeypatch.setattr(
        update.Update, "run_server",
        lambda self: pytest.fail("the app must not be started after a schema change"),
    )
    shop.commit_upstream("app/schema.sql", "-- tables\n-- and a new column\n")

    assert run(start=True) == 1

    out = capsys.readouterr().out
    assert "app/schema.sql changed" in out
    assert "has NOT been started" in out
    # The code did come down - it stops before starting, not before updating.
    assert "new column" in (shop.clone / "app" / "schema.sql").read_text()


def test_a_new_migration_script_stops_it_too():
    reasons = update.needs_attention(["scripts/migrate_prices.py", "app/main.py"])
    assert len(reasons) == 1
    assert "scripts/migrate_prices.py" in reasons[0]


def test_an_ordinary_pull_stops_nothing():
    assert update.needs_attention(["app/main.py", "app/templates/home.html"]) == []


# ------------------------------------------------------------- starting the app

def test_it_starts_the_app_when_the_update_is_clean(shop, monkeypatch):
    """The whole point of one double-click: update, then straight into serving."""
    started = []
    monkeypatch.setattr(update.Update, "run_server", lambda self: started.append(True) or 0)
    shop.commit_upstream("app/main.py", "app = 'new'\n")

    assert run(start=True) == 0
    assert started == [True]


def test_no_start_updates_and_stops(shop, monkeypatch):
    monkeypatch.setattr(
        update.Update, "run_server",
        lambda self: pytest.fail("--no-start must not start the app"),
    )
    shop.commit_upstream("app/main.py", "app = 'new'\n")

    assert run(start=False) == 0
    assert (shop.clone / "app" / "main.py").read_text() == "app = 'new'\n"
