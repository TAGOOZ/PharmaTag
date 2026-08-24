"""Offline replay of a transfer from its outbox snapshot (#55).

Both branches receive the SAME `entity='transfer'` payload copy (G12), so
dedupe is keyed on the SOURCE namespace UNIQUE(source_branch_id, transfer_no)
— never on sync_log.branch_id (a target-side copy would otherwise pass a
spurious existence check). Replay applies RECORDED EFFECTS VERBATIM —
lot-exact, because ETA cost trails and expiry tracking are legally
significant: allocations carry canonical 4dp/2dp strings and land exactly as
`receive_line` books them; validation and FEFO are NEVER re-run. Draft and
cancelled payloads are metadata-only (nothing moved yet).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.core.money import dec
from app.models import Transfer, TransferLine
from app.transfers import stock as tstock


async def transfer_exists(session: AsyncSession, payload: dict) -> bool:
    """Dedupe check keyed on the SOURCE namespace (uq_transfers_branch_no).

    Malformed payloads report "absent" so they fall through to the apply path
    and are recorded as failures instead of being silently skipped."""
    source_branch_id = payload.get("source_branch_id")
    transfer_no = payload.get("transfer_no")
    if source_branch_id is None or not transfer_no:
        return False
    row = (
        await session.execute(
            select(Transfer.id).where(
                Transfer.source_branch_id == int(source_branch_id),
                Transfer.transfer_no == str(transfer_no),
            )
        )
    ).scalars().first()
    return row is not None


async def apply_transfer_payload(
    session: AsyncSession,
    *,
    payload: dict[str, Any],
    user_id: Optional[int] = None,
) -> Transfer:
    """Reconstruct a transfer from its outbox snapshot.

    The caller (sync.replay_pending) owns dedupe and the status/failure
    transitions; this runs inside that row's SAVEPOINT. Assumes it runs inside
    the caller's transaction.
    """
    try:
        transfer_no = str(payload["transfer_no"])
        record_status = str(payload["status"])
        line_rows = list(payload["lines"])
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "malformed transfer outbox row"
        ) from exc

    transfer = Transfer(
        source_branch_id=int(payload["source_branch_id"]),
        target_branch_id=int(payload["target_branch_id"]),
        transfer_no=transfer_no,
        status=record_status,
        legacy_fatid=payload.get("legacy_fatid"),
    )
    session.add(transfer)
    await session.flush()

    lines: list[TransferLine] = []
    for lp in line_rows:
        received_raw = lp.get("received_qty")
        if record_status == "received" and received_raw is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "received transfer payload missing received_qty",
            )
        line = TransferLine(
            transfer_id=transfer.id,
            drug_id=int(lp["drug_id"]),
            sent_qty=dec(lp["sent_qty"]),
            received_qty=dec(received_raw) if received_raw is not None else None,
            alloc_json=(
                list(lp["allocations"]) if lp.get("allocations") is not None else None
            ),
        )
        session.add(line)
        lines.append(line)
    await session.flush()

    if record_status in ("dispatched", "received"):
        # recorded effects verbatim — no validation, no FEFO re-run. A merely
        # dispatched snapshot lands every allocated unit (the goods left the
        # source); a received snapshot lands up to received_qty head-first and
        # receive_line reproduces the shortfall auto-return itself.
        for line in lines:
            allocations = tstock.allocations_from_json(line.alloc_json)
            if record_status == "dispatched":
                received = sum((a.take for a in allocations), Decimal("0"))
            else:
                received = dec(line.received_qty)
            await tstock.receive_line(
                session,
                source_branch_id=transfer.source_branch_id,
                target_branch_id=transfer.target_branch_id,
                user_id=user_id,
                drug_id=line.drug_id,
                allocations=allocations,
                received_qty=received,
                transfer_no=transfer_no,
            )

    await audit(
        session,
        branch_id=transfer.source_branch_id,
        user_id=user_id,
        entity="transfer",
        entity_id=transfer.id,
        field="status",
        old_value=None,
        new_value=record_status,
        action=ACTION_INSERT,
        typevalue=transfer_no,
    )
    return transfer
