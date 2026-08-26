-- PharmaTag core rev 033 — SQLite twin of alembic 033_chain_sales_catalog.py
-- Chain sales summary catalog row (#34): the titanksasales projection (A06)
-- regenerated from canonical invoices; engine in app/reports/views.py.
INSERT INTO report_catalog (code, category, title_ar, title_en, params, paper, sort) VALUES
    ('chain_sales', 'chain', 'مبيعات السلسلة', 'Chain Sales Summary', '["date_from", "date_to"]', 'A4', 200);
