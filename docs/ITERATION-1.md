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

### 2. HTTPS via mkcert, and the certificates onto the iPads — day 2, **blocked on one command**

`start.bat` already switches by itself when `certs/` exists. No code change expected.

`mkcert` itself is installed (`brew install mkcert`, run by Mohit, v1.4.4). **`mkcert -install`
has not run** — checked directly on 12 Aug: no `rootCA.pem`, no CA directory, nothing in the
login keychain. It needs to run in an interactive terminal (Terminal.app), not from an assistant
session, because on macOS it shells out to `sudo security add-trusted-cert` and needs a password
prompt to answer. This is the actual next step blocking everything below it.

```
mkcert -install                                             # Mohit runs this, in Terminal.app
mkcert -key-file certs\key.pem -cert-file certs\cert.pem <laptop-ip>
```

Then install the mkcert root certificate on each iPad — Settings → Profile Downloaded → Install,
then General → About → Certificate Trust Settings → toggle it on. About two minutes per iPad.

Also reserve the laptop's IP on the router, or the iPad bookmarks break between sessions.

Acceptance: an iPad loads `https://<ip>:8443`, signs in, and the **Camera** button on a product
screen opens a camera. That button is already built and hides itself where `getUserMedia` is
unavailable, so it appearing is the proof the certificates worked. **This acceptance test used to
be weaker than it looked — see item 3.**

### 3. Camera scanning in the aisles — **built and merged**, one real bug found since

SPEC §3.3, SPEC §8 names ZXing-js. Merged to `main` via PR #2 (`92734f7`): ZXing 0.21.3 vendored
into `app/static/vendor/`, no CDN, loaded on first tap rather than up front so the counter path
pays nothing for it. A "Scan with camera" button on `/scan`, meant to be visible only where
`getUserMedia` exists, filling the same barcode field and submitting the same form.

Acceptance criteria, all met:
- [x] The camera button is absent where `getUserMedia` is unavailable, and the gun path is unaffected
- [x] A decoded barcode goes into the same lookup as a typed one — one route, one duplicate check
- [x] The vendored library is served from `/static/vendor/`, with no external request anywhere
- [x] Nothing about the counter flow changes: scan, type date, Enter

**Bug found 12 Aug, serving the app on the LAN to test from an iPad.** The button was on screen
over plain HTTP — a page where the camera cannot work. The JS-side gate was correct
(`isSecureContext: false`, `getUserMedia` undefined, the button's `hidden` attribute correctly
set), but the browser's own rule for `hidden` is just `[hidden] { display: none }`, and `.btn`
sets `display: inline-block`, which outranks it. The button was drawn anyway, and tapping it did
nothing — `scanner.js` returns before it binds a click. Fixed with one CSS rule
(`[hidden] { display: none !important; }` in `app/static/css/app.css`) plus
`test_the_hidden_attribute_actually_hides` in `tests/test_rules.py`, break-checked both ways
(remove the rule, drop `!important`) — both go red.

**This fix is not yet on `main`** — it's uncommitted on the `excel-export` branch along with the
export work (see item 5). Until it lands, the item 2 acceptance test above — "the Camera button
appearing proves the certificates worked" — is checking a button that appeared regardless of
whether they did.

Still not verified: a real camera reading a real barcode on a real iPad. That needs item 2 done.

### 4. Deploy to the shop laptop — day 3

`git clone` on the laptop, `pip install -r requirements.txt`, then **do not copy
`data/tecoma.db`** — run the importer there, or copy the database once and never again. Two copies
diverging is the one unrecoverable mistake available here.

Run `python scripts\check_db.py --expect-import` on the laptop and expect **All 16 checks passed**.

### 5. Excel export — **done**, built day 2

`scripts/export_xlsx.py`, called both by the Settings button and from the command line.

Built wider than suggested in one respect: **every** batch, not only the live ones. `CLAUDE.md`
keeps pulled and sold rows "so waste can be reviewed later", and a spreadsheet is where that
review would actually happen — the Status column filters back to the shelf in one click. Live
rows sort first, or the shop's 583 pulled rows sit above everything that still matters.

Worth knowing if this is ever changed: the export is where Excel gets to reinterpret the data,
and `tests/test_rules.py` pins the four places that showed up as real. Barcodes are text
(`0000001051117` is a real product, and a number eats the zeros); expiry is a real date (a string
is Excel's to guess at, and its guess is US order); timestamps are shifted to GMT+10 but a
date-only `resolved_at` is not, because +10h would invent a 10am nobody recorded; and a name
starting with `=` is forced to text rather than becoming a formula.

**Not yet on `main`.** Built and verified on the `excel-export` branch — 2,340 rows, 139 KB,
served in under 200 ms against a copy of the real database, downloaded file reopens cleanly. Not
yet committed.

### 6. Training notes — day 3

One page, printed, stuck by the counter. What staff actually need: how to start it, how to sign in,
scan → date → Enter, what "Already tracked" means, and what to do on the weekend with the sheet.

### 7. Dry run — day 4

The gun and one iPad, on the real laptop, before staff see it. Add twenty real items. Time it. The
number that matters is seconds per item, and it should be about five.

### 8. First staff session — day 5, Sat 15 Aug

Keep the day otherwise empty. The first session always surfaces something.

---

## Session — 12 August 2026

Picked up with `camera-scanning` built but not merged, and `mkcert` binary installed but its CA
not yet created. What happened, in order:

1. **Merged `camera-scanning` to `main`** as PR #2 (`92734f7`), then branched `excel-export` off
   the clean result — see item 3 above for what shipped.
2. **Built item 5, the Excel export**, end to end: `scripts/export_xlsx.py`, a button on
   Settings, 18 new tests, 19/19 break-checked. Details under item 5 above.
3. **Served the app on the LAN** (`0.0.0.0:8000`, against a throwaway copy of `data/tecoma.db`)
   so Mohit could test from his MacBook and home iPad while `mkcert -install` was still
   outstanding. Confirmed working on both for every screen except the camera, which needs HTTPS.
4. **Found and fixed the `[hidden]` CSS bug** described under item 3 — the camera button was
   rendering (inert) on insecure origins. This was live on `main` until fixed here.
5. **Checked `mkcert -install` directly** rather than taking "it is done" at face value: no CA
   directory, no keychain entry. Diagnosed why (needs an interactive terminal for the admin
   password prompt) and handed back the exact command to run in Terminal.app.
6. Stopped the background LAN server before closing out — nothing should keep listening on
   `0.0.0.0:8000` between sessions.

**State at close of session:**

| | |
|---|---|
| Tests | 166 passing (`pytest`) — was 147 after the camera-scanning merge |
| `main` | has the merged camera-scanning work, **including the `[hidden]` bug** |
| `excel-export` branch | export feature + the bug fix + doc updates, all **uncommitted** |
| Real data | untouched throughout — every check ran against a copy |
| `mkcert -install` | **not run.** Blocks item 2, which blocks the iPad half of item 3 |

**Next session, in order:**
1. Mohit runs `mkcert -install` in Terminal.app (needs a password prompt; can't be run from here).
2. Generate the LAN cert, restart over HTTPS against a DB copy, hand over `rootCA.pem` to AirDrop
   to the iPad, walk through the profile install and Certificate Trust Settings toggle.
3. The actual acceptance test: Camera button appears on the iPad and reads a real barcode.
4. Separately, and not blocked on any of the above: review and commit the `excel-export` branch
   (export feature + the `[hidden]` fix), then PR and merge to `main`.

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
