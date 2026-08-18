"""S1.7 correction approval (ticket #13): a manager (perm >= 7) approves a
pending count request and the server applies the delta atomically — batches +
branch_stock + audit + sync outbox + a balanced `correction` journal +
price_change_log (G12, plan/02 §4.4, feature_stock_counting §2.2/§4)."""
import asyncio
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    BranchStock,
    Journal,
    JournalLine,
    PriceChangeLog,
    StockBatch,
    StockCorrectionRequest,
    SyncLog,
)
from tests.stock_test_utils import (
    _batches,
    _cleanup,
    _login_token,
    _make_drug_and_stock,
    _request,
    _stock_qty,
)


async def _submit(client, token, drug_id, counted) -> int:
    r = await client.post(
        "/api/v1/stock/count-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_id": drug_id, "counted": counted},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _approve(client, token, request_id):
    return await client.post(
        f"/api/v1/stock/count-requests/{request_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _latest_correction_journal() -> dict[str, tuple[Decimal, Decimal]]:
    """account_code -> (debit, credit) of the highest-id correction journal."""
    async with SessionLocal() as session:
        from app.models import Account

        journal_id = (
            await session.execute(
                select(Journal.id)
                .join(JournalLine, JournalLine.journal_id == Journal.id)
                .where(Journal.source == "correction")
                .order_by(Journal.id.desc())
                .limit(1)
            )
        ).scalar()
        if journal_id is None:
            return {}
        rows = (
            await session.execute(
                select(Account.code, JournalLine.debit, JournalLine.credit)
                .join(Account, Account.id == JournalLine.account_id)
                .where(JournalLine.journal_id == journal_id)
            )
        ).all()
        return {code: (debit, credit) for code, debit, credit in rows}


async def _correction_journal_count() -> int:
    async with SessionLocal() as session:
        return len(
            (
                await session.execute(
                    select(Journal.id).where(Journal.source == "correction")
                )
            ).scalars().all()
        )


async def _count_rows(drug_id, model, entity: str | None = None):
    async with SessionLocal() as session:
        q = select(model)
        if entity is not None:
            q = q.where(getattr(model, "entity") == entity)
        if hasattr(model, "drug_id"):
            q = q.where(model.drug_id == drug_id)
        return len((await session.execute(q)).scalars().all())


async def test_approve_overage_creates_correction_batch(client):
    """counted 25 vs system 20 -> +5 overage: new correction batch, stock up,
    balanced journal (Dr 1200 / Cr 5900), audit + outbox + price_change_log."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None), ("10.0000", "8.0000", None)],
        stock_qty="20.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "25")
        request_ids.append(request_id)

        r = await _approve(client, token, request_id)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"

        # stock: branch_stock 25; a new typee='correction' batch qty 5 at avg cost
        assert await _stock_qty(drug_id) == Decimal("25.0000")
        batches = await _batches(drug_id)
        correction = [b for b in batches if b.typee == "correction"]
        assert len(correction) == 1
        assert correction[0].qty == Decimal("5.0000")
        assert correction[0].cost == Decimal("6.5000")  # (10*5 + 10*8) / 20

        # balanced correction journal: value = 5 x 6.50 = 32.50
        lines = await _latest_correction_journal()
        assert lines["1200"] == (Decimal("32.50"), Decimal("0"))
        assert lines["5900"] == (Decimal("0"), Decimal("32.50"))

        # price_change_log row: corrected units at unit cost
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(PriceChangeLog).where(PriceChangeLog.drug_id == drug_id)
                )
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].quant == Decimal("5.0000")
            assert rows[0].price == Decimal("6.5000")
            assert "stock count correction #" in rows[0].tips

        # audit + outbox
        assert await _count_rows(drug_id, AuditLog, "branch_stock") == 1
        assert await _count_rows(drug_id, AuditLog, "stock_batches") == 1
        async with SessionLocal() as session:
            syncs = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "branch_stock",
                        SyncLog.branch_id == 1,
                    )
                )
            ).scalars().all()
            mine = [
                s for s in syncs if s.payload and s.payload.get("drug_id") == drug_id
            ]
            assert len(mine) == 1
            assert mine[0].payload["qty"] == "25.0000"
            assert mine[0].action == "correction"
    finally:
        await _cleanup([drug_id], request_ids)


async def test_approve_deficit_fifo(client):
    """counted 6 vs system 10 -> -4 deficit: FIFO by expiry, stock down,
    balanced journal (Dr 5900 / Cr 1200)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[
            ("3.0000", "5.0000", "2025-01-01"),
            ("7.0000", "8.0000", "2026-01-01"),
        ],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "6")
        request_ids.append(request_id)
        r = await _approve(client, token, request_id)
        assert r.status_code == 200, r.text

        assert await _stock_qty(drug_id) == Decimal("6.0000")
        batches = await _batches(drug_id)
        assert batches[0].qty == Decimal("0.0000")  # 3 taken fully (exp 2025)
        assert batches[1].qty == Decimal("6.0000")  # 1 taken from 7 (exp 2026)

        # avg cost = (3*5 + 7*8) / 10 = 7.10; value = 4 x 7.10 = 28.40
        lines = await _latest_correction_journal()
        assert lines["5900"] == (Decimal("28.40"), Decimal("0"))
        assert lines["1200"] == (Decimal("0"), Decimal("28.40"))
    finally:
        await _cleanup([drug_id], request_ids)


async def test_approve_single_batch(client):
    """batch_id-scoped request adjusts only that batch (deficit capped by it)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        batch_id = (await _batches(drug_id))[0].id
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {token}"},
            json={"drug_id": drug_id, "counted": "7", "batch_id": batch_id},
        )
        assert r.status_code == 201, r.text
        request_ids.append(r.json()["id"])
        assert r.json()["delta"] == "-3.0000"

        g = await _approve(client, token, request_ids[0])
        assert g.status_code == 200, g.text
        assert await _stock_qty(drug_id) == Decimal("7.0000")
        batches = await _batches(drug_id)
        assert batches[0].qty == Decimal("7.0000")
        assert batches[0].oldstock == Decimal("10.0000")
    finally:
        await _cleanup([drug_id], request_ids)


async def test_approve_from_zero_stock_overage(client):
    """A drug with no stock at all: counted 5 -> branch_stock upserted from 0,
    value falls back to the drug master cost (feature §2.3 opening at cost)."""
    drug_id = await _make_drug_and_stock(tax_type="14%", cost_price="4.0000")
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "5")
        request_ids.append(request_id)
        r = await _approve(client, token, request_id)
        assert r.status_code == 200, r.text
        assert await _stock_qty(drug_id) == Decimal("5.0000")
        lines = await _latest_correction_journal()
        assert lines["1200"] == (Decimal("20.00"), Decimal("0"))  # 5 x 4.00
        assert lines["5900"] == (Decimal("0"), Decimal("20.00"))
    finally:
        await _cleanup([drug_id], request_ids)


async def test_approve_stale_deficit_rejected(client):
    """The balance changed after the request: the deficit no longer fits and the
    approval is rejected atomically (feature §2.4 — 'cannot accept after change')."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "3")  # delta -7
        request_ids.append(request_id)
        before_journals = await _correction_journal_count()

        # stock drops to 2 before the manager approves
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(BranchStock).where(
                        BranchStock.branch_id == 1, BranchStock.drug_id == drug_id
                    )
                )
            ).scalar_one()
            row.qty = Decimal("2.0000")
            await session.commit()

        r = await _approve(client, token, request_id)
        assert r.status_code == 409
        assert "changed since" in r.json()["detail"]

        row = await _request(request_id)
        assert row.status == "pending"  # untouched
        assert await _stock_qty(drug_id) == Decimal("2.0000")
        assert await _correction_journal_count() == before_journals  # no journal
    finally:
        await _cleanup([drug_id], request_ids)


async def test_approve_already_decided_rejected(client):
    """A request approved once cannot be approved again (409)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "15")
        request_ids.append(request_id)
        assert (await _approve(client, token, request_id)).status_code == 200
        r = await _approve(client, token, request_id)
        assert r.status_code == 409
        assert "not pending" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("15.0000")  # no double apply
    finally:
        await _cleanup([drug_id], request_ids)


async def test_approve_missing_request_404(client):
    token = await _login_token(client)
    r = await _approve(client, token, 99999999)
    assert r.status_code == 404


async def test_concurrent_approvals_one_wins(client):
    """Two simultaneous approvals of the same request: exactly one applies."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "20")
        request_ids.append(request_id)

        codes = await asyncio.gather(
            _approve(client, token, request_id),
            _approve(client, token, request_id),
        )
        assert sorted(r.status_code for r in codes) == [200, 409]
        assert await _stock_qty(drug_id) == Decimal("20.0000")
        row = await _request(request_id)
        assert row.status == "approved"
    finally:
        await _cleanup([drug_id], request_ids)


async def test_approve_audits_and_outbox_single_transaction(client):
    """G12: approval writes batch + branch_stock audit and one sync outbox row."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "12")
        request_ids.append(request_id)
        r = await _approve(client, token, request_id)
        assert r.status_code == 200, r.text

        async with SessionLocal() as session:
            audits = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.drug_id == drug_id,
                        AuditLog.action == "correction",
                    )
                )
            ).scalars().all()
            assert len(audits) == 2  # one per batch, one branch_stock -> see below
            entities = sorted(a.entity for a in audits)
            assert entities == ["branch_stock", "stock_batches"]

            syncs = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "branch_stock",
                        SyncLog.branch_id == 1,
                    )
                )
            ).scalars().all()
            mine = [s for s in syncs if s.payload and s.payload.get("drug_id") == drug_id]
            assert len(mine) == 1
            assert mine[0].payload["qty"] == "12.0000"
            assert mine[0].action == "correction"
    finally:
        await _cleanup([drug_id], request_ids)