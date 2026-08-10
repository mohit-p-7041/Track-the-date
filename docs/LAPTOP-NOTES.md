# The shop laptop

Acer Aspire A515-51G — `LAPTOP-S65BPC8C`

| | |
|---|---|
| CPU | Intel Core i5-8250U, 4 cores / 8 threads, 1.60 GHz |
| RAM | 8 GB (7.88 usable) |
| Storage | 238 GB, **57.9 GB free** |
| Graphics | NVIDIA MX130 2 GB + Intel UHD 620 |
| OS | Windows 11 Home, 25H2, build 26200.8875 |

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

**What will actually take this app down is not the hardware.** It's the laptop going to sleep, or
Windows rebooting for an update mid-shift. Both are fixable, and both are below.

## Before you install anything

**Install the pending update first.** Settings is showing 2026-07 Preview Update (KB5101684)
waiting. Get it done now, on your terms, rather than having Windows choose a moment during
trading hours.

## The app runs on demand

Decided 10 Aug 2026: this laptop is **not** a always-on server. Staff scan in sessions, mainly on
the weekend. Someone double-clicks `start.bat`, the app comes up in about two seconds, and the
window gets closed when the session is done.

That removes several things this document used to call for — no NSSM service, no auto-start on
boot, no keeping the machine awake around the clock. It also means **backups run when the app
starts**, not overnight, because an overnight job would never fire.

The settings below still matter, but only for the length of a session: you don't want the screen
sleeping while someone is halfway through a shelf.

## Stop it going to sleep mid-session

If the laptop sleeps while staff are scanning, every iPad loses the app until it wakes. Nothing
is lost — saved items are already on disk — but it interrupts the session.

**Power mode** — Settings → System → Power & battery → Power mode → **Best performance** when
plugged in.

**Screen and sleep** — Settings → System → Power & battery → Screen and sleep. Set **both**
"When plugged in, turn off my screen after" and "When plugged in, put my device to sleep after"
to **Never**.

**Lid closing** — this one isn't in Settings. Control Panel → Hardware and Sound → Power Options →
**Choose what closing the lid does** → set "When I close the lid" to **Do nothing** for
Plugged in.

Without that last step, closing the lid at the end of a shift kills the app even with sleep
disabled. If the laptop is going to sit closed on a shelf, also confirm it isn't overheating —
an A515 with a blocked vent will throttle.

## Windows Update

Windows 11 Home gives you less control here than Pro, but active hours are enough.

Settings → Windows Update → Advanced options → **Active hours**. Set these to cover the full
trading day, so Windows won't restart to finish an update while staff are scanning.

Also turn **off** "Get me up to date" if you see it — that setting lets Windows restart as soon as
it likes, active hours or not.

With the app running on demand this is much less critical than it would be for an always-on
server — a reboot outside a scan session costs nothing, and the next session just starts the app
again. Set active hours anyway so an update doesn't restart the machine mid-session.

## Let the iPads reach it

**Find the address** — open PowerShell and run `ipconfig`. Look for IPv4 Address under your WiFi
adapter, something like `192.168.1.42`.

**Reserve it on the router** so it doesn't change. Otherwise the iPad bookmarks break the next
time the router reassigns addresses, usually on a day when you're busy.

**Allow it through the firewall** — the first time you run the app, Windows will ask. Tick
**Private networks** and allow. If you miss the prompt, Windows Defender Firewall → Allow an app
through firewall → find Python → tick Private.

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

`scripts/backup.py` runs automatically every time `start.bat` brings the app up. It takes a
consistent snapshot of the database (safe even while the app is serving), copies any new photos,
and keeps the last 7 snapshots. The database is around 450 KB, so seven copies cost about 3 MB.

**Those backups sit on the same disk as the original**, which protects you from a mistake but not
from a dead drive or a stolen laptop. Copy `data/backups` to OneDrive or a USB stick. A
single-machine setup with no off-machine copy is one hardware failure away from starting over.

Test a restore before you trust it. An untested backup is a guess. To check one:

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'data\backups\tecoma-YYYY-MM-DD_HHMM.db'); print(c.execute('select count(*) from batches').fetchone())"
```
