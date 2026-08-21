"""The report registry (S3.1, ticket #23): code → query + view.

A report slice (S3.2–S3.5) contributes ONE registry row: a `query` that
runs branch-scoped and returns the JSON payload, and a `view` that flattens
that payload into the generic grid spec (`meta/columns/rows/foot/note`)
the template, exports, and ReportView all render. Nothing else is needed
to add a report — the catalog row + this pair is the whole integration.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.reports.day_profit import day_profit_report
from app.reports.drawer_handover import drawer_handover_report
from app.reports.period_totals import period_totals_report
from app.reports.stock_minimum import stock_minimum_report

# grid spec: JSON-safe, shared by template.py / exports / ReportView
ViewSpec = dict[str, Any]

QueryFn = Callable[[AsyncSession, int, dict[str, str]], Awaitable[dict]]
ViewFn = Callable[[dict], ViewSpec]


def parse_date(name: str, raw: str | None) -> date | None:
    if raw is None or raw == "":
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD)") from exc


def require_ordered_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValueError("date_from must not be after date_to")


# --- view builders: payload → grid spec -------------------------------------


def _day_profit_view(payload: dict) -> ViewSpec:
    meta = [
        ("التاريخ", payload["datee"]),
        ("عدد فواتير البيع", payload["sales_count"]),
        ("عدد مرتجعات البيع", payload["sales_returns_count"]),
    ]
    labels = [
        ("صافي الإيراد (بدون ضريبة)", "net_revenue"),
        ("تكلفة المبيعات", "cogs"),
        ("المصروفات", "expenses"),
        ("صافي الربح", "net_profit"),
        ("الخصومات", "discounts"),
        ("ضريبة المبيعات", "vat_sales"),
        ("ضريبة المشتريات", "vat_purchases"),
        ("المشتريات", "purchases"),
        ("كاش اليوم", "net_cash"),
        ("شبكة اليوم", "net_network"),
    ]
    rows = [[label, str(payload[key])] for label, key in labels]
    return {
        "meta": meta,
        "columns": ["البيان", "القيمة"],
        "rows": rows,
        "foot": None,
        "note": None,
    }


def _period_totals_view(payload: dict) -> ViewSpec:
    kinds = payload["kinds"]
    rows = [
        [
            "المبيعات",
            kinds["sale"]["count"],
            kinds["sale"]["total"],
            kinds["sale"]["vat"],
            kinds["sale"]["discount"],
        ],
        [
            "مرتجع المبيعات",
            kinds["sale_return"]["count"],
            kinds["sale_return"]["total"],
            kinds["sale_return"]["vat"],
            kinds["sale_return"]["discount"],
        ],
        [
            "المشتريات",
            kinds["purchase"]["count"],
            kinds["purchase"]["total"],
            kinds["purchase"]["vat"],
            kinds["purchase"]["discount"],
        ],
        [
            "مرتجع المشتريات",
            kinds["purchase_return"]["count"],
            kinds["purchase_return"]["total"],
            kinds["purchase_return"]["vat"],
            kinds["purchase_return"]["discount"],
        ],
    ]
    return {
        "meta": [
            ("من تاريخ", payload["date_from"] or "—"),
            ("إلى تاريخ", payload["date_to"] or "—"),
        ],
        "columns": ["البيان", "عدد الفواتير", "الإجمالي", "الضريبة", "الخصم"],
        "rows": rows,
        "foot": [
            "الصافي",
            "",
            payload["net_sales"],
            payload["net_vat_sales"],
            payload["net_discounts"],
        ],
        "note": None,
    }


def _stock_minimum_view(payload: dict) -> ViewSpec:
    rows = [
        [
            f"{item['drugname']} ({item['drugnamear']})"
            if item["drugnamear"]
            else item["drugname"],
            item["barcode"] or "—",
            item["qty"],
            item["minimum"],
            item["shortage"],
            item["price"],
        ]
        for item in payload["items"]
    ]
    note = None
    if payload.get("truncated"):
        note = (
            f"هناك أصناف أخرى غير معروضة (الحد 1000) — العدد الإجمالي {payload['count']}."
        )
    return {
        "meta": [("عدد الأصناف الأقل من الحد الأدنى", payload["count"])],
        "columns": ["الصنف", "الباركود", "الرصيد", "الحد الأدنى", "العجز", "السعر"],
        "rows": rows,
        "foot": None,
        "note": note,
    }


def _drawer_handover_view(payload: dict) -> ViewSpec:
    rows = [
        [
            cashier["name"],
            cashier["opening_in"],
            cashier["cash_sales_in"],
            cashier["card_sales_in"],
            cashier["returns_out"],
            cashier["card_returns_out"],
            cashier["expenses_out"],
            cashier["other_in"],
            cashier["other_out"],
            cashier["net_cash"],
        ]
        for cashier in payload["cashiers"]
    ]
    totals = payload["totals"]
    return {
        "meta": [
            ("من تاريخ", payload["date_from"] or "—"),
            ("إلى تاريخ", payload["date_to"] or "—"),
        ],
        "columns": [
            "الكاشير", "فتح", "كاش مبيعات", "شبكة مبيعات", "مرتجعات كاش",
            "مرتجعات شبكة", "مصروفات", "واردة أخرى", "صادرة أخرى", "صافي كاش",
        ],
        "rows": rows,
        "foot": [
            "الإجمالي",
            totals["opening_in"],
            totals["cash_sales_in"],
            totals["card_sales_in"],
            totals["returns_out"],
            totals["card_returns_out"],
            totals["expenses_out"],
            totals["other_in"],
            totals["other_out"],
            totals["net_cash"],
        ],
        "note": None,
    }


# --- query adapters: raw string params → typed query call --------------------


async def _query_day_profit(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    return await day_profit_report(
        session, branch_id=branch_id, datee=parse_date("datee", params.get("datee"))
    )


async def _query_period_totals(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await period_totals_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )


async def _query_stock_minimum(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    return await stock_minimum_report(session, branch_id=branch_id)


async def _query_drawer_handover(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await drawer_handover_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )


REGISTRY: dict[str, dict[str, Callable]] = {
    "day_profit": {"query": _query_day_profit, "view": _day_profit_view},
    "period_totals": {"query": _query_period_totals, "view": _period_totals_view},
    "stock_minimum": {"query": _query_stock_minimum, "view": _stock_minimum_view},
    "drawer_handover": {
        "query": _query_drawer_handover,
        "view": _drawer_handover_view,
    },
}


def get_entry(code: str) -> dict | None:
    """The registry row for a catalog code (None = no engine behind it)."""
    return REGISTRY.get(code)
