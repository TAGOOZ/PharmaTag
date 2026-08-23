"""Chain verification + reconciliation invariants (S4.1, #28 AC2/AC5).

Per (branch, device, kind) stream:
* counters are 1..N gapless, never reset in fiscal year (A15);
* the first document chains from an EMPTY previousUUID;
* every uuid recomputes from its stored payload + previous_uuid
  (toolkit.receipt_uuid);
* einvoice_counters.last_counter == Σ log rows for the stream.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.einvoicing.toolkit import receipt_uuid
from app.models import EInvoiceCounter, EInvoiceLog


async def verify_chain(
    *, branch_id: int, session: Optional[AsyncSession] = None
) -> dict:
    """Verify every stream of a branch; returns {ok, problems}.

    Problems carry the words 'uuid' (hash/chain break), 'gap' (missing
    counter) or 'counter' (reconciliation) so callers can classify failures.
    """
    owned = session is None
    if owned:
        session = SessionLocal()  # type: ignore[assignment]
    try:
        problems: list[str] = []
        rows = (
            await session.execute(
                select(EInvoiceLog)
                .where(EInvoiceLog.branch_id == branch_id)
                .order_by(EInvoiceLog.kind, EInvoiceLog.counter)
            )
        ).scalars().all()
        counters = {
            c.kind: c
            for c in (
                await session.execute(
                    select(EInvoiceCounter).where(
                        EInvoiceCounter.branch_id == branch_id
                    )
                )
            ).scalars().all()
        }

        streams: dict[tuple[str, str | None], list[EInvoiceLog]] = {}
        for row in rows:
            streams.setdefault((row.kind, row.device_serial), []).append(row)

        seen_kinds: set[str] = set()
        for (kind, device), stream in sorted(
            streams.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
        ):
            seen_kinds.add(kind)
            label = f"{kind}/{device or '-'}"
            expected = 1
            prev_uuid = ""
            for row in stream:
                if row.counter != expected:
                    problems.append(
                        f"{label}: gap in counter sequence — expected "
                        f"{expected}, found {row.counter}"
                    )
                    expected = row.counter
                if row.previous_uuid != prev_uuid:
                    problems.append(
                        f"{label}: chain broken at counter {row.counter} — "
                        f"previousUUID {row.previous_uuid!r} != chained "
                        f"{prev_uuid!r}"
                    )
                if receipt_uuid(row.payload_json or {}) != row.uuid:
                    problems.append(
                        f"{label}: uuid mismatch at counter {row.counter} — "
                        "payload does not recompute to the stored uuid"
                    )
                prev_uuid = row.uuid
                expected += 1

            counter_row = counters.get(kind)
            if counter_row is None:
                problems.append(f"{label}: missing einvoice_counters row")
            elif counter_row.last_counter != len(stream):
                problems.append(
                    f"{label}: counter reconciliation failed — last_counter "
                    f"{counter_row.last_counter} != Σ log rows {len(stream)}"
                )

        for kind, counter_row in sorted(counters.items()):
            if kind not in seen_kinds and counter_row.last_counter > 0:
                problems.append(
                    f"{kind}: counter reconciliation failed — last_counter "
                    f"{counter_row.last_counter} with no log rows"
                )

        return {"ok": not problems, "problems": problems}
    finally:
        if owned:
            await session.close()  # type: ignore[union-attr]
