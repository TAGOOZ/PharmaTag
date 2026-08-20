"""A4 printable ميزان pages (S2.5, issue #20).

Same black-on-white A4 convention as the statements/reports pages (RTL
Arabic-first, brand accent in the header only). Each render takes the same JSON
payload the endpoint returns.
"""
from __future__ import annotations

import html

from app.sales.print_html import BRAND_ACCENT


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _period_text(period: dict) -> str:
    if period["month"] is not None:
        return f"{period['month']} / {period['year']}"
    return f"{period['date_from']} → {period['date_to']}"


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
  table.data {{ width: 100%; border-collapse: collapse; margin-bottom: 3mm; }}
  table.data th, table.data td {{ padding: 1.5mm 2mm; border: 1px solid #000; text-align: right; }}
  table.data th {{ background: #f2f0f7; }}
  .num {{ text-align: left; white-space: nowrap; }}
  tfoot td {{ font-weight: 700; }}
  .section {{ font-size: 13px; font-weight: 700; margin: 4mm 0 2mm; }}
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
  <div class="footer">ميزان PharmaTag — S2.5</div>
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


def render_trial_balance(payload: dict) -> str:
    period = payload["period"]
    meta = [
        ("الفترة", _period_text(period)),
        ("الفرع", payload["branch_id"]),
        ("رصيد مدين", payload["totals"]["closing_debit"]),
        ("رصيد دائن", payload["totals"]["closing_credit"]),
        ("متوازن", "نعم" if payload["balanced"] else "لا"),
    ]
    columns = ["الكود", "الحساب", "افتتاحي مدين", "افتتاحي دائن", "مدين", "دائن", "ختامي مدين", "ختامي دائن"]
    rows = [
        [
            r["code"],
            r["name_ar"] or r["name_en"],
            r["opening_debit"],
            r["opening_credit"],
            r["debit"],
            r["credit"],
            r["closing_debit"],
            r["closing_credit"],
        ]
        for r in payload["accounts"]
    ]
    t = payload["totals"]
    foot = [
        "الإجمالي",
        "",
        t["opening_debit"],
        t["opening_credit"],
        t["debit"],
        t["credit"],
        t["closing_debit"],
        t["closing_credit"],
    ]
    return _page(
        title_ar="ميزان المراجعة",
        title_en="Trial Balance",
        meta=meta,
        body=_table(columns=columns, rows=rows, foot=foot),
    )


def _section_table(section: dict) -> str:
    columns = ["الكود", "الحساب", "رصيد"]
    rows = [
        [r["code"], r["name_ar"] or r["name_en"], r["amount"]]
        for r in section["accounts"]
    ]
    foot = ["الإجمالي", "", section["total"]] if section["accounts"] else None
    return _table(columns=columns, rows=rows, foot=foot)


def render_balance_sheet(payload: dict) -> str:
    period = payload["period"]
    meta = [
        ("الفترة", _period_text(period)),
        ("الفرع", payload["branch_id"]),
        ("إجمالي الأصول", payload["total_assets"]),
        ("إجمالي الخصوم + حقوق الملكية", payload["total_liabilities_equity"]),
        ("صافي الربح / الخسارة", payload["net_income"]),
    ]
    body = (
        f"<div class='section'>الأصول (Assets)</div>{_section_table(payload['assets'])}"
        f"<div class='section'>الخصوم (Liabilities)</div>{_section_table(payload['liabilities'])}"
        f"<div class='section'>حقوق الملكية (Equity)</div>{_section_table(payload['equity'])}"
    )
    return _page(
        title_ar="ميزانية عمومية",
        title_en="Balance Sheet",
        meta=meta,
        body=body,
    )