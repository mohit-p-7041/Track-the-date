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
  backups/      nightly zips — never commit
  imports/      the beep Excel export
scripts/
  init_db.py    create the database
  import_beep.py  load the old app's Excel export
docs/reference/ screenshots of the old app, for UI reference
```

## Commands

```bash
python scripts/init_db.py                                   # create the database
python scripts/init_db.py --reset                           # destructive rebuild
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx --dry-run
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx
uvicorn app.main:app --host 0.0.0.0 --port 8443 --reload     # dev
```

## Conventions

- Dates are stored as ISO `YYYY-MM-DD` text and displayed as `D MMM YYYY`. Australian format,
  never US. The shop is GMT+10.
- Money and quantities are integers. There is no pricing in this app.
- Batch status is one of `active`, `discounted`, `pulled`, `sold`. Nothing is hard-deleted by
  default so waste can be reviewed later.
- The unique index `idx_batches_unique_live` is the duplication guard. The app should catch a
  duplicate before insert and offer "add to quantity"; the index is the backstop. Never drop it.
- Every write that a person initiates records `added_by` / `resolved_by`.
- Images: resize client-side before upload, then Pillow to max 800px long edge, JPEG q72, EXIF
  stripped. Target under 80KB. Filenames keyed to barcode.

## The data

The beep export at `data/imports/beep_2026-08-10.xlsx` is real production data:
2343 rows, 952 unique products, 2 staff accounts. It imports cleanly — see `docs/DATA-NOTES.md`.
Use it for realistic testing rather than inventing fixtures.

Product names are messy in ways that matter for search: inconsistent case
(`C/RIDGE WATER 1L` vs `Cool Ridge Water 600ml`), trailing whitespace, some non-English
characters, and a few with dates baked into the name. Search must be case-insensitive and
whitespace-tolerant. Don't "clean" the names in the database — staff recognise them as they are.

## Testing

There is no test framework yet. When adding one, prefer `pytest` against a temporary SQLite file
built from `schema.sql`. Always verify against the real export, not toy data — the edge cases
that matter are in there.
