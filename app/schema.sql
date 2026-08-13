-- Track the Date — Tecoma
-- SQLite schema. Applied by scripts/init_db.py.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- users
-- There are no roles. Every member of staff can do everything, including
-- adding categories and removing batches. The PIN exists so the audit trail
-- says who did what, not to gate anything off.

CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL UNIQUE,
    pin_hash   TEXT    NOT NULL,
    pin_salt   TEXT    NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ----------------------------------------------------------- categories
-- The list starts empty and grows as staff type categories while scanning.
-- There is no 'Uncategorised' row: products.category_id IS NULL means
-- uncategorised, which is a valid and common state.

CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 100,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Case-insensitive uniqueness. Ten people typing freely will otherwise produce
-- 'Drinks', 'drinks' and 'DRINKS' as three separate categories within a week.
CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_name_nocase
    ON categories(name COLLATE NOCASE);

-- ------------------------------------------------------------- products
-- One row per barcode. Name, category and photo live here so they are
-- stored once, not repeated for every expiry date.
--
-- THE BARCODE RULE, as a backstop.
-- Digits only, 6 to 18 of them. app/catalogue.py checks this first and is
-- where the wording staff read comes from; this constraint is what makes it
-- impossible by another route, the way idx_batches_unique_live is for
-- duplicates. Never drop it.
--
-- A product is never deleted by staff, so a barcode typed as a word would be
-- permanent. `NOT GLOB '*[^0-9]*'` is how SQLite says "every character is a
-- digit" — the length test alone would still admit 'cool ridge water'.
-- The gun's leading AIM identifier (']' plus two characters) is stripped
-- before it ever reaches here; it is transport noise, not a barcode.

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    barcode     TEXT    NOT NULL UNIQUE
                        CHECK (length(barcode) BETWEEN 6 AND 18
                               AND barcode NOT GLOB '*[^0-9]*'),
    name        TEXT    NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    image_path  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    -- No created_by. Dropped 13 Aug: a batch is something somebody did and
    -- carries added_by / resolved_by, but a product is just a fact about a
    -- barcode the shop sells. The column held nothing anyway — 0 rows set.
);

CREATE INDEX IF NOT EXISTS idx_products_name     ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);

-- -------------------------------------------------------------- batches
-- One row per (product, expiry date). This is what the shop actually
-- tracks day to day.
--
-- There is no counting. A second Redbull Zero 250ml is only ever entered if
-- its expiry date differs from one already recorded. `quantity` is reserved
-- for a possible future change and is always 1 — do not surface it in the UI.

CREATE TABLE IF NOT EXISTS batches (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    expiry_date TEXT    NOT NULL,                        -- ISO 'YYYY-MM-DD'
    quantity    INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),  -- reserved, always 1
    note        TEXT,
    -- Two endings, not four. Amended 13 Aug: a batch is 'active' or it is
    -- 'discounted', and anything else that happens to it is a real deletion.
    -- 'pulled' and 'sold' are gone because the shop never used either — 1757
    -- active and 583 pulled arrived from the import, zero sold, zero
    -- discounted — and because a record of every item ever removed only grows,
    -- on a laptop nobody prunes. The Excel export is how history gets kept.
    status      TEXT    NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'discounted')),
    added_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TEXT
);

-- THE DUPLICATION GUARD.
-- A product cannot have two live batches with the same expiry date. The app
-- should catch this before insert and tell the person it is already tracked
-- and when it expires — there are no quantities to add to. This index is the
-- backstop so it can never happen by another route.
--
-- The WHERE clause is historical: it existed to exclude resolved rows so a
-- date could be reused. With only two live statuses left it now matches every
-- row, and that is correct — a batch that ends is deleted, so its date is free
-- again immediately with nothing to exclude. Left partial rather than rebuilt
-- because the two are equivalent here and the clause documents the intent.
CREATE UNIQUE INDEX IF NOT EXISTS idx_batches_unique_live
    ON batches(product_id, expiry_date)
    WHERE status IN ('active', 'discounted');

CREATE INDEX IF NOT EXISTS idx_batches_expiry
    ON batches(expiry_date)
    WHERE status IN ('active', 'discounted');

CREATE INDEX IF NOT EXISTS idx_batches_product ON batches(product_id);

-- ------------------------------------------------------------- settings

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
