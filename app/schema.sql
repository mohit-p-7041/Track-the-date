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

CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 100,
    active     INTEGER NOT NULL DEFAULT 1
);

-- ------------------------------------------------------------- products
-- One row per barcode. Name, category and photo live here so they are
-- stored once, not repeated for every expiry date.

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    barcode     TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    image_path  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL
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
    status      TEXT    NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'discounted', 'pulled', 'sold')),
    added_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TEXT
);

-- THE DUPLICATION GUARD.
-- A product cannot have two live batches with the same expiry date. The app
-- catches this before insert and offers "add to quantity" instead; this index
-- is the backstop so it can never happen by another route.
-- Resolved rows (pulled/sold) are excluded so history can repeat a date.
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
