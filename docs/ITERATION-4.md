# Iteration 4 — 2–3 September 2026

A polish and hardening pass, three weeks after the shop started using the app. No new screens:
everything here is something that was already built behaving badly, and most of it was found by
measuring rather than by anyone reporting it.

> **Where iteration 3 is.** There is no `ITERATION-3.md`. Iteration 3 was the iPad punch list of
> 13 August, and it is recorded inline in `docs/BACKLOG.md` under "After the screens" — all nine
> items, with what each one turned out to be. This file picks up after it.

---

## What started it

Four things noticed while working the shop floor:

1. Coming back from a product dropped you at the top of the products list.
2. The barcode camera did nothing from the home-screen icon on the iPads.
3. Tapping a product photo did not open it.
4. Search made you press a button and wait for a page.

Then, having opened the bonnet, a deliberate audit for the same class of thing: performance,
correctness, what staff see when something fails, and whether a person who has never used it
could.

---

## The performance finding, which was the big one

**Nothing in the app had ever been compressed.** The Due screen is the first page of every
session and renders every live batch — 186 past date, 232 inside the window, 100 beyond it — and
all of it crossed the WiFi uncompressed.

| screen | uncompressed | on the wire | saved |
|---|---:|---:|---:|
| **Due (home)** | 484,752 B | **19,684 B** | **95.9%** |
| Products (show all) | 536,826 B | 32,124 B | 94.0% |
| Products (first 100) | 61,740 B | 5,107 B | 91.7% |
| Sheet | 20,067 B | 3,055 B | 84.8% |
| app.css | 41,504 B | 13,967 B | 66.3% |

Roughly **2.5 seconds of a weak link** given back before the first row appears. Gzip at level 6,
not the library's default 9 — on this HTML the two are within about a percent of each other and 9
costs several times the CPU on a laptop that is also serving everything else.

**Assets were also re-fetched on every navigation.** `asset_url()` and `photo_url()` have stamped
the file's mtime into every URL since 15 August, so those bytes can never change and the browser
was being made to ask anyway; a 304 saves the body and not the round trip, and on shop WiFi the
round trips are the slow part. A stamped URL is now kept for a year. Anything unstamped gets five
minutes, because the icons and `manifest.json` are referenced by plain path and freezing those
would mean a redrawn icon never reaching a device.

**The server itself was never the problem.** Every screen renders in 2–11 ms against the real 945
products. `photo_url`'s per-row `stat()` costs 0.07 ms. The indexes are right. It was all wire.

---

## The bug that could lose data

`store_upload` caught `OSError`, which covers "that file is not a photograph" and very little
else.

On the scan screen the batch is inserted **before** the photo is processed and the commit that
keeps it is **after**. So anything Pillow raised that was not an `OSError` came out of the route,
the commit never ran, and **the date somebody had just typed correctly was rolled back** — with a
crash on screen instead of the confirmation.

It does not take a malicious file. A solid-colour 20000×12000 PNG is 730 KB on disk, so the 12 MB
limit never sees it coming, and it becomes 240 million pixels the moment Pillow opens it:
`DecompressionBombError`, which is not an `OSError`.

Now caught along with everything else. The contract this function is part of is *a photo must
never block an add*, and that has to mean any failure, not the one that was thought of first.

The refusal reason also used to be discarded at the redirect and replaced with "it was not an
image" — the wrong sentence for a picture that was a perfectly good image and merely too big, and
one that sends somebody looking for the wrong problem. It travels as a code now, with one table
of sentences behind it, so the scan screen and the product screen cannot describe the same
failure differently.

## The bug that gave wrong answers

**Searching for a percent sign returned all 945 products.** `%` and `_` are LIKE's wildcards and
went through unescaped. Never an injection — the value was always bound — but a wrong answer, and
live search made it worse by firing the wildcard halfway through a word.

The shop sells `70% dark chocolate` and `99% sugar free`. Typing `70%` now finds them.

---

## What staff see when something goes wrong

A stale bookmark, or a product another iPad deleted a minute ago, produced
`{"detail":"Not Found"}` on a blank page. On an iPad that reads as the app being broken rather
than a link being out of date.

There is a page now, and it **extends nothing and asks the database for nothing** — an error page
that needs a query in order to say "something went wrong" fails hardest exactly when it is
needed. It carries no nav bar, so it carries its own way back.

Two things this had to not break:

- `current_user` bounces a retired account by raising a **303 with a `Location` header**. A
  handler rendering HTML for every `HTTPException` would have quietly turned that into a page
  saying "303". Anything with a `Location` goes back out as a redirect, and a test holds it shut.
- FastAPI answers a **validation failure itself**, before any of that runs, with a JSON list of
  the fields it could not parse. A validation error is not an `HTTPException`, so it needed its
  own handler or forms would still have leaked `["body","days"]` onto the screen.

---

## Usable by anyone

**The row buttons were 31px tall.** Apple asks for 44. Discount and Delete are the most-tapped
controls in the building — 332 of each on the Due screen — pressed one-handed, walking, holding
stock, and one of the two cannot be undone.

Growing the padding would have fixed the target and cost 13px on every one of 500 rows, so the
buttons keep their size and the **touch area is stretched past them**: 7px above and below turns
31 into 44, measured in a browser, with nothing moving on screen.

Vertically only, and that is the point. There were **five pixels** between Discount and Delete —
not a gap on a thumb — so the hit area does not reach sideways, or Delete's target would sit
under Discount's label. The gap itself is doubled to ten. `test_the_row_buttons_keep_a_thumb_
sized_target` fails if either is undone.

**The signed-in name was under the contrast floor.** `rgba(255,255,255,0.72)` on the green is
4.34:1, under the 4.5 small text is meant to clear, on the one label saying who every write is
recorded against. Now 0.80, which is 4.97:1 and still visibly quieter than the 6.81:1
destinations beside it. The rest of the palette was checked and needs nothing — the espresso on
the sticker's yellow is 10.97:1.

**A shop that had not started was told "nothing due in the next 7 days".** That sentence is
reassurance — all clear, nothing coming up — and on an empty database the truth is the opposite.
Same on Products, where an empty catalogue answered "Nothing matches that." to a question nobody
asked. Both now say what is true and point at the one thing to do next.

---

## The four that started it

- **Scroll position.** The browser restores it for a plain back navigation, but not for the
  redirect after saving an edit and not for a tap on the Products link — the two ways staff
  actually come back. Remembered per list URL now; a *different* list still starts at the top.
- **Photo lightbox.** The stored image is already up to 800px, so tapping the thumbnail opens the
  picture it already loaded. A class toggle rather than a `:target` hash, so closing it does not
  push a history entry or jump a long product screen to the top.
- **The iPad camera.** iOS blocks `getUserMedia` in a standalone home-screen web app on these
  iPads, so the "Scan with camera" button never even appeared — the gate working correctly on a
  browser that lies about what it can do. `apple-mobile-web-app-capable` is `no` now, so the icon
  opens in Safari. The manifest still says `display:standalone`, because the Android scanner
  phone has no such restriction. **An iPad already holding the old icon must remove and re-add
  it** — see `docs/DEVICE-SETUP.md`.
- **Live search.** Filters as you type, against the same `/products` query with `partial=1`
  returning the same rows from the same template — so the scoring, the 100-row cap and its
  show-all link are the server's, unchanged, and there is no second search to keep in step.

---

## Checked, and needing nothing

Recorded so it is not re-investigated:

- **Concurrency is fine for ten staff.** Ten simultaneous adds: all ten written, slowest 101 ms.
  Eight writers all typing the same brand-new category at once produced exactly **one** category
  row with all eight products attached — the race `resolve_category` documents, working. Twelve
  concurrent operations including four heavy Due reads finished in 128 ms. WAL plus
  `synchronous=FULL` plus the 5-second busy timeout is the right shape.
- **No horizontal overflow** on any screen at 375px, and the mobile layout wraps the row buttons
  onto their own line at a comfortable size.
- **The "No staff yet" sign-in screen** already explains itself on a fresh database.
- **`serve.py`'s startup backup** already refuses to raise, whatever happens, so a failed backup
  cannot stop the shop opening the app.
- **The photo route's path-traversal guard** holds.

---

## Left alone deliberately

**The Due screen still builds ~518 rows.** Gzip solved the download; what remains is the parse
and layout cost on an old iPad. Capping it would collide with the locked decision of 16 August —
*nothing live is hidden from the Due screen any more* — so it is not being changed on a guess.
The shop is clearing its past-date backlog, which will move the number on its own; revisit with
real data after that, not before.

---

## Where it stands

326 tests, up from 308, and all 14 `check_db.py` checks. Everything above is covered, and the
photo crash, the compression, both LIKE fixes and the touch-target rule were each confirmed to go
red when the thing they cover is broken.
