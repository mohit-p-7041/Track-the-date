# Backlog

What to build, in order. One item per session — `/feature <item>`.

The order is forced by dependency, not preference. Login comes first because every write records
who did it, and building the add path before there's a signed-in user means either faking
`added_by` or retrofitting it through every route later.

Each item lists **acceptance criteria**. They are written to be testable: each one should become
a test in `tests/`, and a feature isn't done until a broken version of it would go red.

Status: `[ ]` not started · `[~]` in progress · `[x]` done, verified

---

## 1. PIN login `[ ]`

SPEC §3.1, §2 Accountability. Blocks everything else.

Big number pad. Pick your name from a list, type four digits. Signed-in name is available to
every route so writes can record it.

- [ ] `GET /login` lists active staff and renders a numeric keypad
- [ ] Correct PIN sets a signed session cookie and redirects to `/`
- [ ] Wrong PIN re-renders with a plain message and does not say which part was wrong
- [ ] A request with no session redirects to `/login`, except `/login` and `/static/*`
- [ ] The signed-in user's id is reachable from any route without re-querying the session
- [ ] `GET /logout` clears the session
- [ ] Keypad is usable one-handed on an iPad — big targets, no keyboard needed
- [ ] No lockout, no complexity rules, no roles. PINs are accountability, not security

Notes: `itsdangerous` is already in `requirements.txt` for the signed cookie. `app/security.py`
already does the hashing.

Two accounts came across in the import — `BP TECOMA` and `sar ob` — and **both PINs are the
placeholder `1234`** (`import_beep.py` line 42). That's fine for building against, but the real
names and PINs have to be set before the first staff session in week 3. Staff management is
item 8; if login lands well before that, a one-off `scripts/add_user.py` is enough.

## 2. Scan & add `[ ]`

SPEC §3.3. **The feature the whole app exists for.** Used hundreds of times a week.

One field takes a barcode. Known barcode fills in the rest and jumps to the date. Unknown barcode
opens a short new-product form. Submit writes immediately.

- [ ] `GET /scan` puts the cursor in the barcode field on load, with no click required
- [ ] A USB scanner gun's trailing Enter submits the lookup — no mouse anywhere in the path
- [ ] Known barcode: name and category shown read-only, focus lands on the date field
- [ ] Unknown barcode: name field appears, category optional, date required
- [ ] Submitting writes one batch with `added_by` set to the signed-in user
- [ ] **Duplicate: the app catches it before insert** and says "Already tracked — expires
      14 Sep 2026". Not a database error, and no offer to increase a quantity
- [ ] A duplicate whose earlier batch is `pulled` or `sold` is accepted, not blocked
- [ ] After a successful add the form resets to the barcode field, ready for the next scan
- [ ] Nothing is held in browser state between entries — the laptop can sleep mid-session
- [ ] Date entry accepts a fast typed date; never renders or parses US format
- [ ] Works with no category and no photo. Neither ever blocks the add

Notes: this is the one screen worth being fussy about. Count the keystrokes from scan to saved
and say what the number is. If it's more than "scan, type date, Enter", explain why.

## 3. Inline categories `[ ]`

SPEC §3 "Categories grow themselves". Part of the add path — build it right after §2, not before.

- [ ] The category input suggests existing categories as you type, so people pick over invent
- [ ] Typing a new name creates it, attached to the product, with `created_by` set
- [ ] Matching is case-insensitive: typing "energy drinks" finds "Energy Drinks"
- [ ] Creating a case-variant duplicate is impossible and doesn't surface a database error
- [ ] Leaving it blank is normal and never warned about
- [ ] Setting a category on a product applies to every batch of that barcode, past and future
- [ ] No 'Uncategorised' option in the list. Blank means blank
- [ ] No bulk-categorisation screen. That was considered and dropped

## 4. Home screen, finished `[x]`

SPEC §3.2. Already built and under test. Revisit only for the category filter.

- [x] Overdue first, then due within the window
- [x] Window read from `expiry_window_days`, not hard-coded
- [x] Overdue is a normal state, presented without alarm
- [x] Fixed-size placeholder where a photo is missing
- [ ] Filter by category, including a filter for uncategorised
- [ ] Each row links to the product detail screen (blocked on item 6)

## 5. Photos `[ ]`

SPEC §5. Optional, backfilling, attached to the product.

- [ ] Capture from iPad camera or laptop webcam, or upload a file
- [ ] Resized in the browser before upload — a 4 MB original never crosses the shop WiFi
- [ ] Server: Pillow, max 800px long edge, JPEG q72, EXIF stripped, under 80 KB
- [ ] Saved to `data/photos/`, filename keyed to the barcode, path stored on the product
- [ ] Adding a photo makes it appear on batches recorded months ago
- [ ] Replacing a photo doesn't orphan the old file
- [ ] Lists do not reflow when a photo arrives
- [ ] A product with no photo is normal everywhere it appears
- [ ] `scripts/check_db.py` still passes its "every referenced photo exists on disk" check

Notes: check what the compressed size actually is on ten real products and report it. The 57 MB
projection in SPEC §5 assumes 50–70 KB each.

## 6. Product list and detail `[ ]`

SPEC §3.4, §3.5.

- [ ] Search by name or barcode, case-insensitive and whitespace-tolerant
- [ ] Searching "cool ridge" finds `C/RIDGE WATER 1L` — or explain honestly why it can't
- [ ] Trailing whitespace and curly apostrophes in stored names don't break search
- [ ] Filter by category, sort by soonest expiry
- [ ] Detail shows the photo, every batch for that barcode, and its history
- [ ] Resolve a batch — discounted, pulled, sold — recording `resolved_by` and `resolved_at`
- [ ] Nothing is hard-deleted, so waste stays reviewable
- [ ] Fast with 952 products on an iPad over shop WiFi

Notes: the messy names are in `docs/DATA-NOTES.md`. Don't clean them in the database — staff
recognise them as they are. Fix the search, not the data.

## 7. Weekly discount sheet `[ ]`

SPEC §4. The printable. Staff walk the aisles with it on the weekend.

- [ ] Every batch expiring in the next 7 days, range adjustable before printing
- [ ] Grouped by category, sorted by date within each group
- [ ] One line per item: tick box, name, expiry date, barcode, blank column for the price
- [ ] Clean A4 print CSS — no nav, no heavy colour, no toner-eating backgrounds
- [ ] Print preview at A4 actually fits; check the page count for a realistic week

## 8. Settings `[ ]`

SPEC §3.7. Open to everyone — there are no roles.

- [ ] Add and rename categories
- [ ] Add staff and reset PINs
- [ ] Run a backup on demand and show when the last one ran
- [ ] Edit `expiry_window_days`
- [ ] No admin tier, no manager PIN, no gated features

---

## After the screens

**HTTPS + iPad certificates** (SPEC §1) — week 3. `start.bat` already switches automatically when
`certs/` exists; this is mkcert plus about two minutes per iPad, not a code change.

**First real weekend scan session with staff** — week 3. The point of the whole schedule.

**Fixes from real use** — week 4. Keep it empty. The first staff session always surfaces
something.

**Excel export** — week 4, deliberately deferred. The startup backup already protects the data.

---

## Not being built

Recorded here so it doesn't get re-proposed.

- Bulk categorisation screen — categories grow through normal scanning
- Quantity per batch — column exists at 1 and hidden, pending the manager's answer
- Shelf location — considered and rejected, it slows entry down
- Roles or an admin tier — ~10 staff, one shop
- Email or push alerts — home screen plus the printed sheet
- Multi-band expiry thresholds — one 7-day window
