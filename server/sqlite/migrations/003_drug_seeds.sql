-- PharmaTag core rev 003 — SQLite drug-master seeds (mirrors alembic 003_drug_seeds.py)
-- Medicines are VAT-exempt (G06), so tax_type = 'exempt', vat = 0.
-- Money minor units (plan/01 §4.2): price/price_now ×10000, vat rate ×100.
INSERT INTO drugs (drugname, drugnamear, generic, classy, pharmacology, co,
                   unitsclass, tax_type, vat, units, unitsmall, price, price_now,
                   disco, active)
VALUES
    ('Panadol Extra',    'بانادول إكسترا', 'paracetamol + caffeine', 'analgesic',        '', 'GSK',      'pack', 'exempt', 0, 24, 0, 125000, 125000, 0, 1),
    ('Augmentin 1g',     'أوجمنتين',       'amoxicillin/clavulanate', 'antibiotic',      '', 'GSK',      'pack', 'exempt', 0, 14, 0, 480000, 480000, 0, 1),
    ('Amaryl 2mg',       'أماريل',         'glimepiride',            'antidiabetic',     '', 'Sanofi',   'pack', 'exempt', 0, 30, 0, 287500, 287500, 0, 1),
    ('Cataflam 50mg',    'كاتافلام',       'diclofenac potassium',   'antiinflammatory', '', 'Novartis', 'pack', 'exempt', 0, 20, 0, 150000, 150000, 0, 1),
    ('Ventolin Inhaler', 'فينتولين',       'salbutamol',             'bronchodilator',   '', 'GSK',      'pack', 'exempt', 0, 1,  0, 225000, 225000, 0, 1);