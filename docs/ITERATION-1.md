# Iteration 1 — 11 August 2026

What the first working session did, what it decided, and what the next session should pick up.

Read this before starting iteration 2. `SPEC.md` is still the design and `CLAUDE.md` is still the
working rules — this file only records what changed and what is now true.

---

## Where the project stands

**Every screen in `docs/BACKLOG.md` is built, tested and on GitHub.** The app went from a home
screen to the whole thing in one session.

| | |
|---|---|
| Commit | `173de76` on `main`, pushed to `mohit-p-7041/Track-the-date` |
| Branch | also `build-the-screens`, same commit, kept as a rollback point |
| Tests | 122 passing (`pytest`) — was 39 |
| Data checks | 12 passing (`scripts/check_db.py`) against the real database |
| Real data | untouched: 952 products, 2,340 batches, 2 staff |
| Timeline | compressed from one month to five days, 11–15 Aug — see SPEC §9 |

### How the session actually ran

`CLAUDE.md` describes one feature per session with `/feature` and a `/clear` in between. This
session did all eight in one pass instead, because the ask was to build the system rather than one
item. It worked, but note what it costs: nothing was committed until the end, so a bad step would
have been unpicked by hand rather than by `git reset`. **Iteration 2 should go back to one item per
session, committing on green** — the remaining work touches the shop laptop and the iPads, where a
mistake is slower to undo than a wrong route.

---

## What was built

Seven screens, all behind the PIN.

| Screen | Route | What it does |
|---|---|---|
| Sign in | `/login` | Pick a name, four digits on a keypad. Signed cookie, no lockout |
| Due | `/` | Past-date first, then the window. Category filter, rows link to the product |
| Scan & add | `/scan` | Scan, type the date, Enter. Duplicates caught before the insert |
| Products | `/products` | Search, category filter, soonest expiry first, 100 shown by default |
| Product | `/products/{id}` | Photo, every date on that barcode, history, resolve, set category |
| Discount sheet | `/sheet` | A4 printable, adjustable range, grouped by category |
| Settings | `/settings` | Categories, staff PINs, expiry window, backup on demand |

### New files

```
app/auth.py            session cookie + the signed-in-or-redirect middleware
app/views.py           templates, au_date / au_when / photo_url, render()
app/catalogue.py       shared product/category/batch logic; the duplicate rule lives here
app/photos.py          Pillow compression, where photo files go
app/routes/            login, home, scan, products, sheet, settings
app/templates/         login, scan, products, product, sheet, settings
app/static/js/         keypad.js, photo.js
scripts/add_user.py    first sign-in on a fresh database, or a forgotten PIN
```

`app/main.py` is now wiring only — middleware, mounts, routers.

### Verified, not assumed

- Every screen was loaded in a browser at iPad width and looked at, not just curled.
- The discount sheet was printed to PDF at A4 and the pages counted: **a realistic week (69 items)
  is two pages**.
- The write path was exercised end to end against a **copy** of the real database: adding a date to
  a real barcode, the duplicate reply, and a new barcode creating a product plus a category.
- Each new test was checked by breaking the thing it covers and confirming it went red.

---

## Decisions taken during the build

These were not in `SPEC.md`. They are now, and here is the reasoning in case one needs reversing.

**`connect()` passes `check_same_thread=False`** (`scripts/init_db.py`). FastAPI runs a sync route
and the dependency that opened its connection on worker threads, and under two iPads at once those
are not guaranteed to be the same worker. Without this it works by luck and fails intermittently
with a `ProgrammingError`. The connection is still opened per request and closed on the way out, so
this relaxes a check that does not apply rather than allowing real sharing.

**The session signing key is a file, not a settings row** (`data/session.key`, gitignored). The
middleware runs before routing and has no `Depends(get_conn)`, and a middleware calling `connect()`
itself would read the shop's real database during a test run — the exact thing `app/db.py` exists
to prevent. Losing the key file signs everyone out and costs nothing else.

**Search scores a point per word matched** rather than requiring all of them. "cool ridge" cannot
substring-match `C/RIDGE WATER 1L` — the shop's abbreviation is not derivable — so an
all-words-must-match search drops that row entirely. Scoring returns 23 products for that query,
properly spelled ones first, with `C/RIDGE WATER 1L` among them.

**A year outside today −1 to today +10 is refused** on the add path. Not asked for. A mistyped year
is silent and poisons the due list for years, which is the one data error this app cannot shrug off.

**The discount sheet shows exactly what the home screen shows**, past-date items included and
marked "(past)". Two definitions of "due" would eventually disagree and the shelf would follow the
wrong one.

**The product list caps at 100** with a "show all" link. All 952 is 477 KB of HTML — fine on the
laptop, slow on an old iPad. Both render in under 20 ms server-side.

**Backups follow the connection.** The settings screen asks the connection which file it is
attached to (`PRAGMA database_list`) rather than assuming `data/tecoma.db`, so a backup started
during a test cannot snapshot the shop's data. `scripts/backup.py` gained parameters for this;
its CLI behaviour is unchanged.

**Photo files are written to a staging name and moved into place**, and are keyed to the barcode.
Replacing a photo therefore overwrites rather than orphaning, and a laptop closing mid-write never
leaves half a file behind the old one. `photo_url()` stamps the URL with the file's mtime so an
iPad cannot show a cached older photo.

**`au_when` filter added** for timestamps, shifting UTC to GMT+10 and building the hour by hand —
`%-I` does not exist on Windows any more than `%-d` does.

---

## Not built, deliberately

| | Why |
|---|---|
| Camera scanning in the aisles | Needs HTTPS to work on an iPad at all. Day 2, with the certificates |
| Excel export | Deferred by SPEC §9. Day 3 |
| Renaming a product | "Tidy the names" is the change `CLAUDE.md` warns against — wants a decision, not a text box that appeared by itself |
| Deactivating staff who leave | `users.active` exists and login honours it. A button plus a "not the last one" guard when wanted |

---

## State of things, and gotchas

- **Both imported accounts still have the placeholder PIN `1234`.** `BP TECOMA` and `sar ob`. Until
  real names and PINs are set, the audit trail says `BP TECOMA` for everybody — which defeats the
  only reason PINs exist. **This is the first job of iteration 2.**
- **No photos exist yet.** All 952 products are without one. They rebuild by themselves as staff
  scan; nothing is missing.
- **The categories table is empty**, by design. It fills as staff type while scanning.
- **583 batches imported already expired** and sit as `pulled` with a migration note. Leave them.
- **A `.venv` was created** at the repo root (gitignored) because neither Python on the Mac had the
  dependencies. Use `.venv/bin/python -m pytest`, or activate it. The shop laptop does not need it —
  `pip install -r requirements.txt` against system Python is right there.
- **`data/session.key` is generated on first run** and gitignored. Do not copy it between machines.

---

## Running it

```bash
.venv/bin/python -m pytest                          # 122 tests, temp database
.venv/bin/python scripts/check_db.py                # 12 checks, real database
.venv/bin/python -m uvicorn app.main:app --port 8000 --reload
```

Then `http://localhost:8000`, sign in as `BP TECOMA` with `1234`.

On the shop laptop it is still `start.bat`, unchanged.

---

## Iteration 2 — what to do next

In this order. The order is dependency, not preference: certificates gate the camera, and the
camera gates the aisle half of the first staff session.

### 1. Real staff names and PINs — day 2, blocks the audit trail

Do this first and it is done for good.

- Get the actual list of staff from the station (~10 people).
- Add them in Settings, or `python scripts/add_user.py "Name" 1234` on a fresh database.
- Reset `BP TECOMA` and `sar ob` — or better, rename what they should have been. There is no rename
  in the UI yet; adding one to Settings is a small, contained job and probably worth it.
- Confirm afterwards: sign in as two different people, add a batch as each, and check the product
  screen shows the right name against each date.

### 2. HTTPS via mkcert, and the certificates onto the iPads — day 2

`start.bat` already switches by itself when `certs/` exists. No code change expected.

```
mkcert -key-file certs\key.pem -cert-file certs\cert.pem <laptop-ip>
```

Then install the mkcert root certificate on each iPad — Settings → Profile Downloaded → Install,
then General → About → Certificate Trust Settings → toggle it on. About two minutes per iPad.

Also reserve the laptop's IP on the router, or the iPad bookmarks break between sessions.

Acceptance: an iPad loads `https://<ip>:8443`, signs in, and the **Camera** button on a product
screen opens a camera. That button is already built and hides itself where `getUserMedia` is
unavailable, so it appearing is the proof the certificates worked.

### 3. Camera scanning in the aisles — day 2, straight after

The only backlog feature genuinely missing. SPEC §3.3, SPEC §8 names ZXing-js.

- Vendor ZXing-js into `app/static/vendor/`. **No CDN link** — the app must work with the internet
  down.
- Add a "Scan with camera" button to `/scan`, visible only where a camera is available, filling the
  existing barcode field and submitting the same form. Do not build a second add path.
- The counter path must not change. The gun plus keyboard is what gets used hundreds of times a
  week; the camera is for the aisles.

Acceptance criteria to write as tests:
- [ ] The camera button is absent where `getUserMedia` is unavailable, and the gun path is unaffected
- [ ] A decoded barcode goes into the same lookup as a typed one — one route, one duplicate check
- [ ] The vendored library is served from `/static/vendor/`, with no external request anywhere
- [ ] Nothing about the counter flow changes: scan, type date, Enter

### 4. Deploy to the shop laptop — day 3

`git clone` on the laptop, `pip install -r requirements.txt`, then **do not copy
`data/tecoma.db`** — run the importer there, or copy the database once and never again. Two copies
diverging is the one unrecoverable mistake available here.

Run `python scripts\check_db.py --expect-import` on the laptop and expect **All 16 checks passed**.

### 5. Excel export — day 3

Deferred deliberately since the start; the startup backup already protects the data, so this is for
the manager rather than for safety. `openpyxl` is already in `requirements.txt`.

Suggested: a button in Settings writing one sheet of every live batch — product, barcode, category,
expiry, status, added by, added at. Nothing clever.

### 6. Training notes — day 3

One page, printed, stuck by the counter. What staff actually need: how to start it, how to sign in,
scan → date → Enter, what "Already tracked" means, and what to do on the weekend with the sheet.

### 7. Dry run — day 4

The gun and one iPad, on the real laptop, before staff see it. Add twenty real items. Time it. The
number that matters is seconds per item, and it should be about five.

### 8. First staff session — day 5, Sat 15 Aug

Keep the day otherwise empty. The first session always surfaces something.

---

## How to start the next session

```bash
cd ~/Track_the_Date_Tecoma
git status                    # clean, so a bad iteration is one command to undo
claude
```

Then, one item at a time:

```
/feature real staff names and PINs
/verify
                              # then load the page and look at it yourself
git commit
/clear
```

Point it at this file first: *"Read docs/ITERATION-1.md, then start on item 1 of iteration 2."*

Two things worth repeating from `CLAUDE.md`, because a compressed schedule is exactly when they get
skipped: **a failing check is a real failure** — fix the cause, never the check — and **write the
test so that it would fail**, by breaking the thing it covers and watching it go red.
