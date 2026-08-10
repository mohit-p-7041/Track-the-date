---
description: Build one feature from SPEC.md, properly
argument-hint: [which feature]
---

Build this feature: $ARGUMENTS

Before writing code:
1. Read the relevant section of `SPEC.md` and the locked decisions in `CLAUDE.md`.
2. Look at `docs/reference/` — screenshots of the old app the staff already know.
3. Tell me your plan and wait for me to confirm it. Do not start coding yet.

While building:
- Plain HTML/CSS/vanilla JS. No framework, no build step, no CDN links.
- Optimise the add path above all else. No animation.
- Use the real data — 952 products and 2340 batches are already loaded.

After building:
- Run `python scripts/check_db.py` and report the result.
- Start the app and confirm the page actually renders before telling me it works.
- Tell me what you did NOT do, and anything you were unsure about.
