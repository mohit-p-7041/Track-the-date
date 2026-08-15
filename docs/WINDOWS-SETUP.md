# Getting it running on the shop laptop

Everything here happens once, at the laptop, plugged in and on the shop WiFi. Allow about an
hour the first time. After it, the whole thing is **one icon on the desktop and one address that
never changes**.

Do it in this order. Each part depends on the one above it, and the address has to be settled
before any iPad or phone is touched — otherwise every device gets bookmarked to an address that
moves and you do the device half twice.

```
1. Windows itself      power, updates, network profile        20 min
2. Python and the code                                        15 min
3. Pin the address     name, IP, port                         15 min   <- do not skip
4. setup.bat           dependencies, database, certificate,   5 min
                       firewall, desktop icon
5. Start it and look at it                                    5 min
6. The iPads and the scanner phone   -> docs/DEVICE-SETUP.md
7. Show the staff                    -> docs/STAFF-GUIDE.md
```

> **The one thing to get right:** the laptop's address must stop changing (part 3). Every home
> screen icon in the shop points at it, and the HTTPS certificate is issued for it. If it moves,
> every device stops working at once, on a Saturday, and the error message says nothing useful.

---

## 1. Windows itself

### 1.1 Stop it sleeping mid-session

**Settings → System → Power & battery → Screen and sleep → "When plugged in, put my device to
sleep after" → Never.**

During a scan session nobody touches the laptop — all the activity is on the iPads. Windows sees
an idle machine and sleeps it, and every iPad drops out at once. This is the single most likely
way to lose a session.

Leave the *screen* timeout alone, and leave the lid settings alone. Closing the lid is a fine way
to end a session. Full reasoning in `docs/LAPTOP-NOTES.md`.

### 1.2 Get updates out of the way

Settings → Windows Update → install everything pending, restart, and set **Active hours** to
cover the trading day so Windows doesn't restart mid-session.

### 1.3 Tell Windows the shop WiFi is a private network

**Settings → Network & internet → WiFi → (the shop network) → Network profile type → Private.**

This is not cosmetic. Windows applies a different firewall to networks it thinks are public, and
on a public network it blocks other devices from reaching this laptop at all. The app then works
perfectly on the laptop itself and is unreachable from every iPad, which is a confusing hour to
spend. `setup.bat` checks this and tells you if it is wrong.

---

## 2. Python and the code

### 2.1 Python

Download from [python.org](https://www.python.org/downloads/windows/) — 3.12 or newer.

**On the first screen of the installer, tick "Add python.exe to PATH".** PATH is the list of
places Windows looks when you type a command. Miss the tick and every command below fails with
`'python' is not recognized`.

Check it took:

```powershell
python --version
```

You want `Python 3.12.x` or higher. If you get "not recognized", re-run the installer, choose
**Modify**, and tick the PATH box.

> If Windows opens the Microsoft Store when you type `python`, that is a stub, not Python. Install
> from python.org properly. `start.bat` detects that stub and refuses rather than half-working.

### 2.2 Git, and the code onto the laptop

Install [Git for Windows](https://git-scm.com/downloads/win), accept every default.

```powershell
cd $env:USERPROFILE\Documents
git clone https://github.com/<you>/Track_the_Date_Tecoma.git
cd Track_the_Date_Tecoma
```

`cd` changes folder. `git clone` copies the project down, including its history, so a bad change
can be undone with one command later.

**Every command from here runs from inside that folder.**

**Check you are on the right branch.** A clone lands you on `main`, and this work may be on
another one:

```powershell
git branch --show-current
git checkout <branch>      # only if the line above is not the branch you want
```

Getting this wrong is the confusing kind of wrong — the app runs, but it is an older version of
it, and none of the files this guide talks about are there.

To update the laptop later, from the same folder:

```powershell
git pull
```

That is safe: the shop's database, photos, certificates and backups are all excluded from git, so
a pull brings new code and never touches the real data. If `git pull` complains about local
changes, run `git status` first and read what it says rather than forcing anything.

> **Copied the folder from a USB stick instead?** Windows marks files that came from elsewhere as
> blocked, and a blocked `.bat` refuses to run. Right-click `start.bat` → Properties → tick
> **Unblock** → OK. Files that arrive by `git clone` are never blocked.

---

## 3. Pin the address

Three separate things make the address stable. Do all three; they cover each other's failure
modes.

### 3.1 The port — already fixed, nothing to do

**8443 for the normal HTTPS setup, 8000 if there is no certificate.** These are set in
`scripts/serve.py` and are asserted by a test so nobody can drift them. There is no configuration
file to get wrong.

The port is part of the address (`https://tecoma.local:8443`). It is only typed once per device —
after that it lives inside the home screen icon.

### 3.2 The name — `tecoma.local`

Give the laptop a short name, and iPads can reach it by name instead of by number. Windows
answers to `<computername>.local` on the local network by itself, and iPhones and iPads resolve
that with no setup at all. **A name keeps working even if the number changes**, which makes it
the best safety net there is.

In an **administrator** PowerShell (right-click Start → Terminal (Admin)):

```powershell
Rename-Computer -NewName TECOMA -Restart
```

`Rename-Computer` renames the machine; `-Restart` reboots, which the rename needs. The laptop is
then `tecoma.local` and the app is at `https://tecoma.local:8443`.

Same thing without a command: Settings → System → About → Rename this PC.

> **Android does not resolve `.local`.** The scanner phone needs the number. That is why the next
> step still matters, and why the certificate is issued for both.

### 3.3 The number — reserve it

Pick **one** of these. The first is better if you can get into the router.

**Option A — reserve it on the router (preferred).** Log into the router's admin page, find the
DHCP reservation / static lease list, and tie the laptop's MAC address to a fixed IP. The laptop
then asks for an address as normal and is always handed the same one. Nothing changes on the
laptop, and it still works normally on any other network.

Get the MAC address and the current IP with:

```powershell
ipconfig /all
```

Look under the WiFi adapter for **Physical Address** (the MAC, six pairs like `A4-B1-C2-...`) and
**IPv4 Address** (the current number, like `192.168.1.57`).

**Option B — set it on the laptop.** Use this if the router is managed by someone else. First
find the three numbers you need, from the same `ipconfig /all` output: **IPv4 Address**, **Subnet
Mask** (almost always `255.255.255.0`) and **Default Gateway** (the router, usually `.1`).

Choose a new address on the same network but high up, where the router is unlikely to hand it to
anything else — if the laptop is `192.168.1.57`, choose `192.168.1.240`. Check nothing is already
there:

```powershell
ping 192.168.1.240
```

`ping` asks "is anything at this address?". You want **"Request timed out"** or "Destination host
unreachable" — that means it is free. If something replies, pick a different number.

Then, in an **administrator** Command Prompt or Terminal:

```powershell
netsh interface show interface
netsh interface ip set address name="Wi-Fi" static 192.168.1.240 255.255.255.0 192.168.1.1
netsh interface ip set dns name="Wi-Fi" static 192.168.1.1
```

- The first line lists the network adapters so you can confirm the name — usually `Wi-Fi`. If the
  laptop is on a cable it will be `Ethernet`. Use whatever it prints.
- The second sets the address, the subnet mask, and the gateway, in that order. **The WiFi will
  drop for a second or two.**
- The third points DNS at the router, so the internet still works. Without it, name lookups fail
  and Windows Update and everything else silently stops.

Substitute your own numbers — the ones above are an example, not a recipe. If the adapter name
has a space in it (`Wi-Fi 2`), run those `netsh` lines from **Command Prompt** rather than
PowerShell, which handles the quotes differently and will pass the name through half-eaten.

**To undo it** (do this before taking the laptop to another network):

```powershell
netsh interface ip set address name="Wi-Fi" dhcp
netsh interface ip set dns name="Wi-Fi" dhcp
```

> Whichever option you take, **change the address before running `setup.bat`**, because the
> certificate is issued for whatever the address is at that moment. If you change it afterwards,
> just run `setup.bat` again — it notices and reissues.

---

## 4. setup.bat

Everything else is automatic. **Right-click `setup.bat` → Run as administrator.**

Administrator matters for exactly one step — opening the firewall. Without it the other steps
still run and it tells you which one it skipped.

It prints a line per step and is safe to run as many times as you like; each step checks whether
it is already done. What it does, in order:

| Step | What it does | What to look for |
|---|---|---|
| Python | Checks the version is new enough | `[ ok ] Python 3.12.x` |
| Dependencies | `pip install -r requirements.txt` — FastAPI, uvicorn, Pillow and the rest | `[ ok ] installed` |
| Database | Creates `data\tecoma.db` if there isn't one. **Never touches an existing one** | `left alone` on a laptop already in use |
| Certificate | Issues the HTTPS certificate for this laptop's name *and* number | `[ ok ] issued for tecoma.local, 192.168.1.240` |
| Firewall | Allows ports 8443 and 8000 in, on private networks only | `[ ok ] port 8443 allowed` |
| Network | Warns if Windows has the shop WiFi down as Public | `[ ok ] network profile is Private` |
| Desktop icon | Puts **Track the Date** on the desktop, pointing at `start.bat` | the path it was written to |

> **No desktop icon after running it as administrator?** The icon goes to the desktop of whichever
> account ran it, and on some machines "Run as administrator" switches account. Just double-click
> `setup.bat` normally afterwards — everything else is already done, and it will put the icon on
> the desktop you actually use.

### If the certificate step says mkcert is not installed

The certificate is what lets the **camera** work on an iPad or phone. Safari and Chrome refuse to
open a camera on a plain `http://` address, so without it, aisle scanning and product photos
don't work. Everything else does.

```powershell
winget install FiloSottile.mkcert
```

`winget` is Windows' built-in installer. Close the terminal, open a new one (so PATH picks it
up), and run `setup.bat` again.

If winget can't find it, download `mkcert-v1.4.4-windows-amd64.exe` from
[the mkcert releases page](https://github.com/FiloSottile/mkcert/releases), rename it to
`mkcert.exe`, and put it in the project folder next to `start.bat`.

Windows may show a **security warning about installing a certificate** the first time. That is
expected — mkcert is adding its own local authority to this laptop's trust store, which is what
makes the certificate it then issues acceptable to this machine. Click Yes.

### On a laptop that has never held the shop's data

Only on a brand new setup — `setup.bat` will say so:

```powershell
python scripts\import_beep.py data\imports\beep_2026-08-10.xlsx
python scripts\add_user.py "Your Name" 1234
python scripts\check_db.py
```

The first loads the old app's export (944 products, 1746 batches). The second creates a sign-in so
you can get in. The third checks the data is sound and should print **All 14 checks passed**.

**If the shop is already using this laptop, do not run any of those.** They are for an empty
database. `import_beep.py` on a live database would re-add every old row.

---

## 5. Start it

**Double-click the Track the Date icon on the desktop.**

A black window opens and prints the addresses. That window *is* the app — leave it open. Closing
it, or Ctrl+C, stops the app.

```
   ======================================================
     Track the Date  -  Tecoma
   ======================================================

   On this laptop:   https://localhost:8443
   On the iPads:     https://tecoma.local:8443
   By address:       https://192.168.1.240:8443
```

Write those two addresses down. They are what you type into the iPads and the phone.

Things it may tell you instead, all of them deliberate:

- **"Track the Date is already running"** — someone double-clicked twice. Nothing is wrong; use
  the address it prints.
- **"WARNING: the certificate does not cover ..."** — the laptop's address has moved since the
  certificate was issued. Devices will refuse to connect. Run `setup.bat` again; it reissues.
- **"No certificates, so this is plain http"** — mkcert step not done. The app works; cameras
  don't. The address is `http://...:8000` while this is true.

Now check it on the laptop itself: open **https://localhost:8443** in Edge or Chrome. You should
get the sign-in screen, and the padlock should be normal. Sign in with a PIN, and add one test
date so you know the whole path works before anyone else is involved.

Then go to `docs/DEVICE-SETUP.md` for the iPads and the scanner phone.

---

## Every day after that

**Double-click the desktop icon. That is the whole procedure.** It backs up the database, prints
the address, and serves. Close the window when the session is done.

The app is deliberately not a service and does not start with Windows: staff scan in sessions,
mainly at weekends, and a machine that is switched off cannot run a scheduled backup — so the
backup runs at startup instead.

**If you would rather it started by itself** whenever the laptop is switched on, that is one
command, and one to undo it:

```powershell
python scripts\setup_laptop.py --autostart      # start with Windows
python scripts\setup_laptop.py --no-autostart   # stop doing that
```

It puts the same shortcut in the Startup folder. The trade-off is a console window appearing on
every login, including when the laptop is being used for something else entirely.

---

## When something is wrong

Work down this list. It is in order of how often each one is actually the problem.

| What you see | What it is | What to do |
|---|---|---|
| iPads can't reach it, laptop is fine | Windows has the WiFi as Public | Part 1.3, then run `setup.bat` again |
| Same, and the profile is Private | Firewall | Run `setup.bat` as administrator |
| Same, and the firewall is open | The WiFi has client isolation on — devices can reach the internet but not each other | Router setting. Turn off AP/client isolation, or use a different network |
| It worked last week, nothing works now | The laptop's address moved | The startup window says so. Run `setup.bat`, then re-check the iPads |
| `'python' is not recognized` | PATH | Part 2.1 — re-run the installer, Modify, tick PATH |
| Safari says it can't establish a secure connection | That iPad doesn't trust the certificate | `docs/DEVICE-SETUP.md` part 1 — both halves of it |
| The camera button isn't there | Same thing, or you're on the `http://` address | Check the address bar says `https` |
| A red wall of text in the black window | Something genuinely broke | The last few lines name it. `data\logs\ttd-<today>.log` has the same thing with timestamps |
| Nothing happens on double-click | The `.bat` is blocked (came off a USB stick) | Right-click → Properties → Unblock |

**The log.** Every session writes `data\logs\ttd-YYYY-MM-DD.log` — the requests, the errors, and
anything that crashed. Kept for a fortnight. It is the only way to answer "what happened on
Saturday" on the Monday, so send that file rather than describing the symptom.

**Getting back to a working state.** Backups run automatically at every startup into
`data\backups\`, and the last seven are kept. `docs/LAPTOP-NOTES.md` has how to check one is
readable — and it is worth copying that folder to OneDrive or a USB stick occasionally, because
those backups are on the same disk as the original.

---

## What was verified, and what was not

Written on a Mac, so this section is the honest half.

**Verified:**

- `scripts/serve.py` end to end — chooses HTTPS and 8443 when the certificates exist and HTTP and
  8000 when they don't, serves the app over TLS, writes the log file, prints the addresses, and
  refuses a second start with a message instead of a traceback. 27 tests in `tests/test_serve.py`,
  each confirmed to go red when the thing it covers is broken.
- The certificate check against a real mkcert certificate: it correctly finds the address the
  certificate was issued for and correctly rejects the address one digit away.
- `scripts/setup_laptop.py --dry-run`, which prints each step and changes nothing.
- The home screen icon: served, the right size, linked from the page, and reachable without
  signing in — which matters because that is the state an iPad is in when it is first set up.

**Not verified, and not verifiable off the shop laptop:**

- `start.bat` and `setup.bat` themselves. The Python they run is tested; the batch around it
  cannot be. It is deliberately short for that reason — finding Python, and nothing else.
- Every Windows-only step: the firewall rules, the desktop shortcut, the network profile check,
  `Rename-Computer`, and the `netsh` static-address commands.
- Whether `mkcert -install` needs an elevated prompt on this particular laptop.
- Whether Windows answers to `tecoma.local` on the shop's network. It should, and it is the
  reason the certificate covers the name as well as the number — but if an iPad can't find it,
  use the number and move on rather than debugging it during a session.
