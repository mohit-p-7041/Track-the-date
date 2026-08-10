# Track the Date — Tecoma

Expiry tracker for BP Tecoma. Runs on one shop laptop, reachable from iPads on the shop WiFi.

- `SPEC.md` — what we're building and why
- `CLAUDE.md` — working rules, read automatically by Claude Code
- `docs/DATA-NOTES.md` — what's in the old app's export
- `docs/LAPTOP-NOTES.md` — the shop machine: sleep settings, firewall, backups

> **Where to build:** recommend developing on the Mac and deploying to the shop laptop via git.
> The laptop handles running the app easily, but Claude Code plus a browser plus the app on 8 GB
> is a slow way to work. Reasoning in `docs/LAPTOP-NOTES.md`. The steps below apply to whichever
> machine you build on; the shop laptop needs them regardless.

---

## Setting up the Windows laptop

Do these once, in order. Everything after step 3 you can hand to Claude Code.

### 1. Install Python

Download Python 3.12 from [python.org/downloads](https://www.python.org/downloads/windows/).

**On the first installer screen, tick "Add python.exe to PATH".** Miss this and every command
below fails with `'python' is not recognized`.

Check it worked — open PowerShell and run:

```powershell
python --version
```

### 2. Install Git

Download [Git for Windows](https://git-scm.com/downloads/win). Accept the defaults.

You need this for two reasons: it's how the project gets onto the laptop, and Claude Code uses
Git Bash for running commands. Without it Claude Code falls back to PowerShell, which works but
is rougher.

### 3. Install Claude Code

In PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Then verify:

```powershell
claude --version
claude doctor
```

`claude doctor` prints a health check — read what it says before moving on.

You need a Claude Pro, Max, Team or Enterprise account. The free plan does not include Claude
Code. The first time you run `claude`, it opens a browser to log in.

> If `irm` isn't recognised you're in CMD, not PowerShell. Your prompt shows `PS C:\` in
> PowerShell. Either switch, or use `winget install Anthropic.ClaudeCode`.

### 4. Get the project onto the laptop

This folder currently lives on your Mac. Two ways across:

**Git (recommended)** — create a private repo on GitHub, push from the Mac, then on the laptop:

```powershell
cd $env:USERPROFILE\Documents
git clone https://github.com/<you>/track-the-date-tecoma.git
cd track-the-date-tecoma
```

Worth the ten minutes. It gives you version history, so when Claude Code writes something that
breaks the app you can roll back with one command instead of losing an afternoon.

**USB stick** — copy the whole folder. Fine to start, but you're on your own for undo.

Either way, do **not** copy `data/tecoma.db` or `data/photos/` between machines casually. The
laptop's copy is the real one once you go live.

### 5. Install dependencies and build the database

```powershell
pip install -r requirements.txt
python scripts\init_db.py
python scripts\import_beep.py data\imports\beep_2026-08-10.xlsx
```

That loads all 952 products and 2340 batches from the old app.

### 6. Run it

```powershell
.\start.bat
```

Then open `http://localhost:8000` on the laptop.

---

## Using Claude Code on this project

Open PowerShell **in the project folder** and run:

```powershell
cd $env:USERPROFILE\Documents\track-the-date-tecoma
claude
```

Starting it inside the project folder matters — that's how it picks up `CLAUDE.md`, which tells
it the design decisions so it doesn't reinvent them.

### The workflow that works

Ask for one screen or one feature at a time, then test it in the browser before moving on. The
spec is already written, so you can point at it:

> Read SPEC.md and CLAUDE.md. Build the scan-and-add screen described in section 3, including
> the duplicate check. Don't touch anything else yet.

Then, once it's working:

> Now the home screen dashboard with the colour-coded bands.

Asking for the whole app in one go produces a lot of code you haven't tested, and debugging it is
slower than building it piece by piece.

### Useful things to know

- `/clear` starts a fresh conversation. Do this between features — it keeps responses sharp.
- Claude Code asks before editing files. You can approve individual changes, or use
  `/permissions` to let it edit `app/` freely once you trust the pattern.
- If it's going the wrong direction, press Escape and redirect. Don't let it finish something
  wrong out of politeness.
- `git commit` after every feature that works. This is your undo button.
- `claude doctor` diagnoses installation problems.

### Things to tell it not to do

`CLAUDE.md` already covers this, but if you see it happening, push back:

- Adding React, Vue, npm or a build step
- Linking to CDN-hosted CSS or JavaScript (the app must work offline)
- Dropping the duplicate-prevention index to make an insert work
- Storing images as base64 in the database

---

## Going live in the shop

Not needed for development, but this is what makes it real. Full detail with the exact Windows
settings is in `docs/LAPTOP-NOTES.md`.

The app runs **on demand**, not as an always-on server. Someone double-clicks `start.bat` at the
start of a scan session and closes the window at the end. Everything saved is already on disk;
there is no shutdown procedure.

1. **HTTPS via mkcert** — required for iPad camera scanning. Safari refuses camera access over
   plain `http://` from a network address.
2. **Reserve the laptop's IP** on the router, so the iPad bookmarks survive between sessions.
3. **Stop the laptop idle-sleeping mid-session** — set "put my device to sleep after" to Never
   while plugged in. During a session nobody touches the laptop, so Windows will otherwise sleep
   it and drop every iPad. Leave the lid settings alone; closing the lid is a fine way to finish.
4. **Copy `data/backups` off the machine.** Backups run automatically on startup, but they land
   on the same disk as the original. Point them at OneDrive or a USB stick.

---

## Troubleshooting

**`'python' is not recognized`** — Python isn't on PATH. Re-run the installer, choose Modify, and
tick "Add python.exe to PATH".

**iPads can't reach the app** — check the laptop's IP with `ipconfig`, confirm both devices are on
the same WiFi, and allow Python through Windows Firewall on private networks. Corporate or guest
WiFi with client isolation will block this entirely.

**Camera won't open on the iPad** — expected over `http://`. This needs the mkcert step.

**Database is locked** — something else has it open. Close other instances of the app; SQLite in
WAL mode handles concurrent readers fine but not two writers.
