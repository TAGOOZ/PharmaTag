"""Shared helpers for the S1.4 purchase test themes (ticket #10).

Each themed test file imports these; the helpers create + clean up their own
throwaway supplier/drug/batch rows on branch 1 (MAIN, seed admin). Cleanup
walks the FK chain (journal_lines → journals → invoices → batches → drugs →
parties) so a mid-suite failure never blocks later deletes.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    Account,
    AuditLog,
    Balance,
    Branch,
    BranchStock,
    DrawerMovement,
    Drug,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    Party,
    PaymentSplit,
    StockBatch,
    SyncLog,
    User,
)

BRANCH_ID = 1

# Namespace every throwaway row by the pytest process id so a crashed run that
# leaked rows can never collide with the next run's fresh counter.
import os as _os

_PID = _os.getpid()

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_pur_{_PID}_{tag}_{_seq[0]}__"


def _uniq_id() -> str:
    """A unique (branch, randomid) value — `parties.randomid` is UNIQUE per branch."""
    _seq[0] += 1
    return f"__t2_pty_{_PID}_{_seq[0]}__"


async def _login_token(client) -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _make_supplier(
    *, namee: Optional[str] = None, active: bool = True, branch_id: int = BRANCH_ID
) -> int:
    """Create a throwaway supplier party; returns party_id."""
    async with SessionLocal() as session:
        party = Party(
            branch_id=branch_id,
            kind="supplier",
            namee=namee or _uniq("sup"),
            randomid=_uniq_id(),
            active=active,
        )
        session.add(party)
        await session.flush()
        party_id = party.id
        await session.commit()
        return party_id


async def _make_drug(
    *,
    tax_type: str = "14%",
    active: bool = True,
    existing_stock: Optional[tuple[str, str, Optional[str]]] = None,
) -> int:
    """Create a throwaway drug with NO stock by default; optionally pre-seed one
    existing batch (qty, cost, expire) so purchases add alongside it."""
    async with SessionLocal() as session:
        drug = Drug(drugname=_uniq("drug"), tax_type=tax_type, price=Decimal("0.0000"))
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        if existing_stock is not None:
            qty, cost, expire = existing_stock
            session.add(
                BranchStock(
                    branch_id=BRANCH_ID,
                    drug_id=drug_id,
                    qty=Decimal(qty),
                    minimum=0,
                )
            )
            session.add(
                StockBatch(
                    branch_id=BRANCH_ID,
                    drug_id=drug_id,
                    randomid=_uniq("existing"),
                    qty=Decimal(qty),
                    cost=Decimal(cost),
                    expire=date.fromisoformat(expire) if expire else None,
                )
            )
        if not active:
            drug.active = False
        await session.commit()
        return drug_id


async def _make_user(username: str, permission_level: int, branch_id=None, active=True) -> int:
    async with SessionLocal() as session:
        user = User(
            username=username,
            pass_hash="x",
            permission_level=permission_level,
            branch_id=branch_id,
            active=active,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


async def _make_other_branch() -> int:
    """Create a throwaway branch (the seed DB has no branch 2) and return its id."""
    _seq[0] += 1
    async with SessionLocal() as session:
        branch = Branch(
            pharmacyid=f"pt{_seq[0]}",
            phar="",
            mobile="0",
            pharname=_uniq("branch"),
            is_active=True,
        )
        session.add(branch)
        await session.flush()
        branch_id = branch.id
        await session.commit()
        return branch_id


async def _delete_other_branch(branch_id: int) -> None:
    """Remove the throwaway branch, its users, and any accounts created on it
    (accounts are branch-scoped config rows; a leftover account would otherwise
    FK-block the branch delete and leak it past the mobile unique constraint)."""
    async with SessionLocal() as session:
        await session.execute(delete(Account).where(Account.branch_id == branch_id))
        await session.execute(delete(User).where(User.branch_id == branch_id))
        await session.execute(delete(Branch).where(Branch.id == branch_id))
        await session.commit()


async def _delete_users(user_ids: list[int]) -> None:
    """Remove throwaway users by id (their audit rows go first — G12 keeps an
    audit row per write, referencing user_id)."""
    async with SessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.user_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def _token_for(user_id: int, branch_id) -> str:
    from app.auth.security import create_access_token

    return create_access_token(
        str(user_id), branch_id=branch_id or 0, roles=[], permission_level=0
    )


async def _cleanup(drug_ids: list[int], invoice_ids: list[int], party_ids: list[int]) -> None:
    async with SessionLocal() as session:
        # any invoice that touches one of our drugs must be removed first
        linked = (
            await session.execute(
                select(InvoiceLine.invoice_id).where(
                    InvoiceLine.drug_id.in_(drug_ids) if drug_ids else False
                )
            )
        ).scalars().all()
        invoice_ids = list(set(invoice_ids) | set(linked))
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
                delete(DrawerMovement).where(DrawerMovement.ref_invoice_id == iid)
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
        for pid in party_ids:
            await session.execute(delete(AuditLog).where(AuditLog.entity == "parties", AuditLog.entity_id == pid))
            await session.execute(delete(Party).where(Party.id == pid))
        await session.commit()


async def _stock_qty(drug_id: int) -> Decimal:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one_or_none()
        return row.qty if row is not None else Decimal("0")


async def _batches(drug_id: int) -> list:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(StockBatch)
                .where(StockBatch.drug_id == drug_id)
                .order_by(StockBatch.id)
            )
        ).scalars().all()


async def _journal_totals(invoice_id: int) -> tuple[Decimal, Decimal]:
    async with SessionLocal() as session:
        journal = (
            await session.execute(
                select(Journal).where(Journal.ref_invoice_id == invoice_id)
            )
        ).scalar_one()
        lines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id == journal.id)
            )
        ).scalars().all()
        return (
            sum((l.debit for l in lines), Decimal("0")),
            sum((l.credit for l in lines), Decimal("0")),
        )


async def _journal_source(invoice_id: int) -> str:
    async with SessionLocal() as session:
        journal = (
            await session.execute(
                select(Journal).where(Journal.ref_invoice_id == invoice_id)
            )
        ).scalar_one()
        return journal.source