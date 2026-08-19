"""A4 printable receivables page (S2.4, ticket #19).

Same black-on-white A4 convention as the statement/payables pages (RTL
Arabic-first, brand accent in the header only). Takes the same JSON payload the
endpoint returns.
"""
from __future__ import annotations

import html

from app.sales.print_html import BRAND_ACCENT


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def render_receivables(payload: dict) -> str:
    meta = [("إجمالي المستحق للفروع", payload["total"])]
    columns = ["العميل", "النوع", "الحد الائتماني", "رصيد العميل"]
    rows = [
        [
            f"{r['namee']} ({r['name_ar']})" if r["name_ar"] else r["namee"],
            r["kind"],
            r["credit_limit"],
            r["balance"],
        ]
        for r in payload["receivables"]
    ]
    foot = ["الإجمالي", "", "", payload["total"]]
    head = "".join(f"<th>{_e(c)}</th>" for c in columns)
    body_rows = "\n".join(
        "<tr>"
        + "".join(
            f"<td class='num'>{_e(v)}</td>" if i else f"<td>{_e(v)}</td>"
            for i, v in enumerate(row)
        )
        + "</tr>"
        for row in rows
    )
    foot_html = (
        "<tfoot><tr>"
        + "".join(
            f"<td class='num'>{_e(v)}</td>" if i else f"<td>{_e(v)}</td>"
            for i, v in enumerate(foot)
        )
        + "</tr></tfoot>"
    )
    body = (
        f"<table class='data'><thead><tr>{head}</tr></thead>"
        f"<tbody>{body_rows}</tbody>{foot_html}</table>"
    )
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>{_e('أرصدة العملاء')}</title>
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
    <div class="title">{_e('أرصدة العملاء (المستحق)')}</div>
    <div class="muted">Customer Receivables — S2.4</div>
  </div>
  <table class="meta">
    <tr><td class="muted">إجمالي المستحق</td><td class="val">{_e(payload["total"])}</td></tr>
  </table>
  {body}
  <div class="footer">أرصدة العملاء PharmaTag — S2.4</div>
</body>
</html>"""