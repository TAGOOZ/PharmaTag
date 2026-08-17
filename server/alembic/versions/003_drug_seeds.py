"""core rev 003 — seed the MAIN-branch drug master (plan/01 §5.2, ticket #6 S0.3)

The S0.3 slice proves login + branch + drug-master read end-to-end, so the
drug master needs seeded rows (rev 002 seeded users/branches but not drugs).
Drugs are global (wzdrugs, plan/01 §4.3#2); the read is scoped by the user's
branch, and the same catalog is mirrored to the offline SQLite twin
(`sqlite/migrations/003_drug_seeds.sql`) and the desktop bootstrap.

Representative Egyptian retail medicines (G03 CC0 drug database style), all
VAT-exempt per G06 (medicines exempt; only medical devices carry 5%).

Uses explicit, deterministic IDs (like rev 002) so the migration also renders
in offline SQL mode and the SQLite twin can mirror it.

Revision ID: 003_drug_seeds
Revises: 002_seeds
"""
from alembic import op
import sqlalchemy as sa

revision = "003_drug_seeds"
down_revision = "002_seeds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO drugs
            (id, drugname, drugnamear, generic, classy, pharmacology, co,
             unitsclass, tax_type, vat, units, unitsmall, price, price_now,
             disco, active)
        OVERRIDING SYSTEM VALUE
        VALUES
            (1, 'Panadol Extra',     'بانادول إكسترا', 'paracetamol + caffeine', 'analgesic', '', 'GSK',     'pack', 'exempt', 0, 24, 0, 12.5000, 12.5000, 0, true),
            (2, 'Augmentin 1g',      'أوجمنتين',       'amoxicillin/clavulanate', 'antibiotic', '', 'GSK',   'pack', 'exempt', 0, 14, 0, 48.0000, 48.0000, 0, true),
            (3, 'Amaryl 2mg',        'أماريل',         'glimepiride',            'antidiabetic', '', 'Sanofi', 'pack', 'exempt', 0, 30, 0, 28.7500, 28.7500, 0, true),
            (4, 'Cataflam 50mg',     'كاتافلام',       'diclofenac potassium',   'antiinflammatory', '', 'Novartis', 'pack', 'exempt', 0, 20, 0, 15.0000, 15.0000, 0, true),
            (5, 'Ventolin Inhaler',  'فينتولين',       'salbutamol',             'bronchodilator', '', 'GSK', 'pack', 'exempt', 0, 1, 0, 22.5000, 22.5000, 0, true)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM drugs WHERE id IN (1, 2, 3, 4, 5)"
    ))