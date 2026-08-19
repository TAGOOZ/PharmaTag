"""Drawer movement recording + the day ledger (S1.8, ticket #14).

`record_movement` appends one `drawer_movements` row (with its audit) in the
CALLER's transaction; it refuses to write to a day that `daily_close` already
closed (A07: a closed (branch, datee) never silently receives new movements —
the caller must reopen first). `record_payment_splits` maps payment methods
(cash/card/manual_*) onto the drawer's cash/network split so every money
document contributes to the drawer equation (A17).

`day_ledger` computes the drawer equation and the day's totals (idx 9883): the
physical-cash identity `expected = drawer_start + Σcash_in − Σcash_out`, the
cash/network/manual splits, and the period figures (purchases, expenses, COGS,
net profit, VAT, discounts) so `daily_close` snapshots the whole day.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.core.money import dec, format2, round2
from app.models import Account, DailyClose, DrawerMovement, Invoice, JournalLine
from app.sales.numbering import acquire_branch_lock

# cash/net sale flows recorded automatically from money documents
SALE = "cash_sale"            # direction in
SALE_RETURN = "cash_return"   # direction out
SUPPLIER_PAY = "supplier_pay" # out on purchase, in on purchase-return

# reasons that are MANUAL drawer operations (not a money document): the day's
# manual_cash/manual_card totals are their net in−out; supplier_pay counts as a
# purchase (its own column), never as manual money.
_MANUAL_REASONS = ("opening", "customer_settlement", "expense", "transfer", "correction")

# payment methods that touch the drawer (credit never does)
_CASH_METHODS = {"cash", "manual_cash"}
_NETWORK_METHODS = {"card", "manual_card"}

ALREADY_CLOSED = HTTPException(
    status.HTTP_409_CONFLICT, "day is closed; reopen it before recording movements"
)


def _method_to_drawer(method: str) -> str:
    if method in _CASH_METHODS:
        return "cash"
    if method in _NETWORK_METHODS:
        return "network"
    raise ValueError(f"payment method {method!r} never touches the drawer")


async def guard_open_day(
    session: AsyncSession, *, branch_id: int, datee: date
) -> None:
    """Raise 409 if (branch, datee) is closed — a closed day takes no movements."""
    row = (
        await session.execute(
            select(DailyClose.id).where(
                DailyClose.branch_id == branch_id,
                DailyClose.datee == datee,
                DailyClose.status == "closed",
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        raise ALREADY_CLOSED


async def record_movement(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    datee: date,
    direction: str,
    reason: str,
    method: str,
    amount,
    ref_invoice_id: Optional[int] = None,
) -> DrawerMovement:
    """Append one drawer movement + its audit row (G12, caller's transaction).

    Serializes on the branch advisory lock (the same lock `close_day` takes),
    so the open-day guard can never read "open" and then land after a close.
    """
    amount = dec(amount)
    if amount <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "amount must be positive"
        )
    await acquire_branch_lock(session, branch_id)
    await guard_open_day(session, branch_id=branch_id, datee=datee)
    if ref_invoice_id is not None:
        ref = (
            await session.execute(
                select(Invoice.id).where(
                    Invoice.id == ref_invoice_id,
                    Invoice.branch_id == branch_id,
                )
            )
        ).scalar_one_or_none()
        if ref is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "ref_invoice_id must reference a document of your branch",
            )
    if reason == "correction" and direction == "out" and method == "cash":
        if await _drawer_float(session, branch_id=branch_id, datee=datee) - amount < 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "correction-out would take the drawer float below zero",
            )
    if reason == "opening":
        if direction != "in" or method != "cash":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "opening must be an incoming cash movement",
            )
        existing_opening = (
            await session.execute(
                select(DrawerMovement.id).where(
                    DrawerMovement.branch_id == branch_id,
                    DrawerMovement.datee == datee,
                    DrawerMovement.reason == "opening",
                )
            )
        ).scalar_one_or_none()
        if existing_opening is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "opening already recorded for this day",
            )
    row = DrawerMovement(
        branch_id=branch_id,
        datee=datee,
        direction=direction,
        reason=reason,
        method=method,
        amount=amount,
        ref_invoice_id=ref_invoice_id,
        user_id=user_id,
    )
    session.add(row)
    await session.flush()
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="drawer_movements",
        entity_id=row.id,
        action=ACTION_INSERT,
        new_value=(
            f"{direction} {reason} {method} {format2(amount)}"
            + (f" ref_invoice={ref_invoice_id}" if ref_invoice_id else "")
        ),
    )
    return row


async def record_payment_splits(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    datee: date,
    direction: str,
    reason: str,
    splits: list[tuple[str, Decimal]],
    ref_invoice_id: Optional[int] = None,
) -> None:
    """Convert payment splits [(method, amount)] into drawer movements (A17).

    credit splits never touch the drawer; cash/card/manual_cash/manual_card map
    onto the drawer's cash/network split. One movement per positive split.
    """
    for method, amount in splits:
        if method == "credit" or dec(amount) <= 0:
            continue
        await record_movement(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=datee,
            direction=direction,
            reason=reason,
            method=_method_to_drawer(method),
            amount=amount,
            ref_invoice_id=ref_invoice_id,
        )


async def _sum_movements(
    session: AsyncSession,
    *,
    branch_id: int,
    datee: date,
    direction: Optional[str] = None,
    reason: Optional[str] = None,
    reasons: Optional[tuple[str, ...]] = None,
    method: Optional[str] = None,
) -> Decimal:
    q = select(func.coalesce(func.sum(DrawerMovement.amount), 0)).where(
        DrawerMovement.branch_id == branch_id,
        DrawerMovement.datee == datee,
    )
    if direction is not None:
        q = q.where(DrawerMovement.direction == direction)
    if reason is not None:
        q = q.where(DrawerMovement.reason == reason)
    if reasons is not None:
        q = q.where(DrawerMovement.reason.in_(reasons))
    if method is not None:
        q = q.where(DrawerMovement.method == method)
    return dec((await session.execute(q)).scalar_one())


async def _drawer_float(
    session: AsyncSession, *, branch_id: int, datee: date
) -> Decimal:
    """The recorded cash float: the day's opening (+ net cash corrections).

    A correction adjusts the float record, so an in-correction raises it and
    an out-correction lowers it; opening is set once per day. This is the value
    `day_ledger` snapshots as `drawer_start` — and the bound a cash
    correction-out must not push below zero.
    """
    return round2(
        await _sum_movements(session, branch_id=branch_id, datee=datee, direction="in", reason="opening", method="cash")
        + await _sum_movements(session, branch_id=branch_id, datee=datee, direction="in", reason="correction", method="cash")
        - await _sum_movements(session, branch_id=branch_id, datee=datee, direction="out", reason="correction", method="cash")
    )


async def _invoice_sums(
    session: AsyncSession, *, branch_id: int, datee: date
) -> dict[str, dict[str, Decimal]]:
    """Period figures from the invoice table for one (branch, datee).

    Returns net-of-return totals per kind: net revenue (total − vat), vat,
    discounts, purchases, credit (agel) — the sale/purchase side of the day.
    """
    kinds = ("sale", "sale_return", "purchase", "purchase_return")
    rows = (
        await session.execute(
            select(
                Invoice.kind,
                func.coalesce(func.sum(Invoice.totalvalue), 0),
                func.coalesce(func.sum(Invoice.vat), 0),
                func.coalesce(func.sum(Invoice.discount), 0),
            )
            .where(Invoice.branch_id == branch_id, Invoice.datee == datee)
            .group_by(Invoice.kind)
        )
    ).all()
    by = {kind: {"total": Decimal("0"), "vat": Decimal("0"), "discount": Decimal("0")} for kind in kinds}
    for kind, total, vat, discount in rows:
        if kind not in by:
            continue
        by[kind] = {
            "total": dec(total),
            "vat": dec(vat),
            "discount": dec(discount),
        }
    return by


async def _cogs(session: AsyncSession, *, branch_id: int, datee: date) -> Decimal:
    """Net cost of goods sold for the day from journal_lines (account 6000)."""
    debit = await session.execute(
        select(func.coalesce(func.sum(JournalLine.debit), 0))
        .join(Account, Account.id == JournalLine.account_id)
        .where(
            Account.code == "6000",
            JournalLine.branch_id == branch_id,
            JournalLine.datee == datee,
        )
    )
    credit = await session.execute(
        select(func.coalesce(func.sum(JournalLine.credit), 0))
        .join(Account, Account.id == JournalLine.account_id)
        .where(
            Account.code == "6000",
            JournalLine.branch_id == branch_id,
            JournalLine.datee == datee,
        )
    )
    return round2(dec(debit.scalar_one()) - dec(credit.scalar_one()))


async def _corrections_net(session: AsyncSession, *, branch_id: int, datee: date) -> Decimal:
    """Net stock-correction value for the day from journal_lines (account 5900).

    The count-correction journal debits 5900 on a deficit (a stock loss hits
    the P&L as a cost) and credits it on an overage (a count gain nets down the
    expense contra), so net = Σdebit − Σcredit feeds the P&L as a cost below.
    """
    debit = await session.execute(
        select(func.coalesce(func.sum(JournalLine.debit), 0))
        .join(Account, Account.id == JournalLine.account_id)
        .where(
            Account.code == "5900",
            JournalLine.branch_id == branch_id,
            JournalLine.datee == datee,
        )
    )
    credit = await session.execute(
        select(func.coalesce(func.sum(JournalLine.credit), 0))
        .join(Account, Account.id == JournalLine.account_id)
        .where(
            Account.code == "5900",
            JournalLine.branch_id == branch_id,
            JournalLine.datee == datee,
        )
    )
    return round2(dec(debit.scalar_one()) - dec(credit.scalar_one()))


async def day_ledger(
    session: AsyncSession, *, branch_id: int, datee: date
) -> dict[str, Decimal]:
    """The drawer equation + the day's totals for (branch, datee)."""
    cash_in = await _sum_movements(session, branch_id=branch_id, datee=datee, direction="in", method="cash")
    cash_out = await _sum_movements(session, branch_id=branch_id, datee=datee, direction="out", method="cash")
    network_in = await _sum_movements(session, branch_id=branch_id, datee=datee, direction="in", method="network")
    network_out = await _sum_movements(session, branch_id=branch_id, datee=datee, direction="out", method="network")

    drawer_start = await _drawer_float(session, branch_id=branch_id, datee=datee)
    cash_sales = await _sum_movements(session, branch_id=branch_id, datee=datee, direction="in", reason=SALE, method="cash")
    cash_returns = await _sum_movements(session, branch_id=branch_id, datee=datee, direction="out", reason=SALE_RETURN, method="cash")
    network_sales = await _sum_movements(session, branch_id=branch_id, datee=datee, direction="in", reason=SALE, method="network")
    network_returns = await _sum_movements(session, branch_id=branch_id, datee=datee, direction="out", reason=SALE_RETURN, method="network")
    expenses = round2(
        await _sum_movements(session, branch_id=branch_id, datee=datee, direction="out", reason="expense")
    )
    manual_cash = round2(
        await _sum_movements(session, branch_id=branch_id, datee=datee, direction="in", method="cash", reasons=_MANUAL_REASONS)
        - await _sum_movements(session, branch_id=branch_id, datee=datee, direction="out", method="cash", reasons=_MANUAL_REASONS)
    )
    manual_card = round2(
        await _sum_movements(session, branch_id=branch_id, datee=datee, direction="in", method="network", reasons=_MANUAL_REASONS)
        - await _sum_movements(session, branch_id=branch_id, datee=datee, direction="out", method="network", reasons=_MANUAL_REASONS)
    )

    inv = await _invoice_sums(session, branch_id=branch_id, datee=datee)
    sales = inv["sale"]
    sale_returns = inv["sale_return"]
    purchases = inv["purchase"]
    purchase_returns = inv["purchase_return"]

    sales_net = round2((sales["total"] - sales["vat"]) - (sale_returns["total"] - sale_returns["vat"]))
    vat_sales = round2(sales["vat"] - sale_returns["vat"])
    vat_purchases = round2(purchases["vat"] - purchase_returns["vat"])
    discounts = round2(sales["discount"] - sale_returns["discount"])
    purchases_total = round2(purchases["total"] - purchase_returns["total"])
    cogs = await _cogs(session, branch_id=branch_id, datee=datee)
    corrections = await _corrections_net(session, branch_id=branch_id, datee=datee)

    net_cash = round2(cash_sales - cash_returns)
    net_network = round2(network_sales - network_returns)
    # expected counts the opening float once: drawer_start already holds the
    # opening (+ net cash corrections), so the day's OTHER cash receipts are
    # (cash_in − drawer_start), minus cash out. A cash correction therefore
    # appears on the report twice (drawer_start as a float adjustment AND
    # manual_cash as a manual movement) but the identity simplifies to
    # (cash_in − cash_out), so the equation still counts it exactly once.
    expected_cash = round2(drawer_start + (cash_in - drawer_start) - cash_out)
    # stock-count corrections (account 5900) are a P&L cost: a deficit nets
    # down profit, an overage (contra) nets it back up.
    net_profit = round2(sales_net - cogs - expenses - corrections)

    return {
        "drawer_start": drawer_start,
        "expected_cash": expected_cash,
        "net_cash": net_cash,
        "net_network": net_network,
        "manual_cash": manual_cash,
        "manual_card": manual_card,
        "purchases": purchases_total,
        "expenses": expenses,
        "cost_of_sales": cogs,
        "net_profit": net_profit,
        "discounts": discounts,
        "vat_sales": vat_sales,
        "vat_purchases": vat_purchases,
        # Expenses are recorded gross (a manual expense movement is one cash
        # figure, no VAT rate is stored) and no expense journal posts VAT in
        # this slice, so there is no data source for vat_expenses — it stays 0
        # until an expense-VAT path exists (see README §6 money row).
        "vat_expenses": Decimal("0"),
    }