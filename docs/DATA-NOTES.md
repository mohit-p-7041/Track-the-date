# What's in the beep export

`data/imports/beep_2026-08-10.xlsx`, exported 10 Aug 2026. Verified by running the importer
against it — these numbers come from the actual import, not an estimate.

## Shape

| | |
|---|---|
| Rows | 2,343 |
| Unique products (barcodes) | 944 |
| Batches created | 2,327 |
| Duplicate rows collapsed | 3 |
| Rows skipped | 13 — barcodes the rule refuses |
| Staff accounts | 2 — `BP TECOMA` (2,293 rows), `sar ob` (50 rows) |
| Date range | 25 May 2026 → 30 Mar 2032 |

Columns: `Id`, `Name`, `Barcode`, `Expiration Date`, `Category`, `Memo`, `Added User`,
`Added Date`.

**Revised 13 Aug, when the barcode rule landed.** The first import of this file produced 952
products and 2,340 batches, and this page called the export clean. It is not quite: every row has
a readable date and no barcode maps to two names, but **eight barcodes are not barcodes** — seven
marketing URLs someone scanned off the packet instead of the code, and one 40-digit gun misfire.
The importer now refuses them, which drops 13 rows.

Two more were `]C1…` — the gun's AIM identifier stuck to a real code. Those are recovered rather
than refused: the prefix is stripped and the digits underneath are kept, so `golden gay time
lamington` and `magnum almond` survive with their history.

To reproduce these numbers exactly, pin the import date — the expired/live split moves with the
calendar otherwise:

```bash
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx --today 2026-08-10
```

## After import, as at 10 Aug 2026

| Group | Batches |
|---|---|
| Already expired (imported as `pulled`) | 581 |
| Due within 7 days | 62 |
| Upcoming | 1,684 |
| **Live total** | **1,746** |

2,327 batches + 3 collapsed duplicates + 13 refused = 2,343, reconciling exactly with the
original row count.

## Things worth knowing

**Categories don't exist.** Every one of the 2,343 rows has category `All`. The old app had a
single category, so there is nothing to migrate. Products import with `category_id` NULL.

There is no bulk-categorisation job. Categories are created inline as staff scan, and attach to
the barcode rather than the batch — so the products handled most get categorised first and
cover the most rows. One person typing "Energy Drinks" against Monster Ultra Zero covers 31
batches. The long tail nobody scans stays blank, which costs nothing.

**583 expired items were never cleared.** Items dating back to 25 May 2026 were still sitting in
the old system. Either staff stopped resolving items when the premium plan lapsed, or the
"remove once pulled" habit never formed. Worth knowing, because a tool that accumulates stale
rows stops being trusted — the new app should make resolving an item as fast as adding one.

These import as `pulled` with the note *"Expired before migration — not verified"* and no
`resolved_by`, because nobody actually confirmed them. The stock is long gone from the shelves;
only the records lingered. They stay out of the daily view and get cleared naturally as staff
rescan those products.

**Three exact duplicates existed** despite the old app running a duplicate check:

- Trolli Bright Crawlers 150g — 12 Jul 2026
- X-treme sour watermelon 160g — 4 Jul 2026
- K/KAZE CREAMY SODA — 9 Jul 2026

Since the shop doesn't count stock, these collapse into one batch each. The new schema forbids
the pair from recurring at the database level via `idx_batches_unique_live`.

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
row is roughly a 60% saving on image storage before compression even starts. At ~60 KB per photo
across 952 products, the full library lands near 57 MB.

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
photos attach to the barcode, each product only needs shooting once, and once added it appears
against every batch of that product including ones recorded before the photo existed.

**Categories.** Nothing to migrate — see above.
