-- PharmaTag core rev 005 — SQLite twin of alembic 005_drug_price_levels.py
-- Drug-master price levels: public = price, wholesale/cost = new columns.
-- Money minor units (plan/01 §4.2): NUMERIC(18,4) <-> INTEGER ×10000.
-- Table-level CHECKs aren't ALTER-able in SQLite, so each new column carries
-- its own column-level CHECK (mirrors the PG ck_drugs_prices_nonneg intent).
ALTER TABLE drugs ADD COLUMN price_wholesale INTEGER DEFAULT 0 CHECK (price_wholesale >= 0);  -- ×10000
ALTER TABLE drugs ADD COLUMN price_cost     INTEGER DEFAULT 0 CHECK (price_cost >= 0);        -- ×10000

-- Seeded medicines (rev 003): wholesale == public price (same backfill as PG).
UPDATE drugs SET price_wholesale = price WHERE price_wholesale = 0;

-- drugs.manage gates drug-master writes (legacy level-3 area الأصناف والمخزون).
INSERT INTO permissions (code, name_ar) VALUES ('drugs.manage', 'الأصناف والمخزون');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT 1, id FROM permissions WHERE code = 'drugs.manage';