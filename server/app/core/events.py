"""Two-phase domain event bus (plan/08 §2.4, ticket #3 AC2/AC3).

The bus is the #1 core seam: core services emit domain events, plugins
subscribe. Every event is emitted twice with different guarantees:

  * `in_txn`     — inside the core transaction, before commit. A handler whose
                   `strict=True` raises ABORTS the whole transaction (correct
                   for mandatory legal state like ETA counters/hash); a
                   best-effort handler's exception is caught + recorded and the
                   transaction commits normally (A09).
  * `after_commit` — after the transaction committed. Handlers see committed
                   rows and run any async surface (enqueue jobs, HTTP). They are
                   always best-effort: a committed write must never be failed by
                   a plugin that runs after it (plan/08 §2.4.4).

Event names are core-owned constants (an event name is a stable API, versioned
with the SDK). The plugin registry subscribes handlers in dependency order; the
per-branch enablement gate lives in the registry wrapper, not here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("pharmatag.events")

# --- core-owned event catalog (v1; plan/08 §2.4.2) ---
SALE_SAVED = "sale.saved"
KNOWN_EVENTS = frozenset({SALE_SAVED})

# --- phases ---
IN_TXN = "in_txn"
AFTER_COMMIT = "after_commit"
PHASES = (IN_TXN, AFTER_COMMIT)


class HookPhase(str, Enum):
    IN_TXN = IN_TXN
    AFTER_COMMIT = AFTER_COMMIT


Handler = Callable[["SaleContext"], Awaitable[None]]


@dataclass
class SaleContext:
    """Payload carried to every `sale.saved` handler (plan/08 §2.4.1).

    `session` is the SAME transaction the core is about to commit during the
    `in_txn` phase — plugin rows written through core services (audit/outbox)
    join the sale's transaction. `pending` collects post-commit jobs the core
    or plugins want to run after commit.
    """

    session: AsyncSession
    branch_id: int
    user_id: Optional[int]
    sale: Any  # the saved invoice header (flushed in-txn, committed after)
    pending: list[str] = field(default_factory=list)
    # JSON-safe primitives only (no un-hashable invoice objects): lets an
    # after_commit handler reconstruct the sale without a live ORM row.
    payload: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class _Subscription:
    handler: Handler
    strict: bool
    name: str


class EventBus:
    """Registers handlers and dispatches events by phase.

    Public surface is intentionally small: `subscribe` / `emit` / `reset`
    (+ `errors` for observability of caught best-effort failures). Handlers
    run in subscription order = plugin dependency order (the registry subscribes
    in topological order).
    """

    def __init__(self) -> None:
        self._subs: dict[str, dict[str, list[_Subscription]]] = {}
        self.errors: list[dict[str, Any]] = []

    def subscribe(
        self,
        event: str,
        handler: Handler,
        *,
        phase: str = IN_TXN,
        strict: bool = False,
        name: Optional[str] = None,
    ) -> None:
        if event not in KNOWN_EVENTS:
            raise ValueError(f"unknown core event {event!r}")
        if phase not in PHASES:
            raise ValueError(f"unknown phase {phase!r}")
        self._subs.setdefault(event, {}).setdefault(phase, []).append(
            _Subscription(
                handler,
                strict,
                name or getattr(handler, "__name__", "handler"),
            )
        )

    async def emit(self, event: str, ctx: SaleContext, *, phase: str) -> None:
        """Dispatch handlers for (event, phase) in subscription order.

        A strict `in_txn` handler that raises propagates the exception so the
        caller's transaction rolls back; every other failure is caught, recorded
        on `self.errors` and logged — it never aborts the write.
        """
        for sub in self._subs.get(event, {}).get(phase, []):
            try:
                await sub.handler(ctx)
            except Exception as exc:
                if phase == IN_TXN and sub.strict:
                    raise
                self.errors.append(
                    {
                        "event": event,
                        "phase": phase,
                        "handler": sub.name,
                        "error": str(exc),
                    }
                )
                logger.exception(
                    "best-effort handler %r failed for %s/%s", sub.name, event, phase
                )

    def handlers_for(self, event: str, *, phase: str) -> list[_Subscription]:
        return list(self._subs.get(event, {}).get(phase, []))

    def reset(self) -> None:
        self._subs.clear()
        self.errors.clear()


# process-wide bus; core services emit on it, the registry subscribes to it
bus = EventBus()