"""The RPT report catalog (S3.1 #23 + S3.2 #24 + S3.3 #25).

Since rev 015 the catalog lives in the `report_catalog` table — a later
report slice (S3.4–S3.5) adds rows, not code. `SEED_CATALOG` documents the
rows revs 015–017 seed (kept in sync with the migrations); the endpoint
reads the table so operators can deactivate/reorder reports without a
deploy.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReportCatalog

SEED_CATALOG: list[dict] = [
    {
        "code": "drawer_handover",
        "category": "money",
        "title_ar": "تسليم الدرج",
        "title_en": "Drawer Handover",
        "params": ["date_from", "date_to"],
        "sort": 10,
    },
    {
        "code": "day_profit",
        "category": "money",
        "title_ar": "ربح اليوم",
        "title_en": "Day Profit",
        "params": ["datee", "date_from", "date_to"],
        "sort": 20,
    },
    {
        "code": "day_totals",
        "category": "money",
        "title_ar": "الإجماليات اليومية",
        "title_en": "Day Totals",
        "params": ["date_from", "date_to"],
        "sort": 25,
    },
    {
        "code": "period_totals",
        "category": "money",
        "title_ar": "ملخص المبيعات والمشتريات",
        "title_en": "Sales & Purchases Summary",
        "params": ["date_from", "date_to"],
        "sort": 30,
    },
    {
        "code": "sales_invoices",
        "category": "sales",
        "title_ar": "فواتير المبيعات",
        "title_en": "Sales Invoices",
        "params": ["date_from", "date_to"],
        "sort": 90,
    },
    {
        "code": "purchase_invoices",
        "category": "sales",
        "title_ar": "فواتير المشتريات",
        "title_en": "Purchase Invoices",
        "params": ["date_from", "date_to"],
        "sort": 100,
    },
    {
        "code": "returns_period",
        "category": "sales",
        "title_ar": "مرتجعات الفترة",
        "title_en": "Period Returns",
        "params": ["date_from", "date_to"],
        "sort": 110,
    },
    {
        "code": "party_totals",
        "category": "sales",
        "title_ar": "إجمالي العملاء والموردين",
        "title_en": "Customer & Supplier Totals",
        "params": ["date_from", "date_to"],
        "sort": 120,
    },
    {
        "code": "ledger_account",
        "category": "accounting",
        "title_ar": "دفتر الأستاذ لحساب",
        "title_en": "Ledger by Account",
        "params": ["account_code", "month", "year", "date_from", "date_to"],
        "sort": 130,
    },
    {
        "code": "vat_summary",
        "category": "accounting",
        "title_ar": "ملخص ضريبة القيمة المضافة",
        "title_en": "VAT Summary (Form 10)",
        "params": ["month", "year", "date_from", "date_to"],
        "sort": 140,
    },
    {
        # S5.4 (#34): the titanksasales projection (A06) — regenerated from
        # canonical invoices, never a synced table
        "code": "chain_sales",
        "category": "chain",
        "title_ar": "مبيعات السلسلة",
        "title_en": "Chain Sales Summary",
        "params": ["date_from", "date_to"],
        "sort": 200,
    },
    {
        "code": "stock_minimum",
        "category": "stock",
        "title_ar": "النواقص (أقل من الحد الأدنى)",
        "title_en": "Stock Below Minimum",
        "params": [],
        "sort": 40,
    },
    {
        "code": "stock_current",
        "category": "stock",
        "title_ar": "رصيد الأصناف",
        "title_en": "Current Stock",
        "params": [],
        "sort": 50,
    },
    {
        "code": "stock_movements",
        "category": "stock",
        "title_ar": "تتبع تغيير الرصيد",
        "title_en": "Drug Movement Track",
        "params": ["drug_id", "date_from", "date_to"],
        "sort": 60,
    },
    {
        "code": "stock_expired",
        "category": "stock",
        "title_ar": "الادوية منتهية الصلاحية",
        "title_en": "Expired / Expiring Stock",
        "params": ["datee", "horizon_days"],
        "sort": 70,
    },
    {
        "code": "stock_needs",
        "category": "stock",
        "title_ar": "احتياجات الطلب (الحد الأدنى)",
        "title_en": "Order Needs (Minimum-Based)",
        "params": [],
        "sort": 80,
    },
]


async def get_catalog(session: AsyncSession) -> list[dict]:
    """Active catalog rows ordered for the menu (sort asc, then code)."""
    rows = await session.execute(
        select(ReportCatalog)
        .where(ReportCatalog.active.is_(True))
        .order_by(ReportCatalog.sort.asc(), ReportCatalog.code.asc())
    )
    return [
        {
            "code": row.code,
            "category": row.category,
            "title_ar": row.title_ar,
            "title_en": row.title_en,
            "params": list(row.params or []),
            "paper": row.paper,
        }
        for row in rows.scalars()
    ]


async def get_catalog_entry(session: AsyncSession, code: str) -> ReportCatalog | None:
    """One active catalog row by code (None when unknown or deactivated)."""
    row = await session.get(ReportCatalog, code)
    if row is None or not row.active:
        return None
    return row
