"""Need use-cases (#33): entry, list, cancel, fulfillment link.

A need is a branch's stock request to a sister branch (titanneed semantics):
the caller's branch is always the requesting/target side (C9 branch scoping);
`sender_branch_id` optionally pins ONE fulfilling branch, NULL = open request.
Every mutation writes its audit row AND `entity='need'` outbox rows per
affected branch atomically (G12); `rev` bumps per transition as the ordering
authority for versioned offline replay (#55 pattern).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit, enqueue_sync
from app.core.db import atomic
from app.core.money import dec, round4
from app.models import Branch, Drug, Need, User

ENTITY = "need"

# Strictly increasing ladder — every transition must EXCEED the previous rev
# or versioned peers will skip the follow-up payload (rev <= local rev).
REV_CREATE = 1
REV_LINK = 2      # handoff pickup: transfer linked / sender pinned
REV_TERMINAL = 3  # fulfilled / cancelled

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "need not found")
FORBIDDEN_BRANCH = HTTPException(
    status.HTTP_403_FORBIDDEN, "caller is not a party to this need"
)
NO_BRANCH = HTTPException(
    status.HTTP_403_FORBIDDEN, "caller is not pinned to a branch"
)
UNKNOWN_DRUG = HTTPException(status.HTTP_400_BAD_REQUEST, "unknown drug")
UNKNOWN_BRANCH = HTTPException(status.HTTP_400_BAD_REQUEST, "unknown sender branch")
SELF_PINNED = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    "sender branch must differ from the requesting branch",
)


def _qty4(value: Decimal) -> str:
    return format(round4(value), "f")


def public_need(need: Need) -> dict:
    return {
        "id": need.id,
        "branch_id": need.branch_id,
        "drug_id": need.drug_id,
        "qty": _qty4(need.qty),
        "datee": need.datee.isoformat() if need.datee else None,
        "sender_branch_id": need.sender_branch_id,
        "target_branch_id": need.target_branch_id,
        "status": need.status,
        "transfer_id": need.transfer_id,
        "rev": int(need.rev or 1),
        "created_at": need.created_at.isoformat() if need.created_at else None,
        "fulfilled_at": (
            need.fulfilled_at.isoformat() if need.fulfilled_at else None
        ),
    }


def snapshot_payload(need: Need) -> dict:
    """JSON-primitive LWW snapshot for the sync outbox."""
    stamps = [ts for ts in (need.fulfilled_at, need.created_at) if ts is not None]
    return {
        "kind": ENTITY,
        "id": need.id,
        "branch_id": need.branch_id,
        "drug_id": need.drug_id,
        "qty": _qty4(need.qty),
        "datee": need.datee.isoformat() if need.datee else None,
        "sender_branch_id": need.sender_branch_id,
        "target_branch_id": need.target_branch_id,
        "status": need.status,
        "transfer_id": need.transfer_id,
        "rev": int(need.rev or 1),
        "updated_at": max(stamps).isoformat() if stamps else None,
    }


async def get_need(session: AsyncSession, need_id: int) -> Need:
    need = (await session.execute(
        select(Need).where(Need.id == need_id)
    )).scalar_one_or_none()
    if need is None:
        raise NOT_FOUND
    return need


async def create_need(
    session: AsyncSession,
    *,
    caller: User,
    drug_id: int,
    qty: Decimal,
    sender_branch_id: Optional[int],
    datee: Optional[date],
) -> Need:
    if caller.branch_id is None:
        raise NO_BRANCH
    drug = (await session.execute(
        select(Drug).where(Drug.id == drug_id)
    )).scalar_one_or_none()
    if drug is None:
        raise UNKNOWN_DRUG
    sender: Optional[Branch] = None
    if sender_branch_id is not None:
        if sender_branch_id == caller.branch_id:
            raise SELF_PINNED
        sender = (await session.execute(
            select(Branch).where(Branch.id == sender_branch_id)
        )).scalar_one_or_none()
        if sender is None:
            raise UNKNOWN_BRANCH

    async with atomic(session):
        need = await _insert_need(
            session,
            caller=caller,
            drug_id=drug_id,
            qty=dec(qty),
            sender_branch_id=sender_branch_id,
            datee=datee,
        )
    return need


async def _insert_need(
    session: AsyncSession,
    *,
    caller: User,
    drug_id: int,
    qty: Decimal,
    sender_branch_id: Optional[int],
    datee: Optional[date],
) -> Need:
    need = Need(
        branch_id=caller.branch_id,
        drug_id=drug_id,
        qty=qty,
        datee=datee,
        sender_branch_id=sender_branch_id,
        target_branch_id=caller.branch_id,
        status="pending",
        rev=REV_CREATE,
        created_by=caller.id,
    )
    session.add(need)
    await session.flush()

    await audit(
        session,
        branch_id=need.branch_id,
        user_id=caller.id,
        entity=ENTITY,
        entity_id=need.id,
        field="status",
        old_value=None,
        new_value=need.status,
        action=ACTION_INSERT,
    )
    payload = snapshot_payload(need)
    branches = {need.branch_id} | ({sender_branch_id} if sender_branch_id else set())
    for branch_id in branches:
        await enqueue_sync(
            session,
            branch_id=branch_id,
            entity=ENTITY,
            entity_id=need.id,
            action=ACTION_INSERT,
            payload=payload,
        )
    return need


async def list_needs(session: AsyncSession, caller: User, *, status_filter: Optional[str]) -> list[Need]:
    """Needs the caller's branch participates in (requested OR fulfilling)."""
    if caller.branch_id is None:
        return []
    query = select(Need).where(
        or_(
            Need.branch_id == caller.branch_id,
            Need.sender_branch_id == caller.branch_id,
        )
    )
    if status_filter:
        query = query.where(Need.status == status_filter)
    rows = (await session.execute(query.order_by(Need.id.desc()))).scalars().all()
    return list(rows)


async def cancel_need(session: AsyncSession, *, caller: User, need: Need) -> Need:
    if caller.branch_id != need.branch_id:
        # existence of foreign needs is not disclosed
        raise NOT_FOUND
    async with atomic(session):
        # re-read under the row lock: serializes concurrent cancels AND the
        # receive-path fulfillment hook (first writer wins; the loser's
        # re-check sees the new state -> 409, never a double transition)
        query = select(Need).where(Need.id == need.id).with_for_update()
        try:
            need = (
                await session.execute(query.execution_options(populate_existing=True))
            ).scalar_one()
        except Exception:
            if _is_sqlite(session):
                need = (
                    await session.execute(
                        select(Need).where(Need.id == need.id).execution_options(
                            populate_existing=True
                        )
                    )
                ).scalar_one()
            else:
                raise
        if need.status != "pending":
            raise HTTPException(
                status.HTTP_409_CONFLICT, "need state does not allow this"
            )
        old = need.status
        need.status = "cancelled"
        need.rev = REV_TERMINAL
        await session.flush()

        await audit(
            session,
            branch_id=need.branch_id,
            user_id=caller.id,
            entity=ENTITY,
            entity_id=need.id,
            field="status",
            old_value=old,
            new_value=need.status,
            action=ACTION_UPDATE,
        )
        payload = snapshot_payload(need)
        for branch_id in {need.branch_id, need.sender_branch_id} - {None}:
            await enqueue_sync(
                session,
                branch_id=branch_id,
                entity=ENTITY,
                entity_id=need.id,
                action=ACTION_UPDATE,
                payload=payload,
            )
    return need


async def fulfill_needs_for_transfer(
    session: AsyncSession, *, caller_id: Optional[int], transfer, full_delivery: bool
) -> None:
    """Auto-fulfill pending needs linked to a received transfer (N4).

    Only a FULL delivery (every line received its entire sent_qty) fulfills —
    a partial or zero receipt (shortage auto-return) leaves the need pending
    so the requester can re-request. Called from transfers.service.receive
    INSIDE its atomic transaction, so the need's status flip + audit + outbox
    rows land atomically with the stock landing (G12).
    """
    if not full_delivery:
        return
    needs = (
        await session.execute(
            select(Need).where(
                Need.transfer_id == transfer.id, Need.status == "pending"
            )
        )
    ).scalars().all()
    for need in needs:
        old = need.status
        need.status = "fulfilled"
        need.rev = REV_TERMINAL
        need.fulfilled_at = datetime.now(timezone.utc)
        await audit(
            session,
            branch_id=need.branch_id,
            user_id=caller_id,
            entity=ENTITY,
            entity_id=need.id,
            field="status",
            old_value=old,
            new_value=need.status,
            action=ACTION_UPDATE,
        )
        payload = snapshot_payload(need)
        for branch_id in {need.branch_id, need.sender_branch_id} - {None}:
            await enqueue_sync(
                session,
                branch_id=branch_id,
                entity=ENTITY,
                entity_id=need.id,
                action=ACTION_UPDATE,
                payload=payload,
            )


HANDOFF_NOT_PENDING = HTTPException(
    status.HTTP_409_CONFLICT, "need state does not allow this"
)

_HANDOFF_LOCK_NAMESPACE = "pharmatag:need-handoff"


def _is_sqlite(session: AsyncSession) -> bool:
    try:
        bind = session.get_bind()
    except Exception:
        return False
    return getattr(getattr(bind, "dialect", None), "name", "") == "sqlite"


async def create_handoff_transfer(session: AsyncSession, *, caller: User, need: Need):
    """Sender picks up a pending need → transfer draft sender→requester (F06.4).

    Authority: the pinned sender branch when one is set; any sister branch
    (≠ requester) may pick up an open request — picking up PINS them. A need
    already linked to a live draft replays that transfer (200-style idempotent
    contract mirrors legacy_fatid #56); only cancelled/lost drafts allow a
    fresh handoff.

    Concurrency: a SESSION-level advisory lock per need id serializes pickups
    (two volunteers racing on one open need must not mint two drafts — last-
    write-wins would strand one dispatchable orphan). Session-level, not
    xact-scoped, because create_draft commits its own atomic() midway; released
    in finally. SQLite twin: skipped (single writer).
    """
    # eligibility is decided from the PRE-LOCK snapshot: a volunteer who saw
    # an open (or self-pinned) need stays eligible through the lock wait —
    # losing a pickup race replays the winner's draft instead of 403ing.
    was_eligible = need.sender_branch_id in (None, caller.branch_id)
    if _is_sqlite(session):
        return await _handoff_locked(
            session, caller=caller, need=need, was_eligible=was_eligible
        )

    # The lock MUST live on one dedicated connection: the Session may swap
    # pooled connections after create_draft's atomic() commits mid-handoff,
    # and an unlock landing on a different connection would leak the lock on
    # the original (any later taker of the same key would hang forever).
    from app.core.db import engine

    async with engine.connect() as lock_conn:
        await lock_conn.execute(
            text("SELECT pg_advisory_lock(hashtext(:ns), :need_id)"),
            {"ns": _HANDOFF_LOCK_NAMESPACE, "need_id": need.id},
        )
        try:
            return await _handoff_locked(
                session, caller=caller, need=need, was_eligible=was_eligible
            )
        finally:
            await lock_conn.execute(
                text("SELECT pg_advisory_unlock(hashtext(:ns), :need_id)"),
                {"ns": _HANDOFF_LOCK_NAMESPACE, "need_id": need.id},
            )


async def _handoff_locked(
    session: AsyncSession, *, caller: User, need: Need, was_eligible: bool
):
    # re-read AFTER the lock so the loser of a race sees the winner's link
    need = (
        await session.execute(
            select(Need).where(Need.id == need.id).execution_options(
                populate_existing=True
            )
        )
    ).scalar_one()
    if need.status != "pending":
        raise HANDOFF_NOT_PENDING
    if caller.branch_id is None:
        raise NO_BRANCH
    if caller.branch_id == need.branch_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "the requesting branch cannot fulfill its own need",
        )
    if not was_eligible and need.sender_branch_id != caller.branch_id:
        raise FORBIDDEN_BRANCH

    if need.transfer_id is not None:
        from app.transfers import service as tservice

        existing, _ = await tservice.get_transfer(session, need.transfer_id)
        if existing.status in ("draft", "dispatched"):
            return existing, False  # replay: the live handoff wins
        if existing.status == "received":
            raise HANDOFF_NOT_PENDING
        # cancelled draft: free to re-handoff below

    from app.transfers import service as tservice

    transfer, _lines, _replayed = await tservice.create_draft(
        session,
        caller=caller,
        target_branch_id=need.branch_id,
        lines=[{"drug_id": need.drug_id, "qty": dec(need.qty)}],
    )

    async with atomic(session):
        old_link = need.transfer_id
        need.sender_branch_id = caller.branch_id
        need.transfer_id = transfer.id
        need.rev = REV_LINK
        await audit(
            session,
            branch_id=need.branch_id,
            user_id=caller.id,
            entity=ENTITY,
            entity_id=need.id,
            field="transfer_id",
            old_value=str(old_link) if old_link is not None else None,
            new_value=str(transfer.id),
            action=ACTION_UPDATE,
        )
        payload = snapshot_payload(need)
        for branch_id in {need.branch_id, caller.branch_id}:
            await enqueue_sync(
                session,
                branch_id=branch_id,
                entity=ENTITY,
                entity_id=need.id,
                action=ACTION_UPDATE,
                payload=payload,
            )
    return transfer, True
