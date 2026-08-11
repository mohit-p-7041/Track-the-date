# Track the Date — Tecoma

Expiry-date tracker for BP Tecoma. Replaces a paid app ("beep"). Runs on one Windows laptop in
the shop, served over the local network so iPads can use it in Safari.

**Read `SPEC.md` before implementing any feature.** It holds the agreed design. This file holds
the working rules.

## Locked decisions — do not revisit without asking

These were considered and settled. Don't "improve" them into something else.

- **No cloud, no hosting, no paid services.** Everything runs on the shop laptop.
- **No JavaScript framework and no build step.** Plain HTML, CSS and vanilla JS served by
  Jinja2 templates. No npm, no bundler, no TypeScript. Someone must be able to open this in
  eighteen months and fix it.
- **Python + FastAPI + SQLite.** Standard library where possible; every dependency added is a
  thing that can break on a shop laptop.
- **No CDN links.** The app must work if the internet drops. Vendored assets go in
  `app/static/vendor/`.
- **Product and Batch are separate.** A Product is a barcode. A Batch is one expiry date for
  that barcode. Photos and category live on the Product so they're stored once.
- **PINs are accountability, not security.** 4 digits, LAN-only app. Don't add password
  complexity rules, lockouts, or session hardening. Do keep the audit trail accurate.
- **No roles.** ~10 staff, one shop. Everyone can do everything, including adding categories and
  removing batches. Don't build an admin tier or gate features behind a manager PIN.
- **No counting.** A batch is "this product has stock dying on this date", not a quantity. The
  `quantity` column exists, defaults to 1, and is never shown or edited. A second item is only
  entered when its date differs.
- **One 7-day window**, not a set of bands. Read `expiry_window_days` from settings. Items past
  their date and not yet resolved are normal, not an error.
- **No shelf location field.** Considered and rejected — it slows down entry.
- **Categories are optional and grow by themselves.** The table starts empty. Staff pick or type
  one while scanning; it attaches to the product so it covers every batch of that barcode.
  `products.category_id IS NULL` means uncategorised and is a normal state — there is no
  'Uncategorised' row. Never block the add path on a category. Don't build a bulk-categorisation
  screen; that was considered and dropped.
- **Photos are optional and backfill.** Attached to the product, so adding one later makes it
  appear on batches recorded months ago. Lists show a fixed-size placeholder and must not reflow
  when images arrive.
- **No animation, no transitions.** Adding a product happens hundreds of times a week. Clean and
  fast beats polished. Optimise the add path above everything else.
- **On demand, not always on.** Staff double-click `start.bat` for a scan session (mainly
  weekends) and close the window after. No service, no auto-start. Backups therefore run at
  startup — a nightly job would never fire.

## Layout

```
start.bat       double-click launcher; picks HTTP or HTTPS automatically
app/
  main.py         FastAPI app — wiring only: middleware, mounts, routers
  db.py           get_conn dependency — the only way a route opens the database
  auth.py         the session cookie and the signed-in-or-redirect middleware
  views.py        templates, au_date / au_when / photo_url, and render()
  catalogue.py    shared product/category/batch logic — the duplicate rule lives here
  photos.py       Pillow compression and where photo files go
  schema.sql      tables and indexes
  seed.sql        settings only; no categories are seeded by design
  security.py     PIN hashing
  routes/         one module per area: login, home, scan, products, sheet, settings
  templates/      Jinja2 — base.html and one per screen
  static/         css, js (keypad, photo), vendor
tests/
  conftest.py     temp-database fixtures; never touches data/tecoma.db or data/photos
  test_screens.py routes render and show the right rows
  test_rules.py   the locked decisions, as executable tests
data/
  tecoma.db       the database — never commit
  photos/         compressed product images — never commit
  backups/        snapshots written at startup — never commit
  imports/        the beep Excel export
scripts/
  init_db.py      create the database; also holds connect()
  import_beep.py  load the old app's Excel export
  check_db.py     sanity checks — run these
  backup.py       snapshot db + photos, keep last 7
  show_address.py print the URL for the iPads
docs/
  BACKLOG.md      what to build next, in order, with acceptance criteria
  DATA-NOTES.md   what's in the beep export, verified by running the import
  LAPTOP-NOTES.md the shop machine: specs, sleep settings, firewall, backups
  reference/      screenshots of the old app and the laptop, for reference
```

## Commands

```bash
pip install -r requirements.txt -r requirements-dev.txt      # dev machine
pytest                                                       # run before committing
python scripts/init_db.py                                    # create the database
python scripts/init_db.py --reset                            # destructive rebuild
python scripts/add_user.py "Name" 1234                       # first sign-in on a fresh database
python scripts/add_user.py "Name" 4821 --reset               # forgotten PIN
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx --dry-run
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx
python scripts/check_db.py                                   # run before committing
python scripts/check_db.py --expect-import                   # also assert the import numbers
python scripts/backup.py                                     # snapshot db + photos
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload      # dev server
```

**Run `pytest` and `scripts/check_db.py` before any commit.** Together they cover both halves:
pytest proves the app renders and that the locked decisions can't be violated, `check_db.py`
proves the shop's real data is sound. Both exit non-zero on failure. If something fails, fix the
cause — don't weaken the check or delete the test. If a design decision genuinely changed, say so
explicitly and update it deliberately.

## Conventions

- Dates are stored as ISO `YYYY-MM-DD` text and displayed as `D MMM YYYY` via the `au_date`
  filter in `app/main.py`. Australian format, never US. The shop is GMT+10.
- **Don't use `strftime('%-d')`** — that format code doesn't exist on Windows, and this runs on
  Windows. Build day-of-month by hand, as `au_date` does.
- Batch status is one of `active`, `discounted`, `pulled`, `sold`. Nothing is hard-deleted by
  default so waste can be reviewed later.
- The unique index `idx_batches_unique_live` is the duplication guard. The app should catch the
  duplicate first and tell the person it's already tracked and when it expires — not surface a
  database error, and not offer to increase a quantity, because there are no quantities. The
  index is the backstop. Never drop it.
- Every write that a person initiates records `added_by` / `resolved_by`.
- **Always open the database via `scripts.init_db.connect()`**, never `sqlite3.connect()`
  directly. `foreign_keys` and `synchronous` are per-connection pragmas — a raw connect silently
  drops both, which loses referential integrity and crash durability.
- **Routes take the connection with `Depends(get_conn)`** from `app/db.py`; they never call
  `connect()` themselves. It closes the handle even when a route raises, and it's the seam the
  tests use to point the app at a temp database. A route that opens its own connection will read
  the shop's real data during a test run, which makes the suite both wrong and dangerous.
- **Every screen is behind the PIN.** One middleware in `app/auth.py` either puts the signed-in
  user on `request.state.user` or redirects to `/login`; only `/login`, `/logout` and `/static/*`
  are public. A route that writes takes `user: dict = Depends(current_user)` and stamps
  `added_by` / `resolved_by` from it. In tests, the `client` fixture is signed in and
  `anon_client` is not — don't reach past the middleware, and don't forge the cookie.
- **Submit each entry immediately.** Don't build multi-step wizards holding state in the browser.
  The laptop can sleep at any moment, and anything not yet posted is gone.
- Images: resize client-side before upload, then Pillow to max 800px long edge, JPEG q72, EXIF
  stripped. Target under 80 KB. Filenames keyed to barcode, stored under `data/photos/`.

## The data

The beep export at `data/imports/beep_2026-08-10.xlsx` is real production data: 2343 rows,
952 unique products, 2 staff accounts. It imports cleanly to 2340 batches — see
`docs/DATA-NOTES.md`. Use it for realistic testing rather than inventing fixtures.

Every product imports with `category_id` NULL — the old app only ever had one category ('All'),
so there was nothing to migrate. 583 batches were already expired at import and carry a note
saying so; leave them alone, staff clear that backlog as they rescan.

Product names are messy in ways that matter for search: inconsistent case
(`C/RIDGE WATER 1L` vs `Cool Ridge Water 600ml`), trailing whitespace, curly apostrophes, one
name in Korean, and a few with dates baked in. Search must be case-insensitive and
whitespace-tolerant. Don't "clean" the names in the database — staff recognise them as they are.

## Testing

Two layers. Run both.

**`pytest`** — 122 tests against a temporary database built from `schema.sql` in a temp directory.
It never touches `data/tecoma.db`, and an autouse fixture points photo uploads at a temp folder
too, so it's safe to run on the shop laptop.

- `tests/test_screens.py` — routes return 200, render, and show the right rows. This is the layer
  `check_db.py` cannot provide: it catches template errors, wrong queries, off-by-one windows.
- `tests/test_rules.py` — the locked decisions as tests. Not "nobody has broken this yet" but
  "this cannot be done": the duplicate guard raises, categories collide case-insensitively,
  `au_date` never emits US format or a leading zero.

**`python scripts/check_db.py`** — 12 structural checks against the real database, or 16 with
`--expect-import`, which also asserts the original migration numbers.

### Adding tests

Every new screen gets tests in `tests/test_screens.py`, one per acceptance criterion in
`docs/BACKLOG.md`. Every new rule gets a test in `tests/test_rules.py` that proves the rule is
enforced rather than merely respected.

Use offsets from today (`days(-4)`, `days(7)`) rather than fixed dates, or the suite starts
failing in November. Use the awkward names from the real export — mixed case, trailing
whitespace, the curly apostrophe — not tidy fixtures. The edge cases that matter are in the data.

**Write the test so that it would fail.** After adding one, break the thing it covers and confirm
it goes red. A test that passes against a broken implementation is worse than no test, because it
is what an unattended loop will trust.

Before saying a screen works, actually load it and look at the response. `curl -s localhost:8000`
catches a template error; only your eyes catch a bad layout.
