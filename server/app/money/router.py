"""Manual-journal endpoints (S2.2, ticket #17).

Posting + reversal are gated by the granular `journals.manage` permission
(legacy floor 7: ledger-area balance edits, plan/02 §3; granted to admin,
accountant, and manager roles). Reads (list/detail) are open to any
authenticated user so the ledger can feed pickers and the Phase-3 reports —
same posture as the chart-of-accounts reads. Every write is branch-scoped to
the caller and atomic with its audit row (G12).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.service import caller_branch_id
from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.money import entries
from app.money.schemas import ManualJournalCreate
from app.models import User

router = APIRouter()

JOURNALS_WRITE = require_permission("journals.manage")


@router.post("/manual", status_code=status.HTTP_201_CREATED)
async def post_manual_entry(
    body: ManualJournalCreate,
    caller: User = Depends(JOURNALS_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(caller)
    entry = await entries.post_manual_entry(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        datee=body.datee,
        description=body.description,
        lines=body.lines,
    )
    return await entries.serialize_entry(session, entry)


@router.get("/manual")
async def list_manual_entries(
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return {
        "entries": await entries.list_manual_entries(
            session, branch_id=branch_id, limit=limit
        )
    }


@router.get("/manual/{entry_id}")
async def get_manual_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return await entries.get_manual_entry(
        session, branch_id=branch_id, entry_id=entry_id
    )


@router.post("/manual/{entry_id}/reverse", status_code=status.HTTP_201_CREATED)
async def reverse_manual_entry(
    entry_id: int,
    caller: User = Depends(JOURNALS_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(caller)
    entry = await entries.reverse_manual_entry(
        session, branch_id=branch_id, user_id=caller.id, entry_id=entry_id
    )
    return await entries.serialize_entry(session, entry)