-- PharmaTag core twin of alembic 018–021 (S3.4, ticket #26)
-- Sales/purchase report catalog rows: invoice registers, returns register,
-- and supplier/customer period totals. Engines live in app/reports/views.py.

INSERT INTO report_catalog (code, category, title_ar, title_en, params, paper, sort) VALUES
    ('sales_invoices', 'sales', 'فواتير المبيعات', 'Sales Invoices', '["date_from", "date_to"]', 'A4', 90),
    ('purchase_invoices', 'sales', 'فواتير المشتريات', 'Purchase Invoices', '["date_from", "date_to"]', 'A4', 100),
    ('returns_period', 'sales', 'مرتجعات الفترة', 'Period Returns', '["date_from", "date_to"]', 'A4', 110),
    ('party_totals', 'sales', 'إجمالي العملاء والموردين', 'Customer & Supplier Totals', '["date_from", "date_to"]', 'A4', 120);
