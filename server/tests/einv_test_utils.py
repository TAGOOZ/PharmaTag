"""S4.1 e-invoice issue path (ticket #28): sale ⇒ einvoice_log row + counter
increment + UUID chain + QR, all atomic with the invoice (G12, STRICT A09).

Tests run on a THROWAWAY branch so the per-(branch, kind) counters start at
zero and "first-of-device has an empty previousUUID" is assertable.
"""
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AppConfig,
    AuditLog,
    EInvoiceCounter,
    EInvoiceLog,
    Party,
    SyncLog,
    User,
)
from app.einvoicing.toolkit import PROD_PORTAL_URL, qr_string, receipt_uuid
from tests.sales_test_utils import _token_for
from tests.returns_test_utils import (
    _delete_branch,
    _make_branch,
    _make_drug_and_stock_branch,
)

RIN = "200173707"

# Namespace every throwaway row by the pytest process id (same convention as
# sales_test_utils): the DB persists between runs, so a crashed run's leftover
# rows must never collide with the next run's fresh counters.
import os

_PID = os.getpid()

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t28_{_PID}_{tag}_{_seq[0]}__"


async def _set_rin() -> None:
    async with SessionLocal() as session:
        # idempotent: a crashed earlier run may have left the row behind
        await session.execute(delete(AppConfig).where(AppConfig.key == "eta.rin"))
        session.add(AppConfig(key="eta.rin", value=RIN))
        await session.commit()


async def _clear_rin() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(AppConfig).where(AppConfig.key == "eta.rin"))
        await session.commit()


async def _make_user(username: str, branch_id: int) -> int:
    async with SessionLocal() as session:
        user = User(
            username=username,
            pass_hash="x",
            permission_level=7,
            branch_id=branch_id,
            active=True,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


async def _make_tax_party(branch_id: int, *, rin: str | None) -> int:
    async with SessionLocal() as session:
        party = Party(
            branch_id=branch_id,
            kind="customer",
            namee=_uniq("party"),
            # uq_parties_branch_randomid
            randomid=f"t28-{_PID}-{_seq[0]}",
            tax_registration_no=rin or "",
        )
        session.add(party)
        await session.flush()
        party_id = party.id
        await session.commit()
        return party_id


async def _log_for(invoice_id: int) -> EInvoiceLog:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
            )
        ).scalar_one()


async def _counter_for(branch_id: int, kind: str) -> EInvoiceCounter:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(EInvoiceCounter).where(
                    EInvoiceCounter.branch_id == branch_id,
                    EInvoiceCounter.kind == kind,
                )
            )
        ).scalar_one()
