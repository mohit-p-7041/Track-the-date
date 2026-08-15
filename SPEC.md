# Track the Date — Tecoma

Local expiry-date tracker for BP Tecoma. Replaces a paid app ("beep") whose plan lapsed in
May 2026.

This is the agreed design. `CLAUDE.md` holds the working rules for building it.

---

## 1. How it runs

One Windows laptop in the shop runs everything. No cloud, no hosting, no monthly fee.

```
   Shop WiFi
      │
      ├── Windows laptop ──── runs the app + holds the database + photos
      │                        (USB scanner gun plugged in at the counter)
      │
      ├── iPad  ──┐
      ├── iPad  ──┤  open the laptop's address in Safari
      └── Phone ──┘  (added to home screen, looks like a native app)
```

- Everything lives on the laptop: one SQLite database file and one photos folder.
- iPads are just browsers pointed at the laptop. Nothing installed, nothing synced.
- If the laptop is off, nothing works. That's the trade for zero hosting cost.

### Operating model: on demand, not always on

The laptop is not a server and won't be treated as one. Staff scan in sessions, mainly on the
weekend, so the app runs when it's wanted:

- Double-click `start.bat`. It backs up, prints the address for the iPads, and comes up in about
  two seconds.
- Use it. Close the window when done.
- Everything saved is already on disk. There is no shutdown procedure.

**This removes work rather than adding it.** No service to install, no auto-start on boot, no
always-awake configuration.

Two consequences worth holding onto:

**Backups run at startup, not overnight.** A nightly scheduled job would never fire on a machine
that's off overnight. `start.bat` calls `scripts/backup.py` every time the app comes up.

**Nothing can be recorded while the app is down.** If someone spots a short-dated item on a
Tuesday it isn't captured unless they bring the app up. Starting it is one double-click, so this
is habit rather than architecture — but it's a real gap, and if it bites often that's the signal
to reconsider always-on.

### Addresses and HTTPS

`start.bat` picks its mode automatically:

| | Address | Camera on iPad |
|---|---|---|
| No certificates (default) | `http://<laptop-ip>:8000` | No |
| Certificates present | `https://<laptop-ip>:8443` | Yes |

Safari refuses camera access over plain `http://` from a network address, so aisle scanning on
an iPad needs HTTPS. Everything else — browsing, searching, entering dates, the print sheet —
works fine over HTTP, and the laptop's own webcam works on `localhost` either way.

So HTTP is correct for development, and HTTPS is a day-2 task, not a prerequisite. To switch:

```
mkcert -key-file certs\key.pem -cert-file certs\cert.pem <laptop-ip>
```

Then install the mkcert root certificate on each iPad — Settings → Profile Downloaded → Install,
then General → About → Certificate Trust Settings → toggle it on. About two minutes per iPad,
once. `start.bat` detects the certificates and switches by itself.

Also worth doing: reserve the laptop's IP on the router so the iPad bookmarks survive between
sessions.

---

## 2. Data model

The key decision: **Product** and **Batch** are separate things.

A Product is a barcode — "Solo Energy Lemon 500ml". It has one name, one category, one photo,
forever. A Batch is one expiry date for that product.

This matters for three reasons:

- **Photos are stored once per barcode, not once per date.** The export holds 2,343 entries
  across 952 unique products — about 2.5 batches per product, and far more for fast movers.
  Storing photos per product rather than per entry cuts image storage by roughly 60%, and makes
  it plateau instead of growing forever.
- **Duplicate prevention becomes a database rule.** A unique index on (product, expiry date) for
  live rows. Scan a pair that already exists and the app says *"Already tracked — expires
  25 May"* rather than silently creating a twin.
- **Scanning gets fast.** A known barcode auto-fills name, category and photo. Staff enter only
  the date.

### Tables

| Table | Fields |
|---|---|
| `users` | id, name, pin_hash, pin_salt, active, created_at |
| `categories` | id, name, sort_order, active, created_at, created_by |
| `products` | id, **barcode (unique)**, name, category_id, image_path, created_at, created_by |
| `batches` | id, product_id, expiry_date, quantity, note, status, added_by, added_at, resolved_by, resolved_at |
| `settings` | key, value |

`idx_batches_unique_live` is a partial unique index on (product_id, expiry_date) covering only
`active` and `discounted` rows. That's the duplication guard. With only those two statuses left
it now covers every row — a date recurs by the earlier batch having been deleted, not by being
excluded from the index.

Batch `status` is `active` or `discounted` — **revised 13 Aug**, down from four. A batch ends one
of two ways: it gets a discount sticker, or it is deleted. `pulled` and `sold` were removed
because the shop never used them (1757 `active` and 583 imported `pulled`, zero of each of the
others) and because keeping every item ever taken off a shelf means a database that only grows,
on a laptop where nobody will ever prune it. The Excel export is the way to keep a snapshot of
history before it goes.

Deleting is therefore a normal, frequent action rather than an exception, and it is real: the row
is removed. It warns first only when the item has not yet expired — see §3.2. **Products are
never deleted**, including when their last date goes; they keep their name, photo and category so
the next scan of that barcode still knows what it is.

`barcode` is digits only, 6–18 of them, after a leading AIM identifier (`]` plus two characters)
is stripped from what the gun sends. Anything else is refused, which is what stops a typed word
becoming a permanent product.

### No counting

The shop does not track how many of a thing it has. A second Redbull Zero 250ml is entered only
if its expiry date differs from one already recorded. A batch is a fact — "this product has stock
dying on this date" — not a quantity.

This is why the duplicate rule is the whole data model rather than a validation nicety. The
schema keeps a `quantity` column defaulting to 1 in case the manager later wants counts, but it
is never shown and never edited.

### Accountability

Every batch records who added it and who resolved it, with a timestamp. Staff log in with their
name and a 4-digit PIN.

**There are no roles.** Around 10 staff, one shop, everyone can do everything — including adding
categories and removing batches. The PIN exists so the log says who did what, not to gate
features. Don't build an admin tier.

---

## 3. Screens

1. **PIN login** — big number pad, pick your name, four digits.
2. **Home** — what's due. Anything past its date first, then anything due within 7 days. Filter
   by category.
3. **Scan & Add** — the main workflow.
   - Counter (laptop): USB scanner gun fires the barcode straight into the field.
   - Aisle (iPad): camera scanner.
   - Known barcode → name, category, photo pre-filled, cursor lands on the date.
   - Unknown barcode → new product form, optional photo, optional category, enter date.
4. **Product list** — search by name or barcode, filter by category, sort by soonest expiry.
5. **Product detail** — photo, all batches for that barcode, history.
6. **Weekly discount sheet** — the printable. See section 4.
7. **Settings** — categories, staff PINs, backup. Open to everyone.

### One window: 7 days

A single threshold, not a set of bands. Within 7 days is due; beyond it is upcoming. Stored as
`expiry_window_days` so it can change without touching code.

Items past their date but not yet resolved are a normal, expected state — they sit at the top of
the home screen until someone deals with them. Don't treat them as an error condition.

### Categories grow themselves

There is no categorisation project and no seeded list. The categories table starts empty.

When staff scan a product they can pick an existing category or type a new one. That choice
attaches to the **product**, so it covers every batch of that barcode — past and future — and is
never asked again. Category is optional; an uncategorised product is a normal, valid state and
shows blank.

The useful consequence: the products staff scan most get categorised first. Monster Ultra Zero
has 31 batches in the export, so one person typing "Energy Drinks" once covers all 31. The
catalogue sorts itself in order of how much it matters, at zero migration cost. The long tail
nobody touches stays uncategorised, and nobody was looking for it.

Because ten people are typing freely, the categories table has a **case-insensitive unique
index**. Without it you get "Drinks", "drinks" and "DRINKS" within a week. The category input
should also suggest existing categories as you type, so people pick rather than invent.

### Photos backfill the same way

Products start with no photo. When someone adds one it attaches to the barcode, so it
immediately appears everywhere that product shows up, including batches recorded months ago.

A photo is never required. Nothing in the add path waits for a camera. Lists show a fixed-size
placeholder where there's no image yet and must not reflow when photos appear later.

### UI principles

Clean and no-nonsense. No animation, no transitions, no decorative flourish.

Adding a product is the action that happens hundreds of times a week, and every extra field or
half-second of motion is a tax on it. Optimise that path above everything else; the rest of the
app can be plain.

Deliberately **not** captured: shelf location, aisle, fridge number. Staff know where things are,
and the field would only slow entry down.

---

## 4. Weekly discount sheet

Printed on the weekend, covering the week ahead.

- Every batch expiring in the next 7 days (range adjustable before printing).
- Grouped by category, sorted by date within each group.
- One line per item: tick box, product name, expiry date, barcode, blank column for the
  discount price.
- Clean A4 print layout — no navigation, no colours that eat toner.
- Staff walk the aisles with paper, tick items off, then mark them discounted in the app after.

The print is for the aisle walk; the home screen is always live. **Amended 13 Aug:** the sheet is
the *sellable* part of what the home screen shows — bounded today to the cutoff. Past-date stock
stays on the home screen's worklist, because it gets pulled off the shelf rather than discounted.

---

## 5. Images

- Captured from the iPad camera or laptop webcam, or uploaded from a file.
- Shrunk **in the browser before upload** (canvas resize), so we're not pushing 4 MB over the
  shop WiFi per product.
- Server side: Pillow resizes to max 800px on the long edge, JPEG quality 72, EXIF stripped.
  Lands around 50–70 KB.
- Stored as files in `data/photos/`, filename keyed to the barcode. Not in the database — that
  keeps the database tiny and easy to back up.

**Expected total: around 57 MB** at 952 products, rising to perhaps 90 MB as the catalogue grows,
then flattening. Storing per entry instead would pass 550 MB within three years and keep going.

---

## 6. Migration from the old app

**Done and verified.** The export is at `data/imports/beep_2026-08-10.xlsx` and
`scripts/import_beep.py` loads it. See `docs/DATA-NOTES.md` for the full picture.

- 2,343 rows → 952 products and 2,340 batches. 0 rows skipped.
- 3 rows were exact duplicates and collapse into single batches.
- All products import with no category — the old app only ever had one ('All').
- 583 already-expired batches import as `pulled`, noted *"Expired before migration — not
  verified"*, with `resolved_by` left empty because nobody actually confirmed them.

Those 583 are stale records; the stock left the shelves long ago and only the entries lingered.
They stay out of the daily view but remain in history. No cleanup session needed.

Photos can't come across in an Excel export. They rebuild naturally, one per barcode.

---

## 7. Backups

The whole system is one `.db` file plus a `photos/` folder, which makes backup trivial.

`scripts/backup.py` runs automatically every time `start.bat` starts the app:

- Snapshots the database using SQLite's own backup API, so it's safe even while the app is
  serving requests.
- Copies photos that are new or changed, so it stays cheap after the first run.
- Keeps the last 7 snapshots. The database is around 450 KB, so seven copies cost about 3 MB.

**These land on the same disk as the original.** That protects against a mistake, not a dead
drive. Copy `data/backups` to OneDrive or a USB stick. Test a restore before trusting it.

---

## 8. Stack

| Piece | Choice | Why |
|---|---|---|
| Server | Python 3.12 + FastAPI + uvicorn | One `start.bat`, no build step |
| Database | SQLite (WAL, `synchronous=FULL`) | Single file, zero admin, survives a flat battery |
| Frontend | Plain HTML + CSS + JS, Jinja2 templates | No framework, no npm, nothing to break in a year |
| Barcode (camera) | ZXing-js, vendored locally | Works offline, no CDN dependency |
| Images | Pillow | Reliable on Windows |
| Certificates | mkcert | Makes iPad camera access work |
| Launcher | `start.bat` | Double-click to run a session; no service needed |

Deliberately boring. In eighteen months someone needs to be able to open this and fix it.

---

## 9. Timeline

**Five days, 11–15 August 2026.** Compressed from the original month on 11 Aug: the station needs
this, and every screen landed in one sitting rather than two weeks.

Database, schema, importer, backup and checks were already done and verified before day 1.

| Day | Work |
|---|---|
| 1 — Tue 11 Aug | **Done.** All seven screens: sign in, scan & add, inline categories, due list, products, photos, discount sheet, settings |
| 2 — Wed 12 Aug | Real staff names and PINs. HTTPS via mkcert, certificates onto the iPads, camera scanning in the aisles |
| 3 — Thu 13 Aug | Deploy to the shop laptop, Excel export, training notes for staff |
| 4 — Fri 14 Aug | Dry run at the counter with the gun and one iPad. Fix what that finds |
| 5 — Sat 15 Aug | First real weekend scan session with staff |

The order still comes from dependency, not preference. Day 2 is the one that cannot slip: without
certificates the iPads have no camera, and without real PINs the audit trail says `BP TECOMA` for
everybody.

**Keep day 5 genuinely empty.** The first staff session always surfaces something, and a day with
nothing else in it is what turns that from a problem into a fix. This was true of week 4 in the
month-long plan and is more true now, not less — a shorter schedule removes the slack that used
to absorb surprises.

What the compression costs, stated plainly: there is no longer a week of real use between "works"
and "the shop depends on it". The mitigation is that nothing is destructive — every batch is an
update, backups run at every startup, and the old paper habit still works if a session goes badly.

### Deferred, deliberately

- **Excel export.** ~~Wanted, not needed to go live — the startup backup already protects the
  data. Day 3.~~ Built on day 2: a button on the settings screen and `scripts/export_xlsx.py`.
- **Quantity per batch.** Column exists at 1, hidden. Pending the manager's view.
- **Bulk categorisation screen.** Not being built. Categories grow through normal scanning.

---

## 10. Settled

All answered 10 Aug 2026.

| Question | Answer |
|---|---|
| Near-expiry thresholds | One window, 7 days. No multi-band scheme. |
| Quantity | Not tracked. One batch per product + date. |
| Shelf location | Not captured — adds friction, staff know the shop. |
| Roles | None. ~10 staff, everyone can do everything. |
| Categories | No fixed list. Created inline while scanning, optional, attached to the barcode. |
| Expired backlog | Left as-is with a migration note. Cleared naturally, no cleanup session. |
| Photos | Optional, added over time, attached to the barcode so they backfill. |
| Scanning | Both — USB gun at the counter, iPad camera in the aisles. |
| Alerts | No email. Home screen plus a printable weekly sheet. |
| Excel export | Wanted, deferred to day 3. |
| Operating model | On demand. `start.bat` for a session, close the window after. |
| Laptop | Acer Aspire A515-51G, Windows 11 Home. See `docs/LAPTOP-NOTES.md`. |
| UI | Clean, fast, no animation. |

### Still open

1. **Where development happens** — recommend building on the Mac and deploying to the laptop by
   git. See `docs/LAPTOP-NOTES.md`.
2. **Quantity per batch** — Mohit is checking whether the manager wants counts. The column is
   there at 1 and hidden, so enabling it later is a UI change, not a migration.
