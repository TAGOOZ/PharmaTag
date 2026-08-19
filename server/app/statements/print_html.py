"""A4 printable statement / payables pages (S2.3, issue #18).

Same black-on-white A4 convention as the reports (RTL Arabic-first, brand
accent in the header only). Each render takes the same JSON payload the
endpoint returns.
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
  <div class="footer">كشف حساب PharmaTag — S2.3</div>
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


def render_statement(payload: dict) -> str:
    party = payload["party"]
    period = payload["period"]
    if period["date_from"] is not None:
        meta = [
            ("الطرف", f"{party['namee']} ({party['name_ar']})" if party["name_ar"] else party["namee"]),
            ("النوع", party["kind"]),
            ("من تاريخ", period["date_from"]),
            ("إلى تاريخ", period["date_to"]),
            ("الحساب", f"{payload['account_code']} — {payload['account_name']}"),
            ("الرصيد الافتتاحي", payload["opening_balance"]),
        ]
    else:
        meta = [
            ("الطرف", f"{party['namee']} ({party['name_ar']})" if party["name_ar"] else party["namee"]),
            ("النوع", party["kind"]),
            ("الشهر", f"{period['month']} / {period['year']}"),
            ("الحساب", f"{payload['account_code']} — {payload['account_name']}"),
            ("الرصيد الافتتاحي", payload["opening_balance"]),
        ]
    columns = ["التاريخ", "البيان", "الحساب", "مدين", "دائن", "الرصيد"]
    rows = [
        [
            m["datee"],
            m["description"],
            f"{m['account_code']} — {m['account_name']}",
            m["debit"],
            m["credit"],
            m["running_balance"],
        ]
        for m in payload["movements"]
    ]
    foot = [
        "الإجمالي",
        "",
        "",
        payload["debit_total"],
        payload["credit_total"],
        payload["closing_balance"],
    ]
    body = _table(columns=columns, rows=rows, foot=foot)
    if not rows:
        body += (
            "<p class='muted' style='margin-top:3mm;'>لا توجد حركات خلال الفترة.</p>"
        )
    return _page(title_ar="كشف حساب", title_en="Account Statement", meta=meta, body=body)


def render_payables(payload: dict) -> str:
    meta = [("إجمالي المستحق للموردين", payload["total"])]
    columns = ["المورد", "النوع", "رصيد المورد"]
    rows = [
        [
            f"{r['namee']} ({r['name_ar']})" if r["name_ar"] else r["namee"],
            r["kind"],
            r["balance"],
        ]
        for r in payload["payables"]
    ]
    foot = ["الإجمالي", "", payload["total"]]
    body = _table(columns=columns, rows=rows, foot=foot)
    return _page(
        title_ar="أرصدة الموردين (المستحق)", title_en="Supplier Payables", meta=meta, body=body
    )