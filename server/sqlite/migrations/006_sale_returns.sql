-- PharmaTag core rev 006 — SQLite twin of alembic 006_sale_returns.py
-- Sales-return links: the return invoice references the original sale, and
-- each return line references its exact original line (partial-return tracking).
ALTER TABLE invoices ADD COLUMN ref_invoice_id INTEGER REFERENCES invoices(id);
ALTER TABLE invoice_lines ADD COLUMN ref_invoice_line_id INTEGER REFERENCES invoice_lines(id);

CREATE INDEX ix_invoices_ref_invoice ON invoices (ref_invoice_id);
CREATE INDEX ix_invoice_lines_ref_line ON invoice_lines (ref_invoice_line_id);