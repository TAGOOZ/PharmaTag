"""Sync conflict review panel — LWW auto-resolve + non-destructive UI (G10, #60).

Lists LWW losses (sync_log rows that were skipped as stale/duplicate) with
loser payload + winner snapshot + updated_at, branch-scoped. Restore reapplies
the loser as a new rev with audit — never mutates history in place.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit, enqueue_sync
from app.core.db import atomic
from app.models import (
    Branch,
    BranchIdentity,
    BranchStock,
    SyncLog,
    Transfer,
)

# entities that support LWW conflict listing
CONFLICT_ENTITIES = {
    "invoice",
    "branch_stock",
    "transfer",
    "need",
    "purchase_order",
    "branch",
    "branch_identity",
    "chain_buy_order",
}


async def _winner_branch(payload: dict, session: AsyncSession) -> Optional[dict]:
    raw = payload.get("id")
    if raw is None:
        return None
    try:
        bid = int(raw)  # type: ignore[arg-type]
    except Exception:
        return None
    row = await session.get(Branch, bid)
    if row is None:
        return None
    return {
        "id": row.id,
        "pharmacyid": row.pharmacyid,
        "mobile": row.mobile,
        "pharname": row.pharname,
        "phar": row.phar,
        "is_active": row.is_active,
        "is_main_device": row.is_main_device,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def _winner_branch_identity(payload: dict, session: AsyncSession) -> Optional[dict]:
    try:
        lt = str(payload["legacy_table"])
        lc = str(payload["legacy_column"])
        lv = str(payload["legacy_value"])
    except Exception:
        return None
    from app.models import BranchIdentity

    row = (
        await session.execute(
            select(BranchIdentity).where(
                BranchIdentity.legacy_table == lt,
                BranchIdentity.legacy_column == lc,
                BranchIdentity.legacy_value == lv,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return {
        "legacy_table": row.legacy_table,
        "legacy_column": row.legacy_column,
        "legacy_value": row.legacy_value,
        "branch_id": row.branch_id,
    }


async def _winner_branch_stock(payload: dict, session: AsyncSession, branch_id: int) -> Optional[dict]:
    try:
        drug_id = int(payload.get("drug_id"))
    except Exception:
        return None
    row = (
        await session.execute(
            select(BranchStock).where(
                BranchStock.branch_id == branch_id,
                BranchStock.drug_id == drug_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return {
        "branch_id": row.branch_id,
        "drug_id": row.drug_id,
        "qty": str(row.qty),
        "minimum": str(row.minimum),
        "silsilaid": row.silsilaid or "",
        "classy": row.classy or "",
        "lastedit": row.lastedit.isoformat() if row.lastedit else None,
        "updated_at": row.lastedit.isoformat() if row.lastedit else None,
    }


async def _winner_transfer(payload: dict, session: AsyncSession) -> Optional[dict]:
    try:
        transfer_no = str(payload["transfer_no"])
        source_branch_id = int(payload["source_branch_id"])
    except Exception:
        return None
    row = (
        await session.execute(
            select(Transfer).where(
                Transfer.source_branch_id == source_branch_id,
                Transfer.transfer_no == transfer_no,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "source_branch_id": row.source_branch_id,
        "target_branch_id": row.target_branch_id,
        "transfer_no": row.transfer_no,
        "status": row.status,
        "rev": row.rev,
        "updated_at": (
            row.received_at.isoformat()
            if row.received_at
            else row.dispatched_at.isoformat()
            if row.dispatched_at
            else row.created_at.isoformat()
            if row.created_at
            else None
        ),
    }


async def _winner_generic(payload: dict, entity: str) -> Optional[dict]:
    # fallback for entities without dedicated winner query — payload itself
    return None


async def _fetch_winner(
    session: AsyncSession, row: SyncLog, payload: dict
) -> Optional[dict]:
    entity = row.entity
    try:
        if entity == "branch":
            return await _winner_branch(payload, session)
        if entity == "branch_identity":
            return await _winner_branch_identity(payload, session)
        if entity == "branch_stock":
            return await _winner_branch_stock(payload, session, row.branch_id)
        if entity == "transfer":
            return await _winner_transfer(payload, session)
        if entity == "need":
            # use generic need fetch via direct SQL to avoid import cycles
            try:
                nid = int(payload.get("id"))
                result = await session.execute(
                    select(
                        # import lazily
                        __import__("app.models.chain", fromlist=["Need"]).Need
                    ).where(
                        __import__("app.models.chain", fromlist=["Need"]).Need.id == nid
                    )
                )
                obj = result.scalar_one_or_none()
                if obj is not None:
                    return {
                        "id": obj.id,
                        "status": getattr(obj, "status", None),
                        "rev": getattr(obj, "rev", None),
                        "updated_at": getattr(obj, "updated_at", None).isoformat() if getattr(obj, "updated_at", None) else None,
                    }
            except Exception:
                pass
            return None
        if entity == "purchase_order":
            return None
        if entity == "chain_buy_order":
            return None
        if entity == "invoice":
            # winner is current invoice if exists
            try:
                from app.models import Invoice

                # dedupe key is (branch_id, invoice_no)
                invoice_no = str(payload.get("invoice_no", ""))
                branch_id = int(payload.get("branch_id", row.branch_id))
                existing = (
                    await session.execute(
                        select(Invoice).where(
                            Invoice.branch_id == branch_id,
                            Invoice.invoice_no == invoice_no,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    return {
                        "id": existing.id,
                        "branch_id": existing.branch_id,
                        "invoice_no": existing.invoice_no,
                        "kind": existing.kind,
                        "status": existing.status,
                        "updated_at": existing.updated_at.isoformat() if existing.updated_at else None,
                    }
            except Exception:
                pass
            return None
    except Exception:
        return None
    return None


def _loser_payload(payload: dict) -> dict:
    """Loser is the original payload without bookkeeping keys."""
    return {k: v for k, v in payload.items() if k not in ("skipped_reason", "failure", "resolved", "resolved_at", "restored_at")}


async def list_conflicts(
    session: AsyncSession,
    *,
    branch_id: int,
    entity: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return LWW losses for a branch, optionally filtered by entity."""
    # conflicts are rows that were delivered but skipped — status applied/skipped with skipped_reason
    stmt = select(SyncLog).where(
        SyncLog.branch_id == branch_id,
        SyncLog.status.in_(["applied", "skipped"]),
    )
    if entity:
        stmt = stmt.where(SyncLog.entity == entity)
    stmt = stmt.order_by(SyncLog.id.desc())
    rows = (await session.execute(stmt)).scalars().all()
    # Python-side filter for skipped_reason presence (JSONB has_key is PG-specific)
    conflicts: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row.payload or {})
        reason = payload.get("skipped_reason")
        if not reason:
            continue
        loser = _loser_payload(payload)
        winner = await _fetch_winner(session, row, loser)
        # updated_at is winner's updated_at or row's synced_at/created_at
        winner_updated = None
        if winner and winner.get("updated_at"):
            winner_updated = winner["updated_at"]
        elif row.synced_at:
            winner_updated = row.synced_at.isoformat()
        elif row.created_at:
            winner_updated = row.created_at.isoformat()
        conflicts.append(
            {
                "id": row.id,
                "branch_id": row.branch_id,
                "entity": row.entity,
                "entity_id": row.entity_id,
                "action": row.action,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "synced_at": row.synced_at.isoformat() if row.synced_at else None,
                "updated_at": winner_updated,
                "skipped_reason": reason,
                "loser": loser,
                "winner": winner,
                "payload": loser,  # alias for loser per AC wording
                "resolved": bool(payload.get("resolved") or payload.get("resolved_at") or payload.get("restored_at")),
            }
        )
    return conflicts


async def restore_conflict(
    session: AsyncSession,
    *,
    conflict_id: int,
    branch_id: int,
    user_id: Optional[int],
) -> dict[str, Any]:
    """Reapply loser payload as a new rev with audit — never mutates history in place."""
    row = await session.get(SyncLog, conflict_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conflict not found")
    if int(row.branch_id) != int(branch_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-branch restore forbidden")
    payload = dict(row.payload or {})
    skipped = payload.get("skipped_reason")
    if not skipped:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "row is not a conflict (no skipped_reason)")
    if payload.get("resolved") or payload.get("resolved_at") or payload.get("restored_at"):
        raise HTTPException(status.HTTP_409_CONFLICT, "conflict already restored")
    loser = _loser_payload(payload)
    entity = row.entity

    async with atomic(session):
        # branch-scoped advisory lock for entities that mutate branch_stock/transfer
        # to avoid racing restores with concurrent writes — must not fail silently
        if entity in ("branch_stock", "transfer", "branch", "branch_identity"):
            from app.sales.numbering import acquire_branch_lock

            try:
                await acquire_branch_lock(session, branch_id)
            except Exception as exc:
                # log and surface as 503 — running without lock would race
                import logging

                logging.getLogger(__name__).exception(
                    "acquire_branch_lock failed for branch %s during restore %s: %s",
                    branch_id,
                    conflict_id,
                    exc,
                )
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "could not acquire branch lock for restore — try again",
                ) from exc

        # --- entity-specific restore ---
        if entity == "branch_stock":
            await _restore_branch_stock(session, loser, branch_id, user_id)
        elif entity == "transfer":
            await _restore_transfer(session, loser, branch_id, user_id)
        elif entity == "branch":
            await _restore_branch(session, loser, user_id)
        elif entity == "branch_identity":
            await _restore_branch_identity(session, loser, user_id)
        elif entity in ("need", "purchase_order", "chain_buy_order"):
            await _restore_versioned_generic(session, loser, entity, branch_id, user_id)
        elif entity == "invoice":
            # invoices are idempotent on (branch_id, invoice_no) — restore would
            # need to re-create a missing invoice? For non-destructive restore,
            # we just audit that we attempted; the winner is kept. Simplest:
            # reapply via sales replay if invoice missing? But winner already exists,
            # so we treat restore as noop with audit.
            await _restore_invoice(session, loser, branch_id, user_id)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"restore not supported for entity '{entity}'")

        # mark original conflict as resolved (does not mutate entity history, only bookkeeping)
        row.payload = {**payload, "resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat(), "restored_by": user_id}
        session.add(row)

        # also record audit for the restore action itself
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity=entity,
            entity_id=row.entity_id,
            field="restore",
            old_value=str(skipped),
            new_value=str(loser),
            action="update",
            namee=f"conflict#{row.id}",
        )

    winner = await _fetch_winner(session, row, loser)
    return {
        "id": row.id,
        "branch_id": row.branch_id,
        "entity": row.entity,
        "loser": loser,
        "winner": winner,
        "restored": True,
    }


async def _restore_branch_stock(
    session: AsyncSession, loser: dict, branch_id: int, user_id: Optional[int]
) -> None:
    """Restore branch_stock absolute values from loser payload as new state."""
    from sqlalchemy import select as sel

    from app.core import money
    from app.models import BranchStock, Drug

    try:
        drug_id = int(loser.get("drug_id"))
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "malformed branch_stock loser payload")
    qty_raw = loser.get("qty")
    minimum_raw = loser.get("minimum")
    # validate loser values are decimal-like
    try:
        if qty_raw is not None:
            money.dec(str(qty_raw))
        if minimum_raw is not None:
            money.dec(str(minimum_raw))
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid qty/minimum in loser payload")

    drug = await session.get(Drug, drug_id)
    if drug is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "drug not found for restore")

    row = (
        await session.execute(
            sel(BranchStock).where(
                BranchStock.branch_id == branch_id,
                BranchStock.drug_id == drug_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = BranchStock(
            branch_id=branch_id,
            drug_id=drug_id,
            qty=money.dec("0"),
            minimum=money.dec("0"),
        )
        session.add(row)
        old_qty = None
        old_min = None
    else:
        old_qty = str(row.qty)
        old_min = str(row.minimum)

    if qty_raw is not None:
        row.qty = money.dec(str(qty_raw))
    if minimum_raw is not None:
        row.minimum = money.dec(str(minimum_raw))
    if "silsilaid" in loser and loser["silsilaid"] is not None:
        row.silsilaid = str(loser["silsilaid"])
    if "classy" in loser and loser["classy"] is not None:
        row.classy = str(loser["classy"])
    row.lastedit = datetime.now(timezone.utc)
    session.add(row)
    await session.flush()

    # audit + outbox as new rev (absolute LWW)
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="branch_stock",
        entity_id=drug_id,
        field="restore",
        old_value=f"qty={old_qty},minimum={old_min}",
        new_value=f"qty={qty_raw},minimum={minimum_raw}",
        drug_id=drug_id,
        action="update",
    )
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity="branch_stock",
        entity_id=drug_id,
        action="update",
        payload={
            "branch_id": branch_id,
            "drug_id": drug_id,
            "qty": str(row.qty) if qty_raw is not None else str(row.qty),
            "minimum": str(row.minimum) if minimum_raw is not None else str(row.minimum),
            "silsilaid": row.silsilaid or "",
            "classy": row.classy or "",
        },
    )


async def _restore_transfer(
    session: AsyncSession, loser: dict, peer_branch_id: int, user_id: Optional[int]
) -> None:
    """Restore transfer loser as new rev = current rev +1, folding if needed."""
    from app.transfers.replay import _rev_of

    try:
        transfer_no = str(loser["transfer_no"])
        source_branch_id = int(loser["source_branch_id"])
        target_branch_id = int(loser["target_branch_id"])
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "malformed transfer loser payload")
    # current local row
    existing = (
        await session.execute(
            select(Transfer).where(
                Transfer.source_branch_id == source_branch_id,
                Transfer.transfer_no == transfer_no,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    current_rev = int(existing.rev or 1) if existing else 0
    loser_rev = _rev_of(loser)
    # new rev must exceed current to win LWW; if loser already newer, keep it else bump
    new_rev = max(loser_rev, current_rev + 1)
    # build new payload that will be applied as current +1
    new_payload = dict(loser)
    new_payload["rev"] = new_rev
    new_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    # use versioned applier directly
    from app.transfers.replay import apply_transfer_versioned

    outcome = await apply_transfer_versioned(
        session, payload=new_payload, peer_branch_id=peer_branch_id, user_id=user_id
    )
    # normalize: versioned appliers may return (status, reason)
    outcome_status = outcome[0] if isinstance(outcome, tuple) else outcome
    if outcome_status == "skipped":
        # bumped rev should never be skipped — do not silently mutate header
        # without audit/outbox; surface as conflict so manager can retry
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "restore was skipped — newer local state exists or payload could not be applied",
        )


async def _restore_branch(
    session: AsyncSession, loser: dict, user_id: Optional[int]
) -> None:
    """Restore branch loser as new updated_at = now() with same fields."""
    try:
        bid = int(loser["id"])
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "malformed branch loser payload")
    new_payload = dict(loser)
    new_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    # bump updated_at to now so LWW will win
    from app.branches.replay import apply_branch_versioned

    outcome, _ = await apply_branch_versioned(session, payload=new_payload, user_id=user_id)
    if outcome == "skipped":
        raise HTTPException(status.HTTP_409_CONFLICT, "restore was skipped — newer local state exists")


async def _restore_branch_identity(
    session: AsyncSession, loser: dict, user_id: Optional[int]
) -> None:
    from app.branches.replay import apply_identity_versioned

    outcome, _ = await apply_identity_versioned(session, payload=loser, user_id=user_id)
    if outcome == "skipped":
        raise HTTPException(status.HTTP_409_CONFLICT, "restore was skipped — mapping already matches")


async def _restore_versioned_generic(
    session: AsyncSession, loser: dict, entity: str, branch_id: int, user_id: Optional[int]
) -> None:
    """Generic LWW versioned restore for need/purchase_order/chain_buy."""
    # bump rev to current +1 so it wins
    try:
        current_rev = int(loser.get("rev", 1))
    except Exception:
        current_rev = 1
    # fetch current local rev if exists
    new_rev = current_rev + 1
    # try to increment to be safe: if local rev is higher, bump past it
    try:
        if entity == "need":
            from app.models.chain import Need  # type: ignore

            nid = int(loser.get("id"))
            local = await session.get(Need, nid)
            if local is not None and int(getattr(local, "rev", 1) or 1) >= new_rev:
                new_rev = int(getattr(local, "rev", 1)) + 1
        elif entity == "purchase_order":
            from app.models.chain import PurchaseOrder  # type: ignore

            pid = int(loser.get("id"))
            local = await session.get(PurchaseOrder, pid)
            if local is not None and int(getattr(local, "rev", 1) or 1) >= new_rev:
                new_rev = int(getattr(local, "rev", 1)) + 1
    except Exception:
        pass
    new_payload = dict(loser)
    new_payload["rev"] = new_rev
    new_payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    if entity == "need":
        from app.needs.replay import apply_need_versioned

        outcome, _ = await apply_need_versioned(session, payload=new_payload, user_id=user_id)  # type: ignore
        # apply_need_versioned returns tuple? Actually returns str|tuple; normalize
        if isinstance(outcome, tuple):
            outcome = outcome[0]
        if outcome == "skipped":
            raise HTTPException(status.HTTP_409_CONFLICT, "restore skipped")
    elif entity == "purchase_order":
        from app.purchase_orders.replay import apply_po_versioned

        outcome, _ = await apply_po_versioned(session, payload=new_payload, user_id=user_id)  # type: ignore
        if isinstance(outcome, tuple):
            outcome = outcome[0]
        if outcome == "skipped":
            raise HTTPException(status.HTTP_409_CONFLICT, "restore skipped")
    elif entity == "chain_buy_order":
        from app.chain_buy.replay import apply_chain_buy_versioned

        result = await apply_chain_buy_versioned(session, payload=new_payload, peer_branch_id=branch_id, user_id=user_id)
        if isinstance(result, tuple):
            result = result[0]
        if result == "skipped":
            raise HTTPException(status.HTTP_409_CONFLICT, "restore skipped")
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported entity for restore")


async def _restore_invoice(
    session: AsyncSession, loser: dict, branch_id: int, user_id: Optional[int]
) -> None:
    """Invoice restore: if loser invoice_no missing locally, re-create it; else audit only."""
    invoice_no = str(loser.get("invoice_no", ""))
    if not invoice_no:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "malformed invoice loser payload")
    from sqlalchemy import select as sel

    from app.models import Invoice

    exists = (
        await session.execute(
            sel(Invoice.id).where(
                Invoice.branch_id == branch_id,
                Invoice.invoice_no == invoice_no,
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        # already exists — restore is a no-op but we audit that manager reviewed
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="invoice",
            entity_id=exists,
            field="restore",
            old_value="winner kept",
            new_value=f"loser reviewed invoice_no={invoice_no}",
            action="update",
        )
        return
    # missing — reapply loser via replay (reuse sale replay path)
    from app.sync.service import _apply_row

    try:
        await _apply_row(session, branch_id=branch_id, payload=loser, user_id=user_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"restore failed: {exc}")
    # audit already inside _apply_row's replay? We add an explicit audit for restore
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="invoice",
        field="restore",
        old_value="missing",
        new_value=invoice_no,
        action="insert",
    )
