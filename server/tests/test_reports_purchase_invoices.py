"""S3.4 purchase-invoice register (ticket #26): RPT-P01 (+EDA batch/expiry).

فواتير المشتريات lists purchase lines over a date range — invoice, supplier,
drug, qty, discounted net unit cost, VAT amount, line total and the created
batch's randomid + expiry (EDTS traceability columns) — with a summary that
ties to period_totals' purchase kind and the journal's stock+input-VAT debit
legs.
"""
from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.core.time import business_date
from app.models import Account, Journal, JournalLine, Party

from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def _make_supplier(client, token: str) -> int:
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "supplier", "namee": "t2 s34 supplier"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _drop_party(party_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == party_id))
        await session.commit()


async def _purchase_journal_legs(account_code: str, invoice_ids: list[int]) -> str:
    """Σdebit on an account code over this test's purchase journals."""
    async with SessionLocal() as session:
        account_id = (
            await session.execute(
                select(Account.id).where(
                    Account.branch_id == 1, Account.code == account_code
                )
            )
        ).scalar_one()
        total = (
            await session.execute(
                select(func.coalesce(func.sum(JournalLine.debit), 0)).where(
                    JournalLine.account_id == account_id,
                    JournalLine.journal_id.in_(
                        select(Journal.id).where(
                            Journal.source == "purchase",
                            Journal.ref_invoice_id.in_(invoice_ids),
                        )
                    ),
                )
            )
        ).scalar_one()
        return f"{total:.2f}"


async def test_purchase_register_lists_lines_with_batches(client):
    """One purchase with two lines lists as two rows carrying batch + expiry;
    the summary ties to period_totals and the journal."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    supplier_id = None
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        supplier_id = await _make_supplier(client, token)

        p = await client.post(
            "/api/v1/purchases", headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [
                    {
                        "drug_id": drug_id,
                        "qty": "10",
                        "unit_cost": "4.0000",
                        "expire": "2027-06-30",
                    },
                    {
                        "drug_id": drug_id,
                        "qty": "5",
                        "unit_cost": "2.0000",
                        "expire": "2027-12-31",
                    },
                ],
            },
        )
        assert p.status_code == 201, p.text
        purchase = p.json()
        invoice_ids.append(purchase["id"])
        assert purchase["totalvalue"] == "57.00"

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/purchase_invoices",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        assert len(body["rows"]) == 2
        first = body["rows"][0]
        assert first["invoice_no"] == purchase["invoice_no"]
        assert first["datee"] == today
        assert first["supplier_namee"] == "t2 s34 supplier"
        assert first["qty"] == "10.0000"
        assert first["unit_cost"] == "4.0000"
        assert first["expire"] == "2027-06-30"
        assert first["batch_randomid"]
        second = body["rows"][1]
        assert second["qty"] == "5.0000"
        assert second["unit_cost"] == "2.0000"
        assert second["expire"] == "2027-12-31"
        assert second["batch_randomid"] != first["batch_randomid"]

        assert body["totals"]["line_count"] == 2
        assert body["totals"]["invoice_count"] == 1
        assert body["totals"]["total"] == "57.00"
        assert body["totals"]["vat"] == "7.00"

        pt = await client.get(
            "/api/v1/reports/period_totals",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert body["totals"]["total"] == pt.json()["kinds"]["purchase"]["total"]

        stock = await _purchase_journal_legs("1200", invoice_ids)
        vat = await _purchase_journal_legs("2100", invoice_ids)
        from decimal import Decimal

        assert Decimal(body["totals"]["total"]) == Decimal(stock) + Decimal(vat)
    finally:
        await _cleanup([drug_id], invoice_ids)
        if supplier_id:
            await _drop_party(supplier_id)
