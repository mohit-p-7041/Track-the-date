-- Starting categories and settings.
-- Edit the category list to match how Tecoma actually walks the shop —
-- these are a first guess based on the 952 products in the beep export.

INSERT OR IGNORE INTO categories (name, sort_order) VALUES
    ('Energy Drinks',            10),
    ('Soft Drinks',              20),
    ('Water',                    30),
    ('Sports Drinks',            40),
    ('Juice & Iced Tea',         50),
    ('Milk & Dairy',             60),
    ('Coffee & Tea',             70),
    ('Chocolate & Confectionery',80),
    ('Chips & Snacks',           90),
    ('Biscuits & Bakery',       100),
    ('Ice Cream & Frozen',      110),
    ('Grocery & Pantry',        120),
    ('Health & Pharmacy',       130),
    ('Household & Automotive',  140),
    ('Uncategorised',           999);

INSERT OR IGNORE INTO settings (key, value) VALUES
    ('shop_name',            'BP Tecoma'),
    ('band_critical_days',   '7'),    -- red on the home screen
    ('band_warning_days',    '14'),   -- amber
    ('band_watch_days',      '30'),   -- yellow
    ('discount_sheet_days',  '7'),    -- default range for the weekly print
    ('image_max_px',         '800'),
    ('image_quality',        '72'),
    ('backup_keep_days',     '7');
