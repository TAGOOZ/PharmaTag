"""S1.3 sales print (ticket #9): 80mm receipt HTML for a saved sale.

The print endpoint renders the exact sale the caller can see (same branch-scope
as detail) into a thermal-friendly, RTL Arabic receipt: brand, invoice number,
drug name, qty, unit price, line total, VAT and grand total all present.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    Branch,
    BranchStock,
    Drug,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
    User,
)

BRANCH_ID = 1

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_prt_{tag}_{_seq[0]}__"


async def _login_token(client) -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _make_drug_and_stock(
    *,
    tax_type: str = "14%",
    price: str = "10.0000",
    batches: Optional[list[tuple[str, str, Optional[str]]]] = None,
    stock_qty: str = "20.0000",
) -> int:
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq("drug"),
            tax_type=tax_type,
            price=Decimal(price),
        )
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=BRANCH_ID, drug_id=drug_id, qty=Decimal(stock_qty), minimum=0
            )
        )
        for i, (qty, cost, expire) in enumerate(batches or []):
            session.add(
                StockBatch(
                    branch_id=BRANCH_ID,
                    drug_id=drug_id,
                    randomid=f"{_uniq('b')}{i}",
                    qty=Decimal(qty),
                    cost=Decimal(cost),
                    expire=date.fromisoformat(expire) if expire else None,
                )
            )
        await session.commit()
        return drug_id


async def _cleanup(drug_ids: list[int], invoice_ids: list[int]) -> None:
    async with SessionLocal() as session:
        for iid in invoice_ids:
            jids = (
                await session.execute(
                    select(Journal.id).where(Journal.ref_invoice_id == iid)
                )
            ).scalars().all()
            if jids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.journal_id.in_(jids))
                )
                await session.execute(delete(Journal).where(Journal.id.in_(jids)))
            await session.execute(delete(Balance).where(Balance.branch_id == BRANCH_ID))
            await session.execute(
                delete(PaymentSplit).where(PaymentSplit.invoice_id == iid)
            )
            await session.execute(
                delete(InvoiceLine).where(InvoiceLine.invoice_id == iid)
            )
            await session.execute(
                delete(SyncLog).where(SyncLog.entity_id == iid)
            )
            await session.execute(
                delete(AuditLog).where(AuditLog.entity_id == iid)
            )
            await session.execute(delete(Invoice).where(Invoice.id == iid))
        for drug_id in drug_ids:
            await session.execute(
                delete(StockBatch).where(StockBatch.drug_id == drug_id)
            )
            await session.execute(
                delete(BranchStock).where(BranchStock.drug_id == drug_id)
            )
            await session.execute(
                delete(AuditLog).where(AuditLog.drug_id == drug_id)
            )
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.commit()


def _token_for(user_id: int, branch_id) -> str:
    from app.auth.security import create_access_token

    return create_access_token(
        str(user_id), branch_id=branch_id or 0, roles=[], permission_level=0
    )


async def test_print_receipt_renders_sale_html(client):
    """The print endpoint returns RTL HTML carrying every money field."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("20.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])

        pr = await client.get(
            f"/api/v1/sales/{body['id']}/print",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pr.status_code == 200
        assert pr.headers["content-type"].startswith("text/html")
        html = pr.text

        assert "فارما تاج" in html
        assert body["invoice_no"] in html
        async with SessionLocal() as session:
            branch = await session.get(Branch, BRANCH_ID)
            assert branch is not None
            assert branch.pharname in html
            drug = await session.get(Drug, drug_id)
            assert drug is not None
            assert drug.drugname in html
        # qty (4dp), unit price (2dp), line total, VAT, grand total, payed
        assert "12.0000" in html
        assert "10.00" in html
        assert "120.00" in html
        assert "14.74" in html
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_print_requires_auth(client):
    r = await client.get("/api/v1/sales/1/print")
    assert r.status_code == 401


async def test_print_cross_branch_404(client):
    """A branch-2 user cannot print a branch-1 receipt (same scope as detail)."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        price="10.0000",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    branch_id = None
    user_id = None
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        sale_id = r.json()["id"]
        invoice_ids.append(sale_id)

        async with SessionLocal() as session:
            branch = Branch(pharmacyid=f"t2ph{_seq[0]}", mobile="0", pharname="Other")
            session.add(branch)
            await session.flush()
            branch_id = branch.id
            user = User(
                username=_uniq("user"),
                pass_hash="x",
                permission_level=9,
                branch_id=branch_id,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            await session.commit()

        other = await client.get(
            f"/api/v1/sales/{sale_id}/print",
            headers={"Authorization": f"Bearer {_token_for(user_id, branch_id)}"},
        )
        assert other.status_code == 404
    finally:
        async with SessionLocal() as session:
            if user_id:
                await session.execute(delete(User).where(User.id == user_id))
            if branch_id:
                await session.execute(delete(Branch).where(Branch.id == branch_id))
            await session.commit()
        await _cleanup([drug_id], invoice_ids)