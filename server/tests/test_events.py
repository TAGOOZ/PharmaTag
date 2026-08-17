"""Two-phase event bus semantics (ticket #3 AC2, plan/08 §2.4).

The bus is the #1 core seam: `in_txn` hooks run inside the sale's transaction
(before commit) and their side effects commit/roll back WITH it; `after_commit`
hooks run only after a successful commit; strict in_txn failures abort the whole
write, best-effort failures are caught + recorded and never abort it.

These integration tests prove the semantics against the real Postgres through
the public surface (subscribe + save_sale), not by inspecting internals.
"""
import pytest
from sqlalchemy import delete, select

from app.core.audit import audit
from app.core.db import SessionLocal
from app.core.events import (
    AFTER_COMMIT,
    IN_TXN,
    SALE_SAVED,
    EventBus,
    SaleContext,
)
from app.models import AuditLog, Invoice
from app.sales.service import save_sale

BRANCH_ID = 1
USER_ID = 1

_invoice_seq = [10000]


def _next_invoice_no() -> str:
    _invoice_seq[0] += 1
    return str(_invoice_seq[0])


@pytest.fixture
async def clean_sales():
    async with SessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.entity == "invoices"))
        await session.execute(delete(AuditLog).where(AuditLog.entity == "plugin_eta"))
        await session.execute(delete(Invoice))
        await session.commit()
    yield
    async with SessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.entity == "invoices"))
        await session.execute(delete(AuditLog).where(AuditLog.entity == "plugin_eta"))
        await session.execute(delete(Invoice))
        await session.commit()


@pytest.fixture
def empty_bus():
    bus = EventBus()
    yield bus


async def _hook_rows(session, entity: str):
    result = await session.execute(
        select(AuditLog).where(AuditLog.entity == entity).order_by(AuditLog.id)
    )
    return result.scalars().all()


async def test_in_txn_hook_side_effect_commits_with_the_sale(empty_bus, clean_sales):
    async def hook(ctx: SaleContext):
        await audit(
            ctx.session,
            branch_id=ctx.branch_id,
            user_id=ctx.user_id,
            entity="plugin_eta",
            entity_id=ctx.sale.id,
            action="in_txn",
        )

    empty_bus.subscribe(SALE_SAVED, hook, phase=IN_TXN, strict=False)

    async with SessionLocal() as session:
        invoice = await save_sale(
            session,
            branch_id=BRANCH_ID,
            user_id=USER_ID,
            invoice_no=_next_invoice_no(),
            bus=empty_bus,
        )

    assert invoice.id is not None
    async with SessionLocal() as session:
        rows = await _hook_rows(session, "plugin_eta")
        assert len(rows) == 1, "hook side effect committed with the sale"
        assert rows[0].entity_id == invoice.id
        assert rows[0].action == "in_txn"


async def test_strict_in_txn_hook_aborts_the_whole_write(empty_bus, clean_sales):
    async def hook(ctx: SaleContext):
        raise RuntimeError("counter chain broken")

    empty_bus.subscribe(SALE_SAVED, hook, phase=IN_TXN, strict=True)

    async with SessionLocal() as session:
        with pytest.raises(RuntimeError, match="counter chain broken"):
            await save_sale(
                session,
                branch_id=BRANCH_ID,
                user_id=USER_ID,
                invoice_no=_next_invoice_no(),
                bus=empty_bus,
            )

    # nothing persisted: no invoice, no core audit row for it
    async with SessionLocal() as session:
        rows = (await session.execute(select(Invoice))).scalars().all()
        assert rows == []
        assert await _hook_rows(session, "invoices") == []


async def test_best_effort_in_txn_hook_never_aborts_the_write(empty_bus, clean_sales):
    async def hook(ctx: SaleContext):
        raise RuntimeError("kpi dashboard hiccup")

    empty_bus.subscribe(SALE_SAVED, hook, phase=IN_TXN, strict=False)

    async with SessionLocal() as session:
        invoice = await save_sale(
            session,
            branch_id=BRANCH_ID,
            user_id=USER_ID,
            invoice_no=_next_invoice_no(),
            bus=empty_bus,
        )

    assert invoice.id is not None
    assert len(empty_bus.errors) == 1, "best-effort failure is recorded, not raised"
    assert empty_bus.errors[0]["phase"] == IN_TXN
    async with SessionLocal() as session:
        assert (await session.execute(select(Invoice))).scalar_one().id == invoice.id


async def test_strict_hook_side_effects_roll_back_with_the_transaction(empty_bus, clean_sales):
    async def hook(ctx: SaleContext):
        await audit(
            ctx.session,
            branch_id=ctx.branch_id,
            user_id=ctx.user_id,
            entity="plugin_eta",
            entity_id=ctx.sale.id,
            action="in_txn",
        )
        raise RuntimeError("strict plugin bails after writing")

    empty_bus.subscribe(SALE_SAVED, hook, phase=IN_TXN, strict=True)

    async with SessionLocal() as session:
        with pytest.raises(RuntimeError):
            await save_sale(
                session,
                branch_id=BRANCH_ID,
                user_id=USER_ID,
                invoice_no=_next_invoice_no(),
                bus=empty_bus,
            )

    async with SessionLocal() as session:
        assert (await session.execute(select(Invoice))).scalars().all() == []
        assert await _hook_rows(session, "plugin_eta") == []
        assert await _hook_rows(session, "invoices") == []


async def test_after_commit_hook_runs_only_after_commit(empty_bus, clean_sales):
    seen_ids: list[int] = []

    async def hook(ctx: SaleContext):
        # the sale must be committed and queryable in a fresh session
        async with SessionLocal() as session:
            row = await session.get(Invoice, ctx.sale.id)
            assert row is not None, "after_commit hook must see the committed sale"
            seen_ids.append(row.id)

    empty_bus.subscribe(SALE_SAVED, hook, phase=AFTER_COMMIT)

    async with SessionLocal() as session:
        invoice = await save_sale(
            session,
            branch_id=BRANCH_ID,
            user_id=USER_ID,
            invoice_no=_next_invoice_no(),
            bus=empty_bus,
        )

    assert seen_ids == [invoice.id]


async def test_after_commit_hooks_are_skipped_when_the_transaction_aborts(empty_bus, clean_sales):
    ran = []

    async def blocker(ctx: SaleContext):
        raise RuntimeError("strict abort")

    async def after(ctx: SaleContext):
        ran.append(ctx.sale.id)

    empty_bus.subscribe(SALE_SAVED, blocker, phase=IN_TXN, strict=True)
    empty_bus.subscribe(SALE_SAVED, after, phase=AFTER_COMMIT)

    async with SessionLocal() as session:
        with pytest.raises(RuntimeError):
            await save_sale(
                session,
                branch_id=BRANCH_ID,
                user_id=USER_ID,
                invoice_no=_next_invoice_no(),
                bus=empty_bus,
            )

    assert ran == [], "after_commit must not run when the commit never happened"


async def test_after_commit_hook_failure_never_fails_the_committed_write(empty_bus, clean_sales):
    async def hook(ctx: SaleContext):
        raise RuntimeError("submission worker down")

    empty_bus.subscribe(SALE_SAVED, hook, phase=AFTER_COMMIT)

    async with SessionLocal() as session:
        invoice = await save_sale(
            session,
            branch_id=BRANCH_ID,
            user_id=USER_ID,
            invoice_no=_next_invoice_no(),
            bus=empty_bus,
        )

    assert invoice.id is not None, "a failing after_commit hook must not fail the sale"
    assert len(empty_bus.errors) == 1
    assert empty_bus.errors[0]["phase"] == AFTER_COMMIT


def test_subscribe_rejects_unknown_event_and_phase(empty_bus):
    with pytest.raises(ValueError, match="unknown core event"):
        empty_bus.subscribe("made.up.event", lambda ctx: None, phase=IN_TXN)
    with pytest.raises(ValueError, match="unknown phase"):
        empty_bus.subscribe(SALE_SAVED, lambda ctx: None, phase="mid_txn")


def _bare_ctx() -> SaleContext:
    return SaleContext(session=None, branch_id=1, user_id=1, sale=None, payload={})


async def test_emit_with_no_subscribers_is_a_noop(empty_bus):
    ctx = _bare_ctx()
    await empty_bus.emit(SALE_SAVED, ctx, phase=IN_TXN)
    await empty_bus.emit(SALE_SAVED, ctx, phase=AFTER_COMMIT)
    assert empty_bus.errors == []


async def test_emit_rejects_unknown_event_and_phase(empty_bus):
    ctx = _bare_ctx()
    with pytest.raises(ValueError, match="unknown core event"):
        await empty_bus.emit("made.up.event", ctx, phase=IN_TXN)
    with pytest.raises(ValueError, match="unknown phase"):
        await empty_bus.emit(SALE_SAVED, ctx, phase="mid_txn")
    with pytest.raises(ValueError, match="unknown phase"):
        await empty_bus.emit(SALE_SAVED, ctx, phase="")


async def test_multiple_subscribers_run_all_in_subscription_order(empty_bus):
    order: list[str] = []

    async def first(ctx):
        order.append("first")

    async def second(ctx):
        order.append("second")

    async def third(ctx):
        order.append("third")

    empty_bus.subscribe(SALE_SAVED, first, phase=IN_TXN)
    empty_bus.subscribe(SALE_SAVED, second, phase=IN_TXN)
    empty_bus.subscribe(SALE_SAVED, third, phase=IN_TXN)

    await empty_bus.emit(SALE_SAVED, _bare_ctx(), phase=IN_TXN)
    assert order == ["first", "second", "third"]


async def test_hooks_run_only_in_their_subscribed_phase(empty_bus):
    counts = {"in_txn": 0, "after_commit": 0}

    async def in_txn(ctx):
        counts["in_txn"] += 1

    async def after(ctx):
        counts["after_commit"] += 1

    empty_bus.subscribe(SALE_SAVED, in_txn, phase=IN_TXN)
    empty_bus.subscribe(SALE_SAVED, after, phase=AFTER_COMMIT)

    ctx = _bare_ctx()
    await empty_bus.emit(SALE_SAVED, ctx, phase=IN_TXN)
    assert counts == {"in_txn": 1, "after_commit": 0}, "after_commit hook leaked into in_txn"
    await empty_bus.emit(SALE_SAVED, ctx, phase=AFTER_COMMIT)
    assert counts == {"in_txn": 1, "after_commit": 1}, "in_txn hook leaked into after_commit"


async def test_best_effort_in_txn_failure_does_not_stop_later_hooks(empty_bus):
    ran: list[str] = []

    async def failing(ctx):
        raise RuntimeError("kpi dashboard hiccup")

    async def later(ctx):
        ran.append("later")

    empty_bus.subscribe(SALE_SAVED, failing, phase=IN_TXN)
    empty_bus.subscribe(SALE_SAVED, later, phase=IN_TXN)

    await empty_bus.emit(SALE_SAVED, _bare_ctx(), phase=IN_TXN)
    assert ran == ["later"], "later in_txn hook must still run after a best-effort failure"
    assert len(empty_bus.errors) == 1
    assert empty_bus.errors[0]["phase"] == IN_TXN


async def test_after_commit_failure_isolation_and_order(empty_bus):
    order: list[str] = []

    async def failing(ctx):
        order.append("failing")
        raise RuntimeError("submission worker down")

    async def later(ctx):
        order.append("later")

    empty_bus.subscribe(SALE_SAVED, failing, phase=AFTER_COMMIT)
    empty_bus.subscribe(SALE_SAVED, later, phase=AFTER_COMMIT)

    await empty_bus.emit(SALE_SAVED, _bare_ctx(), phase=AFTER_COMMIT)
    assert order == ["failing", "later"], "later after_commit hook must still run in order"
    assert len(empty_bus.errors) == 1
    assert empty_bus.errors[0]["phase"] == AFTER_COMMIT


async def test_reentrant_emit_is_deterministic(empty_bus):
    calls = {"n": 0}

    async def reenter(ctx):
        calls["n"] += 1
        if calls["n"] == 1:
            await empty_bus.emit(SALE_SAVED, ctx, phase=IN_TXN)

    empty_bus.subscribe(SALE_SAVED, reenter, phase=IN_TXN)

    await empty_bus.emit(SALE_SAVED, _bare_ctx(), phase=IN_TXN)
    assert calls["n"] == 2, "re-entrant emit re-runs handlers deterministically, no corruption"
    assert empty_bus.errors == []