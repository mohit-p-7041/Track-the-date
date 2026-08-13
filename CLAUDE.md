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
- **A batch has two endings: discounted, or deleted.** Amended 13 Aug, replacing the four
  statuses, and **built** the same day — `scripts/migrate_statuses.py`, 2327→1746 batches, with
  `products.created_by` dropped in the same rebuild. The importer skips already-expired rows for
  the same reason, so a fresh import and a migrated database agree. `status` is `active` or `discounted` — nothing else. Anything else that happens to a
  batch is a deletion: the row goes, for real. `pulled` and `sold` are gone, because the shop
  never used either (1757 `active`, 583 `pulled` from the import, zero `sold`, zero `discounted`)
  and because a record of every item ever removed grows forever on a laptop nobody prunes. Take
  the Excel export first if a snapshot of history is ever wanted — that is what it is for.
- **A product is never deleted.** Not by staff, not when its last date goes, not ever. Name,
  photo and category can all be changed; there is no delete. Only batches are deletable.
- **Deleting a batch warns only when the item is still good and still full price.** No
  confirmation if it is past its date, or if it is already `discounted` — in both cases a
  decision about that item has already been made and staff are standing at the shelf holding it.
  Ask only for an `active` batch still in date: "this expires in N days, are you sure?". No JS
  `confirm()`; reveal the confirmation inline in the row.
- **A barcode is digits only, 6–18 of them.** Amended 13 Aug, and **built** the same day. A
  leading AIM identifier (`]` plus two characters) is stripped as transport noise from the gun;
  everything else must be digits or it is refused. Typed words are the thing this exists to stop.
  Two layers, deliberately: `parse_barcode()` in `app/catalogue.py` produces the sentence staff
  read, and a `CHECK` constraint on `products.barcode` makes it impossible by any other route —
  the same shape as `idx_batches_unique_live`. Never drop the constraint.
  Normalise *before* judging: of the ten legacy rows that failed the rule, **two were `]C1…`
  stuck to a real code and were recovered** (`golden gay time lamington`, `magnum almond`), and
  **eight were deleted** — seven marketing URLs and one 40-digit gun misfire — taking 13 batches.
  Ran 13 Aug via `scripts/migrate_barcodes.py`; 952→944 products, 2340→2327 batches.
  Note that `str.isdigit()` is **not** the right test — it accepts `²` and `٣`, which the `CHECK`
  refuses, and a rule whose halves disagree shows an IntegrityError instead of a message.
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
- **Buttons, not gestures.** Swipe-to-act was built on 13 Aug and removed the same day after the
  iPad session: a person cannot see where the threshold is, so every swipe is a guess, and the
  guesses were "delete" and "discount". Don't propose it again. The Due screen now carries no
  JavaScript at all — the delete confirmation is a `<details>` the server chooses to render.
- **A discount is undoable.** It is one tap, so it will land on the wrong row. "Back to full
  price" clears the resolution rather than recording a second event: `resolved_by` means "who
  discounted this", and a batch nobody discounted has nobody against it. A *deletion* is still
  final — that is the asymmetry, and it is deliberate.
- **A floating + is always in the bottom-right corner**, going to Scan. Adding a date is what this
  app is for; it should never need a trip to the nav bar.
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
  exports/        spreadsheets written by export_xlsx.py — never commit
  imports/        the beep Excel export
scripts/
  init_db.py      create the database; also holds connect()
  import_beep.py  load the old app's Excel export
  migrate_barcodes.py  one-off: put the barcode CHECK on an existing database
  migrate_statuses.py  one-off: four statuses to two, and drop products.created_by
  migrate_edit_columns.py  one-off: add batches.edited_by / edited_at (additive)
  check_db.py     sanity checks — run these
  backup.py       snapshot db + photos, keep last 7
  export_xlsx.py  every batch to one Excel sheet; the settings button calls this
  show_address.py print the URL for the iPads
docs/
  BACKLOG.md      what to build next, in order, with acceptance criteria
  FUTURE-IDEAS.md wanted eventually, not scheduled — parked, not promised
  ITERATION-1.md  what the first session built, and the decisions it took
  ITERATION-2.md  HTTPS and the camera verified; the punch list from the iPad test
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
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx --today 2026-08-10
python scripts/migrate_barcodes.py --db /tmp/copy.db --dry-run  # barcode rule, on a copy first
python scripts/migrate_barcodes.py                           # then for real (asks first)
python scripts/migrate_statuses.py --db /tmp/copy.db --dry-run  # two statuses, on a copy first
python scripts/migrate_statuses.py                           # then for real (asks first)
python scripts/migrate_edit_columns.py                       # edited_by / edited_at; additive
python scripts/check_db.py                                   # run before committing
python scripts/check_db.py --expect-import                   # also assert the import numbers
python scripts/backup.py                                     # snapshot db + photos
python scripts/export_xlsx.py                                # data/exports/tecoma-<date>.xlsx
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
- Batch status is `active` or `discounted`. There is no third state — a batch that is neither is
  deleted. See the locked decision above.
- The unique index `idx_batches_unique_live` is the duplication guard. The app should catch the
  duplicate first and tell the person it's already tracked and when it expires — not surface a
  database error, and not offer to increase a quantity, because there are no quantities. The
  index is the backstop. Never drop it. It is partial (`WHERE status IN (...)`) for historical
  reasons; with only two live statuses left it now covers every row, and that is correct — a
  deleted batch is gone, so its date is free to be used again with no exclusion needed.
- Every write that a person initiates records who: `added_by` when a batch is created,
  `resolved_by` when it is discounted, `edited_by` / `edited_at` when its date is corrected. The
  correction sits *alongside* who added it rather than replacing them — keeping that history is
  the reason editing a date exists instead of delete-and-rescan.
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
- **Photos are served by a route, not a `StaticFiles` mount**, resolved per request from
  `photos.photo_dir()`. A mount binds its directory once at import, which is how the hardcoded
  path and `TTD_PHOTO_DIR` were able to disagree without a single test noticing. Don't turn it
  back into a mount.
- **Taking a photo does not submit the form.** The camera fills a field in; `Save` saves. It used
  to upload immediately, which dropped the person out of edit mode and committed a name they were
  still typing.

## The data

The beep export at `data/imports/beep_2026-08-10.xlsx` is real production data: 2343 rows,
2 staff accounts. It imports to **944 products and 1746 batches** — see `docs/DATA-NOTES.md`.
Use it for realistic testing rather than inventing fixtures.

Pin the date to reproduce those numbers, or the expired/live split moves with the calendar:
`python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx --today 2026-08-10`.
Without the pin the counts still import fine, but `check_db.py --expect-import` will disagree on
the pre-expired total (581 as at the export's date, 608 by 13 Aug).

Was 952 products and 2340 batches before 13 Aug. Two changes that day: the barcode rule refuses
8 barcodes and 13 rows with them, and the status change means rows already expired on the import
date are **skipped rather than imported** — 581 of them. 952 − 8 = 944 products;
2340 − 13 − 581 = 1746 batches.

Every product imports with `category_id` NULL — the old app only ever had one category ('All'),
so there was nothing to migrate. A product is created for every valid barcode even when all of
its dates were expired, because a product is never deleted; some products therefore have zero
batches, which is a normal state.

The 27 `active` batches already past their date are **not** touched by either migration. They are
real stock and the backlog staff clear on Saturday.

Product names are messy in ways that matter for search: inconsistent case
(`C/RIDGE WATER 1L` vs `Cool Ridge Water 600ml`), trailing whitespace, curly apostrophes, one
name in Korean, and a few with dates baked in. Search must be case-insensitive and
whitespace-tolerant. Don't "clean" the names in the database — staff recognise them as they are.

## Testing

Two layers. Run both.

**`pytest`** — 252 tests against a temporary database built from `schema.sql` in a temp directory.
It never touches `data/tecoma.db`, and an autouse fixture points photo uploads at a temp folder
too, so it's safe to run on the shop laptop.

- `tests/test_screens.py` — routes return 200, render, and show the right rows. This is the layer
  `check_db.py` cannot provide: it catches template errors, wrong queries, off-by-one windows.
- `tests/test_rules.py` — the locked decisions as tests. Not "nobody has broken this yet" but
  "this cannot be done": the duplicate guard raises, categories collide case-insensitively,
  `au_date` never emits US format or a leading zero.

**`python scripts/check_db.py`** — 14 structural checks against the real database, or 18 with
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
