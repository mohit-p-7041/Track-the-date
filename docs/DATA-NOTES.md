# What's in the beep export

`data/imports/beep_2026-08-10.xlsx`, exported 10 Aug 2026. Verified by running the importer
against it — these numbers come from the actual import, not an estimate.

## Shape

| | |
|---|---|
| Rows | 2,343 |
| Unique products (barcodes) | 952 |
| Batches created | 2,340 |
| Rows merged as duplicates | 3 |
| Rows skipped | 0 |
| Staff accounts | 2 — `BP TECOMA` (2,293 rows), `sar ob` (50 rows) |
| Date range | 25 May 2026 → 30 Mar 2032 |

Columns: `Id`, `Name`, `Barcode`, `Expiration Date`, `Category`, `Memo`, `Added User`,
`Added Date`.

The export is clean. Every row has a barcode and a readable date, and no barcode maps to two
different product names. That's better than most real-world imports.

## After import, as at 10 Aug 2026

| Band | Batches |
|---|---|
| Already expired (imported as `pulled`) | 583 |
| Expiring today | 7 |
| Next 7 days | 55 |
| 8–14 days | 44 |
| 15–30 days | 121 |
| Beyond 30 days | 1,530 |
| **Live total** | **1,757** |

Sum of all batch quantities is 2,343, reconciling exactly with the original row count.

## Things worth knowing

**Categories don't exist yet.** Every one of the 2,343 rows has category `All`. The old app had a
single category, so there is nothing to migrate. All products import as `Uncategorised` and
someone has to sort 952 products into real categories. `app/seed.sql` proposes 15 categories
based on the actual product mix — edit that list before importing, then plan a session to
bulk-assign. This is the largest piece of manual work in the whole migration.

**583 expired items were never cleared.** Items dating back to 25 May 2026 were still sitting in
the old system. Either staff stopped resolving items when the premium plan lapsed, or the
"remove once pulled" habit never formed. Worth knowing, because a tool that accumulates stale
rows stops being trusted — the new app should make resolving an item as fast as adding one.

**Three exact duplicates existed** despite the old app running a duplicate check:

- Trolli Bright Crawlers 150g — 12 Jul 2026
- X-treme sour watermelon 160g — 4 Jul 2026
- K/KAZE CREAMY SODA — 9 Jul 2026

These merge into single batches with quantity 2. The new schema forbids this at the database
level via `idx_batches_unique_live`.

**Names are messy in ways that affect search.** Inconsistent casing (`C/RIDGE WATER 1L` next to
`Cool Ridge Water 600ml`), trailing whitespace, curly apostrophes (`Annie's`), one product name in
Korean, and some with dates or pack counts baked in (`POWERADE LEM/LIME 600ML x 2 22.03.22`).

Search has to be case-insensitive and whitespace-tolerant. Don't normalise the stored names —
staff recognise them as written, and rewriting 952 names is a good way to make the app feel
unfamiliar on day one.

**No memos.** The `Memo` field is empty on all 2,343 rows. Staff never used it. Worth keeping the
field but not worth prominent screen space.

**High-turnover products** are heavily repeated, which is what the Product/Batch split is for:

| Product | Batches |
|---|---|
| Monster Ultra Zero 500ml | 31 |
| Cool Ridge Water 600ml | 22 |
| Redbull 473ml | 20 |
| C/Ridge Water 1L | 19 |
| Mt Franklin Still Water 600ml | 18 |

At 2.5 batches per product on average, storing the photo once per barcode rather than once per
row is roughly a 60% saving on image storage before compression even starts.

## Re-running the import

The importer is idempotent for products (matched on barcode) and uses `INSERT OR IGNORE` for
batches, so re-running won't duplicate. To start completely fresh:

```bash
python scripts/init_db.py --reset
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx
```

Use `--dry-run` first to see the report without writing anything.

## Not migrated

**Photos.** An Excel export can't carry them. The old app had images for at least some products
(see `docs/reference/`), but they're only retrievable through the app itself. Plan is to let them
rebuild naturally — staff photograph products as they scan them over the following weeks. Since
photos attach to the barcode, each product only needs shooting once.
