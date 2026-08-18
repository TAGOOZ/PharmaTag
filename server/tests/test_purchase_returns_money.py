"""S1.6 purchase-return money invariants (ticket #12): the return reverses the
purchased batch qty + branch_stock, reduces supplier payable (AP) + refunds the
drawer, recomputes at the ORIGINAL line prices with proportional header
discount, and posts a balanced `purchase_return` journal — audit + outbox +
invoice_versions all atomic with the write.

Every money slice carries invariant tests (AGENTS.md): SUM(debit) ==
SUM(credit) per journal, and the invoice reconciles to the per-line VAT engine
(total = subtotal - discount, vat = Σ per-line vat, net = total - vat).
"""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Account, AuditLog, Invoice, InvoiceVersion, JournalLine, SyncLog
from tests.purchase_returns_test_utils import (
    _batches,
    _cleanup,
    _journal_source,
    _journal_totals,
    _login_token,
    _make_drug,
    _make_supplier,
    _purchase,
    _return,
    _stock_qty,
)


async def test_purchase_return_happy_path_money_invariants(client):
    """Return 4 of 10 × 10.00 (14%): net 35.09 / vat 4.91, batch decremented to
    6.0000, branch_stock down to 6.0000, journal balanced, audit + outbox + the
    original's version snapshot written."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        assert await _stock_qty(drug_id) == Decimal("10.0000")

        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])

        # money at the original prices: 4 × 10.00, 14% split
        assert ret["subtotal"] == "40.00"
        assert ret["discount"] == "0.00"
        assert ret["vat"] == "4.91"
        assert ret["totalvalue"] == "40.00"
        assert ret["net"] == "35.09"
        assert ret["payed"] == "40.00"
        assert ret["agel"] == "0.00"
        assert ret["party_id"] == supplier_id

        line = ret["lines"][0]
        assert line["qty"] == "4.0000"
        assert line["unit_price"] == "10.00"
        assert line["cost"] == "8.7720"  # the original batch's net unit cost
        assert line["vat_amount"] == "4.91"
        assert line["line_total"] == "40.00"

        # stock reversed: batch qty down, branch_stock down
        batches = await _batches(drug_id)
        assert len(batches) == 1
        assert batches[0].qty == Decimal("6.0000")
        assert await _stock_qty(drug_id) == Decimal("6.0000")

        # balanced reversal journal: Dr drawer 40 vs Cr stock 35.09 + VAT 4.91
        debit, credit = await _journal_totals(ret["id"])
        assert debit == Decimal("40.00")
        assert credit == Decimal("40.00")
        assert debit == credit, "SUM(debit) must equal SUM(credit)"
        assert await _journal_source(ret["id"]) == "purchase_return"

        # audit + outbox landed; original snapshotted into invoice_versions
        async with SessionLocal() as session:
            audits = (
                await session.execute(
                    select(AuditLog).where(AuditLog.branch_id == 1)
                )
            ).scalars().all()
            entities = {a.entity for a in audits}
            assert {
                "invoices",
                "invoice_lines",
                "journals",
                "stock_batches",
                "branch_stock",
                "parties",
            }.issubset(entities)
            outbox = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice",
                        SyncLog.entity_id == ret["id"],
                    )
                )
            ).scalars().all()
            assert len(outbox) == 1
            assert outbox[0].status == "pending"
            assert outbox[0].payload["kind"] == "purchase_return"
            assert outbox[0].payload["original_invoice_no"] == pur["invoice_no"]
            versions = (
                await session.execute(
                    select(InvoiceVersion).where(InvoiceVersion.invoice_id == pur["id"])
                )
            ).scalars().all()
            assert len(versions) == 1
            assert versions[0].action == "purchase_return"
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_credit_split_reduces_supplier_payable(client):
    """Original cash 60 + credit 40; a 40% return refunds 24 cash and reduces
    the supplier payable (AP) by 16 — the AP leg is a DEBIT carrying the
    supplier as contra_party (the mirror of the purchase's AP credit)."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id,
            [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
            payments=[{"method": "cash", "amount": "60.00"},
                      {"method": "credit", "amount": "40.00"}],
        )
        invoice_ids.append(pur["id"])

        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["totalvalue"] == "40.00"
        assert ret["payed"] == "24.00"
        assert ret["agel"] == "16.00"

        # exempt: net == total; journal Dr drawer 24 + Dr AP 16 = Cr stock 40
        debit, credit = await _journal_totals(ret["id"])
        assert debit == Decimal("40.00")
        assert credit == Decimal("40.00")
        assert debit == credit

        async with SessionLocal() as session:
            journal = (
                await session.execute(
                    select(JournalLine)
                    .join(Account, Account.id == JournalLine.account_id)
                    .where(
                        Account.code == "2000",
                        JournalLine.debit > 0,
                    )
                )
            ).scalars().all()
            assert len(journal) == 1
            assert journal[0].contra_party_id == supplier_id
            assert journal[0].debit == Decimal("16.00")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_explicit_payments_override(client):
    """Client-provided payments override the proportional mirror."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur,
            [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}],
            payments=[{"method": "credit", "amount": "40.00"}],
        )
        invoice_ids.append(ret["id"])
        assert ret["totalvalue"] == "40.00"
        assert ret["payed"] == "0.00"
        assert ret["agel"] == "40.00"
        assert [p["method"] for p in ret["payments"]] == ["credit"]
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_explicit_payments_mismatch_rejected(client):
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        r = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}],
                "payments": [{"method": "cash", "amount": "1.00"}],
            },
        )
        assert r.status_code == 400
        assert "payment total does not match" in r.json()["detail"]
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_full_reverses_exactly(client):
    """Returning everything reverses the original purchase 1:1: batch and
    branch_stock back to zero, balanced reversal journal."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "10"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "100.00"
        assert ret["vat"] == "12.28"
        assert ret["totalvalue"] == "100.00"
        assert ret["net"] == "87.72"
        assert ret["payed"] == "100.00"
        batches = await _batches(drug_id)
        assert batches[0].qty == Decimal("0.0000")
        assert await _stock_qty(drug_id) == Decimal("0.0000")
        debit, credit = await _journal_totals(ret["id"])
        assert debit == Decimal("100.00")
        assert credit == Decimal("100.00")
        assert debit == credit
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_reverses_header_discount_proportionally(client):
    """Original: 10 × 10.00 with 10% header discount (total 90.00). Returning 4
    keeps the SAME per-line split; the header discount reverses at the same
    proportion (round2(10 × 40/100) = 4.00)."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id,
            [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
            disc_percent="10",
        )
        assert pur["discount"] == "10.00"
        assert pur["totalvalue"] == "90.00"
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "40.00"
        assert ret["discount"] == "4.00"
        assert ret["vat"] == "4.91"
        assert ret["totalvalue"] == "36.00"
        assert ret["net"] == "31.09"
        assert ret["payed"] == "36.00"
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("36.00")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_keeps_original_untouched(client):
    """The original purchase row keeps its status/totals; only a version
    snapshot is appended to it."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        async with SessionLocal() as session:
            orig = await session.get(Invoice, pur["id"])
            assert orig.status == "saved"
            assert orig.totalvalue == Decimal("100.00")
            assert orig.payed == Decimal("100.00")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_reads_back(client):
    """GET /purchases/{id} returns the purchase_return with its original link."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "3", "unit_cost": "4.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "1"}]
        )
        invoice_ids.append(ret["id"])
        g = await client.get(
            f"/api/v1/purchases/{ret['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200
        got = g.json()
        assert got["kind"] == "purchase_return"
        assert got["ref_invoice_id"] == pur["id"]
        assert got["totalvalue"] == "4.00"
        assert got["journal"]["balanced"] is True
        assert got["lines"][0]["ref_invoice_line_id"] == pur["lines"][0]["id"]
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])