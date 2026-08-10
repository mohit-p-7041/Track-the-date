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

### Staying up

- Run as a Windows service (NSSM) so it starts on boot and survives reboots.
- Power settings: never sleep, never hibernate while on mains.
- Reserve the laptop's IP on the router so the iPad bookmark never breaks.

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
| `users` | id, name, pin_hash, role (staff / manager), active |
| `categories` | id, name, sort_order, active |
| `products` | id, **barcode (unique)**, name, category_id, image_path, created_at, created_by |
| `batches` | id, product_id, expiry_date, quantity, note, status, added_by, added_at, resolved_by, resolved_at |
| `settings` | key, value (thresholds, shop name, backup path) |

`batches` carries a unique index on (product_id, expiry_date) for active rows — that is the
duplication guard.

Batch `status` is one of `active`, `discounted`, `pulled`, `sold`. Nothing is hard-deleted by
default, so you keep a record of what actually got wasted vs. sold down. Managers can purge old
resolved rows.

### Accountability

Every batch records who added it and who resolved it, with a timestamp. Staff log in with their
name and a 4-digit PIN — enough to know who did what, not so much that it slows the counter down.
Manager PIN is needed for: adding categories, adding/removing staff, bulk delete, and export.

---

## 3. Screens

1. **PIN login** — big number pad, pick your name, four digits.
2. **Home** — near-expiry dashboard. Colour-coded bands: Expired / ≤7 days / ≤14 days / ≤30 days,
   with counts. Tap a band to see the list. Filter by category.
3. **Scan & Add** — the main workflow.
   - Counter (laptop): USB scanner gun fires the barcode straight into the field.
   - Aisle (iPad): camera scanner.
   - Known barcode → name, category, photo pre-filled, cursor lands on the date.
   - Unknown barcode → new product form, take a photo, pick category, enter date.
4. **Product list** — search by name or barcode, filter by category, sort by soonest expiry.
5. **Product detail** — photo, all batches for that barcode, history.
6. **Weekly discount sheet** — the printable. See below.
7. **Admin** — categories, staff PINs, backup, Excel export.

---

## 4. Weekly discount sheet

Printed on the weekend, covering the week ahead.

- Pulls every batch expiring in the next 7 days (date range adjustable before printing).
- Grouped by category, sorted by date within each group.
- One line per item: tick box, product name, expiry date, quantity, barcode, blank column for
  the discount price.
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

An import script reads it and:
- Creates one Product per unique barcode (first name/category wins, flagged for review if names
  disagree across rows).
- Creates one Batch per row.
- Drops rows already past expiry into `status = pulled` so they don't clutter the home screen but
  stay in the history.
- Prints a summary: X products, Y batches, Z rows skipped and why.

Photos won't come across in an Excel export — those get rebuilt naturally as staff scan items over
the following weeks.

**Action needed from you:** run that export and drop the file in this folder. Your premium plan
lapsed on 23 May, so if export is locked behind it, tell me early and we plan around it.

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
| Service | NSSM | Starts on boot, restarts on crash |

Deliberately boring. In eighteen months someone needs to be able to open this and fix it.

---

## 9. Timeline

One month available. Realistic plan:

| Week | Work |
|---|---|
| 1 | Database, PIN login, scan & add, home dashboard, categories |
| 2 | Photos + compression, weekly print sheet, admin screens, Excel import |
| 3 | HTTPS + iPad certificates, install as service, backups, staff trial run |
| 4 | Fixes from real-world use, training notes, handover doc |

A usable v1 should exist by the end of week 2. Weeks 3–4 are what turn it from "works on my
machine" into something the shop actually relies on.

---

## 10. Open questions

1. **Categories** — what are the predetermined ones? (Drinks, Dairy, Snacks, Bakery, Frozen…?)
2. **Near-expiry thresholds** — is 7 / 14 / 30 days right, or does BP use different windows?
3. **Quantity** — do you track how many of each batch, or is it one row per physical item?
4. **Location** — worth recording where in the shop an item sits (fridge 2, aisle 3), to speed up
   the aisle walk?
5. **Laptop** — Windows 10 or 11? Does it stay switched on overnight?
6. **Staff count** — how many people need a PIN?
