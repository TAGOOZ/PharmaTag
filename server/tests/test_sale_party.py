"""S2.3 sale→party wiring (issue #18): optional customer party on a sale.

A sale may reference a tracked customer party (walk-in stays party-less and
backward-compatible). When present the invoice header records the party and the
sale journal's AR (1100) line carries the customer as its contra party — so a
customer كشف حساب (built from AR lines) reflects their credit sales. Cash sales
record the header party but post no AR line, so they never pollute the ledger.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    Account,
    Drug,
    Invoice,
    Journal,
    JournalLine,
    Party,
    SyncLog,
)
from tests.returns_test_utils import _cleanup
from tests.sales_test_utils import (
    BRANCH_ID,
    _login_token,
    _make_drug_and_stock,
)
from tests.purchase_test_utils import (
    _cleanup as _cleanup_purchase,
    _make_drug as _make_drug_for_purchase,
    _make_supplier,
)

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_stmt_{tag}_{_seq[0]}__"


async def _make_customer(*, active: bool = True) -> int:
    async with SessionLocal() as session:
        party = Party(
            branch_id=BRANCH_ID,
            kind="customer",
            namee=_uniq("cust"),
            randomid=_uniq("pty"),
            active=active,
        )
        session.add(party)
        await session.flush()
        pid = party.id
        await session.commit()
        return pid


async def _cleanup_party(pid: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == pid))
        await session.commit()


async def _account_id(session, code: str) -> int:
    return (
        await session.execute(
            select(Account.id).where(
                Account.branch_id == BRANCH_ID, Account.code == code
            )
        )
    ).scalar_one()


async def test_credit_sale_to_customer_tags_ar_line(client):
    """A credit sale to a tracked customer: header records party_id and the AR
    line's contra_party is the customer (the drawer line stays party-less)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [
                    {"method": "cash", "amount": "20.00"},
                    {"method": "credit", "amount": "30.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])

        async with SessionLocal() as session:
            inv = await session.get(Invoice, body["id"])
            assert inv.party_id == customer_id

            journal = (
                await session.execute(
                    select(Journal).where(Journal.ref_invoice_id == inv.id)
                )
            ).scalar_one()
            lines = (
                await session.execute(
                    select(JournalLine).where(JournalLine.journal_id == journal.id)
                )
            ).scalars().all()
            ar = await _account_id(session, "1100")
            by_account = {l.account_id: l for l in lines}
            assert by_account[ar].contra_party_id == customer_id
            drawer = await _account_id(session, "1000")
            assert by_account[drawer].contra_party_id is None
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_cash_sale_records_header_but_posts_no_ar(client):
    """A cash sale to a tracked customer records the header party but posts no
    AR line (walk-in parity): the customer ledger stays empty."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])

        async with SessionLocal() as session:
            inv = await session.get(Invoice, body["id"])
            assert inv.party_id == customer_id
            journal = (
                await session.execute(
                    select(Journal).where(Journal.ref_invoice_id == inv.id)
                )
            ).scalar_one()
            lines = (
                await session.execute(
                    select(JournalLine).where(JournalLine.journal_id == journal.id)
                )
            ).scalars().all()
            ar = await _account_id(session, "1100")
            assert all(l.account_id != ar for l in lines)
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_sale_requires_customer_kind_and_active(client):
    """A sale may not reference a non-customer or inactive party."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    supplier_id = await _make_supplier()
    inactive_customer = await _make_customer(active=False)
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        for party_id in (supplier_id, inactive_customer):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "party_id": party_id,
                    "lines": [{"drug_id": drug_id, "qty": "1"}],
                },
            )
            assert r.status_code == 400, r.text
        assert await _stock_qty_after(drug_id) == Decimal("20.0000")  # nothing written
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(inactive_customer)
        await _cleanup_supplier(supplier_id)


async def _stock_qty_after(drug_id):
    from app.models import BranchStock

    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one()
        return row.qty


async def _cleanup_supplier(pid: int) -> None:
    from sqlalchemy import delete

    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == pid))
        await session.commit()


async def test_sale_party_missing_is_404(client):
    """A sale against a party from another branch (or none) is 404."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": 999999,
                "lines": [{"drug_id": drug_id, "qty": "1"}],
            },
        )
        assert r.status_code == 404, r.text
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_return_mirrors_customer_party(client):
    """Returning a credit sale to a tracked customer mirrors the party on the
    return header and tags the return journal's AR credit line with the
    customer — so the credit refund reverses the customer ledger."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale_r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [{"method": "credit", "amount": "50.00"}],
            },
        )
        assert sale_r.status_code == 201, sale_r.text
        sale = sale_r.json()
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]

        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])

        async with SessionLocal() as session:
            inv = await session.get(Invoice, ret["id"])
            assert inv.party_id == customer_id
            journal = (
                await session.execute(
                    select(Journal).where(Journal.ref_invoice_id == inv.id)
                )
            ).scalar_one()
            lines = (
                await session.execute(
                    select(JournalLine).where(JournalLine.journal_id == journal.id)
                )
            ).scalars().all()
            ar = await _account_id(session, "1100")
            by_account = {l.account_id: l for l in lines}
            assert by_account[ar].contra_party_id == customer_id
            assert by_account[ar].credit == Decimal("50.00")
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_sale_outbox_payload_carries_party(client):
    """The sale outbox snapshot carries party_id so the target store's replay
    reproduces the same customer attach."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [{"method": "credit", "amount": "50.00"}],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice", SyncLog.entity_id == body["id"]
                    )
                )
            ).scalar_one()
            assert row.payload["party_id"] == customer_id
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_purchase_attaches_party_on_ap_line_only(client):
    """A purchase's contra party lands on the AP (2000) line only — the drawer
    line stays party-less, so the supplier ledger sees only real payables."""
    drug_id = await _make_drug_for_purchase()
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [
                    {"method": "cash", "amount": "14.00"},
                    {"method": "credit", "amount": "100.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])

        async with SessionLocal() as session:
            journal = (
                await session.execute(
                    select(Journal).where(Journal.ref_invoice_id == body["id"])
                )
            ).scalar_one()
            lines = (
                await session.execute(
                    select(JournalLine).where(JournalLine.journal_id == journal.id)
                )
            ).scalars().all()
            by_account = {l.account_id: l for l in lines}
            ap = await _account_id(session, "2000")
            drawer = await _account_id(session, "1000")
            assert by_account[ap].contra_party_id == supplier_id
            assert by_account[drawer].contra_party_id is None
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [supplier_id])