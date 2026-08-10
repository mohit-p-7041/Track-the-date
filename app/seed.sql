-- Settings only.
--
-- There are deliberately NO seeded categories. The category list grows as staff
-- scan products and type the category they want; a product with no category is
-- perfectly valid and shows blank. See SPEC.md section 3.

INSERT OR IGNORE INTO settings (key, value) VALUES
    ('shop_name',          'BP Tecoma'),
    ('expiry_window_days', '7'),
    ('image_max_px',       '800'),
    ('image_quality',      '72'),
    ('backup_keep_days',   '7');
