"""Printable tax documents (S4.1, #28 AC4) — the four legacy template kinds
via the print_html pattern (80mm thermal / A5, black-on-white, RTL
Arabic-first, brand accent only in the header):

* فاتورة ضريبية  — B2B tax invoice (kind=invoice/credit_note)
* فاتورة مبسطة   — simplified receipt (cash/walk-in sale)
* فاتورة أجل      — deferred-payment variant (agel > 0, unregistered party)
* فاتورة مرتجع    — return (receipt 'r' or credit note 'C')

Every variant carries the QR (data-URI PNG linking the ETA consumer
verification page), the seller RIN/branch block, the internal invoice_no +
tax-document counter, and a VAT breakdown by rate that reconciles to the
invoice's VAT column.
"""
from __future__ import annotations

import html
from decimal import Decimal
from typing import Any, Optional

from app.core.money import dec, format2
from app.einvoicing.toolkit import qr_png_data_uri
from app.models import Branch, EInvoiceLog, Invoice, InvoiceLine

BRAND_ACCENT = "#7c5cbf"


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def route_variant(invoice: Invoice, log: EInvoiceLog) -> str:
    """Which of the four template kinds prints for this invoice."""
    if invoice.kind == "sale_return":
        return "مرتجع"
    if log.kind in ("invoice", "credit_note"):
        return "ضريبية"
    if dec(invoice.agel) > 0:
        return "أجل"
    return "مبسطة"


TITLES = {
    "ضريبية": ("فاتورة ضريبية", "Tax Invoice"),
    "مبسطة": ("فاتورة مبسطة", "Simplified Tax Receipt"),
    "أجل": ("فاتورة أجل", "Deferred Payment Invoice"),
    "مرتجع": ("فاتورة مرتجع", "Return Invoice"),
}


def render_tax_document(
    *,
    branch_name: str,
    invoice_no: str,
    datee,
    cashier: str = "",
    variant: str,
    counter: int,
    status: str,
    qr_data: str,
    seller_rin: str,
    seller_trade_name: str,
    branch_code: str,
    device_serial: str = "",
    buyer_name: str = "",
    buyer_tax_registration_no: str = "",
    reference_invoice_no: str = "",
    lines: list[dict],
    subtotal: Any,
    discount: Any,
    vat: Any,
    totalvalue: Any,
    payed: Any,
    agel: Any,
) -> str:
    """Render one printable A5/80mm tax document."""
    title_ar, title_en = TITLES[variant]
    rows = "\n".join(
        f"""<tr>
            <td class="name">{_e(l['description'])}</td>
            <td class="num">{_e(l['qty'])}</td>
            <td class="num">{_e(l['unit_price'])}</td>
            <td class="num">{_e(l['vat_amount'])}</td>
            <td class="num">{_e(l['line_total'])}</td>
          </tr>"""
        for l in lines
    )
    vat_rows = "\n".join(
        f"""<tr>
            <td class="label">ضريبة {_e(rate)}</td>
            <td class="label">صافي {format2(net)}</td>
            <td class="val">{format2(amount)}</td>
          </tr>"""
        for rate, net, amount in _vat_breakdown(lines)
    )
    qr_img = ""
    if qr_data:
        qr_img = (
            f'<img src="{qr_png_data_uri(qr_data)}" alt="QR" '
            f'width="110" height="110">'
        )

    buyer_block = ""
    if buyer_tax_registration_no or buyer_name:
        buyer_block = (
            f"<tr><td>العميل</td><td>{_e(buyer_name)}</td></tr>"
            f"<tr><td>السجل التجاري للعميل</td><td>"
            f"{_e(buyer_tax_registration_no)}</td></tr>"
        )

    reference_block = (
        f'<tr><td>مرتجع للفاتورة</td><td>{_e(reference_invoice_no)}</td></tr>'
        if reference_invoice_no
        else ""
    )
    status_ar = {
        "pending": "معلقة (بانتظار الرفع)",
        "submitted": "مرفوعة",
        "accepted": "مقبولة",
        "rejected": "مرفوضة",
        "failed": "فشل الرفع",
    }.get(status, status)

    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>{_e(title_ar)} {_e(invoice_no)}</title>
<style>
  :root {{ --accent: {BRAND_ACCENT}; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Thmanyah', 'Segoe UI', Tahoma, sans-serif;
    color: #000; background: #fff; width: 80mm; margin: 0 auto;
    padding: 4mm; font-size: 11px; line-height: 1.45;
  }}
  .header {{ text-align: center; border-bottom: 1px dashed #000;
             padding-bottom: 2mm; margin-bottom: 2mm; }}
  .brand {{ color: var(--accent); font-weight: 700; font-size: 15px; }}
  .title {{ font-weight: 700; font-size: 13px; margin-top: 1mm; }}
  .muted {{ color: #444; font-size: 10px; }}
  table.meta {{ width: 100%; border-collapse: collapse; margin-bottom: 2mm; }}
  table.meta td {{ padding: 1px 0; vertical-align: top; }}
  table.items {{ width: 100%; border-collapse: collapse; }}
  table.items th, table.items td {{ padding: 1mm; border-bottom: 1px dotted #000;
                                    text-align: right; }}
  table.items th {{ border-bottom: 1px solid #000; }}
  .num {{ text-align: left; white-space: nowrap; }}
  .name {{ max-width: 30mm; overflow-wrap: anywhere; }}
  table.totals {{ width: 100%; border-collapse: collapse; margin-top: 2mm; }}
  table.totals td {{ padding: 1mm; }}
  .totals .label {{ text-align: right; }}
  .totals .val {{ text-align: left; }}
  .grand {{ font-weight: 700; font-size: 13px; border-top: 1px solid #000; }}
  .vatbox {{ border: 1px dashed #000; padding: 1.5mm; margin-top: 2mm;
             font-size: 10px; }}
  .qr {{ text-align: center; margin-top: 2mm; }}
  .footer {{ text-align: center; margin-top: 3mm; border-top: 1px dashed #000;
             padding-top: 2mm; font-size: 10px; }}
  @media print {{ body {{ width: 80mm; margin: 0; }} @page {{ size: 80mm auto;
                   margin: 2mm; }} }}
</style>
</head>
<body>
  <div class="header">
    <div class="brand">فارما تاج</div>
    <div class="tagline muted">PharmaTag</div>
    <div>{_e(seller_trade_name or branch_name)}</div>
    <div class="title">{_e(title_ar)} — {_e(title_en)}</div>
  </div>

  <table class="meta">
    <tr><td>رقم الفاتورة</td><td class="num">{_e(invoice_no)}</td></tr>
    <tr><td>رقم المستند</td><td class="num">{int(counter)}</td></tr>
    <tr><td>التاريخ</td><td class="num">{_e(datee)}</td></tr>
    {f'<tr><td>الكاشير</td><td class="num">{_e(cashier)}</td></tr>' if cashier else ""}
    {reference_block}
    <tr><td>حالة المستند</td><td class="num">{_e(status_ar)}</td></tr>
  </table>

  <table class="meta">
    <tr><td class="muted">السجل الضريبي (RIN)</td><td class="num">{_e(seller_rin)}</td></tr>
    <tr><td class="muted">كود الفرع الضريبي</td><td class="num">{_e(branch_code)}</td></tr>
    <tr><td class="muted">الفرع</td><td class="num">{_e(branch_name)}</td></tr>
    {buyer_block}
  </table>

  <table class="items">
    <thead>
      <tr><th>الصنف</th><th class="num">الكمية</th><th class="num">السعر</th>
          <th class="num">الضريبة</th><th class="num">الإجمالي</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <table class="totals">
    <tr><td class="label">الإجمالي قبل الخصم</td><td class="val">{format2(subtotal)}</td></tr>
    <tr><td class="label">الخصم</td><td class="val">{format2(discount)}</td></tr>
    <tr><td class="label">ضريبة القيمة المضافة</td><td class="val">{format2(vat)}</td></tr>
    <tr class="grand"><td class="label">الإجمالي</td><td class="val">{format2(totalvalue)}</td></tr>
    <tr><td class="label">مدفوع</td><td class="val">{format2(payed)}</td></tr>
    <tr><td class="label">آجل</td><td class="val">{format2(agel)}</td></tr>
  </table>

  <div class="vatbox">
    <div><b>تفاصيل الضريبة حسب النسبة</b></div>
    <table style="width:100%">
      {vat_rows}
    </table>
  </div>

  <div class="qr">
    {qr_img}
    <div class="muted">امسح للتحقق من الفاتورة لدى مصلحة الضرائب المصرية</div>
  </div>

  <div class="footer">
    {_e(title_ar)} — PharmaTag فارما تاج
    {f'<div class="muted">جهاز نقاط البيع: {_e(device_serial)}</div>' if device_serial else ""}
  </div>
</body>
</html>"""


def _vat_breakdown(lines: list[dict]) -> list[tuple[str, Decimal, Decimal]]:
    """Per-rate (net, vat) pairs ordered exempt→5%→14%, reconciling to Σ VAT."""
    order = {
        "exempt": ("معفاة / 0%", 0),
        "5%": ("5%", 1),
        "14%": ("14%", 2),
    }
    buckets: dict[str, tuple[Decimal, Decimal]] = {}
    for l in lines:
        net, vat = buckets.get(l["tax_type"], (Decimal("0"), Decimal("0")))
        buckets[l["tax_type"]] = (
            net + dec(l["net"]),
            vat + dec(l["vat_amount"]),
        )
    out = []
    for tax_type, (_, pos) in sorted(order.items(), key=lambda kv: kv[1][1]):
        if tax_type in buckets:
            net, vat = buckets[tax_type]
            out.append((order[tax_type][0], net, vat))
    return out
