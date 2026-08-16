# The shop laptop

Acer Aspire A515-51G — `TECOMA` (renamed from `LAPTOP-S65BPC8C` on 16 Aug, so the machine
answers to `tecoma.local`)

| | |
|---|---|
| CPU | Intel Core i5-8250U, 4 cores / 8 threads, 1.60 GHz |
| RAM | 8 GB (7.88 usable) |
| Storage | 238 GB, **57.9 GB free** |
| Graphics | NVIDIA MX130 2 GB + Intel UHD 620 |
| OS | Windows 11 Home, 25H2, build 26200.8875 |

Screenshots of these settings are in `docs/reference/laptopinformationreferenceimages/`.

## Is it enough?

Yes, comfortably, and it isn't close.

The entire workload is a Python process serving a few hundred page views a day against a SQLite
file holding 2,340 rows. Expect roughly 150 MB of RAM and effectively no sustained CPU. A query
across the whole table completes in single-digit milliseconds on hardware far older than this.
The 2017-era i5 and 8 GB of RAM are not a constraint for what this app does.

Disk is the one number worth watching: 57.9 GB free is fine, but the app plus Python plus the
photo library will want around 1.5 GB, and Windows needs headroom for updates. If it drops below
about 20 GB, clear it out. The 5.54 GB of temporary files showing in Storage settings is free to
reclaim any time via Settings → System → Storage → Temporary files.

**What will actually take this app down is not the hardware.** It's the laptop idle-sleeping
during a scan session, because all the activity is on the iPads and Windows sees an untouched
machine. One setting fixes it, below.

## Before you install anything

**Install the pending update first.** Settings is showing 2026-07 Preview Update (KB5101684)
waiting. Get it done now, on your terms, rather than having Windows choose a moment during
trading hours.

## The app runs on demand

This laptop is **not** an always-on server. Staff scan in sessions, mainly on the weekend.
Someone double-clicks `start.bat`, the app comes up in about two seconds, and the window gets
closed when the session is done.

That means no service to install, no auto-start on boot, and no keeping the machine awake around
the clock. It also means **backups run when the app starts**, not overnight — an overnight job
would never fire on a machine that's switched off.

Only one power setting matters, and it isn't the lid.

## Idle sleep is the one real problem

**This is the trap.** During a scan session, all the activity is on the iPads. Nobody touches the
laptop's keyboard or trackpad for twenty minutes at a stretch. Windows has no idea the app is
busy serving requests — it sees an idle machine and puts it to sleep. Every iPad drops out
mid-session.

Fix it in one place:

**Settings → System → Power & battery → Screen and sleep.** Set **"When plugged in, put my device
to sleep after"** to **Never**.

Leave the *screen* timeout alone — the screen going dark is fine and saves the panel. It's the
machine sleeping that kills the app.

Optionally set Power mode to **Best performance** while plugged in. Not required; this workload
is trivial for an i5.

## Closing the lid is fine

**Leave the lid settings at their default.** Don't change "Choose what closing the lid does".

With the app running on demand, closing the lid *is* the natural way to end a session. The
laptop sleeps, the app stops, and everything staff saved is already on disk. Nothing is lost and
nothing needs doing. Next session, open it and double-click `start.bat` again.

**Do not set the lid to "Do nothing"** — that's the right setting for an always-on server and the
wrong one here. It would leave the laptop awake on a shelf with a blocked vent, burning battery
for nothing.

The only case worth a thought: someone closes the lid while a colleague is still scanning on an
iPad. In practice the laptop sits open on the counter during a session, and whoever closes it can
see the app window on screen. If that turns out to be a recurring annoyance, revisit it then —
don't pre-configure around a problem you haven't had.

## Windows Update

Windows 11 Home gives you less control here than Pro, but active hours are enough.

Settings → Windows Update → Advanced options → **Active hours**. Set these to cover the full
trading day, so Windows won't restart to finish an update while staff are scanning.

Also turn **off** "Get me up to date" if you see it — that setting lets Windows restart as soon as
it likes, active hours or not.

With the app running on demand this is much less critical than it would be for an always-on
server — a reboot outside a scan session costs nothing, and the next session just starts the app
again. Set active hours anyway so an update doesn't restart the machine mid-session.

## The address, as actually configured

Set at the shop on 16 Aug. **These are the live numbers, not an example** — the certificate is
issued for them and every home-screen icon in the shop points at them.

| | |
|---|---|
| Computer name | `TECOMA`, so `tecoma.local` resolves for the iPads |
| IP address | **`192.168.31.240`** — static, set on the laptop |
| Subnet mask | `255.255.255.0` |
| Gateway / DNS / DHCP | **`192.168.31.99`** — all three are the same box |
| Adapter | `Wi-Fi` (Qualcomm Atheros QCA9377). No space in the name, so the `netsh` quoting is safe in PowerShell |
| Was, on DHCP | `192.168.31.102`, lease from the same `.99` box |

```
https://tecoma.local:8443       the iPads — iOS resolves .local
https://192.168.31.240:8443     the Android scanner — it does not
```

**It is static on the laptop, not reserved on the router** — option B in
`docs/WINDOWS-SETUP.md`, chosen because the router was not available to log into at the time.
That is worth knowing for two reasons. The laptop will now try to use `192.168.31.240` on
*whatever* network it joins, so it needs putting back to DHCP before it goes anywhere else:

```powershell
netsh interface ip set address name="Wi-Fi" dhcp
netsh interface ip set dns name="Wi-Fi" dhcp
```

And nothing on the router knows `.240` is spoken for. It sits well clear of the DHCP pool — the
laptop was handed `.102`, so the pool starts around `.100` — and `ping 192.168.31.240` answered
"destination host unreachable" from the laptop's own address before it was taken, meaning nothing
was there. If a clash ever does happen, reserving it properly on the router is the permanent fix.

**The gateway is `192.168.31.99`, which is unusual** — routers are nearly always `.1`, and the
DHCP-supplied DNS suffix was `localdomain`. Recorded here because if the shop network is ever
rebuilt or that box is replaced, this is the number to re-check first.

**There is Symantec VPN software on this machine** — a `Symantec TAP Driver` bound to
`Ethernet 2`, disconnected as of 16 Aug. It is not interfering, but a VPN client is a classic
cause of "the laptop is fine and no iPad can reach it", so check it before anything else if that
ever happens.

## Let the iPads reach it

**The address is printed for you.** `start.bat` runs `scripts/show_address.py` on startup and
displays both the laptop URL and the iPad URL. No need to read `ipconfig` output.

**Allow it through the firewall** — `setup.bat` does this when run as administrator. If you miss
it, Windows Defender Firewall → Allow an app through firewall → find Python → tick Private.

**Check the WiFi allows it.** Some routers have "client isolation" or "AP isolation" enabled,
which blocks devices from talking to each other. If the iPads can reach the internet but not the
laptop, this is almost certainly why.

## Should you develop on this laptop?

Probably not. Recommend developing on your Mac and deploying here.

Claude Code, a browser, and the app all running at once on 8 GB is workable but sluggish, and the
laptop is a working shop machine. Python is cross-platform, so the code runs identically on both.

The workflow: build and test on the Mac, `git push`, then on the laptop `git pull` and restart.
Do a real test on the laptop after each significant feature — not just at the end — since
Windows path handling and the camera behaviour are the two places where "works on the Mac" stops
being true.

If you'd rather keep everything on the one machine, that also works. It'll just be slower.

## Backups

Everything that matters is `data/tecoma.db` and `data/photos/`. Nothing else on this laptop is
irreplaceable.

`scripts/backup.py` runs when `start.bat` brings the app up, **and again every two hours while it
is running**. It takes a consistent snapshot of the database (safe even while the app is serving)
and copies any new photos into one shared folder.

**It keeps two snapshots**, and deletes each one's `-wal` / `-shm` alongside it. Changed from
seven on 15 Aug because the folder was to stay small enough to read at a glance. The cost of two:
both are usually from the current session, so the furthest back you can go is a couple of hours —
a mistake spotted the following week has no snapshot from before it. `KEEP` in
`scripts/backup.py` is the single place to change that.

**Those backups sit on the same disk as the original**, which protects you from a mistake but not
from a dead drive or a stolen laptop. Copying `data/backups` to OneDrive or a USB stick now and
then is the only thing that does.

Test a restore before you trust it. An untested backup is a guess. To check one:

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'data\backups\tecoma-YYYY-MM-DD_HHMM.db'); print(c.execute('select count(*) from batches').fetchone())"
```
