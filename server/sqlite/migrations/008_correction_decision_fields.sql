-- PharmaTag core rev 008 — SQLite twin of alembic 008_correction_decision_fields.py
-- Counted qty snapshot (×10000 minor units, like delta) for the approval
-- staleness check; rejected_by for the rejecting manager. Both nullable.
ALTER TABLE stock_correction_requests ADD COLUMN counted INTEGER;  -- ×10000
ALTER TABLE stock_correction_requests ADD COLUMN rejected_by INTEGER REFERENCES users(id);