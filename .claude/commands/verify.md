---
description: Run every check — tests against a temp database, then the real one
---

Verify the current state of the project. Two layers, both required — the tests prove the app
renders and the rules hold, `check_db.py` proves the shop's actual data is sound.

## 1. Tests

```
pytest
```

Runs against a temporary database built from `app/schema.sql`. Never touches `data/tecoma.db`.
If pytest isn't installed: `pip install -r requirements-dev.txt`.

## 2. The real database

```
python scripts/check_db.py
```

## 3. Clean-slate rebuild — only when the schema or the importer changed

```
python scripts/init_db.py --reset
python scripts/import_beep.py data/imports/beep_2026-08-10.xlsx
python scripts/check_db.py --expect-import
```

## 4. Look at it

For any change touching a screen, start the app and load the page. A passing suite does not mean
the layout is usable, and the add path is used hundreds of times a week.

```
uvicorn app.main:app --port 8000
curl -s localhost:8000 | head -40
```

## Rules

- **A failing check is a real failure.** Read it, find the cause, fix the cause. Do not weaken a
  check or delete a test to reach green.
- If a design decision genuinely changed, say so explicitly and ask before editing the check or
  the test. Those files encode the locked decisions in `CLAUDE.md`.
- Report which checks passed and failed, and say plainly what you did not verify.
