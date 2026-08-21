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
    if method in ("cash", "network"):
        return method
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
    # S2.6: a closed month also blocks drawer movements (month is the ledger period)
    from app.money.monthclose import guard_open_month
    await guard_open_month(session, branch_id=branch_id, datee=datee)
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


async def supplier_payments(
    session: AsyncSession, *, branch_id: int, datee: date
) -> Decimal:
    """Net supplier payments for the day (the day report's named column for
    سند صرف): payments OUT minus payment reversals IN, both reasons carry
    `supplier_pay` (a reversal posts the opposite movement). Not a daily_close
    snapshot column — that table mirrors legacy MonyInfo.phy exactly — so the
    report computes it live from movements (a closed day is frozen, so it is
    stable until reopen)."""
    out = await _sum_movements(
        session, branch_id=branch_id, datee=datee, direction="out", reason=SUPPLIER_PAY
    )
    inn = await _sum_movements(
        session, branch_id=branch_id, datee=datee, direction="in", reason=SUPPLIER_PAY
    )
    return round2(out - inn)


async def supplier_payments_by_date(
    session: AsyncSession, *, branch_id: int, datees: list[date]
) -> dict[date, Decimal]:
    """`supplier_payments` for many dates in ONE query each (out/in) — the
    day-close list must not compute it per row."""
    if not datees:
        return {}
    out_rows = (
        await session.execute(
            select(DrawerMovement.datee, func.sum(DrawerMovement.amount))
            .where(
                DrawerMovement.branch_id == branch_id,
                DrawerMovement.reason == SUPPLIER_PAY,
                DrawerMovement.direction == "out",
                DrawerMovement.datee.in_(list(dict.fromkeys(datees))),
            )
            .group_by(DrawerMovement.datee)
        )
    ).all()
    in_rows = (
        await session.execute(
            select(DrawerMovement.datee, func.sum(DrawerMovement.amount))
            .where(
                DrawerMovement.branch_id == branch_id,
                DrawerMovement.reason == SUPPLIER_PAY,
                DrawerMovement.direction == "in",
                DrawerMovement.datee.in_(list(dict.fromkeys(datees))),
            )
            .group_by(DrawerMovement.datee)
        )
    ).all()
    out_by_date = dict(out_rows)
    in_by_date = dict(in_rows)
    return {
        d: round2(dec(out_by_date.get(d, 0)) - dec(in_by_date.get(d, 0)))
        for d in datees
    }


async def day_ledger(
    session: AsyncSession, *, branch_id: int, datee: date
) -> dict[str, Decimal]:
    """The drawer equation + the day's totals for (branch, datee)."""
    return await period_ledger(
        session, branch_id=branch_id, date_from=datee, date_to=datee
    )


# The granular per-day buckets `day_ledgers` computes. Every identity is
# LINEAR in these buckets, so a period total is exactly Σ(day values) — that
# is what makes `period_ledger`, the day_totals grid and the single-day
# `day_ledger` provably consistent: all three read this one bucket engine.
_LEDGER_KEYS = (
    "drawer_start",
    "expected_cash",
    "cash_in",
    "cash_out",
    "cash_sales",
    "network_sales",
    "cash_returns",
    "network_returns",
    "net_cash",
    "net_network",
    "manual_cash",
    "manual_card",
    "supplier_payments",
    "purchases",
    "expenses",
    "cost_of_sales",
    "corrections",
    "sales_net",
    "net_profit",
    "discounts",
    "vat_sales",
    "vat_purchases",
    "vat_expenses",
    "sales_count",
    "sales_returns_count",
)

_MONEY_KEYS = tuple(k for k in _LEDGER_KEYS if k not in ("sales_count", "sales_returns_count"))


def _empty_ledger() -> dict[str, Decimal]:
    ledger = {key: Decimal("0") for key in _LEDGER_KEYS}
    # Expenses are recorded gross (a manual expense movement is one cash
    # figure, no VAT rate is stored) and no expense journal posts VAT in
    # this slice, so there is no data source for vat_expenses — it stays 0
    # until an expense-VAT path exists (see README §6 money row).
    ledger["vat_expenses"] = Decimal("0")
    return ledger


def _finalize(lg: dict[str, Decimal]) -> None:
    """Round the raw buckets and derive the compound figures in place."""
    for key in _MONEY_KEYS:
        lg[key] = round2(lg[key])
    lg["net_cash"] = round2(lg["cash_sales"] - lg["cash_returns"])
    lg["net_network"] = round2(lg["network_sales"] - lg["network_returns"])
    # expected counts the opening float once: drawer_start already holds the
    # opening (+ net cash corrections), so the day's OTHER cash receipts are
    # (cash_in − drawer_start), minus cash out. A cash correction therefore
    # appears on the report twice (drawer_start as a float adjustment AND
    # manual_cash as a manual movement) but the identity simplifies to
    # (cash_in − cash_out), so the equation still counts it exactly once.
    lg["expected_cash"] = round2(lg["cash_in"] - lg["cash_out"])
    # stock-count corrections (account 5900) are a P&L cost: a deficit nets
    # down profit, an overage (contra) nets it back up.
    lg["net_profit"] = round2(
        lg["sales_net"] - lg["cost_of_sales"] - lg["expenses"] - lg["corrections"]
    )


async def day_ledgers(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict[date, dict[str, Decimal]]:
    """Granular per-day ledgers for every day with data in the window.

    The batched form of `day_ledger`: four GROUP BY datee queries cover the
    whole range regardless of its length — drawer movements by
    date/direction/reason/method, invoices by date/kind, and journal_lines
    per account for COGS (6000) and stock corrections (5900) — then the same
    bucket math runs per day in Python.
    """
    where = [DrawerMovement.branch_id == branch_id]
    if date_from is not None:
        where.append(DrawerMovement.datee >= date_from)
    if date_to is not None:
        where.append(DrawerMovement.datee <= date_to)
    movement_rows = (
        await session.execute(
            select(
                DrawerMovement.datee,
                DrawerMovement.direction,
                DrawerMovement.reason,
                DrawerMovement.method,
                func.coalesce(func.sum(DrawerMovement.amount), 0),
            )
            .where(*where)
            .group_by(
                DrawerMovement.datee,
                DrawerMovement.direction,
                DrawerMovement.reason,
                DrawerMovement.method,
            )
        )
    ).all()

    inv_where = [Invoice.branch_id == branch_id]
    if date_from is not None:
        inv_where.append(Invoice.datee >= date_from)
    if date_to is not None:
        inv_where.append(Invoice.datee <= date_to)
    invoice_rows = (
        await session.execute(
            select(
                Invoice.datee,
                Invoice.kind,
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.totalvalue), 0),
                func.coalesce(func.sum(Invoice.vat), 0),
                func.coalesce(func.sum(Invoice.discount), 0),
            )
            .where(*inv_where)
            .group_by(Invoice.datee, Invoice.kind)
        )
    ).all()

    async def _journal_net_by_day(code: str) -> dict[date, Decimal]:
        jwhere = [Account.code == code, JournalLine.branch_id == branch_id]
        if date_from is not None:
            jwhere.append(JournalLine.datee >= date_from)
        if date_to is not None:
            jwhere.append(JournalLine.datee <= date_to)
        rows = (
            await session.execute(
                select(
                    JournalLine.datee,
                    func.coalesce(func.sum(JournalLine.debit), 0),
                    func.coalesce(func.sum(JournalLine.credit), 0),
                )
                .join(Account, Account.id == JournalLine.account_id)
                .where(*jwhere)
                .group_by(JournalLine.datee)
            )
        ).all()
        return {row_datee: dec(debit) - dec(credit) for row_datee, debit, credit in rows}

    cogs_by_day = await _journal_net_by_day("6000")
    corrections_by_day = await _journal_net_by_day("5900")

    ledgers: dict[date, dict[str, Decimal]] = {}

    def _ledger_for(datee: date) -> dict[str, Decimal]:
        if datee not in ledgers:
            ledgers[datee] = _empty_ledger()
        return ledgers[datee]

    for datee, direction, reason, method, amount in movement_rows:
        lg = _ledger_for(datee)
        value = dec(amount)
        if direction == "in":
            if method == "cash":
                lg["cash_in"] += value
                if reason in ("opening", "correction"):
                    lg["drawer_start"] += value
                elif reason == SALE:
                    lg["cash_sales"] += value
                if reason in _MANUAL_REASONS:
                    lg["manual_cash"] += value
            elif method == "network":
                if reason == SALE:
                    lg["network_sales"] += value
                if reason in _MANUAL_REASONS:
                    lg["manual_card"] += value
            if reason == SUPPLIER_PAY:
                lg["supplier_payments"] -= value
        else:
            if method == "cash":
                lg["cash_out"] += value
                if reason == "correction":
                    lg["drawer_start"] -= value
                elif reason == SALE_RETURN:
                    lg["cash_returns"] += value
                if reason in _MANUAL_REASONS:
                    lg["manual_cash"] -= value
            elif method == "network":
                if reason == SALE_RETURN:
                    lg["network_returns"] += value
                if reason in _MANUAL_REASONS:
                    lg["manual_card"] -= value
            if reason == SUPPLIER_PAY:
                lg["supplier_payments"] += value
            elif reason == "expense":
                lg["expenses"] += value

    for datee, kind, count, total, vat, discount in invoice_rows:
        if kind not in ("sale", "sale_return", "purchase", "purchase_return"):
            continue
        lg = _ledger_for(datee)
        sign = 1 if kind in ("sale", "purchase") else -1
        if kind == "sale":
            lg["sales_count"] += count
        elif kind == "sale_return":
            lg["sales_returns_count"] += count
        if kind in ("sale", "sale_return"):
            lg["sales_net"] += sign * (dec(total) - dec(vat))
            lg["vat_sales"] += sign * dec(vat)
            lg["discounts"] += sign * dec(discount)
        else:
            lg["purchases"] += sign * dec(total)
            lg["vat_purchases"] += sign * dec(vat)

    for datee, net in cogs_by_day.items():
        _ledger_for(datee)["cost_of_sales"] = net
    for datee, net in corrections_by_day.items():
        _ledger_for(datee)["corrections"] = net

    for lg in ledgers.values():
        _finalize(lg)
    return ledgers


async def period_ledger(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict[str, Decimal]:
    """The ledger buckets over a whole window: Σ of the per-day values.

    Linear identities make the merge exact, so a ranged report and the
    per-day grid can never disagree. Returns the full granular bucket set
    (`_LEDGER_KEYS`) — callers project the columns they show.
    """
    ledgers = await day_ledgers(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )
    total = _empty_ledger()
    for lg in ledgers.values():
        for key in _LEDGER_KEYS:
            total[key] += lg[key]
    _finalize(total)
    return total
