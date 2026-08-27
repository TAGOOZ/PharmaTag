-- PharmaTag core twin of alembic 016_day_totals_catalog.py (S3.2, ticket #24)
-- Drift backfill: day_totals report + day_profit window widening.
-- Uses INSERT OR IGNORE / conditional UPDATE so existing twin DBs upgrade cleanly
-- and fresh DBs get the full catalog. Mirrors alembic 016 exactly.
-- NOTE: lexical order is 016_day < 016_sales (alembic 018-021 coalesced as
-- 016_sales_reports_catalog.sql) but catalog seeds are set semantics
-- (INSERT OR IGNORE) so final report_catalog converges regardless of order.

INSERT OR IGNORE INTO report_catalog (code, category, title_ar, title_en, params, paper, sort) VALUES
    ('day_totals', 'money', 'الإجماليات اليومية', 'Day Totals', '["date_from", "date_to"]', 'A4', 25);

UPDATE report_catalog SET params = '["datee", "date_from", "date_to"]' WHERE code = 'day_profit';
