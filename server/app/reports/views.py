"""The report registry (S3.1, ticket #23): code → query + view.

A report slice (S3.2–S3.5) contributes ONE registry row: a `query` that
runs branch-scoped and returns the JSON payload, and a `view` that flattens
that payload into the generic grid spec (`meta/columns/rows/foot/note`)
the template, exports, and ReportView all render. Nothing else is needed
to add a report — the catalog row + this pair is the whole integration.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.reports.day_profit import day_profit_report
from app.reports.chain_sales import chain_sales_report
from app.reports.day_totals import DAY_COLUMNS, day_totals_report
from app.reports.drawer_handover import drawer_handover_report
from app.reports.ledger_account import ledger_account_report
from app.reports.party_totals import party_totals_report
from app.reports.period_totals import period_totals_report
from app.reports.purchase_invoices import purchase_invoices_report
from app.reports.returns_period import returns_period_report
from app.reports.sales_invoices import sales_invoices_report
from app.reports.stock_current import stock_current_report
from app.reports.stock_expired import _DEFAULT_HORIZON_DAYS, stock_expired_report
from app.reports.stock_minimum import stock_minimum_report
from app.reports.stock_movements import stock_movements_report
from app.reports.stock_needs import stock_needs_report
from app.reports.vat_summary import vat_summary_report

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


# catalog params that are integers, not dates, with their accepted bounds —
# ONE source of truth so enqueue-time validation can never accept a value
# the renderer would later reject
INT_PARAM_BOUNDS: dict[str, tuple[int, int]] = {
    "horizon_days": (0, 3650),
    "drug_id": (1, 2_147_483_647),
    "month": (1, 12),
    "year": (1900, 9999),
}
INT_PARAMS = set(INT_PARAM_BOUNDS)

# catalog params validated as strings against a regex — same single source of
# truth contract as INT_PARAM_BOUNDS: the queue never accepts what render rejects
STR_PARAM_PATTERNS: dict[str, str] = {
    # chart codes are short opaque handles (seeded digits; user codes may carry
    # dots/dashes) — anything else is a typo or injection bait
    "account_code": r"^[0-9A-Za-z._-]{1,30}$",
}

# params a report cannot render without — the print queue refuses to enqueue
# a job missing them (a job that can only fail at render must not queue)
REQUIRED_PARAMS: dict[str, set[str]] = {
    "stock_movements": {"drug_id"},
    "ledger_account": {"account_code"},
}


def parse_int(name: str, raw: str | None) -> int | None:
    if name not in INT_PARAM_BOUNDS:
        raise ValueError(f"{name} is not an integer param")
    lo, hi = INT_PARAM_BOUNDS[name]
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}")
    return value


def parse_str(name: str, raw: str | None) -> str | None:
    if name not in STR_PARAM_PATTERNS:
        raise ValueError(f"{name} is not a string param")
    if raw is None or raw == "":
        return None
    if not re.fullmatch(STR_PARAM_PATTERNS[name], raw):
        raise ValueError(f"{name} has an invalid format")
    return raw


def require_ordered_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValueError("date_from must not be after date_to")


# --- view builders: payload → grid spec -------------------------------------


def _day_profit_view(payload: dict) -> ViewSpec:
    if "datee" in payload:
        meta = [
            ("التاريخ", payload["datee"]),
            ("عدد فواتير البيع", payload["sales_count"]),
            ("عدد مرتجعات البيع", payload["sales_returns_count"]),
        ]
    else:
        meta = [
            ("من تاريخ", payload["date_from"] or "مفتوح"),
            ("إلى تاريخ", payload["date_to"] or "مفتوح"),
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


def _sales_invoices_view(payload: dict) -> ViewSpec:
    totals = payload["totals"]
    rows = [
        [
            row["invoice_no"],
            row["datee"],
            row["party_namee"] or "بدون عميل",
            row["totalvalue"],
            row["payed"],
            row["agel"],
            row["vat"],
            row["writer"] or "—",
        ]
        for row in payload["rows"]
    ]
    return {
        "meta": [
            ("من تاريخ", payload["date_from"] or "مفتوح"),
            ("إلى تاريخ", payload["date_to"] or "مفتوح"),
            ("عدد الفواتير", totals["count"]),
        ],
        "columns": [
            "رقم الفاتورة",
            "التاريخ",
            "العميل",
            "الاجمالي",
            "المدفوع",
            "الآجل",
            "الضريبة",
            "الموظف",
        ],
        "rows": rows,
        "foot": [
            "الإجمالي",
            "",
            "",
            totals["total"],
            totals["payed"],
            totals["agel"],
            totals["vat"],
            "",
        ],
        "note": (
            f"هناك فواتير أخرى غير معروضة (الحد 1000) — العدد الإجمالي {totals['count']}."
            if payload.get("truncated")
            else None
        ),
    }


def _purchase_invoices_view(payload: dict) -> ViewSpec:
    totals = payload["totals"]
    rows = [
        [
            row["invoice_no"],
            row["datee"],
            row["supplier_namee"] or "—",
            row["drugname"],
            row["qty"],
            row["unit_cost"],
            row["vat_amount"],
            row["line_total"],
            row["expire"] or "—",
            row["batch_randomid"] or "—",
        ]
        for row in payload["rows"]
    ]
    return {
        "meta": [
            ("من تاريخ", payload["date_from"] or "مفتوح"),
            ("إلى تاريخ", payload["date_to"] or "مفتوح"),
            ("عدد الفواتير", totals["invoice_count"]),
            ("عدد الأصناف", totals["line_count"]),
        ],
        "columns": [
            "رقم الفاتورة",
            "التاريخ",
            "المورد",
            "الصنف",
            "الكمية",
            "سعر التكلفة",
            "الضريبة",
            "اجمالي السطر",
            "تاريخ الصلاحية",
            "رقم التشغيلة",
        ],
        "rows": rows,
        "foot": [
            "الإجمالي",
            "",
            "",
            "",
            "",
            "",
            totals["vat"],
            totals["total"],
            "",
            "",
        ],
        "note": (
            f"هناك بنود أخرى غير معروضة (الحد 1000) — عدد البنود {totals['line_count']}."
            if payload.get("truncated")
            else None
        ),
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


def _stock_current_view(payload: dict) -> ViewSpec:
    rows = [
        [
            f"{item['drugname']} ({item['drugnamear']})"
            if item["drugnamear"]
            else item["drugname"],
            item["barcode"] or "—",
            item["qty"],
            item["value"],
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
        "meta": [("عدد الأصناف", payload["count"])],
        "columns": ["الصنف", "الباركود", "الرصيد", "قيمة المخزون", "سعر البيع"],
        "rows": rows,
        # whole-branch value computed in SQL — correct even when truncated
        "foot": ["إجمالي قيمة المخزون", "", "", payload["total_value"], ""],
        "note": note,
    }


def _stock_movements_view(payload: dict) -> ViewSpec:
    rows = [
        [
            day["datee"],
            day["opening"],
            day["purchases"],
            day["sales"],
            day["sales_returns"],
            day["purchase_returns"],
            day["adjustments"],
            day["closing"],
        ]
        for day in payload["days"]
    ]
    return {
        "meta": [
            ("الصنف", payload["drugname"]),
            ("الرصيد الحالي", payload["current_qty"]),
        ],
        "columns": [
            "التاريخ",
            "رصيد افتتاحي",
            "مشتريات",
            "مبيعات",
            "مرتجع مبيعات",
            "مرتجع مشتريات",
            "تسويات",
            "رصيد نهائي",
        ],
        "rows": rows,
        "foot": None,
        "note": None,
    }


def _stock_expired_view(payload: dict) -> ViewSpec:
    status_ar = {"expired": "منتهي", "warning": "قارب على الانتهاء"}
    rows = [
        [
            f"{item['drugname']} ({item['drugnamear']})"
            if item["drugnamear"]
            else item["drugname"],
            item["barcode"] or "—",
            item["expire"],
            item["days_to_expiry"],
            item["qty"],
            item["value"],
            status_ar[item["status"]],
        ]
        for item in payload["items"]
    ]
    note = None
    if payload.get("truncated"):
        note = (
            f"هناك دفعات أخرى غير معروضة (الحد 1000) — العدد الإجمالي {payload['count']}."
        )
    return {
        "meta": [
            ("كشف حتى تاريخ", payload["datee"]),
            ("نطاق التنبيه (أيام)", payload["horizon_days"]),
            ("عدد الدفعات المتأثرة", payload["count"]),
        ],
        "columns": ["الصنف", "الباركود", "تاريخ الانتهاء", "الأيام المتبقية",
                    "الرصيد", "القيمة", "الحالة"],
        "rows": rows,
        # whole-branch affected value computed in SQL — correct when truncated
        "foot": ["إجمالي قيمة المخزون المتأثر", "", "", "",
                 "", payload["total_value"], ""],
        "note": note,
    }


def _stock_needs_view(payload: dict) -> ViewSpec:
    rows = [
        [
            f"{item['drugname']} ({item['drugnamear']})"
            if item["drugnamear"]
            else item["drugname"],
            item["barcode"] or "—",
            item["qty"],
            item["minimum"],
            item["suggested_order"],
            item["last_cost"] or "—",
        ]
        for item in payload["items"]
    ]
    note = None
    if payload.get("truncated"):
        note = (
            f"هناك أصناف أخرى غير معروضة (الحد 1000) — العدد الإجمالي {payload['count']}."
        )
    return {
        "meta": [("عدد الأصناف المطلوب تعويضها", payload["count"])],
        "columns": ["الصنف", "الباركود", "الرصيد", "الحد الأدنى",
                    "الكمية المقترح طلبها", "اخر سعر شراء"],
        "rows": rows,
        "foot": ["إجمالي الكمية المقترحة", "", "", "",
                 payload["suggested_total"], ""],
        "note": note,
    }


def _day_totals_view(payload: dict) -> ViewSpec:
    rows = [
        [day["datee"]] + [day[key] for key, _ in DAY_COLUMNS]
        for day in payload["days"]
    ]
    totals = payload["totals"]
    return {
        "meta": [
            ("من تاريخ", payload["date_from"] or "—"),
            ("إلى تاريخ", payload["date_to"] or "—"),
            ("عدد الأيام", len(payload["days"])),
        ],
        "columns": ["التاريخ"] + [label for _, label in DAY_COLUMNS],
        "rows": rows,
        "foot": ["الإجمالي"] + [totals[key] for key, _ in DAY_COLUMNS],
        "note": None,
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
        session,
        branch_id=branch_id,
        datee=parse_date("datee", params.get("datee")),
        date_from=parse_date("date_from", params.get("date_from")),
        date_to=parse_date("date_to", params.get("date_to")),
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


async def _query_stock_current(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    return await stock_current_report(session, branch_id=branch_id)


async def _query_stock_movements(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    drug_id = parse_int("drug_id", params.get("drug_id"))
    if drug_id is None:
        raise ValueError("drug_id is required")
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await stock_movements_report(
        session,
        branch_id=branch_id,
        drug_id=drug_id,
        date_from=date_from,
        date_to=date_to,
    )


async def _query_stock_expired(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    datee = parse_date("datee", params.get("datee"))
    horizon = parse_int("horizon_days", params.get("horizon_days"))
    return await stock_expired_report(
        session,
        branch_id=branch_id,
        datee=datee,
        horizon_days=horizon if horizon is not None else _DEFAULT_HORIZON_DAYS,
    )


async def _query_stock_needs(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    return await stock_needs_report(session, branch_id=branch_id)


async def _query_day_totals(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await day_totals_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )


async def _query_drawer_handover(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await drawer_handover_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )


async def _query_chain_sales(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    # chain-wide by design (A06): the projection reads EVERY active branch,
    # `branch_id` is only the requesting caller's
    return await chain_sales_report(session, date_from=date_from, date_to=date_to)


async def _query_sales_invoices(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await sales_invoices_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )


async def _query_purchase_invoices(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await purchase_invoices_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )


async def _query_returns_period(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await returns_period_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )


async def _query_party_totals(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await party_totals_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )


def _parse_period_params(params: dict[str, str]) -> tuple[int | None, int | None]:
    return (
        parse_int("month", params.get("month")),
        parse_int("year", params.get("year")),
    )


async def _query_ledger_account(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    account_code = parse_str("account_code", params.get("account_code"))
    if account_code is None:
        raise ValueError("account_code is required")
    month, year = _parse_period_params(params)
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await ledger_account_report(
        session,
        branch_id=branch_id,
        account_code=account_code,
        month=month,
        year=year,
        date_from=date_from,
        date_to=date_to,
    )


async def _query_vat_summary(
    session: AsyncSession, branch_id: int, params: dict[str, str]
) -> dict:
    month, year = _parse_period_params(params)
    date_from = parse_date("date_from", params.get("date_from"))
    date_to = parse_date("date_to", params.get("date_to"))
    require_ordered_range(date_from, date_to)
    return await vat_summary_report(
        session,
        branch_id=branch_id,
        month=month,
        year=year,
        date_from=date_from,
        date_to=date_to,
    )


def _returns_period_view(payload: dict) -> ViewSpec:
    totals = payload["totals"]
    rows = [
        [
            "مرتجع مبيعات" if row["kind"] == "sale_return" else "مرتجع مشتريات",
            row["invoice_no"],
            row["datee"],
            row["party_namee"] or "—",
            row["ref_invoice_no"] or "—",
            row["totalvalue"],
            row["vat"],
        ]
        for row in payload["rows"]
    ]
    return {
        "meta": [
            ("من تاريخ", payload["date_from"] or "مفتوح"),
            ("إلى تاريخ", payload["date_to"] or "مفتوح"),
        ],
        "columns": [
            "النوع",
            "رقم الفاتورة",
            "التاريخ",
            "الطرف",
            "الفاتورة الأصلية",
            "القيمة (سالب)",
            "الضريبة",
        ],
        "rows": rows,
        "foot": [
            "الصافي",
            "",
            "",
            "",
            "",
            totals["net"],
            "",
        ],
        "note": (
            f"هناك مرتجعات أخرى غير معروضة (الحد 1000) — العدد الإجمالي {totals['count']}."
            if payload.get("truncated")
            else "قيم المرتجعات بالسالب: تُخصم من إجماليات الفترة وضريبتها."
        ),
    }


def _party_totals_view(payload: dict) -> ViewSpec:
    rows = []
    for section, label in (("customers", "عميل"), ("suppliers", "مورد")):
        for row in payload[section]:
            rows.append(
                [
                    label,
                    row["namee"],
                    row["period_debit"],
                    row["period_credit"],
                    row["closing"],
                ]
            )
    return {
        "meta": [
            ("من تاريخ", payload["date_from"] or "مفتوح"),
            ("إلى تاريخ", payload["date_to"] or "مفتوح"),
        ],
        "columns": [
            "النوع",
            "الاسم",
            "مدين الفترة",
            "دائن الفترة",
            "الرصيد الختامي",
        ],
        "rows": rows,
        "foot": None,
        "note": None,
    }


_VAT_RATE_AR = {"exempt": "معفاة", "5%": "5%", "14%": "14%"}


def _vat_summary_view(payload: dict) -> ViewSpec:
    rows = []
    for section, label in (("output", "ضريبة المخرجات"), ("input", "ضريبة المدخلات")):
        for rate in payload[section]["rates"]:
            rows.append(
                [
                    f"{label} — {_VAT_RATE_AR[rate['tax_type']]}",
                    rate["net"],
                    rate["vat"],
                ]
            )
    foot_label = (
        "رصيد دائن (المدخلات تتجاوز المخرجات)"
        if payload["credit_balance"]
        else "صافي الضريبة المستحقة"
    )
    return {
        "meta": _period_meta(payload["period"]),
        "columns": ["البيان", "صافي القيمة", "الضريبة"],
        "rows": rows,
        "foot": [foot_label, "", payload["net_vat_payable"]],
        "note": (
            "المرتجعات مخصومة داخل بندها. لا يتم توزيع ضريبة المدخلات تلقائياً "
            "على المخرجات المعفاة — القرار للمحاسب."
        ),
    }


def _period_meta(period: dict) -> list[tuple[str, str]]:
    if period["month"] is not None:
        return [("الفترة", f"{period['month']:02d}/{period['year']}")]
    return [
        ("من تاريخ", period["date_from"] or "مفتوح"),
        ("إلى تاريخ", period["date_to"] or "مفتوح"),
    ]


def _ledger_account_view(payload: dict) -> ViewSpec:
    account = payload["account"]
    name = account["name_ar"] or account["name_en"]
    rows = [
        [
            movement["datee"],
            movement["entry_no"],
            movement["description"],
            movement["party"] or "—",
            movement["debit"],
            movement["credit"],
            movement["running_balance"],
        ]
        for movement in payload["movements"]
    ]
    return {
        "meta": [
            ("الحساب", f"{account['code']} — {name}" if name else account["code"]),
            ("رصيد افتتاحي", payload["opening_balance"]),
            *_period_meta(payload["period"]),
        ],
        "columns": [
            "التاريخ",
            "رقم القيد",
            "البيان",
            "الطرف",
            "مدين",
            "دائن",
            "الرصيد",
        ],
        "rows": rows,
        "foot": [
            "الإجمالي",
            "",
            "",
            "",
            payload["debit_total"],
            payload["credit_total"],
            payload["closing_balance"],
        ],
        "note": None,
    }


def _chain_sales_view(payload: dict) -> ViewSpec:
    totals = payload["totals"]
    rows = [
        [
            row["datee"],
            row["branch"],
            row["invoice_count"],
            row["total"],
            row["payed"],
            row["agel"],
            row["vat"],
        ]
        for row in payload["rows"]
    ]
    return {
        "meta": [
            ("من تاريخ", payload["date_from"] or "مفتوح"),
            ("إلى تاريخ", payload["date_to"] or "مفتوح"),
            ("عدد الفواتير", totals["invoice_count"]),
        ],
        "columns": [
            "التاريخ",
            "الفرع",
            "عدد الفواتير",
            "الاجمالي",
            "المدفوع",
            "الآجل",
            "الضريبة",
        ],
        "rows": rows,
        "foot": [
            "الإجمالي",
            "",
            totals["invoice_count"],
            totals["total"],
            totals["payed"],
            totals["agel"],
            totals["vat"],
        ],
        "note": (
            "هناك أيام/فروع أخرى غير معروضة (الحد 1000)."
            if payload.get("truncated")
            else None
        ),
    }


REGISTRY: dict[str, dict[str, Callable]] = {
    "day_profit": {"query": _query_day_profit, "view": _day_profit_view},
    "period_totals": {"query": _query_period_totals, "view": _period_totals_view},
    "stock_minimum": {"query": _query_stock_minimum, "view": _stock_minimum_view},
    "stock_current": {"query": _query_stock_current, "view": _stock_current_view},
    "stock_movements": {
        "query": _query_stock_movements,
        "view": _stock_movements_view,
    },
    "stock_expired": {"query": _query_stock_expired, "view": _stock_expired_view},
    "stock_needs": {"query": _query_stock_needs, "view": _stock_needs_view},
    "drawer_handover": {
        "query": _query_drawer_handover,
        "view": _drawer_handover_view,
    },
    "day_totals": {"query": _query_day_totals, "view": _day_totals_view},
    "sales_invoices": {"query": _query_sales_invoices, "view": _sales_invoices_view},
    "purchase_invoices": {
        "query": _query_purchase_invoices,
        "view": _purchase_invoices_view,
    },
    "returns_period": {
        "query": _query_returns_period,
        "view": _returns_period_view,
    },
    "party_totals": {"query": _query_party_totals, "view": _party_totals_view},
    "ledger_account": {
        "query": _query_ledger_account,
        "view": _ledger_account_view,
    },
    "vat_summary": {
        "query": _query_vat_summary,
        "view": _vat_summary_view,
    },
    "chain_sales": {"query": _query_chain_sales, "view": _chain_sales_view},
}


def get_entry(code: str) -> dict | None:
    """The registry row for a catalog code (None = no engine behind it)."""
    return REGISTRY.get(code)
