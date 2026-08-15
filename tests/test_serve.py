"""The launcher — what start.bat double-clicks into.

Three things here earn a test rather than a look.

The **address must not move**. Every iPad and the scanner phone hold a home
screen icon with the port in it, so a changed number is ten devices to walk
round and re-bookmark. The ports are asserted, not admired.

The **certificate check** is a byte search over DER. That is exactly the kind
of code that works on the machine it was written on and then quietly returns
False for ever, taking its warning with it.

**Starting twice** is what actually happens in a shop: somebody double-clicks
the icon, nothing appears to happen because the window is behind the browser,
so they double-click it again. The second one has to say "already running"
rather than throw a red traceback that reads like a broken app.

Nothing here touches data/tecoma.db — main() is only ever called down paths
that return before uvicorn starts.
"""

from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import backup, serve  # noqa: E402

# A subjectAltName as it sits in the DER: tag, length, value. Written out by
# hand so the test knows what a real certificate looks like without needing
# one — see cert_covers' docstring.
SAN_IP = b"\x87\x04" + bytes([192, 168, 1, 10])
SAN_HOST = b"\x82" + bytes([len(b"tecoma.local")]) + b"tecoma.local"
DER = b"\x30\x82\x01\x0a" + SAN_HOST + SAN_IP + b"\x02\x03\x01\x00\x01"


# ---------------------------------------------------------------- the address

def test_the_ports_never_move():
    """Both are in ten home screen icons. Changing one is a trip round the shop."""
    assert serve.HTTPS_PORT == 8443
    assert serve.HTTP_PORT == 8000


def test_https_whenever_both_certificate_files_are_there(tmp_path, monkeypatch):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text("x")
    key.write_text("x")
    monkeypatch.setattr(serve, "CERT", cert)
    monkeypatch.setattr(serve, "KEY", key)
    assert serve.choose() == ("https", 8443)


def test_plain_http_when_they_are_not(tmp_path, monkeypatch):
    """Half a certificate is not a certificate: both files, or neither."""
    cert = tmp_path / "cert.pem"
    cert.write_text("x")
    monkeypatch.setattr(serve, "CERT", cert)
    monkeypatch.setattr(serve, "KEY", tmp_path / "missing.pem")
    assert serve.choose() == ("http", 8000)


def test_force_http_ignores_a_perfectly_good_certificate(tmp_path, monkeypatch):
    """The escape hatch for the morning the certificate is the broken thing."""
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text("x")
    key.write_text("x")
    monkeypatch.setattr(serve, "CERT", cert)
    monkeypatch.setattr(serve, "KEY", key)
    assert serve.choose(force_http=True) == ("http", 8000)


def test_an_explicit_port_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(serve, "CERT", tmp_path / "no.pem")
    assert serve.choose(port=443) == ("http", 443)


def test_the_machine_name_is_a_dot_local():
    """What an iPad reaches the laptop by when its IP has moved."""
    name = serve.local_name()
    assert name.endswith(".local")
    assert name == name.lower()
    assert " " not in name


# ------------------------------------------------------------ the certificate

def test_an_ip_on_the_certificate_is_found():
    assert serve.cert_covers(DER, "192.168.1.10") is True


def test_a_hostname_on_the_certificate_is_found():
    assert serve.cert_covers(DER, "tecoma.local") is True


def test_a_neighbouring_address_is_not_mistaken_for_it():
    """The failure this exists to catch is the laptop's IP moving by one."""
    assert serve.cert_covers(DER, "192.168.1.11") is False
    assert serve.cert_covers(DER, "192.168.1.1") is False


def test_a_shorter_name_does_not_match_by_accident():
    """The length byte is what stops `ecoma.local` matching `tecoma.local`."""
    assert serve.cert_covers(DER, "ecoma.local") is False


def test_no_certificate_at_all_covers_nothing():
    assert serve.cert_covers(None, "192.168.1.10") is False


def test_a_matching_certificate_says_nothing(monkeypatch):
    assert serve.cert_warning(DER, "192.168.1.10", "tecoma.local") is None


def test_a_stale_certificate_names_the_address_and_the_fix():
    """The Saturday failure: the laptop moved, every iPad refuses, nothing says why."""
    warning = serve.cert_warning(DER, "192.168.1.55", "tecoma.local")
    assert warning is not None
    assert "192.168.1.55" in warning
    assert "tecoma.local" not in warning.split("mkcert")[0]  # it is not the problem
    assert "mkcert -key-file" in warning
    assert "192.168.1.55" in warning.split("mkcert")[1]      # and it is in the fix


def test_a_certificate_that_will_not_parse_is_a_warning_not_a_crash(tmp_path):
    """Starting the app is not the place to raise on a malformed file."""
    junk = tmp_path / "cert.pem"
    junk.write_text("this is not a certificate")
    assert serve.cert_names(junk) is None
    assert serve.cert_names(tmp_path / "absent.pem") is None
    assert serve.cert_warning(None, "192.168.1.10", "tecoma.local") is not None


def test_a_certificate_is_read_out_of_a_file_holding_a_chain(tmp_path):
    """mkcert writes one, but a PEM holding two must not defeat the reader."""
    import base64

    pem = tmp_path / "cert.pem"
    body = base64.b64encode(DER).decode()
    block = f"-----BEGIN CERTIFICATE-----\n{body}\n-----END CERTIFICATE-----\n"
    pem.write_text(block + block)
    assert serve.cert_names(pem) == DER


# --------------------------------------------------------------- starting up

def test_a_port_in_use_is_seen_as_in_use():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    try:
        assert serve.port_free(port) is False
    finally:
        s.close()
    assert serve.port_free(port) is True


def test_it_refuses_to_start_twice_and_prints_the_address(tmp_path, monkeypatch, capsys):
    """The second double-click. Nothing is wrong, so nothing should look wrong."""
    db = tmp_path / "tecoma.db"
    db.write_text("")
    monkeypatch.setattr(serve, "DB", db)
    monkeypatch.setattr(serve, "CERT", tmp_path / "no.pem")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    try:
        code = serve.main(["--port", str(port), "--no-backup"])
    finally:
        s.close()

    out = capsys.readouterr().out
    assert code == 0                      # not a failure. It is already working
    assert "already running" in out
    assert f"localhost:{port}" in out
    assert "Traceback" not in out


def test_no_database_says_which_command_makes_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(serve, "DB", tmp_path / "absent.db")
    assert serve.main([]) == 1
    assert "init_db.py" in capsys.readouterr().out


def test_the_banner_carries_all_three_addresses():
    banner = serve.banner("https", 8443, "192.168.1.10", "tecoma.local", None)
    assert "https://localhost:8443" in banner
    assert "https://tecoma.local:8443" in banner
    assert "https://192.168.1.10:8443" in banner


def test_the_banner_says_so_when_there_is_no_network():
    """An address of None means no iPad can reach this, whatever else is fine."""
    banner = serve.banner("http", 8000, None, "tecoma.local", None)
    assert "No network address" in banner
    assert "tecoma.local:8000" not in banner


def test_nothing_printed_at_startup_is_non_ascii():
    """A Windows console renders by code page, and an em dash lands as rubbish."""
    banner = serve.banner("https", 8443, "192.168.1.10", "tecoma.local", "WARNING: x")
    banner.encode("ascii")


# ----------------------------------------------------------------- the log

def test_the_log_is_todays_and_a_fortnight_ago_is_cleared_out(tmp_path, monkeypatch):
    import datetime as dt

    monkeypatch.setattr(serve, "LOG_DIR", tmp_path / "logs")
    (tmp_path / "logs").mkdir()
    old = tmp_path / "logs" / "ttd-2020-01-01.log"
    old.write_text("last year")
    keep = tmp_path / "logs" / f"ttd-{dt.date.today().isoformat()}.log"
    other = tmp_path / "logs" / "notes.txt"
    other.write_text("not mine")

    path = serve.log_file()

    assert path == keep
    assert not old.exists()
    assert other.exists()               # only its own files are pruned


def test_the_log_gets_the_requests_as_well_as_the_console(tmp_path):
    """Both handlers, because someone at the laptop reads one and I read the other."""
    config = serve.logging_config(tmp_path / "ttd.log")
    assert config["handlers"]["file"]["filename"] == str(tmp_path / "ttd.log")
    assert "file" in config["loggers"]["uvicorn"]["handlers"]
    assert "file" in config["loggers"]["uvicorn.access"]["handlers"]
    assert "default" in config["loggers"]["uvicorn"]["handlers"]   # console kept
    assert "file" in config["root"]["handlers"]                    # app tracebacks


# ----------------------------------------------------------------- backups
# Two files, taken every couple of hours while the app is up. The shop asked
# for a folder that does not pile up; what follows is that decision held in
# place, and the thread that does it not outliving the window it started in.

def test_only_two_snapshots_are_kept():
    """Changed from seven on 15 Aug, at the shop's request. It is a decision,
    not an implementation detail, so it is asserted rather than assumed."""
    assert backup.KEEP == 2


def test_pruning_keeps_the_two_newest_and_deletes_the_rest(tmp_path):
    import os

    for n in range(5):
        snap = tmp_path / f"tecoma-2026-08-1{n}_0900.db"
        snap.write_text(str(n))
        os.utime(snap, (1_700_000_000 + n * 60, 1_700_000_000 + n * 60))

    removed = backup.prune(keep=backup.KEEP, backup_dir=tmp_path)

    left = sorted(p.name for p in tmp_path.glob("tecoma-*.db"))
    assert removed == 3
    assert left == ["tecoma-2026-08-13_0900.db", "tecoma-2026-08-14_0900.db"]


def test_a_deleted_snapshot_takes_its_sidecars_with_it(tmp_path):
    """Found on the real folder: two files were kept and four were left behind.

    SQLite's backup API copies the journal mode, so a snapshot can have a -wal
    and a -shm beside it. Deleting only the .db is how a folder asked to hold
    two files ends up holding six.
    """
    import os

    # Its own folder: the autouse photo fixture already put a directory in
    # tmp_path, and this test asserts on everything left behind.
    backups = tmp_path / "backups"
    backups.mkdir()

    for n in range(3):
        snap = backups / f"tecoma-2026-08-1{n}_0900.db"
        snap.write_text(str(n))
        os.utime(snap, (1_700_000_000 + n * 60, 1_700_000_000 + n * 60))
        for suffix in ("-wal", "-shm"):
            (backups / (snap.name + suffix)).write_text("")

    # And one left behind by some earlier run, with no snapshot at all.
    (backups / "tecoma-2026-01-01_0900.db-wal").write_text("")

    backup.prune(keep=2, backup_dir=backups)

    assert sorted(p.name for p in backups.iterdir()) == [
        "tecoma-2026-08-11_0900.db",
        "tecoma-2026-08-11_0900.db-shm",
        "tecoma-2026-08-11_0900.db-wal",
        "tecoma-2026-08-12_0900.db",
        "tecoma-2026-08-12_0900.db-shm",
        "tecoma-2026-08-12_0900.db-wal",
    ]


def test_the_backup_thread_never_holds_the_window_open():
    """Closing the console has to stop the app dead. A non-daemon thread on a
    two-hour timer would keep the process alive with no window to see it in."""
    stop = threading.Event()
    thread = serve.start_periodic_backup(seconds=60, stop=stop)
    try:
        assert thread.daemon is True
        assert thread.is_alive()
    finally:
        stop.set()
        thread.join(timeout=5)
    assert not thread.is_alive()          # and it stops when told


def test_it_keeps_backing_up_while_the_app_runs(monkeypatch):
    """The whole point of the change: a session that opens at nine and runs to
    three used to be backed up as it stood at nine.

    The interval is turned down through the module constant rather than the
    argument, deliberately. It was a default argument to begin with, which
    froze it at import — so setting it did nothing, and the check that was
    supposed to prove this works sat there passing on a thread that never woke
    up.
    """
    taken = threading.Event()
    monkeypatch.setattr(serve, "BACKUP_EVERY_SECONDS", 0.01)
    monkeypatch.setattr(backup, "run", lambda *a, **k: taken.set() or {
        "file": Path("tecoma-test.db"), "size": 1, "copied": 0, "skipped": 0, "removed": 0,
    })

    stop = threading.Event()
    thread = serve.start_periodic_backup(stop=stop)
    try:
        assert taken.wait(timeout=5), "no backup was taken"
    finally:
        stop.set()
        thread.join(timeout=5)


def test_a_failed_backup_does_not_take_the_app_down(monkeypatch, capsys):
    """Never the reason the shop cannot work. It says so and carries on."""
    def explode(*a, **k):
        raise OSError("the disk is full")

    monkeypatch.setattr(backup, "run", explode)
    serve.snapshot("startup")             # must not raise

    assert "Backup failed" in capsys.readouterr().out


# --------------------------------------------------------------- the launchers

@pytest.mark.parametrize(
    "launcher, target",
    [("start.bat", "scripts\\serve.py"), ("setup.bat", "scripts\\setup_laptop.py")],
)
def test_each_launcher_runs_a_file_that_exists(launcher, target):
    """A renamed script is a double-click that fails in front of a customer."""
    text = (ROOT / launcher).read_text(encoding="utf-8")
    assert target in text
    assert (ROOT / target.replace("\\", "/")).exists()


@pytest.mark.parametrize("launcher", ["start.bat", "setup.bat"])
def test_the_launchers_are_plain_ascii(launcher):
    """cmd.exe renders by code page. A stray em dash arrives as garbage."""
    (ROOT / launcher).read_text(encoding="utf-8").encode("ascii")
