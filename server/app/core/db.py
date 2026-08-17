"""Async SQLAlchemy engine/session + the atomic transaction boundary (plan/02).

`atomic(session)` is the single transaction boundary for every money/stock
write: it commits on success and rolls back on any error, so the mutation, its
audit_log row and its sync_log outbox row live or die together. Nested
atomic() calls join the enclosing transaction.
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request (no transaction begun)."""
    async with SessionLocal() as session:
        yield session


_IN_ATOMIC = "_pharmatag_in_atomic"


@asynccontextmanager
async def atomic(session: AsyncSession) -> AsyncIterator[bool]:
    """Run the body in one transaction; commit on success, rollback on error.

    Yields True when it owns the commit, False when it joined an enclosing
    `atomic()`. Ownership: a fresh session gets a transaction begun here; a
    transaction merely auto-begun by an earlier SELECT (the FastAPI request
    path) is taken over and committed here; a transaction an outer `atomic()`
    already began is joined without committing. The `committed` flag tells
    core services when to fire `after_commit` events.
    """
    if session.info.get(_IN_ATOMIC):
        yield False
        return
    if session.in_transaction():
        begin_cm = None
    else:
        begin_cm = session.begin()
        await begin_cm.__aenter__()
    session.info[_IN_ATOMIC] = True
    try:
        yield True
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    finally:
        session.info.pop(_IN_ATOMIC, None)
        if begin_cm is not None:
            await begin_cm.__aexit__(None, None, None)