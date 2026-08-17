"""80mm thermal receipt renderer for sales invoices (plan/02 §print, P06).

Black-on-white for physical print, RTL Arabic-first, PharmaTag brand accent
(#7c5cbf light) used only for the header so it stays legible on thermal paper.
A5-friendly when printed on plain paper.
"""
from __future__ import annotations

import html
from datetime import date
from typing import Optional

BRAND_ACCENT = "#7c5cbf"


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def render_invoice_print(
    *,
    branch_name: str,
    invoice_no: str,
    datee: date,
    cashier: str,
    lines: list[dict],
    subtotal: str,
    discount: str,
    vat: str,
    totalvalue: str,
    payed: str,
    agel: str,
    status: str = "saved",
) -> str:
    rows = "\n".join(
        f"""<tr>
            <td class="name">{_e(l.get('drugname') or l.get('drugnamear') or '')}</td>
            <td class="num">{_e(l.get('qty', ''))}</td>
            <td class="num">{_e(l.get('unit_price', ''))}</td>
            <td class="num">{_e(l.get('line_total', ''))}</td>
          </tr>"""
        for l in lines
    )
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>فاتورة {_e(invoice_no)}</title>
<style>
  :root {{ --accent: {BRAND_ACCENT}; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Thmanyah', 'Segoe UI', Tahoma, sans-serif;
    color: #000; background: #fff; width: 80mm; margin: 0 auto;
    padding: 4mm; font-size: 11px; line-height: 1.45;
  }}
  .header {{ text-align: center; border-bottom: 1px dashed #000; padding-bottom: 2mm; margin-bottom: 2mm; }}
  .brand {{ color: var(--accent); font-weight: 700; font-size: 15px; }}
  .tagline {{ font-size: 10px; color: #000; }}
  .meta {{ width: 100%; border-collapse: collapse; margin-bottom: 2mm; }}
  .meta td {{ padding: 1px 0; }}
  table.items {{ width: 100%; border-collapse: collapse; }}
  table.items th, table.items td {{ padding: 1mm 1mm; border-bottom: 1px dotted #000; text-align: right; }}
  table.items th {{ border-bottom: 1px solid #000; }}
  .num {{ text-align: left; white-space: nowrap; }}
  .totals {{ width: 100%; border-collapse: collapse; margin-top: 2mm; }}
  .totals td {{ padding: 1mm 1mm; }}
  .totals .label {{ text-align: right; }}
  .totals .val {{ text-align: left; }}
  .grand {{ font-weight: 700; font-size: 13px; border-top: 1px solid #000; }}
  .footer {{ text-align: center; margin-top: 3mm; border-top: 1px dashed #000; padding-top: 2mm; font-size: 10px; }}
  .muted {{ color: #444; }}
  @media print {{ body {{ width: 80mm; margin: 0; }} @page {{ size: 80mm auto; margin: 2mm; }} }}
</style>
</head>
<body>
  <div class="header">
    <div class="brand">فارما تاج</div>
    <div class="tagline">PharmaTag</div>
    <div class="muted">{_e(branch_name)}</div>
  </div>

  <table class="meta">
    <tr><td>رقم الفاتورة</td><td class="num">{_e(invoice_no)}</td></tr>
    <tr><td>التاريخ</td><td class="num">{_e(datee)}</td></tr>
    <tr><td>الكاشير</td><td class="num">{_e(cashier)}</td></tr>
  </table>

  <table class="items">
    <thead>
      <tr><th>الصنف</th><th class="num">الكمية</th><th class="num">السعر</th><th class="num">الإجمالي</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <table class="totals">
    <tr><td class="label">الإجمالي قبل الضريبة</td><td class="val">{_e(subtotal)}</td></tr>
    <tr><td class="label">الخصم</td><td class="val">{_e(discount)}</td></tr>
    <tr><td class="label">الضريبة (VAT)</td><td class="val">{_e(vat)}</td></tr>
    <tr class="grand"><td class="label">الإجمالي</td><td class="val">{_e(totalvalue)}</td></tr>
    <tr><td class="label">مدفوع</td><td class="val">{_e(payed)}</td></tr>
    <tr><td class="label">متبقي</td><td class="val">{_e(agel)}</td></tr>
  </table>

  <div class="footer">
    {_e("فاتورة بيع — PharmaTag فارما تاج")}
    {f'<div class="muted">الحالة: {_e(status)}</div>' if status != "saved" else ""}
  </div>
</body>
</html>"""