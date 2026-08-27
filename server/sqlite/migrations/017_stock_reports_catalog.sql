-- PharmaTag core twin of alembic 017_stock_reports_catalog.py (S3.3, ticket #25)
-- Drift backfill: four stock report catalog rows. INSERT OR IGNORE for idempotent upgrade.
-- NOTE: lexical order is 017_stock after 017_accounting (alembic 022 coalesced as
-- 017_accounting_reports_catalog.sql) but set semantics keep final catalog correct.

INSERT OR IGNORE INTO report_catalog (code, category, title_ar, title_en, params, paper, sort) VALUES
    ('stock_current', 'stock', 'رصيد الأصناف', 'Current Stock', '[]', 'A4', 50),
    ('stock_movements', 'stock', 'تتبع تغيير الرصيد', 'Drug Movement Track', '["drug_id", "date_from", "date_to"]', 'A4', 60),
    ('stock_expired', 'stock', 'الادوية منتهية الصلاحية', 'Expired / Expiring Stock', '["datee", "horizon_days"]', 'A4', 70),
    ('stock_needs', 'stock', 'احتياجات الطلب (الحد الأدنى)', 'Order Needs (Minimum-Based)', '[]', 'A4', 80);
