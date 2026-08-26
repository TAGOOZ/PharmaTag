"""Chain sales summary — the titanksasales projection (#34, S5.4, A06).

Legacy `titanksasales` was a chain-wide sales table replicated by a GUID
insert loop. Decision A06: it is a PROJECTION over canonical `invoices`,
never a synced table. This report regenerates it on demand: per day × branch
sale totals across the whole chain (single-shared-PG, G09), so the owner sees
every صيدلية's day side by side.

Invariants mirror S3.4: money as exact decimal strings; SQL-side totals
computed over EVERY matching invoice so they stay whole-range even when the
row list is capped; the report READS cross-branch and never writes.
"""
from decimal import Decimal
from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.core.time import business_date
from app.models import AuditLog, Branch, BranchIdentity, BranchStock, StockBatch, SyncLog

from tests import needs_test_utils as nu
from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)
from tests.test_branches import _admin_headers
import tests.test_branches as tb


async def _branch_sweep() -> None:
    """Delete the branch rows this test created (its own registry cleanup —
    test_branches' watermark fixture only runs inside that module)."""
    ids = list(tb._created)
    tb._created.clear()
    async with SessionLocal() as session:
        # fan-out (#34) scatters registry copies onto EVERY branch's queue —
        # clear them by ENTITY, not by branch_id, or a leftover pending copy
        # on branch 1 inflates the next replay's counters
        await session.execute(
            delete(SyncLog).where(
                SyncLog.entity.in_(["branch", "branch_identity"])
            )
        )
        await session.execute(
            delete(AuditLog).where(
                AuditLog.entity.in_(["branch", "branch_identity"])
            )
        )
        # new branches are seeded a chart of accounts (+ balances) on first
        # use — clear those before the branch row itself
        from app.models import Account, Balance, User

        await session.execute(delete(Balance).where(Balance.branch_id.in_(ids)))
        await session.execute(delete(Account).where(Account.branch_id.in_(ids)))
        # sales audited BY the branch-pinned user reference them — clear
        # those audit rows before the users themselves
        await session.execute(
            delete(AuditLog).where(
                AuditLog.user_id.in_(
                    select(User.id).where(
                        User.branch_id.in_(ids), User.username != "admin"
                    )
                )
            )
        )
        await session.execute(
            delete(User).where(
                User.branch_id.in_(ids), User.username != "admin"
            )
        )
        await session.execute(
            delete(BranchIdentity).where(BranchIdentity.branch_id.in_(ids))
        )
        await session.execute(delete(Branch).where(Branch.id.in_(ids)))
        mains = (
            await session.execute(
                select(func.count())
                .select_from(Branch)
                .where(Branch.is_main_device.is_(True))
            )
        ).scalar_one()
        if mains == 0:
            root = await session.get(Branch, 1)
            root.is_main_device = True
        await session.commit()


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _give_stock(branch_id: int, drug_id: int, qty: str) -> None:
    async with SessionLocal() as session:
        session.add(
            BranchStock(
                branch_id=branch_id,
                drug_id=drug_id,
                qty=Decimal(qty),
                minimum=Decimal("0"),
            )
        )
        session.add(
            StockBatch(
                branch_id=branch_id,
                drug_id=drug_id,
                randomid=f"cs-{branch_id}-{drug_id}",
                qty=Decimal(qty),
                cost=Decimal("5.0000"),
                expire=None,
            )
        )
        await session.commit()


async def _sister_token(client, branch_id: int) -> str:
    _, username = await nu._make_user(level=9, branch_id=branch_id)
    return await nu._login_token(client, username)


async def test_chain_sales_lists_per_day_per_branch_across_the_chain(client):
    """Sales in TWO branches on the same day render as two rows keyed by
    (datee, branch) with exact header figures and whole-chain foot totals."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    try:
        from tests.test_branches import _uniq_mobile, _uniq_pharmacyid

        admin = await _admin_headers(client)
        r = await client.post(
            "/api/v1/branches",
            headers=admin,
            json={
                "pharmacyid": _uniq_pharmacyid(),
                "mobile": _uniq_mobile(),
                "pharname": "فرع السلسلة",
            },
        )
        assert r.status_code == 201, r.text
        sister_id = r.json()["id"]
        tb._created.append(sister_id)
        await _give_stock(sister_id, drug_id, "20.0000")

        token = await _login_token(client)
        auth = _h(token)

        # main-branch sale: 12 × 10 → 120.00 gross
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        # sister-branch sale: 3 × 10 → 30.00 gross
        sister_token = await _sister_token(client, sister_id)
        r = await client.post(
            "/api/v1/sales", headers=_h(sister_token),
            json={"lines": [{"drug_id": drug_id, "qty": "3"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/chain_sales",
            params={"date_from": today, "date_to": today, "format": "grid"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        cols = body["columns"]
        rows = body["rows"]
        assert len(rows) == 2
        main_row = next(r2 for r2 in rows if r2[cols.index("الفرع")] == "Main Pharmacy")
        assert main_row[cols.index("التاريخ")] == today
        assert main_row[cols.index("عدد الفواتير")] == "1"
        assert main_row[cols.index("الاجمالي")] == "120.00"

        sister_row = next(r2 for r2 in rows if r2[cols.index("الفرع")] == "فرع السلسلة")
        assert sister_row[cols.index("الاجمالي")] == "30.00"
        assert sister_row[cols.index("عدد الفواتير")] == "1"

        foot = body["foot"]
        assert foot is not None
        assert foot[cols.index("الاجمالي")] == "150.00"
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _branch_sweep()


async def test_chain_sales_in_catalog(client):
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    codes = {rep["code"] for rep in r.json()["reports"]}
    assert "chain_sales" in codes
