---
description: Build one feature from the backlog, properly
argument-hint: [which feature]
---

Build this feature: $ARGUMENTS

One feature per session. If the backlog item turns out to contain two features, say so and build
the first.

## Before writing code

1. Read the item in `docs/BACKLOG.md` — it lists the acceptance criteria this has to meet.
2. Read the relevant section of `SPEC.md` and the locked decisions in `CLAUDE.md`.
3. Look at `docs/reference/` — screenshots of the old app the staff already know.
4. Confirm the working tree is clean (`git status`), so this feature can be rolled back on its own.
5. Tell me your plan and wait for me to confirm it. Do not start coding yet.

## While building

- Plain HTML/CSS/vanilla JS. No framework, no build step, no CDN links.
- Routes go in `app/routes/`, one module per area. Take the connection with
  `Depends(get_conn)` — never call `connect()` inside a route, or the tests will silently run
  against the shop's real database.
- Optimise the add path above all else. No animation.
- Submit each entry immediately. No multi-step wizards holding state in the browser.
- Use the real data — 952 products and 2340 batches are already loaded.

## After building

- Write a test per acceptance criterion in `tests/`. A feature is not done until a failing
  version of it would be caught.
- Run `/verify` and report the result.
- Start the app, load the page, and confirm it actually renders before telling me it works.
- Tell me what you did NOT do, and anything you were unsure about.
- Tick the item off in `docs/BACKLOG.md`.
