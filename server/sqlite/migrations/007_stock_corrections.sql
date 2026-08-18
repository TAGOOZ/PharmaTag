-- PharmaTag core rev 007 — SQLite twin of alembic 007_stock_corrections.py
-- Corrections chart account (S1.7): the contra for re-booking inventory value
-- when an approved count correction is applied. Pure seed row; no table change.
INSERT INTO accounts (branch_id, code, name_ar, type, is_active)
VALUES (1, '5900', 'مصروفات.جرد وتعديل الارصدة', 'expense', 1);