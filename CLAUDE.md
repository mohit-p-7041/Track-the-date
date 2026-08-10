# Track the Date — Tecoma

Expiry-date tracker for BP Tecoma. Replaces a paid SaaS app ("beep"). Runs entirely on one
Windows laptop in the shop, served over the local network so iPads can use it in Safari.

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
- **One 7-day window**, not a set of bands. Read `expiry_window_days` from settings.
- **No shelf location field.** Considered and rejected — it slows down entry.
- **Categories are optional and grow by themselves.** The table starts empty. Staff pick or type
  one while scanning; it attaches to the product so it covers every batch of that barcode.
  `products.category_id IS NULL` means uncategorised and is a normal state — there is no
  'Uncategorised' row. Never block the add path on a category. Don't build a bulk-categorisation
  screen; that was considered and dropped.
- **Photos are optional and backfill.** Attached to the product, so adding one later makes it
  appear on batches recorded months ago. Lists show a placeholder and must not reflow when
  images arrive.
- **No animation, no transitions.** Adding a product happens hundreds of times a week. Clean and
  fast beats polished. Optimise the add path above everything else.

## Layout

```
app/          FastAPI application
  schema.sql    tables and indexes
  seed.sql      starting categories and settings
  security.py   PIN hashing
  routes/       one module per area (scan, products, sheet, admin)
  templates/    Jinja2
  static/       css, js, vendor
data/
  tecoma.db     the database — never commit
  photos/       compressed product images — never commit
  backups/      snapshots written at startup — never commit
  imports/      the beep Excel export
scripts/
  init_db.py    create the database
  import_beep.py  load the old app's Excel export
docs/
  DATA-NOTES.md   what's in the beep export, verified by running the import
  LAPTOP-NOTES.md the shop machine: specs, sleep settings, firewall, backups
  reference/      screenshots of the old app, for UI reference
```

## Commands

```bash
python scripts/init_db.py                                   # create the database
python scripts/init_db.py --reset                           # destructive rebuild
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx --dry-run
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx
python scripts/check_db.py                                  # sanity checks — run before committing
python scripts/check_db.py --expect-import                  # also assert the import numbers
python scripts/backup.py                                    # snapshot db + photos, keep last 7
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload     # dev
```

**The app runs on demand.** Staff double-click `start.bat` for a scan session (mainly weekends)
and close the window afterwards. There is no service, no auto-start, no always-on assumption.
Backups therefore run at startup, not overnight — a scheduled nightly job would never fire.

**Run `scripts/check_db.py` after any change that touches the schema, the importer, or how
batches are written.** It enforces the locked decisions above as executable checks and exits
non-zero on failure. If a check fails, fix the cause — don't weaken the check. If a design
decision genuinely changed, say so explicitly and update the check deliberately.

## Conventions

- Dates are stored as ISO `YYYY-MM-DD` text and displayed as `D MMM YYYY`. Australian format,
  never US. The shop is GMT+10.
- Money and quantities are integers. There is no pricing in this app.
- Batch status is one of `active`, `discounted`, `pulled`, `sold`. Nothing is hard-deleted by
  default so waste can be reviewed later.
- The unique index `idx_batches_unique_live` is the duplication guard. The app should catch a
  duplicate before insert and offer "add to quantity"; the index is the backstop. Never drop it.
- Every write that a person initiates records `added_by` / `resolved_by`.
- **Always open the database via `scripts/init_db.connect()`**, never `sqlite3.connect()` directly.
  `foreign_keys` and `synchronous` are per-connection pragmas — a raw connect silently drops
  both, which loses referential integrity and crash durability.
- **Submit each entry immediately.** Don't build multi-step wizards holding state in the browser.
  The laptop can sleep at any moment, and anything not yet posted is gone.
- Images: resize client-side before upload, then Pillow to max 800px long edge, JPEG q72, EXIF
  stripped. Target under 80KB. Filenames keyed to barcode.

## The data

The beep export at `data/imports/beep_2026-08-10.xlsx` is real production data:
2343 rows, 952 unique products, 2 staff accounts. It imports cleanly to 2340 batches — see
`docs/DATA-NOTES.md`. Use it for realistic testing rather than inventing fixtures.

Every product imports with `category_id` NULL — the old app only ever had one category ('All'),
so there was nothing to migrate. 583 batches were already expired at import and carry a note
saying so; leave them alone, staff clear that backlog as they rescan.

Product names are messy in ways that matter for search: inconsistent case
(`C/RIDGE WATER 1L` vs `Cool Ridge Water 600ml`), trailing whitespace, some non-English
characters, and a few with dates baked into the name. Search must be case-insensitive and
whitespace-tolerant. Don't "clean" the names in the database — staff recognise them as they are.

## Testing

There is no test framework yet. When adding one, prefer `pytest` against a temporary SQLite file
built from `schema.sql`. Always verify against the real export, not toy data — the edge cases
that matter are in there.
