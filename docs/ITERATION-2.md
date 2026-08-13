# Iteration 2 — 13 August 2026

What the second working session did, and the punch list that came out of the first real iPad
test. Read this and `docs/ITERATION-1.md` before starting iteration 3.

---

## What this session finished

**HTTPS works, and camera scanning is verified on a real iPad.** That was the last thing in
iteration 1 that could only be confirmed in person, and it is now done.

| | |
|---|---|
| `main` | `d8848da` — PR #3 merged: Excel export + the `[hidden]` camera-button fix |
| Tests | 166 passing (`pytest`) |
| Data checks | 12 passing (`scripts/check_db.py`) against the real database |
| Certificates | `mkcert -install` run, LAN cert issued for `192.168.1.119`, trusted on the iPad |
| Camera | **Verified end to end** — button appears, opens, decodes a real barcode, adds the date |
| Real data | untouched — the LAN test server ran against a copy |

The iPad reads `https://192.168.1.119:8443`, signs in, and every screen works. The camera button
now appears *because* the origin is secure, which is what it was always meant to prove.

Worth recording for the shop laptop: the mkcert profile install on iPadOS is
**Settings → General → VPN & Device Management**, not the "Profile Downloaded" row that older
guides describe. AirDrop was unreliable; serving `rootCA.pem` over plain HTTP from the Mac and
opening the URL in Safari worked first time. Add this to `docs/HTTPS-SETUP.md` before the laptop
deploy.

---

## Punch list from the iPad test

Five issues, from Mohit using the app on the iPad on 13 Aug. Ordered by what would hurt the
first staff session most, not by the order they were reported.

### 1. The barcode field accepts anything typed into it `[ ]`

Typing words into the barcode field creates a product. Nothing rejects it, and because products
are never deleted that junk row is permanent.

**Decided 13 Aug: digits only, 6–18 of them**, after stripping a leading AIM identifier (`]` plus
two characters), which is the gun announcing the symbology rather than part of the code. Nothing
else is accepted — no URLs, no words, no whitespace.

An earlier draft of this item argued for a looser "any shape a scanner can produce" rule, to
avoid invalidating the nine non-numeric barcodes in the real data. Checking what those rows
actually are settled it the other way:

| | |
|---|---|
| 5 of the 9 | **already exist a second time under their proper numeric barcode** — Bundaberg ginger beer, bundaberg peach, Cadbury Marvellous Creations, sam's fruit lunch, golden gay time. Someone scanned the marketing QR instead of the barcode and created a duplicate product |
| 4 of the 9 | have no numeric twin yet — magnum almond, In A Biscuit, Kit Kat Neapolitan 42g, Bundaberg traditional lemonade |
| plus 1 numeric | `1930083008300830083008300830083008300830` — 40 digits, `1930083` repeating. A gun misfire |

So they are not a category of valid barcode to protect. They are the same data-entry accident
this item exists to prevent, already in the database. **10 products carrying 15 batches** fail
the rule — 1% of the catalogue — and the four without a twin come back the next time somebody
scans the actual barcode on the packet.

Build it as: normalise (trim, strip a leading `]xx`), validate in `app/catalogue.py` with a plain
message, and a `CHECK` constraint in `app/schema.sql` as the backstop, the same way
`idx_batches_unique_live` backstops the duplicate rule. SQLite cannot add a constraint to an
existing table, so this is a table rebuild in a migration — which must clear the 10 offending
products first, or the rebuild fails on them. Back up and take an Excel export before running it.

### 2. The discount sheet is full of past-date items `[ ]`

The printed sheet is what staff carry round the aisles on Saturday, and it currently opens with
83 rows marked `(past)` before reaching anything expiring this week. `app/routes/sheet.py` has
a cutoff but **no lower bound** — `WHERE b.expiry_date <= ?` — so every unresolved past date
since the import is on the page.

Fix: bound the range at both ends, `>= today AND <= cutoff`.

**This deliberately amends a decision from iteration 1**, which said the sheet shows exactly
what the home screen shows so that two definitions of "due" cannot disagree. The amendment is
that they are not two definitions of the same thing:

- The **Due screen** is a worklist — everything unresolved, past included, because a past-date
  item is the most urgent thing there is and staff clear that backlog as they go.
- The **discount sheet** is a pricing list — things still sellable that want a sticker this
  week. A past-date item is not discounted, it is pulled off the shelf.

One definition of "due" survives; the sheet is a narrower question asked of it. Cheapest fix on
this list and the most visible on Saturday.

### 3. Swipe to act on a batch, and drop two of the four statuses `[ ]`

The biggest change on the list, and the one that touches the most files. Two parts.

**Statuses go from four to two.** `active` and `discounted` stay; `pulled` and `sold` are
removed. A batch now ends one of two ways — it gets a discount sticker, or it is deleted, really
deleted. The reasoning, from the shop rather than from the design:

- Staff physically remove expired stock from the aisle, and want the same action available in the
  app in one gesture. Marking something `pulled` and keeping it forever is bookkeeping nobody
  asked for.
- That history only grows. Over years, on a shop laptop where nobody will prune it, it is the
  thing that eventually makes the app slow and the exports unreadable.
- The data agrees it was never wanted: **1757 `active`, 583 `pulled` (all from the import), zero
  `sold`, zero `discounted`.** Two of the four statuses have never been used once.

The 583 imported `pulled` rows are unreachable under the new model and go with it. **Take an
Excel export first and keep the file** — that is exactly what it was built for, and it is the
only copy of that history once the migration runs.

**Swipe on the Due screen**, and the directions are set:

| Gesture | Action |
|---|---|
| Right → Left | **Delete** the batch |
| Left → Right | Mark **discounted** |

Deleting warns only when the item is still good:

- **Already past its date** — deleted immediately, no confirmation. Staff are at the shelf with
  the item in their hand; asking is friction for the most common case there is.
- **Not yet expired** — asks first: *"This expires in 4 days. Delete it?"* Confirm, then it goes.

Notes for building it: vanilla JS, no framework, and no `confirm()` dialog — reveal the
confirmation inline in the row. The laptop has no touchscreen and uses the same screen, so both
actions need a non-swipe path as well. `idx_batches_unique_live` gets simpler as a result: with
no resolved-but-present rows, a date is free again as soon as the batch is deleted.

Blast radius, checked: `app/routes/products.py`, `app/schema.sql`, `app/templates/product.html`,
`app/templates/settings.html`, `scripts/check_db.py`, `scripts/export_xlsx.py`,
`scripts/import_beep.py`, and four files under `tests/`. Not a small change — see the schedule
note at the end.

### 4. Product detail should have an edit toggle `[ ]`

The product screen always shows its editing controls — a category picker with a Save, a photo
picker with a Save — whether or not anyone is editing. After saving a category the picker stays
on screen showing the value again, so it reads like unfinished work rather than a saved fact.

Wanted: the product screen shows the product. One **Edit** toggle reveals everything editable
about it in one form — name, category, photo — and hides again on save.

**This settles a question iteration 1 deliberately left open.** Renaming a product was recorded
as "not built — wants a deliberate decision, not a text box that appeared by itself". This is
that decision, made by the shop: **staff can rename a product.** The messy imported names stay
as they are by default because staff recognise them; nothing renames automatically and there is
no bulk tidy-up. But a name typed wrong at 7am on a Saturday can be corrected.

### 5. Edit a batch's expiry date `[ ]`

A date saved wrong currently lives forever. Item 3 makes delete-and-rescan possible, which is
enough to recover, but editing keeps the history — who first recorded it, and when — where a
delete throws that away.

Assessed against the logic flow, and **it does not break it**, provided:

- the edit goes through the same duplicate check as an add, in `app/catalogue.py`, so moving a
  date onto one the product already has live is refused the same way — and
  `idx_batches_unique_live` still backstops it, and
- the change is attributed. There are no `edited_by` / `edited_at` columns yet; add them, because
  "every write that a person initiates records who" is the point of having PINs at all.

Lower priority than item 3: delete-and-rescan already recovers from the mistake, so this buys
tidiness and a better audit trail rather than a capability that is missing.

---

## Iteration 3 — what to build, in order

Two sessions of about three hours, Thu 13 and Fri 14 Aug, before the first staff session on
**Sat 15 Aug**. The order is by risk to that Saturday.

| | Item | Why here | Est. |
|---|---|---|---|
| 1 | Sheet date range (item 2) | Cheapest fix, and the sheet is the thing staff physically carry | 20 min |
| 2 | Barcode rule + migration (item 1) | Junk products are permanent; every hour of scanning adds more | 1½ hr |
| 3 | Statuses + swipe (item 3) | The first session *will* produce mis-scans, and there is no undo today | 2½ hr |
| 4 | Edit toggle + rename (item 4) | Clutter on the busiest screen after Scan | 1 hr |
| 5 | Edit expiry date (item 5) | Only if Friday has room; item 3 already covers recovery | 1 hr |

**That is about six and a half hours against six available, and items 2 and 3 both carry a
migration against real data.** If Friday runs short, item 5 drops first and item 4 second — both
are comfort rather than correctness. Items 1–3 are the ones that change what staff can do wrong
on Saturday, and item 3 is the one to protect time for.

Both migrations delete real rows. Before either: run `scripts/backup.py`, **and** take the Excel
export and keep the file somewhere off the laptop. Then run against a copy of the database and
check the numbers before touching `data/tecoma.db`.

Then, unchanged from iteration 1 and still outstanding:

- **Deploy to the shop laptop** — `git clone`, `pip install -r requirements.txt`, run the
  importer there rather than copying `data/tecoma.db`. Expect `All 16 checks passed` from
  `check_db.py --expect-import`. Generate the laptop's own mkcert certificate for *its* IP, and
  reserve that IP on the router or the iPad bookmarks break between sessions.
- **Real staff names and PINs** — settled: staff add themselves on the Settings screen at the
  laptop during the first session. Both imported accounts are still on the placeholder `1234`.
- **Training notes** — one printed page by the counter.
- **Dry run at the counter** — the gun and one iPad, twenty real items, timed. About five
  seconds an item.

Each item is a `/feature`, committed on green, one at a time — iteration 1's note about going
back to one item per session still applies, and applies more the closer Saturday gets.
