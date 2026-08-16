"""Known .phy record layouts (from RECORD_LAYOUTS_daily_phy.md + PHY_MIGRATION.md).

Each layout's fields are cited to the decompiled p-code; unknown regions are
left unmapped (raw bytes preserved via the RAW tail field where useful).
"""
from phy_reader import Layout, Field

# ---- Daily.phy (614 B) — per-day money/journal record (ModDailyQuiod) ----
# Known: offsets 0x00..0x3c. Offsets 0x3c..614 UNKNOWN (moved wholesale).
DAILY_PHY = Layout(
    name="Daily.phy",
    record_len=614,
    fields=[
        Field("money0", "R4", 0x00),      # cash group value
        Field("money1", "R4", 0x04),      # money group value
        Field("money2", "R4", 0x08),
        Field("money3", "R4", 0x18),
        Field("txn_count", "I2", 0x30),   # transaction count
        Field("money4", "R8", 0x34),
        Field("money5", "R8", 0x3C),
        # 0x3c..614 unknown
        Field("tail_raw", "RAW", 0x44, 614 - 0x44),
    ],
)

# ---- daily-manual.phy (52 B) — manual journal money per day ----
DAILY_MANUAL_PHY = Layout(
    name="daily-manual.phy",
    record_len=52,
    fields=[
        Field("money0", "R4", 0x00),
        Field("tail_raw", "RAW", 0x04, 52 - 0x04),
    ],
)

# ---- daily-manual-2.phy (56 B) — manual variant, +4 B vs daily-manual ----
DAILY_MANUAL2_PHY = Layout(
    name="daily-manual-2.phy",
    record_len=56,
    fields=[
        Field("money0", "R4", 0x00),
        Field("tail_raw", "RAW", 0x04, 56 - 0x04),
    ],
)

# ---- usersmony.phy (318 B) — money per user/shift (FormUsersMony) ----
USERSMONY_PHY = Layout(
    name="usersmony.phy",
    record_len=318,
    fields=[
        Field("user_idx", "I2", 0x00),    # user/shift index
        Field("money", "R4", 0x04),       # money amount
        Field("name", "STR", 0x08, 4),    # tentative
        Field("field0c", "VAR", 0x0C),
        Field("field38", "VAR", 0x38),
        Field("field268", "I2", 0x268),
        Field("tail_raw", "RAW", 0x26A, 318 - 0x26A),
    ],
)

# ---- delivery.phy (55 B) — transfer delivery state (Moddelivery) ----
DELIVERY_PHY = Layout(
    name="delivery.phy",
    record_len=55,
    fields=[
        Field("tail_raw", "RAW", 0x00, 55),
    ],
)

# ---- tar.phy (856 B, 32000 recs) — drug master file (VERIFIED on real install) ----
# Real data: 'DERMOTRACIN AEROSOL POWDER 150 ML' + Arabic name + '150 ' size etc.
TAR_PHY = Layout(
    name="tar.phy",
    record_len=856,
    fields=[
        Field("name_en", "STR", 0x00, 50),   # 'DERMOTRACIN AEROSOL POWDER 150 ML       ' (padded)
        Field("name_ar", "STR", 0x34, 40),   # '150 ' size + Arabic name follow
        Field("tail_raw", "RAW", 0x5C, 856 - 0x5C),
    ],
)

# ---- salesfull.phy (997 B x 50000) — full sales export (FFFOutPut report procs) ----
# Size-derived record length (verified: LitI2 [f3 e5 03] = 0x03E5 = 997 at L26960/30500/31981/...).
# Sparse on fresh install (only 5 bytes set); fields unknown until a populated sample exists.
SALESFULL_PHY = Layout(
    name="salesfull.phy",
    record_len=997,
    fields=[
        Field("tail_raw", "RAW", 0x00, 997),
    ],
)

# ---- customers.w.phy (157 B x 30000) — customer master (FFFNeed @0x00b04314) ----
# Size-derived record length (verified: LitI2 [f3 9d 00] = 0x009D = 157 at L85629).
# Head shows '????? ??????' — Arabic chars stored as literal '?' (0x3F) in this install.
CUSTOMERS_PHY = Layout(
    name="customers.w.phy",
    record_len=157,
    fields=[
        Field("name", "STR", 0x00, 40),
        Field("tail_raw", "RAW", 0x28, 157 - 0x28),
    ],
)

# ---- ShogUser.phy (1114 B x 49) — user/shift log (string 'Files\\DBI\\ShogUser.phy' idx 5011) ----
# Record 0: '????? ????? ?????   ' + codes 4, 5678. Layout unverified beyond names.
SHOGUSER_PHY = Layout(
    name="ShogUser.phy",
    record_len=1114,
    fields=[
        Field("name", "STR", 0x00, 40),
        Field("tail_raw", "RAW", 0x28, 1114 - 0x28),
    ],
)

ALL_LAYOUTS = {
    "Daily.phy": DAILY_PHY,
    "daily-manual.phy": DAILY_MANUAL_PHY,
    "daily-manual-2.phy": DAILY_MANUAL2_PHY,
    "usersmony.phy": USERSMONY_PHY,
    "delivery.phy": DELIVERY_PHY,
    "tar.phy": TAR_PHY,
    "salesfull.phy": SALESFULL_PHY,
    "customers.w.phy": CUSTOMERS_PHY,
    "ShogUser.phy": SHOGUSER_PHY,
}


def layout_for(path: str):
    import os

    base = os.path.basename(path).lower()
    for key, lay in ALL_LAYOUTS.items():
        if base == key.lower():
            return lay
    return None


def import_records(path: str, layout: Layout):
    """Yield dicts ready for a Postgres/Tauri-SQLite loader."""
    from phy_reader import read_records

    for recno, fields in read_records(path, layout):
        fields["_recno"] = recno
        fields["_source"] = path
        yield fields