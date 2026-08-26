"""Branch registry service (ticket #31, S5.1).

The `branches` table IS the registry for the single-shared-PG topology
(plan/00 G09). Rules enforced here so the HTTP seam stays thin:

* new branches are always sub devices (`is_main_device=false`) — the seeded
  main branch keeps its role; the only way to move it is `transfer_main`;
* at most ONE active main device exists at any time (legacy ismaster.txt);
  transfers run under a global advisory lock so two concurrent promotes can
  never split the role;
* pharmacyid/mobile are unique natural keys (uq_branches_*) → 409 on dup;
* deletes are soft (`active=false`) — hard deletes are forbidden (plan/02 §2);
  KNOWN LIMITATION: uq_branches_* span active AND inactive rows, so a
  soft-deleted branch holds its natural keys until re-activated (no un-delete
  endpoint yet — revisit with a partial unique index if re-registering a
  retired pharmacy becomes a real flow);
* the main device cannot be deactivated — transfer its role first.

G12: every mutation writes its audit_log row AND enqueues its sync_log outbox
row (entity='branch'/'branch_identity', full snapshot payload) in the SAME
transaction via atomic(), so peers converge once the chain consumer (#34) runs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_DELETE, ACTION_INSERT, ACTION_UPDATE, audit, enqueue_sync
from app.core.db import atomic
from app.models import Branch, BranchIdentity

_MAIN_LOCK_NS = "pharmatag:branch-main"


def public_branch(branch: Branch) -> dict:
    return {
        "id": branch.id,
        "pharmacyid": branch.pharmacyid,
        "phar": branch.phar or "",
        "mobile": branch.mobile,
        "pharname": branch.pharname,
        "adress": branch.adress or "",
        "governorate": branch.governorate or "",
        "district": branch.district or "",
        "country": branch.country or "",
        "currency": branch.currency or "",
        "vat_default": str(branch.vat_default),
        "vat_inclusive_prices": branch.vat_inclusive_prices,
        "role": "main" if branch.is_main_device else "sub",
        "is_main_device": branch.is_main_device,
        "active": branch.is_active,
        # LWW watermark for the chain replay (#34) — every mutation bumps it
        "updated_at": (
            branch.updated_at.isoformat() if branch.updated_at else None
        ),
    }


async def get_branch(session: AsyncSession, branch_id: int) -> Optional[Branch]:
    return await session.get(Branch, branch_id)


async def _audit_and_enqueue(
    session: AsyncSession,
    *,
    caller_id: Optional[int],
    branch_id: int,
    action: str,
    field: str = "",
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    namee: str = "",
    entity: str = "branch",
    entity_id: Optional[int] = None,
    payload: Optional[dict] = None,
) -> None:
    await audit(
        session,
        branch_id=branch_id,
        user_id=caller_id,
        entity=entity,
        entity_id=entity_id if entity_id is not None else branch_id,
        field=field,
        old_value=old_value,
        new_value=new_value,
        action=action,
        namee=namee,
    )
    # FAN-OUT (#34): every active branch's queue carries a copy so an offline
    # peer converges on reconnect; the origin branch's own copy is idempotent
    # under LWW (its local updated_at already equals the snapshot's).
    # KNOWN LIMITATION: INACTIVE branches receive no copies — a peer that is
    # deactivated mid-history and later re-promoted sees the promote event
    # but not the snapshots it missed while inactive; it converges only as
    # later mutations of those rows fan out again. Revisit with a catch-up
    # mechanism if re-activated peers must replay full history.
    peer_ids = (
        (
            await session.execute(
                select(Branch.id).where(
                    Branch.is_active.is_(True), Branch.id != branch_id
                )
            )
        )
        .scalars()
        .all()
    )
    for peer_id in [*peer_ids, branch_id]:
        await enqueue_sync(
            session,
            branch_id=peer_id,
            entity=entity,
            entity_id=entity_id if entity_id is not None else branch_id,
            action=action,
            payload=payload,
        )


def _touch(branch: Branch) -> None:
    """Bump the LWW watermark IN the mutation transaction (G12)."""
    branch.updated_at = datetime.now(timezone.utc)


async def _dup_key_conflict(
    session: AsyncSession, *, pharmacyid: str, mobile: str
) -> HTTPException:
    """Name WHICH natural key collided — 'pharmacyid or mobile' forces the
    owner to trial-and-error (scenario-QA feedback, ticket #31)."""
    pid_taken = (
        await session.execute(
            select(Branch.id).where(Branch.pharmacyid == pharmacyid)
        )
    ).scalar_one_or_none()
    mob_taken = (
        await session.execute(select(Branch.id).where(Branch.mobile == mobile))
    ).scalar_one_or_none()
    if pid_taken is not None and mob_taken is not None:
        return HTTPException(
            status.HTTP_409_CONFLICT,
            "both pharmacyid and mobile already belong to another branch",
        )
    if pid_taken is not None:
        return HTTPException(
            status.HTTP_409_CONFLICT,
            "a branch with this pharmacyid already exists",
        )
    if mob_taken is not None:
        return HTTPException(
            status.HTTP_409_CONFLICT,
            "a branch with this mobile already exists",
        )
    # race lost between check and constraint: fall back to the generic wording
    return HTTPException(
        status.HTTP_409_CONFLICT,
        "a branch with this pharmacyid or mobile already exists",
    )


async def create_branch(
    session: AsyncSession,
    *,
    caller_id: Optional[int],
    pharmacyid: str,
    mobile: str,
    pharname: str = "",
    phar: str = "",
    adress: str = "",
    governorate: str = "",
    district: str = "",
) -> Branch:
    pharmacyid = pharmacyid.strip()
    mobile = mobile.strip()
    if not pharmacyid or not mobile:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "pharmacyid and mobile are required",
        )
    if len(pharmacyid) > 15 or len(mobile) > 15:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "pharmacyid/mobile must be at most 15 characters",
        )
    try:
        async with atomic(session):
            branch = Branch(
                pharmacyid=pharmacyid,
                mobile=mobile,
                phar=phar.strip(),
                pharname=pharname.strip(),
                adress=adress.strip(),
                governorate=governorate.strip(),
                district=district.strip(),
                is_main_device=False,  # subs only; the role moves via transfer_main
                is_active=True,
            )
            session.add(branch)
            await session.flush()
            _touch(branch)  # LWW watermark for the chain replay (#34)
            await _audit_and_enqueue(
                session,
                caller_id=caller_id,
                branch_id=branch.id,
                action=ACTION_INSERT,
                new_value=pharmacyid,
                namee=branch.pharname,
                payload=public_branch(branch),
            )
    except IntegrityError as exc:
        conflict = await _dup_key_conflict(
            session, pharmacyid=pharmacyid, mobile=mobile
        )
        raise conflict from exc
    return branch


async def update_branch(
    session: AsyncSession,
    *,
    caller_id: Optional[int],
    branch: Branch,
    pharname: Optional[str] = None,
    phar: Optional[str] = None,
    mobile: Optional[str] = None,
    adress: Optional[str] = None,
    governorate: Optional[str] = None,
    district: Optional[str] = None,
) -> Branch:
    if mobile is not None:
        mobile = mobile.strip()
        if not mobile or len(mobile) > 15:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "mobile must be 1-15 characters",
            )
    changes: list[tuple[str, str, str]] = []
    # Deliberately NOT under the main-role advisory lock: this path can never
    # touch is_main_device/is_active, so it cannot break the single-main
    # invariant. Concurrent PATCHes of the same branch resolve last-write-wins
    # (the plan/00 sync policy) — worst case an audit old_value lags one edit.
    for field, value in (
        ("pharname", pharname),
        ("phar", phar),
        ("mobile", mobile),
        ("adress", adress),
        ("governorate", governorate),
        ("district", district),
    ):
        if value is not None and getattr(branch, field) != value.strip():
            changes.append((field, str(getattr(branch, field)), value.strip()))
    try:
        async with atomic(session):
            if changes:
                _touch(branch)  # once per edit — per-field rows share a watermark
            for field, old, new in changes:
                setattr(branch, field, new)
                await _audit_and_enqueue(
                    session,
                    caller_id=caller_id,
                    branch_id=branch.id,
                    action=ACTION_UPDATE,
                    field=field,
                    old_value=old,
                    new_value=new,
                    namee=branch.pharname,
                    payload=public_branch(branch),
                )
    except IntegrityError as exc:
        conflict = await _dup_key_conflict(
            session, pharmacyid=branch.pharmacyid, mobile=branch.mobile
        )
        raise conflict from exc
    return branch


async def deactivate_branch(
    session: AsyncSession, *, caller_id: Optional[int], branch: Branch
) -> Branch:
    """Soft delete. The main device anchors per-branch numbering and the sync
    topology — its role must be transferred first, never deleted.

    Runs under the same global advisory lock as `transfer_main` so a concurrent
    promote of this branch cannot interleave between the role check and the
    write (otherwise an active main could end up deactivated).
    """
    async with atomic(session):
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:ns))"),
            {"ns": _MAIN_LOCK_NS},
        )
        # the ORM object was loaded BEFORE the lock: re-read so the guards
        # below see the post-lock truth, not a pre-lock snapshot.
        await session.refresh(branch)
        if branch.is_main_device:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "the main device cannot be deactivated — transfer the main role first",
            )
        if not branch.is_active:
            return branch  # idempotent replay: already deactivated, nothing to write
        old_active = branch.is_active
        branch.is_active = False
        _touch(branch)  # LWW watermark (#34)
        await _audit_and_enqueue(
            session,
            caller_id=caller_id,
            branch_id=branch.id,
            action=ACTION_DELETE,
            field="is_active",
            old_value=str(old_active),
            new_value="False",
            namee=branch.pharname,
            payload=public_branch(branch),
        )
    return branch


async def transfer_main(
    session: AsyncSession, *, caller_id: Optional[int], caller_level: int, target: Branch
) -> Branch:
    """Move the main-device role to `target` — demote the current main and
    promote the target in ONE transaction (never two mains, never zero).

    A global advisory lock serializes concurrent transfers; the promote of an
    inactive branch also re-activates it. Legacy floor >= 7 (owner tier).
    """
    if caller_level < 7:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "transferring the main device requires permission_level 7",
        )
    async with atomic(session):
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:ns))"),
            {"ns": _MAIN_LOCK_NS},
        )
        # the ORM object was loaded BEFORE the lock: re-read so the guards
        # below see the post-lock truth, not a pre-lock snapshot.
        await session.refresh(target)
        if target.is_main_device and target.is_active:
            return target  # idempotent replay: already THE active main
        demoted: list[Branch] = []
        if not target.is_main_device:
            current = (
                await session.execute(
                    select(Branch).where(
                        Branch.is_main_device.is_(True),
                        Branch.id != target.id,
                    )
                )
            ).scalars().all()
            for b in current:
                b.is_main_device = False
                demoted.append(b)
            target.is_main_device = True
            _touch(target)  # LWW watermark (#34); demoted rows bumped below
        reactivated = not target.is_active
        if reactivated:
            target.is_active = True
        for b in demoted:
            _touch(b)  # LWW watermark (#34)
            await _audit_and_enqueue(
                session,
                caller_id=caller_id,
                branch_id=b.id,
                action=ACTION_UPDATE,
                field="is_main_device",
                old_value="True",
                new_value="False",
                namee=b.pharname,
                payload=public_branch(b),
            )
        if demoted:
            await _audit_and_enqueue(
                session,
                caller_id=caller_id,
                branch_id=target.id,
                action=ACTION_UPDATE,
                field="is_main_device",
                old_value="False",
                new_value="True",
                namee=target.pharname,
                payload=public_branch(target),
            )
        if reactivated:
            await _audit_and_enqueue(
                session,
                caller_id=caller_id,
                branch_id=target.id,
                action=ACTION_UPDATE,
                field="is_active",
                old_value="False",
                new_value="True",
                namee=target.pharname,
                payload=public_branch(target),
            )
    return target


# --- branch_identities alias map (rev 001 table; S5.1 surfaces it) ---


def public_identity(identity: BranchIdentity) -> dict:
    return {
        "legacy_table": identity.legacy_table,
        "legacy_column": identity.legacy_column,
        "legacy_value": identity.legacy_value,
        "branch_id": identity.branch_id,
    }


async def attach_identity(
    session: AsyncSession,
    *,
    caller_id: Optional[int],
    branch: Branch,
    legacy_table: str,
    legacy_column: str,
    legacy_value: str,
) -> BranchIdentity:
    legacy_table = legacy_table.strip()
    legacy_column = legacy_column.strip()
    legacy_value = legacy_value.strip()
    if not (legacy_table and legacy_column and legacy_value):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "legacy_table, legacy_column and legacy_value are required",
        )
    if len(legacy_table) > 50 or len(legacy_column) > 50 or len(legacy_value) > 100:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "identity fields exceed their length limits (50/50/100)",
        )
    try:
        async with atomic(session):
            identity = BranchIdentity(
                legacy_table=legacy_table,
                legacy_column=legacy_column,
                legacy_value=legacy_value,
                branch_id=branch.id,
            )
            session.add(identity)
            await session.flush()
            await _audit_and_enqueue(
                session,
                caller_id=caller_id,
                branch_id=branch.id,
                action=ACTION_INSERT,
                entity="branch_identity",
                entity_id=None,
                new_value=f"{legacy_table}.{legacy_column}={legacy_value}",
                namee=branch.pharname,
                payload=public_identity(identity),
            )
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "this legacy identity is already mapped to a branch",
        ) from exc
    return identity


async def list_identities(
    session: AsyncSession, *, branch: Branch
) -> list[BranchIdentity]:
    result = await session.execute(
        select(BranchIdentity).where(BranchIdentity.branch_id == branch.id)
    )
    return list(result.scalars().all())


async def detach_identity(
    session: AsyncSession,
    *,
    caller_id: Optional[int],
    branch: Branch,
    legacy_table: str,
    legacy_column: str,
    legacy_value: str,
) -> BranchIdentity:
    async with atomic(session):
        # select INSIDE the transaction: two concurrent detaches of the same
        # triple then serialize on row locks instead of the loser's DELETE
        # matching 0 rows (StaleDataError → 500).
        result = await session.execute(
            select(BranchIdentity).where(
                BranchIdentity.legacy_table == legacy_table,
                BranchIdentity.legacy_column == legacy_column,
                BranchIdentity.legacy_value == legacy_value,
                BranchIdentity.branch_id == branch.id,
            )
        )
        identity = result.scalar_one_or_none()
        if identity is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "identity mapping not found"
            )
        await session.delete(identity)
        await session.flush()
        await _audit_and_enqueue(
            session,
            caller_id=caller_id,
            branch_id=branch.id,
            action=ACTION_DELETE,
            entity="branch_identity",
            entity_id=None,
            old_value=f"{legacy_table}.{legacy_column}={legacy_value}",
            namee=branch.pharname,
            payload={
                **public_identity(identity),
                "_deleted": True,
            },
        )
    return identity


async def resolve_branch(
    session: AsyncSession,
    *,
    legacy_table: str,
    legacy_column: str,
    legacy_value: str,
) -> Optional[Branch]:
    """Canonical-branch resolution for the ETL and chain replay (#34/#35).

    Normalizes exactly like `attach_identity` (strip) so a raw caller value
    can never silently miss a stored mapping; resolves even INACTIVE branches
    — historical rows must still map to their origin branch; callers decide
    what to do with an inactive target.
    """
    result = await session.execute(
        select(Branch)
        .join(BranchIdentity, BranchIdentity.branch_id == Branch.id)
        .where(
            BranchIdentity.legacy_table == legacy_table.strip(),
            BranchIdentity.legacy_column == legacy_column.strip(),
            BranchIdentity.legacy_value == str(legacy_value).strip(),
        )
    )
    return result.scalar_one_or_none()
