"""The ONE generic report page renderer (S3.1, ticket #23; plan/09 P06).

Every catalog report prints through `render_report_page`: black-on-white
regardless of theme, RTL Arabic-first, brand accent in the header only,
`@page size` driven by the catalog's paper (A4/A5). Input is a plain
JSON-safe grid spec — `{meta, columns, rows, foot, note}` — so exports
(xlsx/pdf) and the web ReportView consume the exact same shape.
"""
from __future__ import annotations

import html

from app.sales.print_html import BRAND_ACCENT

PAPERS = ("A4", "A5")


def e(value) -> str:
    """Escape any cell/label for HTML."""
    return html.escape(str(value), quote=True)


def render_report_page(
    *,
    title_ar: str,
    title_en: str,
    meta: list[tuple[str, str]],
    columns: list[str],
    rows: list[list[str]],
    foot: list[str] | None = None,
    note: str | None = None,
    paper: str = "A4",
) -> str:
    """Render one report as a printable black-on-white page."""
    meta_rows = "\n".join(
        f'<tr><td class="muted">{e(label)}</td>'
        f'<td class="val">{e(value)}</td></tr>'
        for label, value in meta
    )
    body = _table(columns=columns, rows=rows, foot=foot)
    if note:
        body += f"<p class='muted' style='margin-top:3mm;'>{e(note)}</p>"
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>{e(title_ar)}</title>
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
  @page {{ size: {paper} portrait; margin: 10mm; }}
  @media print {{ body {{ max-width: none; margin: 0; padding: 0; }} }}
</style>
</head>
<body>
  <div class="header">
    <div class="brand">فارما تاج — PharmaTag</div>
    <div class="title">{e(title_ar)}</div>
    <div class="muted">{e(title_en)}</div>
  </div>
  <table class="meta">{meta_rows}</table>
  {body}
  <div class="footer">تقرير PharmaTag</div>
</body>
</html>"""


def _table(
    *, columns: list[str], rows: list[list[str]], foot: list[str] | None = None
) -> str:
    head = "".join(f"<th>{e(c)}</th>" for c in columns)
    body_rows = "\n".join(
        "<tr>"
        + "".join(
            f"<td class='num'>{e(v)}</td>" if i else f"<td>{e(v)}</td>"
            for i, v in enumerate(row)
        )
        + "</tr>"
        for row in rows
    )
    foot_html = (
        "<tfoot><tr>"
        + "".join(
            f"<td class='num'>{e(v)}</td>" if i else f"<td>{e(v)}</td>"
            for i, v in enumerate(foot)
        )
        + "</tr></tfoot>"
        if foot
        else ""
    )
    return (
        f"<table class='data'><thead><tr>{head}</tr></thead>"
        f"<tbody>{body_rows}</tbody>{foot_html}</table>"
    )
