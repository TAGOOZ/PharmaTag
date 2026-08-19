"""Shared helpers for the S2.4 settlement-voucher test themes (ticket #19).

Reuses the purchase helpers for login/users/branches and the sales helpers for
the drug/stock factories + credit-sale cleanup. Adds receivables-specific
helpers: a credit-sale helper (the AR source the vouchers settle) and a
tag-scoped voucher cleanup that walks the voucher → journal → lines → balances
→ drawer-movement chain in FK order (a voucher's drawer movement is matched by
its full fingerprint: branch + datee + direction + reason + method + amount +
user, since movements have no journal_id backlink).
"""
import os as _os
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    DrawerMovement,
    Journal,
    JournalLine,
    Party,
    SettlementVoucher,
)

BRANCH_ID = 1

_PID = _os.getpid()
_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_rec_{_PID}_{tag}_{_seq[0]}__"


from tests.purchase_test_utils import (  # noqa: E402  (re-exported helpers)
    _delete_other_branch,
    _delete_users,
    _login_token,
    _make_other_branch,
    _make_user,
    _token_for,
    _uniq_id,
)
from tests.sales_test_utils import (  # noqa: E402  (re-exported helpers)
    _cleanup as _cleanup_sale,
    _make_drug_and_stock,
)

__all__ = [
    "BRANCH_ID",
    "_cleanup_party",
    "_cleanup_vouchers",
    "_credit_sale",
    "_delete_other_branch",
    "_delete_users",
    "_login_token",
    "_make_customer",
    "_make_drug_and_stock",
    "_make_other_branch",
    "_make_supplier",
    "_make_user",
    "_token_for",
    "_uniq",
    "_voucher",
]


async def _make_customer(
    *, kind: str = "customer", active: bool = True, credit_limit: str = "0"
) -> int:
    """Create a throwaway customer party on branch 1; returns party_id."""
    async with SessionLocal() as session:
        party = Party(
            branch_id=BRANCH_ID,
            kind=kind,
            namee=_uniq("cust"),
            randomid=_uniq_id(),
            active=active,
            credit_limit=Decimal(credit_limit),
        )
        session.add(party)
        await session.flush()
        party_id = party.id
        await session.commit()
        return party_id


async def _make_supplier(*, active: bool = True) -> int:
    async with SessionLocal() as session:
        party = Party(
            branch_id=BRANCH_ID,
            kind="supplier",
            namee=_uniq("sup"),
            randomid=_uniq_id(),
            active=active,
        )
        session.add(party)
        await session.flush()
        party_id = party.id
        await session.commit()
        return party_id


async def _cleanup_party(party_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(
            delete(AuditLog).where(
                AuditLog.entity == "parties", AuditLog.entity_id == party_id
            )
        )
        await session.execute(delete(Party).where(Party.id == party_id))
        await session.commit()


async def _credit_sale(
    client,
    token,
    drug_id: int,
    *,
    party_id: int,
    datee: str,
    qty: str = "5",
) -> dict:
    """A fully-credit sale on branch 1 (VAT-inclusive MAIN: total = price ×
    qty, so qty 5 at price 10.0000 posts a 50.00 AR debt)."""
    amount = str(Decimal(qty) * Decimal("10.00"))
    r = await client.post(
        "/api/v1/sales",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "party_id": party_id,
            "datee": datee,
            "lines": [{"drug_id": drug_id, "qty": qty}],
            "payments": [{"method": "credit", "amount": amount}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _voucher(
    client,
    token,
    *,
    voucher_type: str,
    party_id: int,
    datee: str,
    amount: str,
    method: str = "cash",
    description: str | None = None,
) -> dict:
    body = {
        "voucher_type": voucher_type,
        "party_id": party_id,
        "datee": datee,
        "amount": amount,
        "method": method,
    }
    if description is not None:
        body["description"] = description
    r = await client.post(
        "/api/v1/receivables/vouchers",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _cleanup_vouchers(tag: str) -> None:
    """Remove every settlement whose voucher `description` carries `tag`
    (settlement_vouchers → journals → lines → balances → audit → their drawer
    movements) in FK order, including reversal vouchers linked via
    reverses_voucher_id."""
    async with SessionLocal() as session:
        vouchers = list(
            (
                await session.execute(
                    select(SettlementVoucher).where(
                        SettlementVoucher.description.like(f"%{tag}%")
                    )
                )
            ).scalars().all()
        )
        if not vouchers:
            await session.commit()
            return
        vids = [v.id for v in vouchers]
        reversals = list(
            (
                await session.execute(
                    select(SettlementVoucher).where(
                        SettlementVoucher.reverses_voucher_id.in_(vids)
                    )
                )
            ).scalars().all()
        )
        all_vouchers = list(dict.fromkeys([*vouchers, *reversals]))
        all_jids = list({v.journal_id for v in all_vouchers})
        # the voucher's drawer movement has no journal backlink — match it by
        # its full fingerprint (both directions: a reversal flips the side) so
        # cleanup never touches another slice's rows
        mv_ids: list[int] = []
        for v in all_vouchers:
            reason = (
                "customer_settlement" if v.voucher_type == "receipt" else "supplier_pay"
            )
            mv_ids += list(
                (
                    await session.execute(
                        select(DrawerMovement.id).where(
                            DrawerMovement.branch_id == v.branch_id,
                            DrawerMovement.datee == v.datee,
                            DrawerMovement.reason == reason,
                            DrawerMovement.method == v.method,
                            DrawerMovement.amount == v.amount,
                            DrawerMovement.user_id == v.created_by,
                        )
                    )
                ).scalars().all()
            )
        if mv_ids:
            await session.execute(
                delete(AuditLog).where(
                    AuditLog.entity == "drawer_movements",
                    AuditLog.entity_id.in_(mv_ids),
                )
            )
            await session.execute(
                delete(DrawerMovement).where(DrawerMovement.id.in_(mv_ids))
            )
        lines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id.in_(all_jids))
            )
        ).scalars().all()
        balance_keys = {
            (l.branch_id, l.month, l.year, l.account_id) for l in lines
        }
        for branch_id, month, year, account_id in balance_keys:
            await session.execute(
                delete(Balance).where(
                    Balance.branch_id == branch_id,
                    Balance.month == month,
                    Balance.year == year,
                    Balance.account_id == account_id,
                )
            )
        await session.execute(
            delete(JournalLine).where(JournalLine.journal_id.in_(all_jids))
        )
        await session.execute(
            delete(SettlementVoucher).where(
                SettlementVoucher.journal_id.in_(all_jids)
            )
        )
        await session.execute(
            delete(AuditLog).where(
                AuditLog.entity == "journals", AuditLog.entity_id.in_(all_jids)
            )
        )
        await session.execute(delete(Journal).where(Journal.id.in_(all_jids)))
        await session.commit()


def _voucher_date(offset: int) -> str:
    """A stable per-test business date (distinct so voucher drawer-movement
    fingerprints never collide across tests in one run)."""
    return date(2026, 8, 10 + offset).isoformat()