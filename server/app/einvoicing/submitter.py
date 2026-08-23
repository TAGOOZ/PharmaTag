"""The ETA submission worker (S4.2 #29 + S4.3 #30 signing).

`claim_due` selects due documents; `submit_due`/`poll_due` drive them
through the transport and record transitions. Exclusivity across several
uvicorn workers comes from TWO mechanisms: rows are selected FOR UPDATE
SKIP LOCKED, and — because those locks die at the first commit — each batch
is immediately marked in-flight with a `next_attempt_at` lease committed
before any network I/O. A crashed worker's lease simply expires and the row
becomes due again. Transport failures never touch the chain identity —
counter/uuid/qr_data are frozen (A15); only scheduling state moves.

S4.3: each claimed document is turned into its wire shape (`wire.submission_
document`), signed CAdES-BES over the toolkit serialization (#30), and the
signature rides `signatures[]`. A missing/broken eSeal refuses the whole
pass (defer + audit, retry budgets untouched) instead of crashing the loop.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_UPDATE, audit
from app.einvoicing.eta_client import EtaSubmissionError
from app.einvoicing.signer import SignerUnavailable, load_signer
from app.einvoicing.toolkit import serialize
from app.einvoicing.wire import signature_entry, submission_document
from app.models import EInvoiceLog

MAX_ATTEMPTS = 10  # with the backoff cap below this spans ~8h inside ETA's 24h window
_BACKOFF_CAP = timedelta(minutes=60)
_IN_FLIGHT_LEASE = timedelta(minutes=5)  # per ROW, > worst-case HTTP timeout (30s)
_RIN_REFUSAL_BACKOFF = timedelta(minutes=1)
_SIGNER_REFUSAL_BACKOFF = timedelta(minutes=1)
_DUP_SUBMISSION_BACKOFF = timedelta(minutes=11)  # ETA dedups identical payloads for 10
_RATE_LIMIT_BACKOFF = timedelta(seconds=15)


def _backoff(attempts: int) -> datetime:
    delay = min(timedelta(minutes=2 ** max(attempts, 1)), _BACKOFF_CAP)
    return datetime.now(timezone.utc) + delay


def _deferred(exc: EtaSubmissionError, *, default: timedelta) -> datetime:
    """Honor ETA's Retry-After when present; otherwise the caller's default."""
    if exc.retry_after:
        return datetime.now(timezone.utc) + timedelta(seconds=exc.retry_after)
    return datetime.now(timezone.utc) + default


async def claim_due(
    session: AsyncSession,
    *,
    limit: int = 20,
    branch_id: int | None = None,
    status: str = "pending",
) -> list[EInvoiceLog]:
    """Due documents of ``status`` (backoff gate passed or never set), oldest
    first.

    Global by default (one server serves every branch); pass ``branch_id``
    for scoped runs such as the offline-reconnect flush."""
    now = datetime.now(timezone.utc)
    query = select(EInvoiceLog).where(
        EInvoiceLog.status == status,
        (EInvoiceLog.next_attempt_at.is_(None))
        | (EInvoiceLog.next_attempt_at <= now),
    )
    if branch_id is not None:
        query = query.where(EInvoiceLog.branch_id == branch_id)
    rows = (
        await session.execute(
            query.order_by(EInvoiceLog.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    return list(rows)


def _mark_in_flight(claimed: list[EInvoiceLog]) -> None:
    """Lease every claimed row so other workers skip it while we do network
    I/O (the SELECT's row locks die at the next commit). The lease must
    cover the WHOLE batch's worst case — rows not yet processed when the
    batch commit lands are protected only by it."""
    until = datetime.now(timezone.utc) + _IN_FLIGHT_LEASE * len(claimed)
    for log in claimed:
        log.next_attempt_at = until


async def submit_due(
    session: AsyncSession,
    *,
    client,
    limit: int = 20,
    branch_id: int | None = None,
) -> int:
    """Claim due pending documents, sign and push them to ETA. Returns the
    count of rows that reached a decision (submitted or failed-terminal)."""
    from app.einvoicing.service import seller_identity

    identity = await seller_identity(session)
    if not identity["rin"].strip():
        # pinned by service.seller_identity: issuing never blocks on config,
        # submission refuses on an empty RIN — nothing valid to send ETA.
        claimed = await claim_due(session, limit=limit, branch_id=branch_id)
        retry_after = datetime.now(timezone.utc) + _RIN_REFUSAL_BACKOFF
        for log in claimed:
            log.last_error = (
                "seller RIN not configured (app_config eta.rin); submission refused"
            )
            log.next_attempt_at = retry_after
            await _audit_transition(session, log, detail="refused: seller RIN unconfigured")
        await session.commit()
        return 0

    try:
        signer = load_signer()
    except SignerUnavailable as exc:
        # No eSeal (or a broken one): refuse the whole PASS — the documents
        # are not at fault, so their retry budget stays untouched; Ops gets
        # one audit row per due document pointing at the key configuration.
        claimed = await claim_due(session, limit=limit, branch_id=branch_id)
        retry_after = datetime.now(timezone.utc) + _SIGNER_REFUSAL_BACKOFF
        for log in claimed:
            log.last_error = str(exc)[:2000]
            log.next_attempt_at = retry_after
            await _audit_transition(
                session, log, detail=f"refused: eSeal unavailable ({exc})"
            )
        await session.commit()
        return 0

    claimed = await claim_due(session, limit=limit, branch_id=branch_id)
    if not claimed:
        return 0
    _mark_in_flight(claimed)
    await session.commit()

    handled = 0
    for log in claimed:
        try:
            document = submission_document(log)
        except ValueError as exc:  # permanent payload problem — fail fast, don't burn ETA calls
            log.status = "failed"
            log.attempts += 1
            log.last_error = str(exc)[:2000]
            await _audit_transition(session, log, detail=f"unserializable payload: {log.last_error[:120]}")
            await session.commit()
            handled += 1
            continue

        try:
            # ITIDA procedure: canonicalize the wire document (toolkit
            # algorithm) → SHA-256 inside the signer → CAdES-BES → base64.
            signature = signer.sign(serialize(document))
        except Exception as exc:  # malformed key material surfacing late
            log.attempts += 1
            log.last_error = f"signing failed: {exc}"[:2000]
            if log.attempts >= MAX_ATTEMPTS:
                log.status = "failed"
            else:
                log.next_attempt_at = _backoff(log.attempts)
            await _audit_transition(session, log, detail=f"signing failed: {log.last_error[:120]}")
            await session.commit()
            handled += 1
            continue

        try:
            result = await client.submit_receipts(
                [document], signatures=[signature_entry(signature)]
            )
        except Exception as exc:
            if isinstance(exc, EtaSubmissionError):
                if exc.status_code == 429:  # throttled — not the document's fault
                    log.next_attempt_at = _deferred(exc, default=_RATE_LIMIT_BACKOFF)
                    log.last_error = str(exc)[:2000]
                    await _audit_transition(session, log, detail="rate limited; deferred")
                    await session.commit()
                    handled += 1
                    continue
                if exc.status_code == 422:
                    # DuplicateSubmission: ETA already received this exact payload
                    # (crash after its 202, before our commit). Wait out the dedup
                    # window WITHOUT burning the retry budget.
                    log.last_error = str(exc)[:2000]
                    log.next_attempt_at = _deferred(exc, default=_DUP_SUBMISSION_BACKOFF)
                    await _audit_transition(session, log, detail="duplicate submission; deferred")
                    await session.commit()
                    handled += 1
                    continue
            # transport/auth/other ETA refusal — retryable per backoff
            log.attempts += 1
            log.last_error = str(exc)[:2000]
            if log.attempts >= MAX_ATTEMPTS:
                log.status = "failed"
            else:
                log.next_attempt_at = _backoff(log.attempts)
            await _audit_transition(session, log, detail=f"error: {log.last_error[:120]}")
            await session.commit()
            handled += 1
            continue

        log.status = "submitted"
        log.attempts += 1
        log.submitted_at = datetime.now(timezone.utc)
        log.next_attempt_at = None
        log.last_error = ""
        log.response = json.dumps(
            {
                "submissionUUID": result.submission_uuid,
                "accepted": result.accepted,
                "rejected": result.rejected,
            },
            ensure_ascii=False,
        )
        await _audit_transition(session, log, detail=f"submission {result.submission_uuid}")
        await session.commit()
        handled += 1
    return handled


async def _audit_transition(session: AsyncSession, log: EInvoiceLog, *, detail: str) -> None:
    await audit(
        session,
        branch_id=log.branch_id,
        user_id=None,
        entity="einvoice_log",
        entity_id=log.id,
        action=ACTION_UPDATE,
        new_value=f"status={log.status} attempts={log.attempts} {detail}",
        typevalue=f"counter={log.counter}",
    )


_POLL_INTERVAL = timedelta(seconds=30)

# ETA submission-level status -> our chain (ADR-0002). InProgress keeps
# waiting; Valid/Invalid are final per receipt inside `receipts`.
_ETA_FINAL = {"Valid": "accepted", "Invalid": "rejected"}


async def poll_due(
    session: AsyncSession,
    *,
    client,
    limit: int = 20,
    branch_id: int | None = None,
) -> int:
    """Check in-flight submissions and record ETA's verdict."""
    claimed = await claim_due(session, limit=limit, branch_id=branch_id, status="submitted")
    if not claimed:
        return 0
    _mark_in_flight(claimed)
    await session.commit()

    checked = 0
    for log in claimed:
        submission_uuid = json.loads(log.response or "{}").get("submissionUUID", "")
        if not submission_uuid:
            log.status = "failed"
            log.last_error = "submitted row lost its submissionUUID"
            await _audit_transition(session, log, detail=log.last_error)
            await session.commit()
            checked += 1
            continue

        try:
            details = await client.receipt_submission_details(submission_uuid)
        except Exception as exc:
            # ETA already HAS this receipt (202 + submissionUUID stored), so
            # poll trouble is never the document's fault: defer and keep
            # asking — attempts grow only to shape the backoff, never
            # terminal-fail a received document.
            if isinstance(exc, EtaSubmissionError) and exc.status_code == 429:
                log.next_attempt_at = _deferred(exc, default=_RATE_LIMIT_BACKOFF)
            else:
                log.attempts += 1
                log.next_attempt_at = _backoff(log.attempts)
            log.last_error = str(exc)[:2000]
            await _audit_transition(session, log, detail=f"poll error: {log.last_error[:120]}")
            await session.commit()
            checked += 1
            continue

        eta_status = str(details.get("status", ""))
        verdict = _ETA_FINAL.get(eta_status)
        if verdict is None:
            # still InProgress — come back later without burning the retry budget
            log.next_attempt_at = datetime.now(timezone.utc) + _POLL_INTERVAL
            await session.commit()
            checked += 1
            continue

        log.status = verdict
        log.attempts += 1
        log.next_attempt_at = None
        errors = [
            f"{e.get('errorCode')}: {e.get('error')}".strip(": ")
            for r in details.get("receipts", [])
            for e in (r.get("errors") or [])
        ]
        log.last_error = "; ".join(str(e) for e in errors if e)[:2000] if errors else ""
        log.response = json.dumps(details, ensure_ascii=False)
        await _audit_transition(
            session,
            log,
            detail=verdict + (f" errors: {log.last_error[:160]}" if errors else ""),
        )
        await session.commit()
        checked += 1
    return checked
