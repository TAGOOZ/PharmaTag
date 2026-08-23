"""S4.1 review fixes: a return's regime follows the ORIGINAL document's kind,
never the party's current tax-registration state (ADR-0002 decision 1).

* returning a cash receipt issued to a now-registered party → return_receipt
* returning a B2B invoice after the party's RIN was cleared → credit_note

Both mismatches would otherwise produce fiscal rows ETA structurally rejects
at submission (S4.2).
"""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import EInvoiceLog, Party
from tests.einv_test_utils import (
    _clear_rin,
    _make_tax_party,
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


async def test_return_of_receipt_stays_return_receipt_even_if_party_registered(client):
    """A CASH sale to a tax-registered party issues a receipt (agel == 0);
    returning it must issue a RETURN RECEIPT — a credit note may only correct
    a B2B invoice."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("u"), branch_id)
    rin_party = await _make_tax_party(branch_id, rin="300123456")
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        r_sale = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"party_id": rin_party, "lines": [{"drug_id": drug_id, "qty": "2"}]},
        )
        assert r_sale.status_code == 201, r_sale.text
        sale = r_sale.json()
        invoice_ids.append(sale["id"])
        orig_log = await _log_for(sale["id"])
        assert orig_log.kind == "receipt"  # cash sale → eReceipt even w/ RIN

        line_id = sale["lines"][0]["id"]
        r_ret = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
        )
        assert r_ret.status_code == 201, r_ret.text
        ret = r_ret.json()
        invoice_ids.append(ret["id"])

        ret_log = await _log_for(ret["id"])
        assert ret_log.kind == "return_receipt"
        assert ret_log.reference_uuid == orig_log.uuid
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_return_of_b2b_invoice_is_credit_note_even_if_rin_cleared(client):
    """A deferred sale to a registered party issues a B2B invoice; its return
    must be a CREDIT NOTE referencing that invoice — even if the party's RIN
    field was cleared (or the party deleted) before the return."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, price="100.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    rin_party = await _make_tax_party(branch_id, rin="300654321")
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        r_sale = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": rin_party,
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "payments": [{"method": "credit", "amount": "100.00"}],
            },
        )
        assert r_sale.status_code == 201, r_sale.text
        sale = r_sale.json()
        invoice_ids.append(sale["id"])
        orig_log = await _log_for(sale["id"])
        assert orig_log.kind == "invoice"

        # the party's registration disappears before the return
        async with SessionLocal() as session:
            party = await session.get(Party, rin_party)
            party.tax_registration_no = ""
            await session.commit()

        line_id = sale["lines"][0]["id"]
        r_ret = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
        )
        assert r_ret.status_code == 201, r_ret.text
        ret = r_ret.json()
        invoice_ids.append(ret["id"])

        ret_log = await _log_for(ret["id"])
        assert ret_log.kind == "credit_note"
        assert ret_log.reference_uuid == orig_log.uuid
        # the credit note carries the SAME buyer as the document it corrects —
        # ETA matches C→I pairs by buyer + referenceUUID, so reading the live
        # party row (whose RIN was just cleared) would break the pair
        assert ret_log.payload_json["buyer"] == orig_log.payload_json["buyer"]
        assert ret_log.payload_json["buyer"]["id"] == "300654321"
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)
