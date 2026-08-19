"""A4 printable report pages (S1.9, ticket #15; plan/09 P06).

Tabular reports render black-on-white for physical print (RTL Arabic-first,
brand accent in the header only). Each render function takes the same JSON
payload the endpoint returns and formats it as a printable HTML page; the full
PDF/Excel framework is the S3.1 slice (ticket #23).
"""
from __future__ import annotations

import html

from app.sales.print_html import BRAND_ACCENT


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _page(*, title_ar: str, title_en: str, meta: list[tuple[str, str]], body: str) -> str:
    meta_rows = "\n".join(
        f'<tr><td class="muted">{_e(label)}</td>'
        f'<td class="val">{_e(value)}</td></tr>'
        for label, value in meta
    )
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>{_e(title_ar)}</title>
<style>
  :root {{ --accent: {BRAND_ACCENT}; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Thmanyah', 'Segoe UI', Tahoma, sans-serif;
    color: #000; background: #fff; max-width: 210mm; margin: 0 auto;
    padding: 8mm; font-size: 12px; line-height: 1.5;
  }}
  .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 3mm; margin-bottom: 4mm; }}
  .brand {{ color: var(--accent); font-weight: 700; font-size: 18px; }}
  .title {{ font-size: 15px; font-weight: 700; margin-top: 2mm; }}
  .meta {{ width: 100%; border-collapse: collapse; margin-bottom: 4mm; }}
  .meta td {{ padding: 1px 2mm; }}
  .meta .val {{ text-align: left; }}
  .muted {{ color: #333; }}
  table.data {{ width: 100%; border-collapse: collapse; }}
  table.data th, table.data td {{ padding: 1.5mm 2mm; border: 1px solid #000; text-align: right; }}
  table.data th {{ background: #f2f0f7; }}
  .num {{ text-align: left; white-space: nowrap; }}
  tfoot td {{ font-weight: 700; }}
  .footer {{ text-align: center; margin-top: 6mm; border-top: 1px solid #000; padding-top: 2mm; font-size: 11px; }}
  @media print {{ body {{ max-width: none; margin: 0; padding: 2mm; }} }}
</style>
</head>
<body>
  <div class="header">
    <div class="brand">فارما تاج — PharmaTag</div>
    <div class="title">{_e(title_ar)}</div>
    <div class="muted">{_e(title_en)}</div>
  </div>
  <table class="meta">{meta_rows}</table>
  {body}
  <div class="footer">تقرير PharmaTag — تقرير أساسي S1.9</div>
</body>
</html>"""


def _table(*, columns: list[str], rows: list[list[str]], foot: list[str] | None = None) -> str:
    head = "".join(f"<th>{_e(c)}</th>" for c in columns)
    body_rows = "\n".join(
        "<tr>" + "".join(f"<td class='num'>{_e(v)}</td>" if i else f"<td>{_e(v)}</td>" for i, v in enumerate(row)) + "</tr>"
        for row in rows
    )
    foot_html = (
        "<tfoot><tr>"
        + "".join(f"<td class='num'>{_e(v)}</td>" if i else f"<td>{_e(v)}</td>" for i, v in enumerate(foot))
        + "</tr></tfoot>"
        if foot
        else ""
    )
    return f"<table class='data'><thead><tr>{head}</tr></thead><tbody>{body_rows}</tbody>{foot_html}</table>"


def render_day_profit(payload: dict) -> str:
    meta = [
        ("التاريخ", payload["datee"]),
        ("عدد فواتير البيع", payload["sales_count"]),
        ("عدد مرتجعات البيع", payload["sales_returns_count"]),
    ]
    labels = [
        ("صافي المبيعات", "sales_net"),
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
    rows = "\n".join(
        f'<tr><td>{_e(label)}</td><td class="num">{_e(payload[key])}</td></tr>'
        for label, key in labels
    )
    body = f"""<table class="data">
      <thead><tr><th>البيان</th><th class="num">القيمة</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>"""
    return _page(title_ar="ربح اليوم", title_en="Day Profit", meta=meta, body=body)


def render_period_totals(payload: dict) -> str:
    meta = [
        ("من تاريخ", payload["date_from"] or "—"),
        ("إلى تاريخ", payload["date_to"] or "—"),
    ]
    kinds = payload["kinds"]
    columns = ["البيان", "عدد الفواتير", "الإجمالي", "الضريبة", "الخصم"]
    rows = [
        ["المبيعات", kinds["sale"]["count"], kinds["sale"]["total"], kinds["sale"]["vat"], kinds["sale"]["discount"]],
        ["مرتجع المبيعات", kinds["sale_return"]["count"], kinds["sale_return"]["total"], kinds["sale_return"]["vat"], kinds["sale_return"]["discount"]],
        ["المشتريات", kinds["purchase"]["count"], kinds["purchase"]["total"], kinds["purchase"]["vat"], kinds["purchase"]["discount"]],
        ["مرتجع المشتريات", kinds["purchase_return"]["count"], kinds["purchase_return"]["total"], kinds["purchase_return"]["vat"], kinds["purchase_return"]["discount"]],
    ]
    foot = ["الصافي", "", payload["net_sales"], payload["net_vat_sales"], payload["net_discounts"]]
    body = _table(columns=columns, rows=rows, foot=foot)
    return _page(title_ar="ملخص المبيعات والمشتريات", title_en="Sales & Purchases Summary", meta=meta, body=body)


def render_stock_minimum(payload: dict) -> str:
    meta = [("عدد الأصناف الأقل من الحد الأدنى", payload["count"])]
    columns = ["الصنف", "الباركود", "الرصيد", "الحد الأدنى", "العجز", "السعر"]
    rows = [
        [
            f"{item['drugname']} ({item['drugnamear']})" if item["drugnamear"] else item["drugname"],
            item["barcode"] or "—",
            item["qty"],
            item["minimum"],
            item["shortage"],
            item["price"],
        ]
        for item in payload["items"]
    ]
    body = _table(columns=columns, rows=rows)
    return _page(title_ar="النواقص (أقل من الحد الأدنى)", title_en="Stock Below Minimum", meta=meta, body=body)


def render_drawer_handover(payload: dict) -> str:
    meta = [
        ("من تاريخ", payload["date_from"] or "—"),
        ("إلى تاريخ", payload["date_to"] or "—"),
    ]
    columns = ["الكاشير", "فتح", "كاش مبيعات", "شبكة مبيعات", "مرتجعات", "مصروفات", "صافي كاش"]
    rows = [
        [
            cashier["name"],
            cashier["opening_in"],
            cashier["cash_sales_in"],
            cashier["card_sales_in"],
            cashier["returns_out"],
            cashier["expenses_out"],
            cashier["net_cash"],
        ]
        for cashier in payload["cashiers"]
    ]
    totals = payload["totals"]
    foot = ["الإجمالي", totals["opening_in"], totals["cash_sales_in"], totals["card_sales_in"], totals["returns_out"], totals["expenses_out"], ""]
    body = _table(columns=columns, rows=rows, foot=foot)
    return _page(title_ar="تسليم الدرج", title_en="Drawer Handover", meta=meta, body=body)
