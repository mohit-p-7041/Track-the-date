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

## Stop it going to sleep

The single most important configuration on this machine. If the laptop sleeps, every iPad in the
shop loses the app.

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

## Stop it rebooting during trading hours

Windows 11 Home gives you less control here than Pro, but active hours are enough.

Settings → Windows Update → Advanced options → **Active hours**. Set these to cover the full
trading day, so Windows won't restart to finish an update while staff are scanning.

Also turn **off** "Get me up to date" if you see it — that setting lets Windows restart as soon as
it likes, active hours or not.

Home edition will still install updates eventually and will still reboot outside active hours.
That's fine as long as the app is running as a service (below), because it comes back up by
itself. If you skip the service step, someone has to remember to start the app manually after
every reboot, and eventually nobody will.

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

Given 57.9 GB free, a nightly zip kept for 7 days costs well under a gigabyte. Point it at
OneDrive or a USB stick so a dead laptop doesn't take the data with it — a single-machine setup
with no off-machine copy is one hardware failure away from starting over.

Test a restore before you trust it. An untested backup is a guess.
