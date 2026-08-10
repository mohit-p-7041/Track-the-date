# Track the Date — Tecoma

Local expiry-date tracker for BP Tecoma. Replaces the current paid app.

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
      ├── iPad  ──┤  open https://192.168.x.x:8443 in Safari
      └── Phone ──┘  (added to home screen, looks like a native app)
```

- Everything lives on the laptop: one SQLite database file + one photos folder.
- iPads are just browsers pointed at the laptop. Nothing installed, nothing synced.
- If the laptop is off, nothing works. That's the trade for zero hosting cost.

### HTTPS is required (not optional)

Safari refuses camera access over plain `http://` from a network address. Since we want
camera scanning on the iPads, the app is served over HTTPS from day one using **mkcert**:

1. Generate a local certificate on the laptop, valid for its IP address.
2. Install the mkcert root certificate on each iPad (~2 min each, one time).
   Settings → Profile Downloaded → Install, then General → About → Certificate Trust
   Settings → toggle it on.
3. Done. No warnings, camera works.

### Operating model: on demand, not always on

The laptop is not a server and won't be treated as one. Staff scan in sessions, mainly on the
weekend, so the app runs when it's wanted:

- Double-click `start.bat`. It prints the address for the iPads and comes up in about two seconds.
- Use it. Close the window when done.
- Everything saved is already on the disk. There is no shutdown procedure.

**This deletes work rather than adding it.** No NSSM service, no auto-start on boot, no
always-awake configuration. Sleep and lid settings only matter for the length of a session.

Two consequences worth holding onto:

**Backups run on startup, not overnight.** A nightly scheduled job would never fire on a machine
that is off overnight. `start.bat` calls `scripts/backup.py` every time the app comes up.

**Nothing can be recorded while the app is down.** If someone spots a short-dated item on a
Tuesday it isn't captured unless they bring the app up. Starting it is one double-click, so this
is habit rather than architecture — but it is a real gap, and if it bites often that's the signal
to run it always-on after all.

Still worth doing: reserve the laptop's IP on the router, so the iPad bookmarks survive between
sessions.

---

## 2. Data model

The key decision: **Product** and **Batch** are separate things.

A Product is a barcode — "Solo Energy Lemon 500ml". It has one name, one category, one photo,
forever. A Batch is one expiry date for that product.

This matters for three reasons:

- **Photos stored once per barcode, not per date.** Your 2343 entries are probably ~400 unique
  products. Six times less image storage.
- **Duplicate prevention becomes a database rule.** Unique constraint on (product + expiry date).
  Scan a pair that already exists and the app says *"Already tracked, expires 25 May — add to
  quantity instead?"* rather than silently creating a twin.
- **Scanning gets fast.** Known barcode auto-fills name, category and photo. Staff enter only the
  date. Three seconds instead of fifteen.

### Tables

| Table | Fields |
|---|---|
| `users` | id, name, pin_hash, pin_salt, active |
| `categories` | id, name, sort_order, active |
| `products` | id, **barcode (unique)**, name, category_id, image_path, created_at, created_by |
| `batches` | id, product_id, expiry_date, note, status, added_by, added_at, resolved_by, resolved_at |
| `settings` | key, value (expiry window, shop name, image settings) |

`batches` carries a unique index on (product_id, expiry_date) for live rows — that is the
duplication guard.

Batch `status` is one of `active`, `discounted`, `pulled`, `sold`. Nothing is hard-deleted by
default, so you keep a record of what actually got wasted vs. sold down.

### No counting

The shop does not track how many of a thing it has. A second Redbull Zero 250ml is entered only
if its expiry date differs from one already recorded. So a batch is a fact — "this product has
stock dying on this date" — not a quantity.

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
2. **Home** — what's due. Expired, then due within 7 days, then everything upcoming. Filter by
   category.
3. **Scan & Add** — the main workflow.
   - Counter (laptop): USB scanner gun fires the barcode straight into the field.
   - Aisle (iPad): camera scanner.
   - Known barcode → name, category, photo pre-filled, cursor lands on the date.
   - Unknown barcode → new product form, take a photo, pick category, enter date.
4. **Product list** — search by name or barcode, filter by category, sort by soonest expiry.
5. **Product detail** — photo, all batches for that barcode, history.
6. **Weekly discount sheet** — the printable. See below.
7. **Settings** — categories, staff PINs, backup, Excel export. Open to everyone.

### Categories grow themselves

There is no categorisation project, and no seeded list. The categories table starts empty.

When staff scan a product they can pick an existing category or type a new one. That choice
attaches to the **product**, so it covers every batch of that barcode — past and future — and is
never asked again. Category is optional; an uncategorised product is a normal, valid state and
just shows blank.

The useful consequence: the products staff scan most get categorised first. Monster Ultra Zero
has 31 batches in the export, so one person typing "Energy Drinks" once covers all 31. The
catalogue sorts itself in order of how much it matters, at zero migration cost. The long tail of
products nobody touches stays uncategorised, and that's fine — nobody was looking for them.

Because ten people are typing freely, the categories table has a **case-insensitive unique
index**. Without it you get "Drinks", "drinks" and "DRINKS" inside a week. The category input
should also suggest existing categories as you type, so people pick rather than invent.

### Photos backfill the same way

Products start with no photo. When someone adds one it attaches to the barcode, so it
immediately appears everywhere that product shows up, including batches recorded months ago.

Photo is never required. Nothing in the add path waits for a camera. Lists show a neutral
placeholder where there's no image yet, and must not reflow or jump when photos appear later.

### UI principles

Clean and no-nonsense. No animation, no transitions, no decorative flourish.

Adding a product is the action that happens hundreds of times a week, and every extra field or
half-second of motion is a tax on it. Optimise that path above everything else; the rest of the
app can be plain.

Deliberately **not** captured: shelf location, aisle, fridge number. Staff know where things are,
and the field would only slow entry down.

### One window: 7 days

There is a single threshold, not a set of bands. Within 7 days is due; beyond it is upcoming.
Stored as `expiry_window_days` so it can change without touching code.

---

## 4. Weekly discount sheet

Printed on the weekend, covering the week ahead.

- Pulls every batch expiring in the next 7 days (date range adjustable before printing).
- Grouped by category, sorted by date within each group.
- One line per item: tick box, product name, expiry date, barcode, blank column for the
  discount price.
- Clean A4 print layout — no navigation, no colours that eat toner.
- Staff walk the aisles with paper, tick items off, then mark them discounted in the app after.

The same information is always on the home screen, live. The print is for the aisle walk.

---

## 5. Images

- Captured from the iPad camera or laptop webcam, or uploaded from a file.
- Shrunk **in the browser before upload** (canvas resize) so we're not pushing 4MB over the shop
  WiFi for every product.
- Server side: Pillow resizes to max 800px on the long edge, JPEG quality ~72, EXIF stripped.
  Lands around 50–70KB per photo.
- Stored as files in a `photos/` folder, filename keyed to the barcode. Not in the database —
  keeps the database small and easy to back up or inspect.
- **Estimated total: ~25–35MB** for the whole product catalogue.

---

## 6. Migration from the current app

Your existing app has Settings → Export to Excel. That export is the starting point.

**Done.** The export is at `data/imports/beep_2026-08-10.xlsx` and the importer works — see
`docs/DATA-NOTES.md` for verified numbers.

- 952 products, 2,340 batches, 0 rows skipped.
- All products import with no category.
- 583 already-expired batches import as `pulled`, with a note saying they expired before the
  migration and were never verified. `resolved_by` is left empty — nobody confirmed them, so no
  name goes against them.

Those 583 are stale records; the stock left the shelves long ago and nobody cleared the entries.
They stay out of the daily view but remain in the history, and staff clear the backlog naturally
as they rescan products over the coming weeks. No cleanup session needed.

Photos can't come across in an Excel export. They rebuild naturally, one per barcode.

---

## 7. Backups

The whole system is one `.db` file plus a `photos/` folder. That makes backup trivial:

- Nightly automatic zip of both into a backup folder, keeping the last 7.
- Point that folder at OneDrive or a USB stick and you have an off-machine copy.
- Manual "Download backup" button in Admin for before any risky change.
- Excel export button as a second, human-readable safety net.

This is worth taking seriously — with no cloud, a dead laptop means a dead database unless the
backup is running.

---

## 8. Stack

| Piece | Choice | Why |
|---|---|---|
| Server | Python 3.12 + FastAPI + uvicorn | One `start.bat`, no build step |
| Database | SQLite (WAL mode) | Single file, zero admin, easy backup |
| Frontend | Plain HTML + CSS + JS, Jinja2 templates | No framework, no npm, nothing to break in a year |
| Barcode (camera) | ZXing-js, vendored locally | Works offline, no CDN dependency |
| Images | Pillow | Reliable on Windows |
| Certificates | mkcert | Makes iPad camera access work |
| Launcher | `start.bat` | Double-click to run a session; no service needed |

Deliberately boring. In eighteen months someone needs to be able to open this and fix it.

---

## 9. Timeline

One month available. Database, schema and import are done.

| Week | Work |
|---|---|
| 1 | PIN login, scan & add with duplicate check, home screen, inline categories |
| 2 | Photos + compression, weekly print sheet, search, settings |
| 3 | HTTPS + iPad certificates, first real weekend scan session with staff |
| 4 | Fixes from real-world use, Excel export, training notes |

Week 3 got lighter when the app became on-demand: no service install, no boot configuration.
The backup script is already written and runs on startup.

A usable v1 should exist by the end of week 2. Weeks 3–4 are what turn it from "works on my
machine" into something the shop actually relies on.

### Deferred, deliberately

- **Excel export.** Wanted, but not needed to go live — the startup backup already protects the
  data, and the old app remains readable. Week 4.
- **Quantity per batch.** Column exists at 1, hidden. Pending the manager's view.
- **Bulk categorisation screen.** Not being built. Categories now grow through normal scanning.

---

## 10. Settled and outstanding

Answered 10 Aug 2026:

| Question | Answer |
|---|---|
| Near-expiry thresholds | One window, 7 days. No multi-band scheme. |
| Quantity | Not tracked. One batch per product + date. |
| Shelf location | Not captured — adds friction, staff know the shop. |
| Roles | None. ~10 staff, everyone can do everything. |
| Laptop | Acer Aspire A515-51G, Windows 11 Home. See `docs/LAPTOP-NOTES.md`. |
| UI | Clean, fast, no animation. |

| Categories | No fixed list. Created inline while scanning, optional, attached to the barcode. |
| Expired backlog | Left as-is with a migration note. Cleared naturally, no cleanup session. |
| Photos | Optional, added over time, attached to the barcode so they backfill. |
| Excel export | Wanted, deferred to week 4. |

Still outstanding:

1. **Where development happens** — recommend building on the Mac and deploying to the laptop by
   git. See `docs/LAPTOP-NOTES.md`.
2. **Quantity per batch** — Mohit is checking whether the manager wants counts. The column is
   there at 1 and hidden, so enabling it later is a UI change, not a migration.
