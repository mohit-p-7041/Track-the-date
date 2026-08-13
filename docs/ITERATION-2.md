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
are never deleted (see item 5) that junk row is permanent.

**But "numbers only" is the wrong rule, and would break real data.** Nine of the shop's 952
products have non-numeric barcodes, and all nine are legitimate:

| | |
|---|---|
| `]C10118721274620198`, `]C10119300830022554` | the scanner gun's own AIM prefix for GS1-128 |
| 6 × `https://…` (Bundaberg ×3, Nestlé, qrco.de ×2) | QR codes printed on the packaging |
| `www.ausbev.com.au` | the same, without the scheme |

A digits-only constraint makes those products unscannable in the aisle and fails to apply to the
existing database at all. The rule wanted is **"a shape a scanner can produce"**, not "digits":

- all digits, 6–14 long — covers 940 of 952, and
- starts with `]` — the AIM identifier the gun emits, or
- looks like a URL (`http://`, `https://`, `www.`) — a scanned QR code

and reject anything else, in particular anything containing whitespace. `KinderJoy` typed by
hand fails all three; every real barcode in the database passes.

Enforce it in `app/catalogue.py` so the person gets a plain message, **and** as a `CHECK`
constraint in `app/schema.sql` as the backstop — the same shape as `idx_batches_unique_live`,
which is a database guarantee rather than a promise the app remembers to keep. SQLite cannot add
a constraint to an existing table, so this needs a table rebuild in a migration script, verified
against a copy of the real database first.

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

### 3. Swipe to delete a batch on the Due screen `[ ]`

There is no way to undo a mis-scan. Currently the only route is to resolve it as `pulled`, which
is a lie — it says waste was reviewed when actually the entry never should have existed.

Wanted: swipe a row on the Due screen to delete that batch, removed from the app and from the
database. **The product itself is never deleted**, even when it has no dates left. A product can
have its photo, name and category changed; it cannot be removed.

**This also amends a locked decision**, and the amendment is narrow. `CLAUDE.md` says nothing is
hard-deleted so waste can be reviewed later. That stands for *outcomes* — `discounted`, `sold`
and `pulled` still never delete. It does not stand for *mistakes*: a batch entered in error is
not waste, and keeping it pollutes the waste review with something that never happened. So:

- **Resolve** — a real outcome, recorded, never deleted. Unchanged.
- **Delete** — an entry that should not exist. Actually removed.

Notes for building it: the swipe has to be vanilla JS (no framework, per `CLAUDE.md`) and must
reveal a Delete control that is then tapped, rather than deleting on the swipe itself — one
gesture should not be destructive, and the two-step is the iOS-native pattern anyway. It also
needs a non-touch path, because the laptop has no touchscreen and the same screen is used there.
No JS `confirm()` dialog.

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

| | Item | Why here |
|---|---|---|
| 1 | Sheet date range (item 2) | Cheapest fix, and the sheet is the thing staff physically carry |
| 2 | Barcode shape rule (item 1) | Junk products are permanent; every hour of scanning adds more |
| 3 | Swipe to delete (item 3) | The first session *will* produce mis-scans, and there is no undo today |
| 4 | Edit toggle + rename (item 4) | Clutter on the busiest screen after Scan |
| 5 | Edit expiry date (item 5) | Do it if Friday has room; item 3 already covers recovery |

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
