# Backlog

What to build, in order. One item per session — `/feature <item>`.

The order is forced by dependency, not preference. Login comes first because every write records
who did it, and building the add path before there's a signed-in user means either faking
`added_by` or retrofitting it through every route later.

Each item lists **acceptance criteria**. They are written to be testable: each one should become
a test in `tests/`, and a feature isn't done until a broken version of it would go red.

Status: `[ ]` not started · `[~]` in progress · `[x]` done, verified

---

## 1. PIN login `[x]`

SPEC §3.1, §2 Accountability. Blocks everything else.

Big number pad. Pick your name from a list, type four digits. Signed-in name is available to
every route so writes can record it.

- [x] `GET /login` lists active staff and renders a numeric keypad
- [x] Correct PIN sets a signed session cookie and redirects to `/`
- [x] Wrong PIN re-renders with a plain message and does not say which part was wrong
- [x] A request with no session redirects to `/login`, except `/login` and `/static/*`
- [x] The signed-in user's id is reachable from any route without re-querying the session
- [x] `GET /logout` clears the session
- [x] Keypad is usable one-handed on an iPad — big targets, no keyboard needed
- [x] No lockout, no complexity rules, no roles. PINs are accountability, not security

Notes: `itsdangerous` is already in `requirements.txt` for the signed cookie. `app/security.py`
already does the hashing.

Two accounts came across in the import — `BP TECOMA` and `sar ob` — and **both PINs are the
placeholder `1234`** (`import_beep.py` line 42). That's fine for building against, but the real
names and PINs have to be set before the first staff session on day 5. Staff management is
item 8; if login lands well before that, a one-off `scripts/add_user.py` is enough.

## 2. Scan & add `[x]`

SPEC §3.3. **The feature the whole app exists for.** Used hundreds of times a week.

One field takes a barcode. Known barcode fills in the rest and jumps to the date. Unknown barcode
opens a short new-product form. Submit writes immediately.

- [x] `GET /scan` puts the cursor in the barcode field on load, with no click required
- [x] A USB scanner gun's trailing Enter submits the lookup — no mouse anywhere in the path
- [x] Known barcode: name and category shown read-only, focus lands on the date field
- [x] Unknown barcode: name field appears, category optional, date required
- [x] Submitting writes one batch with `added_by` set to the signed-in user
- [x] **Duplicate: the app catches it before insert** and says "Already tracked — expires
      14 Sep 2026". Not a database error, and no offer to increase a quantity
- [x] A duplicate whose earlier batch is `pulled` or `sold` is accepted, not blocked
- [x] After a successful add the form resets to the barcode field, ready for the next scan
- [x] Nothing is held in browser state between entries — the laptop can sleep mid-session
- [x] Date entry accepts a fast typed date; never renders or parses US format
- [x] Works with no category and no photo. Neither ever blocks the add

Notes: this is the one screen worth being fussy about. Count the keystrokes from scan to saved
and say what the number is. If it's more than "scan, type date, Enter", explain why.

**Counted, for a barcode the shop already knows: scan, type date, Enter.** The gun's own trailing
Enter submits the lookup, the date field is focused when that page arrives, and Enter in it
submits the add. No mouse, and nothing to confirm afterwards. An unknown barcode costs a name and
a Tab on top of that.

The date field is `<input type="date">`, which posts ISO regardless of how it displays — so a US
date cannot be parsed even by accident. On an en-AU machine it shows `dd/mm/yyyy` and takes
`14092026` straight from the keyboard.

A year outside today −1 to today +10 is refused with "Check the year on that date." A mistyped
year is silent otherwise, and it poisons the due list for years.

**Camera scanning in the aisles is built** — iteration 2 item 3. A "Scan with camera" button on
the barcode step, revealed only where `getUserMedia` exists, which means the laptop today and the
iPads once the certificates are on. A decode fills the same field the gun types into and submits
the same form, so there is one route, one lookup and one duplicate check however the barcode
arrived.

- [x] The button is absent where a camera cannot be opened, and the gun path is unaffected
- [x] A decoded barcode takes the ordinary path, duplicate rule included
- [x] ZXing is vendored in `app/static/vendor/`, pinned by SHA-256, with no external request
- [x] The counter flow is unchanged: scan, type date, Enter

ZXing is **not** loaded up front. It is 336 KB and the gun path must not pay for a feature it
never uses, so `scanner.js` injects it on the first tap of the button. Someone scanning at the
counter downloads nothing extra.

Decoding is restricted to EAN-13, EAN-8, UPC-A, UPC-E and CODE-128. Leaving QR and Data Matrix on
makes every frame slower and invites a misread off the printing on a packet.

## 3. Inline categories `[x]`

SPEC §3 "Categories grow themselves". Part of the add path — build it right after §2, not before.

- [x] The category input suggests existing categories as you type, so people pick over invent
- [x] Typing a new name creates it, attached to the product, with `created_by` set
- [x] Matching is case-insensitive: typing "energy drinks" finds "Energy Drinks"
- [x] Creating a case-variant duplicate is impossible and doesn't surface a database error
- [x] Leaving it blank is normal and never warned about
- [x] Setting a category on a product applies to every batch of that barcode, past and future
- [x] No 'Uncategorised' option in the list. Blank means blank
- [x] No bulk-categorisation screen. That was considered and dropped

## 4. Home screen, finished `[x]`

SPEC §3.2. Already built and under test. Revisit only for the category filter.

- [x] Overdue first, then due within the window
- [x] Window read from `expiry_window_days`, not hard-coded
- [x] Overdue is a normal state, presented without alarm
- [x] Fixed-size placeholder where a photo is missing
- [x] Filter by category, including a filter for uncategorised
- [x] Each row links to the product detail screen (blocked on item 6)

## 5. Photos `[x]`

SPEC §5. Optional, backfilling, attached to the product.

- [x] Capture from iPad camera or laptop webcam, or upload a file
- [x] Resized in the browser before upload — a 4 MB original never crosses the shop WiFi
- [x] Server: Pillow, max 800px long edge, JPEG q72, EXIF stripped, under 80 KB
- [x] Saved to `data/photos/`, filename keyed to the barcode, path stored on the product
- [x] Adding a photo makes it appear on batches recorded months ago
- [x] Replacing a photo doesn't orphan the old file
- [x] Lists do not reflow when a photo arrives
- [x] A product with no photo is normal everywhere it appears
- [x] `scripts/check_db.py` still passes its "every referenced photo exists on disk" check

Notes: check what the compressed size actually is on ten real products and report it. The 57 MB
projection in SPEC §5 assumes 50–70 KB each.

**Measured, with the caveat that there are no shop photos yet.** Run over the ten images in
`docs/reference/` the pipeline produces 9–26 KB each, mean 17.6 KB — but those are screenshots,
which compress far better than photographs. A synthetic worst case (4032×3024 of pure random
noise, which no camera produces) lands at 61.6 KB, so **the under-80 KB criterion holds for any
input**, and the real figure will sit between the two. Re-measure on ten actual shop photos after
the first weekend session; SPEC §5's 50–70 KB is still the right planning number until then.

The camera button uses `getUserMedia`, which browsers only allow in a secure context. That means
the laptop on `localhost` today, and the iPads after the mkcert step — the button is absent where
it could not work. On an iPad the file input already offers Take Photo, so nothing is missing
there in the meantime.

## 6. Product list and detail `[x]`

SPEC §3.4, §3.5.

- [x] Search by name or barcode, case-insensitive and whitespace-tolerant
- [x] Searching "cool ridge" finds `C/RIDGE WATER 1L` — or explain honestly why it can't
- [x] Trailing whitespace and curly apostrophes in stored names don't break search
- [x] Filter by category, sort by soonest expiry
- [x] Detail shows the photo, every batch for that barcode, and its history
- [x] Resolve a batch — discounted, pulled, sold — recording `resolved_by` and `resolved_at`
- [x] Nothing is hard-deleted, so waste stays reviewable
- [x] Fast with 952 products on an iPad over shop WiFi

Notes: the messy names are in `docs/DATA-NOTES.md`. Don't clean them in the database — staff
recognise them as they are. Fix the search, not the data.

**How "cool ridge" finds `C/RIDGE WATER 1L`:** it scores a point per word matched, in the name or
the barcode, and shows everything scoring at least one, best first. An all-words-must-match search
would drop that row entirely, because the shop's abbreviation is not derivable from "cool". On the
real data the query returns 23 products, the twenty-odd properly spelled ones first and
`C/RIDGE WATER 1L` among them. Curly apostrophes are normalised on both sides, so "arnott's" and
"arnott’s" behave the same.

The list shows the 100 soonest by default with a link to the rest: 952 rows is 477 KB of HTML,
which is fine on the laptop and slow on an old iPad. Both render in under 20 ms server-side.

**Renaming a product is not built.** The names are ugly on purpose — staff recognise them — and
"tidy the names" is exactly the change CLAUDE.md warns against, so it wants a deliberate decision
rather than a text box that appeared by itself.

## 7. Weekly discount sheet `[x]`

SPEC §4. The printable. Staff walk the aisles with it on the weekend.

- [x] Every batch expiring in the next 7 days, range adjustable before printing
- [x] Grouped by category, sorted by date within each group
- [x] One line per item: tick box, name, expiry date, barcode, blank column for the price
- [x] Clean A4 print CSS — no nav, no heavy colour, no toner-eating backgrounds
- [x] Print preview at A4 actually fits; check the page count for a realistic week

Notes: printed to PDF at A4 and counted — **a realistic week (69 items on 11 Aug) is two pages**,
about 35 lines each. It shows the same rows as the home screen, past-date ones included and
marked "(past)", because two definitions of "due" would eventually disagree and the shelf would
follow the wrong one.

## 8. Settings `[x]`

SPEC §3.7. Open to everyone — there are no roles.

- [x] Add and rename categories
- [x] Add staff and reset PINs
- [x] Run a backup on demand and show when the last one ran
- [x] Edit `expiry_window_days`
- [x] No admin tier, no manager PIN, no gated features
- [x] Rename a staff member, with case-insensitive names so two Sarahs can't both exist
- [x] Take somebody off the sign-in list, and put them back
- [x] The list can never be emptied — the last active account refuses
- [x] An account taken off the list stops being able to write, including from a session
      already signed in as it
- [x] Export every recorded date to Excel

Notes: **the two imported accounts still have the placeholder PIN `1234`.** Set the real names and
PINs on this screen before the first staff session — that is now a job for the shop, not a script.
`scripts/add_user.py "Name" 1234` still exists for a fresh database where nobody can sign in yet.
The procedure is `docs/STAFF-SETUP.md`.

Renaming and taking somebody off the list are both here now. They are not the same operation and
the screen says so: renaming carries every entry that account ever made, which is right for a
person under a tidier name and wrong for `BP TECOMA`, whose 2,290 entries are the old app's
shared shop login. Each row shows its entry count so that number is visible before anyone
renames anything.

---

## After the screens

Every item above is built. What is left is the five-day run-up to the shop using it — see
SPEC §9, and `docs/ITERATION-1.md` for what to pick up next and in what order.

**Real staff names and PINs** — day 2, and the one that cannot slip. Both imported accounts are
still on the placeholder `1234`, so until this is done the audit trail says `BP TECOMA` for
everybody, which is the whole point of having PINs.

*The screen half is built* — rename, take off the list, put back, and a retired account can no
longer write. What is left is the shop-floor half, which needs the actual staff list and cannot
be done from here: **follow `docs/STAFF-SETUP.md` at the laptop.** Roughly twenty minutes.

**HTTPS + iPad certificates** (SPEC §1) — day 2. `start.bat` already switches automatically when
`certs/` exists; this is mkcert plus about two minutes per iPad, not a code change.

*Confirmed, not assumed:* the app does serve over HTTPS with the flags `start.bat` passes (TLS
1.3, every screen), `show_address.py` takes the arguments it is handed, and the session cookie is
correctly not `Secure` so http keeps working. The procedure is `docs/HTTPS-SETUP.md`. The mkcert
run and the iPad profile install need the shop hardware.

**Camera scanning in the aisles** — *built*. ZXing 0.21.3 vendored into `app/static/vendor/`, no
CDN, loaded on demand. Verified on the laptop: the vendored decoder reads a real EAN-13 from the
shop's own data, and a decode fills the barcode field and submits the ordinary lookup. **Not yet
verified on an iPad** — that needs the certificates, and it is the one thing left to confirm in
person, along with holding a real barcode in front of a real camera.

*Bug found and fixed 12 Aug*, serving the app over plain http on the LAN to see what an iPad
would get. The camera button is shipped `hidden` and revealed by JavaScript only where
`getUserMedia` exists — but the browser's own rule is just `[hidden] { display: none }`, and
`.btn` sets `display: inline-block`, which outranks it. So on every device without a camera the
button was drawn anyway, and tapping it did nothing at all: scanner.js returns before it binds a
click. `app.css` now re-asserts `[hidden]` with `!important`, and `test_the_hidden_attribute_
actually_hides` keeps it there. Worth knowing that the acceptance test for the certificates —
"the Camera button appears" — was reading a button that appeared regardless.

**Deploy to the shop laptop, and training notes** — day 3.

**Excel export** — *built*. A button on the settings screen, and `python scripts/export_xlsx.py`
on the laptop; both go through the same code. One sheet, one row per batch, resolved ones
included so waste can be reviewed — filter the Status column to get back to the shelf. Live rows
sort first, because by date alone the shop's 583 pulled rows sit above everything that still
matters.

*Verified against the real data:* 2,340 rows, 139 KB, served in under 200 ms. The things that
would have gone wrong quietly all hold — `0000001051117` keeps its leading zeros instead of
becoming 1.05E+06, the scanner's `]C1…` codes and the QR-URL barcodes survive, expiry is a real
Excel date so it can never render US-style, timestamps read in shop time, and the Korean product
name comes through. It stays a copy for reading: exporting writes nothing.

**Dry run at the counter** — day 4. Gun plus one iPad, on the real laptop, before staff see it.

**First real weekend scan session with staff** — day 5, Sat 15 Aug. The point of the whole
schedule. Keep the day otherwise empty; the first session always surfaces something.

---

## Not being built

Recorded here so it doesn't get re-proposed.

- Bulk categorisation screen — categories grow through normal scanning
- Quantity per batch — column exists at 1 and hidden, pending the manager's answer
- Shelf location — considered and rejected, it slows entry down
- Roles or an admin tier — ~10 staff, one shop
- Email or push alerts — home screen plus the printed sheet
- Multi-band expiry thresholds — one 7-day window
