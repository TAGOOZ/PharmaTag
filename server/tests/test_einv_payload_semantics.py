"""S4.1 payload semantics (review F1): itemData lines must carry ETA's
receipt-base-structure meaning — netSale = post-discount PRE-tax base,
total = netSale + taxes — regardless of the branch's pricing mode. Header
netAmount = Σ netSale and totalAmount = Σ total stay coherent one level up.
"""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import EInvoiceLog
from tests.einv_test_utils import (
    _clear_rin,
    _make_user,
    _set_rin,
    _uniq,
)
from tests.sales_test_utils import _token_for
from tests.test_einv_issue import _cleanup
from tests.returns_test_utils import (
    _make_branch,
    _make_drug_and_stock_branch,
)


async def _log_for(invoice_id: int) -> EInvoiceLog:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
            )
        ).scalar_one()


async def test_inclusive_line_net_is_pretax_total_is_paid(client):
    """VAT-inclusive retail: 114.00 paid @14% → netSale 100.00, total 114.00;
    with a 10% discount → netSale 90.00, total 102.60."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, tax_type="14%", price="114.0000", stock_qty="5.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        log = await _log_for(invoice_ids[0])
        line = log.payload_json["itemData"][0]
        assert line["netSale"] == "100.00"
        assert line["total"] == "114.00"

        r2 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "disc_percent": "10",
            },
        )
        assert r2.status_code == 201, r2.text
        invoice_ids.append(r2.json()["id"])
        line2 = (await _log_for(invoice_ids[1])).payload_json["itemData"][0]
        assert line2["netSale"] == "90.00"
        assert line2["total"] == "102.60"
        doc = (await _log_for(invoice_ids[1])).payload_json
        assert doc["netAmount"] == "90.00"
        assert doc["totalAmount"] == "102.60"
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_exclusive_line_net_equals_linetotal_total_adds_vat(client):
    """VAT-exclusive wholesale: 100.00 @14% → netSale 100.00 (already ex-VAT),
    total 114.00; header netAmount Σ netSale, totalAmount Σ total."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=False)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, tax_type="14%", price="100.0000", stock_qty="5.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        doc = (await _log_for(invoice_ids[0])).payload_json
        line = doc["itemData"][0]
        assert line["netSale"] == "100.00"
        assert line["total"] == "114.00"
        assert doc["netAmount"] == "100.00"
        assert doc["totalAmount"] == "114.00"
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)
