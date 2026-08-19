"""The v1 report catalog (S1.9, ticket #15).

Four basic reports per plan/00 G11 (minimal v1 set) and the legacy catalog:
day profit (RPT-OP02 §7 daily-profit inputs), sales/purchases summary
(RPT-OP01/OP03 aggregates), stock below minimum (RPT-ST01), drawer handover
(RPT-A04). The full report framework (A4/PDF/Excel, report_catalog persistence)
is the S3.1 slice (ticket #23, blocked by #15); here the catalog is the static
list a screen renders, and each code maps to its query module.
"""
from __future__ import annotations

CATALOG: list[dict] = [
    {
        "code": "day_profit",
        "group": "money",
        "title_ar": "ربح اليوم",
        "title_en": "Day Profit",
        "params": ["datee"],
        "source": "drawer day ledger (movements + invoices + journal 6000)",
    },
    {
        "code": "period_totals",
        "group": "money",
        "title_ar": "ملخص المبيعات والمشتريات",
        "title_en": "Sales & Purchases Summary",
        "params": ["date_from", "date_to"],
        "source": "invoices by kind",
    },
    {
        "code": "stock_minimum",
        "group": "stock",
        "title_ar": "النواقص (أقل من الحد الأدنى)",
        "title_en": "Stock Below Minimum",
        "params": [],
        "source": "branch_stock vs minimum",
    },
    {
        "code": "drawer_handover",
        "group": "money",
        "title_ar": "تسليم الدرج",
        "title_en": "Drawer Handover",
        "params": ["date_from", "date_to"],
        "source": "drawer_movements by cashier",
    },
]


def get_catalog() -> list[dict]:
    """The report catalog rows the framework renders (JSON-safe dicts)."""
    return [dict(row) for row in CATALOG]
