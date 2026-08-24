"""Versioned offline replay of `entity='transfer'` outbox rows (#55).

Both branches receive the SAME payload copy of every transition (G12); each
peer replays only its OWN copies (sync_log.branch_id), so every stock effect
is BRANCH-FILTERED: the source copy owns dispatch decrements + shortfall
restores, the target copy owns lot landings. Replay applies RECORDED EFFECTS
VERBATIM — lot-exact, because ETA cost trails and expiry tracking are legally
significant; validation and FEFO are NEVER re-run.

Ordering authority is the monotonic `rev` watermark (draft=1, dispatched=2,
received/cancelled=3) — `updated_at` stays diagnostics-only and is never
compared. A payload whose rev <= local rev is stale/duplicate → skipped.
A payload with rev > local rev UPGRADES by folding the legal chain of stages
between local status and payload status, each stage's effects inside ONE
savepoint (crash-safe: a mid-fold failure rolls back header flip + stock
together). An illegal transition (e.g. received local, cancelled payload) is
poisoned: fails alone, stays pending, recorded (G10).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit
from app.core.money import dec
from app.models import Transfer, TransferLine
from app.transfers import stock as tstock

# canonical stage order; cancel branches off sideways from draft only
_REV_BY_STATUS = {"draft": 1, "dispatched": 2, "received": 3, "cancelled": 3}

MALFORMED = HTTPException(
    status.HTTP_400_BAD_REQUEST, "malformed transfer outbox row"
)


def _rev_of(payload: dict) -> int:
    """Payload revision; legacy pre-030 payloads fall back to their status."""
    raw = payload.get("rev")
    if raw is None:
        return _REV_BY_STATUS.get(str(payload.get("status")), 1)
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise MALFORMED


def _stage_chain(from_status: str, to_status: str) -> list[str]:
    """Legal fold between two states; anything else is a poisoned row."""
    if from_status == to_status:
        return []
    if from_status == "draft" and to_status == "dispatched":
        return ["dispatch"]
    if from_status == "draft" and to_status == "received":
        return ["dispatch", "receive"]
    if from_status == "dispatched" and to_status == "received":
        return ["receive"]
    if from_status == "draft" and to_status == "cancelled":
        return []  # metadata-only: nothing ever moved
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        f"illegal transfer transition {from_status!r} -> {to_status!r}",
    )


async def _load_local(
    session: AsyncSession, source_branch_id: int, transfer_no: str
) -> Optional[Transfer]:
    """Dedupe keyed on the SOURCE namespace (uq_transfers_branch_no)."""
    return (
        await session.execute(
            select(Transfer).where(
                Transfer.source_branch_id == source_branch_id,
                Transfer.transfer_no == str(transfer_no),
            )
        )
    ).scalars().first()


async def _apply_dispatch_stage(
    session: AsyncSession,
    *,
    source_branch_id: int,
    line_rows: list[dict],
    peer_branch_id: int,
    user_id: Optional[int],
    transfer_no: str,
) -> None:
    """Stage dispatch: decrement source batches + branch_stock per alloc_json —
    on the SOURCE peer's copy only (the target copy is header-only)."""
    if int(peer_branch_id) != int(source_branch_id):
        return
    for lp in line_rows:
        allocations = tstock.allocations_from_json(lp.get("allocations"))
        await tstock.dispatch_line(
            session,
            source_branch_id=source_branch_id,
            user_id=user_id,
            drug_id=int(lp["drug_id"]),
            allocations=allocations,
            transfer_no=transfer_no,
        )


async def _apply_receive_stage(
    session: AsyncSession,
    *,
    source_branch_id: int,
    target_branch_id: int,
    line_rows: list[dict],
    peer_branch_id: int,
    user_id: Optional[int],
    transfer_no: str,
) -> None:
    """Stage receive: branch-filtered halves of receive_line (#55 gap fix).
    The TARGET peer lands lots up to received_qty exactly; the SOURCE peer
    restores the shortfall head-first across allocations."""
    peer = int(peer_branch_id)
    for lp in line_rows:
        allocations = tstock.allocations_from_json(lp.get("allocations"))
        drug_id = int(lp["drug_id"])
        received_raw = lp.get("received_qty")
        if received_raw is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "received transfer payload missing received_qty",
            )
        received = dec(received_raw)
        if peer == int(target_branch_id):
            await tstock.land_target_lots(
                session,
                target_branch_id=target_branch_id,
                user_id=user_id,
                drug_id=drug_id,
                allocations=allocations,
                received_qty=received,
                transfer_no=transfer_no,
            )
        elif peer == int(source_branch_id):
            await tstock.restore_source_shortfall(
                session,
                source_branch_id=source_branch_id,
                user_id=user_id,
                drug_id=drug_id,
                allocations=allocations,
                received_qty=received,
                transfer_no=transfer_no,
            )


def _parse_payload(payload: dict[str, Any]) -> tuple[str, str, int, list]:
    try:
        transfer_no = str(payload["transfer_no"])
        record_status = str(payload["status"])
        source_branch_id = int(payload["source_branch_id"])
        line_rows = list(payload["lines"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MALFORMED from exc
    return transfer_no, record_status, source_branch_id, line_rows


async def _upsert_lines_from_payload(
    session: AsyncSession, transfer: Transfer, line_rows: list[dict]
) -> None:
    """Reconcile the local lines to the payload's snapshot (allocations +
    received_qty) so later upgrades have the full evidence chain."""
    existing = {
        line.drug_id: line
        for line in (
            await session.execute(
                select(TransferLine).where(TransferLine.transfer_id == transfer.id)
            )
        ).scalars().all()
    }
    for lp in line_rows:
        drug_id = int(lp["drug_id"])
        received_raw = lp.get("received_qty")
        line = existing.get(drug_id)
        if line is None:
            line = TransferLine(transfer_id=transfer.id, drug_id=drug_id)
            session.add(line)
        line.sent_qty = dec(lp["sent_qty"])
        line.received_qty = dec(received_raw) if received_raw is not None else None
        line.alloc_json = list(lp["allocations"]) if lp.get("allocations") else None


async def apply_transfer_versioned(
    session: AsyncSession,
    *,
    payload: dict[str, Any],
    peer_branch_id: int,
    user_id: Optional[int] = None,
) -> str:
    """Versioned apply of one transfer outbox row; returns 'applied'|'skipped'.

    The caller (sync.replay_pending) owns the SAVEPOINT and the row's status/
    failure transitions; this runs inside the caller's transaction.

    * no local row → create from the full snapshot at the payload's rev,
      folding every stage's branch-filtered effects up to the payload state.
    * payload rev <= local rev → duplicate/stale/out-of-order → 'skipped'.
    * payload rev > local rev → upgrade: fold the legal stages between local
      status and payload status in ONE savepoint (caller-provided); illegal
      chains raise (poisoned row).
    """
    transfer_no, record_status, source_branch_id, line_rows = _parse_payload(payload)
    payload_rev = _rev_of(payload)

    local = await _load_local(session, source_branch_id, transfer_no)
    if local is not None and payload_rev <= int(local.rev or 1):
        return "skipped"

    from_status = local.status if local is not None else "draft"
    stages = _stage_chain(from_status, record_status)

    if local is None:
        local = Transfer(
            source_branch_id=source_branch_id,
            target_branch_id=int(payload["target_branch_id"]),
            transfer_no=transfer_no,
            status=record_status,
            rev=payload_rev,
            legacy_fatid=payload.get("legacy_fatid"),
        )
        session.add(local)
        await session.flush()
        action = ACTION_INSERT
        old_status = None
    else:
        action = ACTION_UPDATE
        old_status = local.status

    for stage in stages:
        if stage == "dispatch":
            await _apply_dispatch_stage(
                session,
                source_branch_id=source_branch_id,
                line_rows=line_rows,
                peer_branch_id=peer_branch_id,
                user_id=user_id,
                transfer_no=transfer_no,
            )
        elif stage == "receive":
            await _apply_receive_stage(
                session,
                source_branch_id=source_branch_id,
                target_branch_id=int(payload["target_branch_id"]),
                line_rows=line_rows,
                peer_branch_id=peer_branch_id,
                user_id=user_id,
                transfer_no=transfer_no,
            )

    # header + lines converge to the payload's truth INSIDE the same savepoint
    local.status = record_status
    local.rev = payload_rev
    session.add(local)
    await session.flush()
    await _upsert_lines_from_payload(session, local, line_rows)

    await audit(
        session,
        branch_id=source_branch_id,
        user_id=user_id,
        entity="transfer",
        entity_id=local.id,
        field="status",
        old_value=old_status,
        new_value=record_status,
        action=action,
        typevalue=transfer_no,
    )
    return "applied"
