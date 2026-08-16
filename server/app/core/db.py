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


@asynccontextmanager
async def atomic(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Run the body in one transaction; commit on success, rollback on error."""
    if session.in_transaction():
        yield session
        return
    async with session.begin():
        yield session