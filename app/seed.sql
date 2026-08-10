-- Starting categories and settings.
--
-- CATEGORIES ARE A PLACEHOLDER. Mohit is confirming the real list with the
-- manager. Replace this block with the agreed list before go-live — these are
-- only a guess based on the 952 products in the beep export, and are here so
-- the app has something to work with during development.

INSERT OR IGNORE INTO categories (name, sort_order) VALUES
    ('Energy Drinks',             10),
    ('Soft Drinks',               20),
    ('Water',                     30),
    ('Sports Drinks',             40),
    ('Juice & Iced Tea',          50),
    ('Milk & Dairy',              60),
    ('Coffee & Tea',              70),
    ('Chocolate & Confectionery', 80),
    ('Chips & Snacks',            90),
    ('Biscuits & Bakery',        100),
    ('Ice Cream & Frozen',       110),
    ('Grocery & Pantry',         120),
    ('Health & Pharmacy',        130),
    ('Household & Automotive',   140),
    ('Uncategorised',            999);

-- One window, seven days. Anything expiring within it is "due"; everything
-- else is just upcoming. Drives both the home screen and the weekly print.
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('shop_name',          'BP Tecoma'),
    ('expiry_window_days', '7'),
    ('image_max_px',       '800'),
    ('image_quality',      '72'),
    ('backup_keep_days',   '7');
