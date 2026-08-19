"""Settlement vouchers (سند قبض / سند صرف) + the receivables register (S2.4, #19).

A settlement is a document, not an edit: it posts one balanced journal through
the shared engine (`money.journal.post_journal`, source `settlement`) inside the
branch advisory lock, records the drawer movement (cash/network), and writes a
`settlement_vouchers` reference row — all atomic with the journal's audit (G12).

A سند قبض (receipt) collects from a customer's receivable: Dr 1000 / Cr 1100
(the AR credit carries the customer as contra party, so the كشف حساب nets it
down). A سند صرف (payment voucher) pays a supplier's payable: Dr 2000 / Cr 1000
(the AP debit carries the supplier). Reversals are A07-style — a fresh
opposite-signed journal + movement linked via `reverses_voucher_id`, never an
edit or delete of the original.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.db import atomic
from app.drawer.movements import _method_to_drawer, guard_open_day, record_movement
from app.money.entries import MAX_AMOUNT
from app.money.journal import AP, AR, DRAWER, account_ids_for_code, post_journal
from app.models import Account, Journal, JournalLine, Party, SettlementVoucher
from app.sales.numbering import acquire_branch_lock, next_journal_entry_no

DEFAULT_AR_CODE = "1100"
DEFAULT_AP_CODE = "2000"

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "settlement voucher not found")
ALREADY_REVERSED = HTTPException(
    status.HTTP_409_CONFLICT, "a reversal voucher cannot be reversed"
)


async def _next_voucher_no(
    session: AsyncSession, branch_id: int
) -> int:
    """Next per-branch monotonic voucher_no (call under the branch lock)."""
    current = (
        await session.execute(
            select(func.max(SettlementVoucher.voucher_no)).where(
                SettlementVoucher.branch_id == branch_id
            )
        )
    ).scalar_one()
    return (current or 0) + 1


async def _party_for_voucher(
    session: AsyncSession,
    *,
    branch_id: int,
    voucher_type: str,
    party_id: int,
) -> Party:
    """The voucher's party: branch-scoped, active, and of a kind the voucher
    type can move (receipt → customer/both, payment → supplier/both)."""
    party = await session.get(Party, party_id)
    if party is None or party.branch_id != branch_id:
        raise NOT_FOUND
    if not party.active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "party is inactive"
        )
    if voucher_type == "receipt" and party.kind not in ("customer", "both"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "a receipt (سند قبض) needs a customer party",
        )
    if voucher_type == "payment" and party.kind not in ("supplier", "both"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "a payment voucher (سند صرف) needs a supplier party",
        )
    return party


def _validated_amount(amount) -> Decimal:
    """Exact round-half-up-2dp; zero/negative/oversized amounts are 400."""
    try:
        amount = money.round2(money.dec(amount))
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "amount is invalid"
        )
    if amount <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "amount must be greater than zero"
        )
    if amount > MAX_AMOUNT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "amount is too large"
        )
    return amount


async def post_voucher(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    voucher_type: str,
    party_id: int,
    datee: date,
    method: str,
    amount,
    description: Optional[str],
) -> SettlementVoucher:
    """Post one settlement (journal + balances + audit + drawer movement +
    settlement_vouchers reference) atomically under the branch lock."""
    amount = _validated_amount(amount)
    try:
        method = _method_to_drawer(method)
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "payment method must be cash or network"
        )
    party = await _party_for_voucher(
        session, branch_id=branch_id, voucher_type=voucher_type, party_id=party_id
    )
    description = (description or "").strip()

    if voucher_type == "receipt":
        entries = [(DRAWER, amount, money.dec("0")), (AR, money.dec("0"), amount)]
        contra_by_code = {AR: party.id}
        reason = "customer_settlement"
        direction = "in"
    elif voucher_type == "payment":
        entries = [(AP, amount, money.dec("0")), (DRAWER, money.dec("0"), amount)]
        contra_by_code = {AP: party.id}
        reason = "supplier_pay"
        direction = "out"
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "voucher_type must be 'receipt' or 'payment'",
        )

    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        await guard_open_day(session, branch_id=branch_id, datee=datee)
        voucher_no = await _next_voucher_no(session, branch_id)
        entry_no = await next_journal_entry_no(session, branch_id, datee)
        journal = await post_journal(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=datee,
            entry_no=entry_no,
            description=(
                f"سند قبض {voucher_no}" if voucher_type == "receipt"
                else f"سند صرف {voucher_no}"
            ),
            source="settlement",
            entries=entries,
            contra_party_by_code=contra_by_code,
        )
        await record_movement(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=datee,
            direction=direction,
            reason=reason,
            method=method,
            amount=amount,
        )
        voucher = SettlementVoucher(
            branch_id=branch_id,
            voucher_no=voucher_no,
            voucher_type=voucher_type,
            party_id=party.id,
            datee=datee,
            method=method,
            amount=amount,
            journal_id=journal.id,
            description=description,
            created_by=user_id,
        )
        session.add(voucher)
        await session.flush()
    return voucher


async def reverse_voucher(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    voucher_id: int,
) -> SettlementVoucher:
    """Post the offsetting reversal of a settlement (A07-style): sides swapped,
    same datee, linked via `reverses_voucher_id`, own journal + movement."""
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        voucher = await session.get(SettlementVoucher, voucher_id)
        if voucher is None or voucher.branch_id != branch_id:
            raise NOT_FOUND
        if voucher.reverses_voucher_id is not None:
            raise ALREADY_REVERSED
        journal = await session.get(Journal, voucher.journal_id)
        if journal is None or journal.status != "posted":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "voucher is not posted and cannot be reversed",
            )
        await guard_open_day(session, branch_id=branch_id, datee=journal.datee)
        lines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id == journal.id)
            )
        ).scalars().all()
        accounts = (
            await session.execute(
                select(Account).where(
                    Account.id.in_({l.account_id for l in lines})
                )
            )
        ).scalars().all()
        code_by_id = {a.id: a.code for a in accounts}
        reversed_entries = [
            # Pin each offset line to the SAME account row the original touched
            # and keep the party contra on the AR/AP line so the ledger sees it.
            (code_by_id[l.account_id], l.credit, l.debit, l.tips or "", l.account_id)
            for l in lines
        ]
        # The original voucher attached its contra to the AR/AP leg (the one
        # line carrying a contra_party_id). The reversal must attach the party
        # contra to the SAME account row its offset touches — keyed by account_id,
        # never re-derived from the hard-coded AR/AP code constants, so a party
        # mapped to a non-default account still nets correctly in its ledger.
        party_line = next((l for l in lines if l.contra_party_id is not None), None)
        contra_by_account = (
            {party_line.account_id: voucher.party_id}
            if party_line is not None
            else {}
        )
        entry_no = await next_journal_entry_no(session, branch_id, journal.datee)
        voucher_no = await _next_voucher_no(session, branch_id)
        reversal = await post_journal(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=journal.datee,
            entry_no=entry_no,
            description=(
                f"إلغاء سند قبض #{voucher.voucher_no}" if voucher.voucher_type == "receipt"
                else f"إلغاء سند صرف #{voucher.voucher_no}"
            ),
            source="settlement",
            entries=reversed_entries,
            contra_party_by_account_id=contra_by_account,
        )
        await record_movement(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=journal.datee,
            direction=("out" if voucher.voucher_type == "receipt" else "in"),
            reason=(
                "customer_settlement" if voucher.voucher_type == "receipt"
                else "supplier_pay"
            ),
            method=voucher.method,
            amount=voucher.amount,
        )
        row = SettlementVoucher(
            branch_id=branch_id,
            voucher_no=voucher_no,
            voucher_type=voucher.voucher_type,
            party_id=voucher.party_id,
            datee=voucher.datee,
            method=voucher.method,
            amount=voucher.amount,
            journal_id=reversal.id,
            description=voucher.description or "",
            reverses_voucher_id=voucher.id,
            created_by=user_id,
        )
        session.add(row)
        await session.flush()
    return row


async def serialize_voucher(
    session: AsyncSession, voucher: SettlementVoucher
) -> dict:
    """One voucher with its party and journal entry_no, money as a decimal string."""
    journal = await session.get(Journal, voucher.journal_id)
    party = await session.get(Party, voucher.party_id)
    return {
        "id": voucher.id,
        "voucher_no": voucher.voucher_no,
        "voucher_type": voucher.voucher_type,
        "party": {
            "id": party.id,
            "namee": party.namee,
            "name_ar": party.name_ar or "",
            "kind": party.kind,
        },
        "datee": voucher.datee.isoformat(),
        "method": voucher.method,
        "amount": money.format2(voucher.amount),
        "description": voucher.description or "",
        "journal_id": voucher.journal_id,
        "entry_no": journal.entry_no,
        "reverses_voucher_id": voucher.reverses_voucher_id,
        "created_by": voucher.created_by,
    }


async def list_vouchers(
    session: AsyncSession, *, branch_id: int, limit: int = 50
) -> list[dict]:
    """Branch-scoped vouchers, newest (datee, entry_no) first — no N+1."""
    rows = (
        await session.execute(
            select(SettlementVoucher, Journal)
            .join(Journal, Journal.id == SettlementVoucher.journal_id)
            .where(SettlementVoucher.branch_id == branch_id)
            .order_by(Journal.datee.desc(), Journal.entry_no.desc(), SettlementVoucher.id.desc())
            .limit(limit)
        )
    ).all()
    if not rows:
        return []
    vouchers = [v for v, _ in rows]
    journals = {j.id: j for _, j in rows}
    parties = (
        await session.execute(
            select(Party).where(Party.id.in_({v.party_id for v in vouchers}))
        )
    ).scalars().all()
    party_by_id = {p.id: p for p in parties}
    return [
        {
            "id": v.id,
            "voucher_no": v.voucher_no,
            "voucher_type": v.voucher_type,
            "party": {
                "id": p.id,
                "namee": p.namee,
                "name_ar": p.name_ar or "",
                "kind": p.kind,
            },
            "datee": v.datee.isoformat(),
            "method": v.method,
            "amount": money.format2(v.amount),
            "description": v.description or "",
            "journal_id": v.journal_id,
            "entry_no": journals[v.journal_id].entry_no,
            "reverses_voucher_id": v.reverses_voucher_id,
            "created_by": v.created_by,
        }
        for v in vouchers
        for p in [party_by_id[v.party_id]]
    ]


async def get_voucher(
    session: AsyncSession, *, branch_id: int, voucher_id: int
) -> dict:
    """One branch-scoped voucher — a cross-branch voucher is a 404."""
    voucher = await session.get(SettlementVoucher, voucher_id)
    if voucher is None or voucher.branch_id != branch_id:
        raise NOT_FOUND
    return await serialize_voucher(session, voucher)


async def get_receivables(
    session: AsyncSession, *, branch_id: int
) -> dict:
    """All active customer/both parties with their all-time net AR balance,
    sorted descending (biggest receivable first). The grand total counts only
    positive balances (what the branch is actually owed); a customer with a net
    credit (advance/overpayment) still appears, sorted last."""
    parties = (
        await session.execute(
            select(Party).where(
                Party.branch_id == branch_id,
                Party.active.is_(True),
                Party.kind.in_(("customer", "both")),
            )
        )
    ).scalars().all()

    rows = []
    total = money.dec("0")
    account_ids = await account_ids_for_code(session, branch_id, DEFAULT_AR_CODE)
    # Per-party account sets: the (branch, code) resolution — own + inherited
    # branch-1 account so a code shadowed after the branch posted history can't
    # orphan those lines — unioned with the party's own receivable mapping when
    # set. One GROUP BY aggregate across all parties, no per-party queries.
    if parties:
        conditions = [
            and_(
                JournalLine.contra_party_id == party.id,
                JournalLine.account_id.in_(
                    list(dict.fromkeys([party.receivable_account_id, *account_ids]))
                    if party.receivable_account_id is not None
                    else account_ids
                ),
            )
            for party in parties
        ]
        grouped = (
            await session.execute(
                select(
                    JournalLine.contra_party_id,
                    func.coalesce(func.sum(JournalLine.debit), 0),
                    func.coalesce(func.sum(JournalLine.credit), 0),
                )
                .where(JournalLine.branch_id == branch_id, or_(*conditions))
                .group_by(JournalLine.contra_party_id)
            )
        ).all()
        sums = {
            party_id: (money.dec(debit), money.dec(credit))
            for party_id, debit, credit in grouped
        }
    else:
        sums = {}
    for party in parties:
        if party.id in sums:
            debit, credit = sums[party.id]
            balance = money.round2(debit - credit)
        else:
            balance = money.dec("0")
        rows.append(
            {
                "party_id": party.id,
                "namee": party.namee,
                "name_ar": party.name_ar or "",
                "kind": party.kind,
                "credit_limit": money.format2(party.credit_limit),
                "balance": money.format2(balance),
            }
        )
        if balance > 0:
            total += balance

    rows.sort(key=lambda r: money.dec(r["balance"]), reverse=True)
    return {
        "branch_id": branch_id,
        "total": money.format2(total),
        "receivables": rows,
    }


async def ensure_credit_ok(
    session: AsyncSession,
    *,
    branch_id: int,
    party: Party,
    new_agel: Decimal,
) -> None:
    """F11.3 credit-limit guard for credit sales (called by the sale builder).

    A credit sale is refused when the customer's current AR debt plus the new
    agel would exceed `credit_limit`. `credit_limit = 0` means unlimited (the
    legacy default), so existing open-limit customers keep working unchanged.
    """
    limit = money.dec(party.credit_limit)
    if limit <= 0:
        return
    account_ids = await account_ids_for_code(session, branch_id, DEFAULT_AR_CODE)
    if party.receivable_account_id is not None:
        account_ids = list(dict.fromkeys([party.receivable_account_id, *account_ids]))
    if not account_ids:
        return
    debit, credit = (
        await session.execute(
            select(
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            ).where(
                JournalLine.branch_id == branch_id,
                JournalLine.account_id.in_(account_ids),
                JournalLine.contra_party_id == party.id,
            )
        )
    ).one()
    debt = money.dec(debit) - money.dec(credit)
    if debt + money.dec(new_agel) > limit:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"credit limit exceeded: current debt {money.format2(debt)} "
            f"+ {money.format2(new_agel)} exceeds limit {money.format2(limit)}",
        )