"""Transfer use-cases: draft, dispatch, receive, cancel (#32; decisions T2/T5/T7).

State machine: `draft → dispatched → received`, `cancelled` reachable only
from draft. Dispatch authority is the SOURCE branch's user, receive the
TARGET branch's user (token-branch enforced — self-receive is impossible
because source == target is rejected at creation); a draft may be cancelled
by either party. Every transition writes its audit row and one `entity=
'transfer'` outbox row PER AFFECTED BRANCH in the same transaction (G12) so
both peers converge. No GL posting in this slice (T3 — quantities move; stock
VALUE stays on the source book).

Numbering follows G07 like invoices: per-SOURCE-branch monotonic transfer_no,
assigned under a branch advisory lock, UNIQUE(source_branch_id, transfer_no)
as the backstop.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import Integer, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit, enqueue_sync
from app.core.db import atomic
from app.core.money import dec, round4
from app.models import Branch, Drug, Transfer, TransferLine, User
from app.transfers import stock as tstock

ENTITY = "transfer"
_LOCK_NAMESPACE = "pharmatag:branch-transfers"


def _qty4(value) -> str:
    """Wire format for quantities: exact 4-dp string (money.py rule)."""
    return format(round4(value), "f")

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "transfer not found")
BAD_STATE = HTTPException(status.HTTP_409_CONFLICT, "transfer state does not allow this")
FORBIDDEN_BRANCH = HTTPException(
    status.HTTP_403_FORBIDDEN, "caller is not a party to this transfer"
)
UNKNOWN_DRUG = HTTPException(status.HTTP_400_BAD_REQUEST, "unknown drug in lines")
UNKNOWN_LINE = HTTPException(status.HTTP_400_BAD_REQUEST, "unknown line id")
LINE_NOT_COVERED = HTTPException(
    status.HTTP_400_BAD_REQUEST, "every line must be provided exactly once"
)
RECEIVE_TOO_MUCH = HTTPException(
    status.HTTP_400_BAD_REQUEST, "received_qty exceeds sent_qty"
)
SAME_BRANCH = HTTPException(
    status.HTTP_400_BAD_REQUEST, "source and target branch must differ"
)


async def acquire_branch_lock(session: AsyncSession, branch_id: int) -> None:
    """Serialize transfer writes for a source branch (int8 advisory xact lock)."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:ns), :branch_id)"),
        {"ns": _LOCK_NAMESPACE, "branch_id": branch_id},
    )


async def next_transfer_no(session: AsyncSession, source_branch_id: int) -> str:
    current = (
        await session.execute(
            select(func.max(func.cast(Transfer.transfer_no, Integer))).where(
                Transfer.source_branch_id == source_branch_id
            )
        )
    ).scalar_one()
    return str((current or 0) + 1)


async def get_transfer(
    session: AsyncSession, transfer_id: int, *, lock: bool = False
) -> tuple[Transfer, list[TransferLine]]:
    query = select(Transfer).where(Transfer.id == transfer_id)
    if lock:
        # serialize concurrent transitions of ONE transfer (double-click /
        # client retry): the second transaction blocks here until the first
        # commits, then its status re-check sees the new state → 409.
        # populate_existing: the router already loaded this row UNLOCKED into
        # the identity map — without this the ORM hands back the stale
        # pre-lock attributes and the status guard passes twice.
        query = query.with_for_update().execution_options(populate_existing=True)
    transfer = (await session.execute(query)).scalar_one_or_none()
    if transfer is None:
        raise NOT_FOUND
    lines = (
        await session.execute(
            select(TransferLine)
            .where(TransferLine.transfer_id == transfer.id)
            .order_by(TransferLine.id)
        )
    ).scalars().all()
    return transfer, list(lines)


def public_transfer(transfer: Transfer, lines: list[TransferLine]) -> dict:
    return {
        "id": transfer.id,
        "transfer_no": transfer.transfer_no,
        "source_branch_id": transfer.source_branch_id,
        "target_branch_id": transfer.target_branch_id,
        "status": transfer.status,
        "note": transfer.note,
        "legacy_fatid": transfer.legacy_fatid,
        "created_at": transfer.created_at.isoformat() if transfer.created_at else None,
        "dispatched_at": (
            transfer.dispatched_at.isoformat() if transfer.dispatched_at else None
        ),
        "received_at": (
            transfer.received_at.isoformat() if transfer.received_at else None
        ),
        "cancelled_at": (
            transfer.cancelled_at.isoformat() if transfer.cancelled_at else None
        ),
        "lines": [
            {
                "id": line.id,
                "drug_id": line.drug_id,
                "sent_qty": _qty4(line.sent_qty),
                "received_qty": (
                    _qty4(line.received_qty) if line.received_qty is not None else None
                ),
                "allocations": [
                    alloc.to_json()
                    for alloc in tstock.allocations_from_json(line.alloc_json)
                ],
            }
            for line in lines
        ],
    }


async def _snapshot_payload(transfer: Transfer, lines: list[TransferLine]) -> dict:
    """JSON-primitive snapshot of the transfer at its current state (outbox)."""
    return {
        "kind": ENTITY,
        "id": transfer.id,
        "transfer_no": transfer.transfer_no,
        "source_branch_id": transfer.source_branch_id,
        "target_branch_id": transfer.target_branch_id,
        "status": transfer.status,
        "legacy_fatid": transfer.legacy_fatid,
        "lines": [
            {
                "drug_id": line.drug_id,
                "sent_qty": _qty4(line.sent_qty),
                "received_qty": (
                    _qty4(line.received_qty) if line.received_qty is not None else None
                ),
                "allocations": line.alloc_json or [],
            }
            for line in lines
        ],
    }


async def _record(
    session: AsyncSession,
    *,
    caller_id: Optional[int],
    transfer: Transfer,
    lines: list[TransferLine],
    old_status: Optional[str],
    action: str,
) -> None:
    """Header audit + per-branch outbox rows for a transition (G12)."""
    await audit(
        session,
        branch_id=transfer.source_branch_id,
        user_id=caller_id,
        entity=ENTITY,
        entity_id=transfer.id,
        field="status",
        old_value=old_status,
        new_value=transfer.status,
        action=action,
        typevalue=transfer.transfer_no,
    )
    payload = await _snapshot_payload(transfer, lines)
    for branch_id in {transfer.source_branch_id, transfer.target_branch_id}:
        await enqueue_sync(
            session,
            branch_id=branch_id,
            entity=ENTITY,
            entity_id=transfer.id,
            action=action,
            payload=payload,
        )


async def create_draft(
    session: AsyncSession,
    *,
    caller: User,
    target_branch_id: int,
    lines: list[dict],
    legacy_fatid: Optional[str] = None,
    note: str = "",
) -> tuple[Transfer, list[TransferLine]]:
    if caller.branch_id is None:
        raise FORBIDDEN_BRANCH
    if int(target_branch_id) == int(caller.branch_id):
        raise SAME_BRANCH
    if not lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "lines must not be empty")
    for line in lines:
        if dec(line["qty"]) <= 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "qty must be positive")

    async with atomic(session):
        target = await session.get(Branch, target_branch_id)
        if target is None or not target.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "target branch not found")
        drug_ids = [line["drug_id"] for line in lines]
        rows = (
            await session.execute(select(Drug.id).where(Drug.id.in_(drug_ids)))
        ).scalars().all()
        if len(set(rows)) != len(set(drug_ids)):
            raise UNKNOWN_DRUG
        if len(drug_ids) != len(set(drug_ids)):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "each drug may appear on at most one line",
            )

        await acquire_branch_lock(session, caller.branch_id)
        transfer = Transfer(
            source_branch_id=caller.branch_id,
            target_branch_id=target_branch_id,
            transfer_no=await next_transfer_no(session, caller.branch_id),
            status="draft",
            legacy_fatid=legacy_fatid,
            note=note,
            created_by=caller.id,
        )
        session.add(transfer)
        await session.flush()

        created: list[TransferLine] = []
        for line in lines:
            tl = TransferLine(
                transfer_id=transfer.id,
                drug_id=line["drug_id"],
                sent_qty=dec(line["qty"]),
            )
            session.add(tl)
            created.append(tl)
        await session.flush()
        await _record(
            session,
            caller_id=caller.id,
            transfer=transfer,
            lines=created,
            old_status=None,
            action=ACTION_INSERT,
        )
        return transfer, created


async def dispatch(
    session: AsyncSession,
    *,
    caller: User,
    transfer: Transfer,
    explicit: dict[int, Optional[list[tuple[int, Decimal]]]] | None,
) -> list[TransferLine]:
    """draft → dispatched: decrement source stock with explicit batch
    allocations (FEFO suggested where the client sends none), validated under
    FOR UPDATE."""
    if transfer.status != "draft":
        raise BAD_STATE
    if caller.branch_id is None or caller.branch_id != transfer.source_branch_id:
        raise FORBIDDEN_BRANCH
    old_status = transfer.status

    async with atomic(session):
        transfer, lines = await get_transfer(session, transfer.id, lock=True)
        if transfer.status != "draft":
            raise BAD_STATE  # re-read post-lock truth
        # target (and source) may have been deactivated between draft and dispatch
        for bid in (transfer.source_branch_id, transfer.target_branch_id):
            b = await session.get(Branch, bid)
            if b is None or not b.is_active:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "source or target branch is inactive")

        per_line: dict[int, list[tstock.Allocation]] = {}
        explicit_ids = set(explicit or {})
        line_ids = {line.id for line in lines}
        if explicit is not None and (explicit_ids - line_ids or not explicit_ids):
            # a typo'd id must never silently fall back to full-FEFO
            raise LINE_NOT_COVERED
        for line in lines:
            takes = (explicit or {}).get(line.id)
            if takes is None:
                allocations = await tstock.suggest_fefo(
                    session,
                    branch_id=transfer.source_branch_id,
                    drug_id=line.drug_id,
                    qty=dec(line.sent_qty),
                )
            else:
                allocations = await tstock.validate_explicit(
                    session,
                    branch_id=transfer.source_branch_id,
                    drug_id=line.drug_id,
                    takes=takes,
                )
                total = sum((a.take for a in allocations), Decimal("0"))
                if total != dec(line.sent_qty):
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        "allocated qty must equal sent_qty",
                    )
            per_line[line.id] = allocations

        # apply only after every line validated
        for line in lines:
            await tstock.dispatch_line(
                session,
                source_branch_id=transfer.source_branch_id,
                user_id=caller.id,
                drug_id=line.drug_id,
                allocations=per_line[line.id],
                transfer_no=transfer.transfer_no,
            )
            line.alloc_json = [a.to_json() for a in per_line[line.id]]

        transfer.status = "dispatched"
        transfer.dispatched_by = caller.id
        transfer.dispatched_at = datetime.now(timezone.utc)
        session.add(transfer)
        await _record(
            session,
            caller_id=caller.id,
            transfer=transfer,
            lines=lines,
            old_status=old_status,
            action=ACTION_UPDATE,
        )
        return lines


async def receive(
    session: AsyncSession,
    *,
    caller: User,
    transfer: Transfer,
    receipts: dict[int, Decimal],
) -> list[TransferLine]:
    """dispatched → received: per-line received_qty ≤ sent_qty; shortfall
    auto-returns to the source batches."""
    if transfer.status != "dispatched":
        raise BAD_STATE
    if caller.branch_id is None or caller.branch_id != transfer.target_branch_id:
        raise FORBIDDEN_BRANCH
    old_status = transfer.status

    async with atomic(session):
        transfer, lines = await get_transfer(session, transfer.id, lock=True)
        if transfer.status != "dispatched":
            raise BAD_STATE
        for bid in (transfer.source_branch_id, transfer.target_branch_id):
            b = await session.get(Branch, bid)
            if b is None or not b.is_active:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "source or target branch is inactive")
        if set(receipts) != {line.id for line in lines}:
            raise LINE_NOT_COVERED
        for line in lines:
            qty = receipts[line.id]
            if qty < 0:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "received_qty must not be negative",
                )
            if qty > dec(line.sent_qty):
                raise RECEIVE_TOO_MUCH

        for line in lines:
            allocations = tstock.allocations_from_json(line.alloc_json)
            line.received_qty = await tstock.receive_line(
                session,
                source_branch_id=transfer.source_branch_id,
                target_branch_id=transfer.target_branch_id,
                user_id=caller.id,
                drug_id=line.drug_id,
                allocations=allocations,
                received_qty=receipts[line.id],
                transfer_no=transfer.transfer_no,
            )

        transfer.status = "received"
        transfer.received_by = caller.id
        transfer.received_at = datetime.now(timezone.utc)
        session.add(transfer)
        await _record(
            session,
            caller_id=caller.id,
            transfer=transfer,
            lines=lines,
            old_status=old_status,
            action=ACTION_UPDATE,
        )
        return lines


async def cancel(session: AsyncSession, *, caller: User, transfer: Transfer) -> list[TransferLine]:
    """draft → cancelled: either managing party; nothing was moved yet."""
    parties = {transfer.source_branch_id, transfer.target_branch_id}
    if caller.branch_id not in parties:
        raise FORBIDDEN_BRANCH
    if transfer.status != "draft":
        raise BAD_STATE
    old_status = transfer.status

    async with atomic(session):
        transfer, lines = await get_transfer(session, transfer.id, lock=True)
        if transfer.status != "draft":
            raise BAD_STATE
        transfer.status = "cancelled"
        transfer.cancelled_by = caller.id
        transfer.cancelled_at = datetime.now(timezone.utc)
        session.add(transfer)
        await _record(
            session,
            caller_id=caller.id,
            transfer=transfer,
            lines=lines,
            old_status=old_status,
            action=ACTION_UPDATE,
        )
        return lines
