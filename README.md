# Track the Date — Tecoma

Expiry tracker for BP Tecoma. Runs on one shop laptop, reachable from iPads on the shop WiFi.

- `SPEC.md` — what we're building and why
- `CLAUDE.md` — working rules, read automatically by Claude Code
- `docs/DATA-NOTES.md` — what's in the old app's export
- `docs/LAPTOP-NOTES.md` — the shop machine: power settings, firewall, backups

## What already works

Not a blank slate. Done and verified:

- Database schema, with the duplicate guard enforced at index level
- Importer — 952 products and 2,340 batches loaded from the real beep export
- `scripts/check_db.py` — 16 checks that enforce the design decisions
- `scripts/backup.py` — snapshot, prune to 7, restore-tested
- `app/main.py` — a working home screen showing what's due
- `tests/` — 39 tests: the screens render, and the locked decisions can't be broken

Still to build: PIN login, scan & add, photos, search, the weekly print sheet, settings.
`docs/BACKLOG.md` has them in order, with acceptance criteria.

> **Where to build:** recommend developing on the Mac and deploying to the shop laptop via git.
> The laptop runs the app easily, but Claude Code plus a browser plus the app on 8 GB is a slow
> way to work. Reasoning in `docs/LAPTOP-NOTES.md`.

---

## Setup

Same steps on Mac or Windows, except where noted.

### 1. Python 3.12

Windows: download from [python.org](https://www.python.org/downloads/windows/) and **tick "Add
python.exe to PATH" on the first installer screen**. Miss it and every command below fails with
`'python' is not recognized`.

```
python --version
```

### 2. Git

Windows: [Git for Windows](https://git-scm.com/downloads/win), accept the defaults. Claude Code
uses Git Bash for running commands; without it, it falls back to PowerShell, which works but is
rougher.

### 3. Claude Code

```powershell
irm https://claude.ai/install.ps1 | iex     # Windows PowerShell
```

```bash
curl -fsSL https://claude.ai/install.sh | bash    # macOS
```

Then `claude --version` and `claude doctor`. Requires a Claude Pro, Max, Team or Enterprise
account — the free plan doesn't include Claude Code.

> If `irm` isn't recognised you're in CMD, not PowerShell — the prompt shows `PS C:\` in
> PowerShell. Either switch, or use `winget install Anthropic.ClaudeCode`.

### 4. Get the project onto the laptop

**Git (recommended)** — push to a private GitHub repo from the Mac, then:

```powershell
cd $env:USERPROFILE\Documents
git clone https://github.com/<you>/track-the-date-tecoma.git
cd track-the-date-tecoma
```

Worth the ten minutes. When Claude Code writes something that breaks the app, you roll back with
one command instead of losing an afternoon.

**USB stick** also works, but you're on your own for undo.

Don't copy `data/tecoma.db` or `data/photos/` between machines once the shop is using it — the
laptop's copy is the real one.

### 5. Dependencies and database

```powershell
pip install -r requirements.txt
python scripts\init_db.py
python scripts\import_beep.py data\imports\beep_2026-08-10.xlsx
python scripts\check_db.py --expect-import
```

On a machine you're developing on, also `pip install -r requirements-dev.txt` and run `pytest`.
The shop laptop doesn't need it — the tests build their own temporary database and never read
`data\tecoma.db`, so running them there is safe, just not necessary.

The last command should print **All 16 checks passed**. If it doesn't, stop and read what failed.

### 6. Run it

```powershell
.\start.bat
```

It prints the address for the laptop and for the iPads. On the laptop, open
`http://localhost:8000`.

Close the window to stop it. Everything saved is already on disk — there's no shutdown step.

---

## Using Claude Code on this project

Start it **inside the project folder** so it picks up `CLAUDE.md`:

```powershell
cd $env:USERPROFILE\Documents\track-the-date-tecoma
claude
```

### Two commands are set up for you

- `/feature <name>` — builds one backlog item properly: reads the spec, shows you a plan first,
  writes tests, runs the checks after
- `/verify` — runs `pytest` and `check_db.py` and reports what passed

### The workflow that works

One item from `docs/BACKLOG.md` at a time, in the order listed:

```
git status          # clean, so this feature can be rolled back on its own
/feature PIN login  # it plans, you confirm, it builds
/verify             # pytest + check_db
                    # then load the page and look at it yourself
git commit          # only on green
/clear              # fresh context for the next one
```

Commit before starting, so a bad iteration is `git reset --hard` rather than an argument. Asking
for the whole app at once produces a lot of code you haven't tested, and debugging that is slower
than building it in pieces.

The tests are what make this safe to repeat. `check_db.py` can tell you the data is sound but not
that a screen renders — without `pytest`, an agent will report success on a page that throws.

### Useful things to know

- **Plan mode** — `Shift+Tab` twice. Use it for anything non-trivial; getting a plan before code
  is the single biggest time saver.
- `/clear` between features. A long conversation carries stale context and answers get worse.
- `git commit` after every feature that works. This is your real undo button.
- Escape interrupts and redirects. Don't let it finish something wrong out of politeness.
- Make it *show* you the page rendered, not just claim it works.
- `claude doctor` diagnoses installation problems.

### Push back if you see these

`CLAUDE.md` forbids them, but habits are strong:

- React, Vue, npm, or any build step
- CDN links for CSS or JavaScript — the app must work with the internet down
- Dropping the duplicate-prevention index to make an insert work
- "Tidying" the messy product names — `C/RIDGE WATER 1L` stays exactly as it is
- Storing images as base64 in the database
- Adding an admin or manager tier — there are no roles
- `strftime('%-d')` for dates — doesn't exist on Windows

---

## Going live in the shop

Full detail with exact Windows settings in `docs/LAPTOP-NOTES.md`.

1. **Stop the laptop idle-sleeping mid-session** — Settings → System → Power & battery → Screen
   and sleep → "When plugged in, put my device to sleep after" → **Never**. During a session
   nobody touches the laptop, so Windows would otherwise sleep it and drop every iPad. Leave the
   lid settings alone; closing the lid is a fine way to finish.
2. **HTTPS via mkcert** — only needed for iPad camera scanning. Everything else works over HTTP.
3. **Reserve the laptop's IP** on the router so the iPad bookmarks survive between sessions.
4. **Copy `data/backups` off the machine** — they run automatically at startup but land on the
   same disk as the original.

---

## Troubleshooting

**`'python' is not recognized`** — Python isn't on PATH. Re-run the installer, choose Modify,
tick "Add python.exe to PATH".

**iPads can't reach the app** — `start.bat` prints the address; check the iPad is on the same
WiFi and that Python is allowed through Windows Firewall on private networks. Guest or corporate
WiFi with client isolation blocks this entirely.

**Camera won't open on the iPad** — expected over `http://`. Needs the mkcert step. The laptop's
own webcam works on `localhost` regardless.

**Database is locked** — something else has it open. SQLite in WAL mode handles concurrent
readers fine but not two writers. Close the other instance.

**`check_db.py` fails after a change** — read which check failed and fix the cause. Each one maps
to a decision in `SPEC.md`. Don't weaken the check to make it pass.

**A test fails after a change** — same rule. `tests/test_rules.py` is the locked decisions in
executable form; a failure there means the change contradicted one. Deleting the test makes the
problem invisible, not absent.
# Track-the-date
