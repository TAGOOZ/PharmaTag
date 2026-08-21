"""The RPT report catalog (S3.1, ticket #23).

Since rev 015 the catalog lives in the `report_catalog` table — a later
report slice (S3.2–S3.5) adds rows, not code. `SEED_CATALOG` documents the
four v1 rows the migration seeds (kept in sync with alembic 015); the
endpoint reads the table so operators can deactivate/reorder reports
without a deploy.
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
        "params": ["datee"],
        "sort": 20,
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
        "code": "stock_minimum",
        "category": "stock",
        "title_ar": "النواقص (أقل من الحد الأدنى)",
        "title_en": "Stock Below Minimum",
        "params": [],
        "sort": 40,
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
