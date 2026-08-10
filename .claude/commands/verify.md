---
description: Run the sanity checks against real data
---

Verify the current state of the project:

1. Run `python scripts/check_db.py` on the working database.
2. If anything fails, read the failing check in `scripts/check_db.py` to see which rule in
   `SPEC.md` it enforces, then fix the cause — do not weaken the check.
3. For a clean-slate test:
   - `python scripts/init_db.py --reset`
   - `python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx`
   - `python scripts/check_db.py --expect-import`

Report which checks passed and failed. If a check fails because a design decision genuinely
changed, say so explicitly and ask before editing the check.
