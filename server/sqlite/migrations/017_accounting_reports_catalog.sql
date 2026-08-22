-- PharmaTag core twin of alembic 022 (S3.5, ticket #27)
-- Accounting report catalog rows: ledger by account + VAT summary
-- (Egyptian Form 10 mirror). Engines live in app/reports/views.py.

INSERT INTO report_catalog (code, category, title_ar, title_en, params, paper, sort) VALUES
    ('ledger_account', 'accounting', 'دفتر الأستاذ لحساب', 'Ledger by Account', '["account_code", "month", "year", "date_from", "date_to"]', 'A4', 130),
    ('vat_summary', 'accounting', 'ملخص ضريبة القيمة المضافة', 'VAT Summary (Form 10)', '["month", "year", "date_from", "date_to"]', 'A4', 140);
