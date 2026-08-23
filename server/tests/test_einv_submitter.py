"""S4.2 submission worker (#29): candidate selection + claiming.

The worker's input contract is the einvoice_log table itself — a sale made
through the real API leaves a genuine ``pending`` row behind, which is what
production workers will see. claim_due is deliberately global (one server
serves every branch); tests therefore filter to their throwaway branch.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.einvoicing.submitter import claim_due, poll_due, submit_due
from app.models import AuditLog, EInvoiceLog
from tests.einv_test_utils import _make_user, _set_rin, _uniq
from tests.sales_test_utils import _token_for
from tests.test_einv_issue import _cleanup
from tests.returns_test_utils import (
    _make_branch,
    _make_drug_and_stock_branch,
)

import pytest


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "einvoicing"


@pytest.fixture(autouse=True)
async def _rin_configured(monkeypatch):
    """Every submission behavior assumes the seller identity AND an eSeal are
    configured (#30); the refusal tests override and rely on restore."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "eta_key_path", str(FIXTURES / "pinned-test-key.pem"))
    monkeypatch.setattr(settings, "eta_cert_path", str(FIXTURES / "pinned-test-cert.pem"))
    await _set_rin()
    yield
    await _set_rin()


async def _setup_branch() -> tuple[int, int, int]:
    """Throwaway branch + stocked drug + cashier -> (branch_id, drug_id, user_id)."""
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("worker"), branch_id)
    return branch_id, drug_id, user_id


async def _sale(client, branch_id: int, user_id: int, drug_id: int) -> int:
    """One real sale; returns the invoice id."""
    token = _token_for(user_id, branch_id)
    r = await client.post(
        "/api/v1/sales",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _set_backoff(invoice_id: int, at: datetime | None) -> None:
    async with SessionLocal() as session:
        log = (
            await session.execute(
                select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
            )
        ).scalar_one()
        log.next_attempt_at = at
        await session.commit()


def _claimed_on(claimed: list[EInvoiceLog], branch_id: int) -> list[int]:
    return [log.invoice_id for log in claimed if log.branch_id == branch_id]


async def test_claim_picks_due_pending_rows_oldest_first(client):
    branch_id, drug_id, user_id = await _setup_branch()
    first = await _sale(client, branch_id, user_id, drug_id)
    try:
        second = await _sale(client, branch_id, user_id, drug_id)

        async with SessionLocal() as session:
            ids = _claimed_on(await claim_due(session, branch_id=branch_id), branch_id)

        assert ids == [first, second]
    finally:
        await _cleanup([drug_id], [first, second], branch_id)


async def test_claim_skips_rows_still_in_backoff_but_takes_expired_ones(client):
    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        await _set_backoff(invoice_id, datetime.now(timezone.utc) + timedelta(hours=1))

        async with SessionLocal() as session:
            assert _claimed_on(await claim_due(session, branch_id=branch_id), branch_id) == []

        await _set_backoff(invoice_id, datetime.now(timezone.utc) - timedelta(minutes=5))

        async with SessionLocal() as session:
            assert _claimed_on(await claim_due(session, branch_id=branch_id), branch_id) == [invoice_id]
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_claim_never_takes_terminal_or_in_flight_rows(client):
    """accepted/rejected/failed are terminal; submitted is in-flight on the
    wire — none of them may be re-claimed by the pending scan."""
    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            for status in ("submitted", "accepted", "rejected", "failed"):
                log.status = status
                await session.commit()

                async with SessionLocal() as session2:
                    assert (
                        _claimed_on(await claim_due(session2, branch_id=branch_id), branch_id)
                        == []
                    )
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_claim_respects_limit(client):
    branch_id, drug_id, user_id = await _setup_branch()
    first = await _sale(client, branch_id, user_id, drug_id)
    try:
        second = await _sale(client, branch_id, user_id, drug_id)

        async with SessionLocal() as session:
            ids = _claimed_on(
                await claim_due(session, limit=1, branch_id=branch_id), branch_id
            )

        assert ids == [first]
    finally:
        await _cleanup([drug_id], [first, second], branch_id)


async def test_submit_job_sends_pending_row_and_marks_it_submitted(client):
    import httpx

    from app.einvoicing.eta_client import EtaClient
    from app.models import AuditLog
    from app.core.config import settings as _s  # noqa: F401

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            return httpx.Response(202, json={
                "submissionUUID": "SUB-XYZ",
                "acceptedDocuments": [{"receiptNumber": "any"}],
                "rejectedDocuments": [],
            })
        return httpx.Response(404)

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()

        transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        eta = EtaClient(transport, identity_base_url="https://fake", api_base_url="https://fake", client_id="c", client_secret="s")
        async with SessionLocal() as session:
            await submit_due(session, client=eta)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "submitted"
            assert log.attempts == 1
            assert "SUB-XYZ" in log.response
            assert log.submitted_at is not None
            audits = (
                await session.execute(
                    select(AuditLog).where(AuditLog.entity == "einvoice_log", AuditLog.entity_id == log.id)
                )
            ).scalars().all()
            assert any("submitted" in (a.action or "") or "SUB-XYZ" in (a.new_value or "") for a in audits)
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_transport_failure_keeps_row_pending_with_backoff(client):
    """Offline pharmacy: ETA unreachable -> the document waits inside the
    24-hour window and retries; nothing about the chain moves."""
    import httpx

    from app.einvoicing.eta_client import EtaClient

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            return httpx.Response(500, text="boom")
        return httpx.Response(404)

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = EtaClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            identity_base_url="https://fake", api_base_url="https://fake",
            client_id="c", client_secret="s",
        )
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "pending"
            assert log.attempts == 1
            assert log.last_error
            assert log.next_attempt_at is not None
            assert log.next_attempt_at > datetime.now(timezone.utc)
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


def _eta_with_submission_flow(details_payload: dict):
    """Fake ETA: token -> 202 submission -> GET details returns details_payload."""
    import httpx

    from app.einvoicing.eta_client import EtaClient

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            return httpx.Response(202, json={
                "submissionUUID": "SUB-XYZ", "acceptedDocuments": [], "rejectedDocuments": [],
            })
        if request.url.path == "/api/v1/receiptsubmissions/SUB-XYZ/details":
            return httpx.Response(200, json=details_payload)
        return httpx.Response(404)

    return EtaClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        identity_base_url="https://fake", api_base_url="https://fake",
        client_id="c", client_secret="s",
    )


_VALID_DETAILS = {
    "submissionuuid": "SUB-XYZ",
    "status": "Valid",
    "receiptsCount": 1,
    "invalidReceiptCount": 0,
    "receipts": [{"receiptNumber": "any", "uuid": "a" * 64, "status": "Valid"}],
}


async def test_poll_marks_submitted_row_accepted(client):
    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = _eta_with_submission_flow(_VALID_DETAILS)
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            await poll_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "accepted"
            assert '"Valid"' in log.response
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


_INVALID_DETAILS = {
    "submissionuuid": "SUB-XYZ",
    "status": "Invalid",
    "receipts": [{
        "receiptNumber": "any", "status": "Invalid",
        "errors": [{"errorCode": "CV307", "error": "ItemCode doesn't belong"}],
    }],
}


async def test_poll_marks_invalid_submission_rejected_with_error_text(client):
    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = _eta_with_submission_flow(_INVALID_DETAILS)
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)
        async with SessionLocal() as session:
            await poll_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "rejected"
            assert "CV307" in log.last_error
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_poll_leaves_inprogress_rows_waiting(client):
    details = dict(_VALID_DETAILS, status="InProgress")
    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = _eta_with_submission_flow(details)
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)
        async with SessionLocal() as session:
            await poll_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "submitted"
            assert log.next_attempt_at > datetime.now(timezone.utc)
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_submission_refuses_while_seller_rin_is_unconfigured(client):
    """(restores eta.rin afterwards — every other submission test depends on it)"""
    """service.seller_identity pins this: issuing never blocks on config,
    submission refuses on an empty RIN (nothing valid to send ETA)."""
    import httpx

    from app.einvoicing.eta_client import EtaClient
    from tests.einv_test_utils import _clear_rin

    eta_calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        eta_calls.append(request.url.path)
        return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        await _clear_rin()
        eta = EtaClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            identity_base_url="https://fake", api_base_url="https://fake",
            client_id="c", client_secret="s",
        )
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)

        assert eta_calls == [], "submission must refuse before touching ETA"

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "pending"
            assert "rin" in log.last_error.lower()
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_concurrent_workers_claim_disjoint_rows(client):
    """SKIP LOCKED: two workers racing on one drawer never take the same
    document — the chain forbids double submission."""
    import asyncio

    branch_id, drug_id, user_id = await _setup_branch()
    first = await _sale(client, branch_id, user_id, drug_id)
    try:
        second = await _sale(client, branch_id, user_id, drug_id)

        async with SessionLocal() as s1, SessionLocal() as s2:
            got1, got2 = await asyncio.gather(
                claim_due(s1, branch_id=branch_id),
                claim_due(s2, branch_id=branch_id),
            )
            ids1 = {log.invoice_id for log in got1}
            ids2 = {log.invoice_id for log in got2}

        assert ids1 | ids2 == {first, second}
        assert ids1.isdisjoint(ids2), "the same document was claimed twice"
    finally:
        await _cleanup([drug_id], [first, second], branch_id)


async def test_submitted_row_survives_a_worker_restart(client):
    """Crash after ETA accepted the submission but before polling: a fresh
    worker finds the submitted row due again and finishes the job."""
    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = _eta_with_submission_flow(_VALID_DETAILS)
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)

        # ...worker dies, process restarts, brand-new session...
        async with SessionLocal() as fresh_session:
            polled = await poll_due(fresh_session, client=eta, branch_id=branch_id)
            assert polled == 1

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "accepted"
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_duplicate_submission_422_backs_off_instead_of_failing(client):
    """ETA rejects identical payloads inside 10 minutes (DuplicateSubmission).
    That is 'already received', not an error worth burning attempts on."""
    import httpx

    from app.einvoicing.eta_client import EtaClient

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            return httpx.Response(422, json={
                "error": {"code": "DuplicateSubmission"}, "Retry-After": 60,
            })
        return httpx.Response(404)

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = EtaClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            identity_base_url="https://fake", api_base_url="https://fake",
            client_id="c", client_secret="s",
        )
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "pending"  # waits out the dedup window
            assert log.attempts == 0  # 'already received' costs no budget
            assert log.next_attempt_at is not None
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_in_flight_lease_hides_claimed_rows_from_other_workers(client):
    """The review bug: SKIP LOCKED row locks die at the next commit. The
    batch lease (next_attempt_at pushed forward, committed before any I/O)
    is what actually keeps worker B out of worker A's batch."""
    from app.einvoicing.submitter import _mark_in_flight

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        async with SessionLocal() as s1:
            claimed = await claim_due(s1, branch_id=branch_id)
            assert [log.invoice_id for log in claimed] == [invoice_id]
            _mark_in_flight(claimed)
            await s1.commit()  # locks released — only the lease protects now

        async with SessionLocal() as s2:
            assert await claim_due(s2, branch_id=branch_id) == []

        await _set_backoff(invoice_id, datetime.now(timezone.utc) - timedelta(seconds=1))
        async with SessionLocal() as s3:
            claimed = await claim_due(s3, branch_id=branch_id)
            assert [log.invoice_id for log in claimed] == [invoice_id]
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_rate_limited_submission_defers_without_burning_budget(client):
    """ETA 429 TooManyRequests (+ Retry-After) is not the document's fault:
    defer exactly as asked, attempts untouched."""
    import httpx

    from app.einvoicing.eta_client import EtaClient

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            return httpx.Response(429, headers={"Retry-After": "90"}, text="slow down")
        return httpx.Response(404)

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = EtaClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            identity_base_url="https://fake", api_base_url="https://fake",
            client_id="c", client_secret="s",
        )
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "pending"
            assert log.attempts == 0
            assert log.next_attempt_at > datetime.now(timezone.utc)
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_max_attempts_exhaustion_marks_row_failed_terminal(client):
    """Persistent transport failure across MAX_ATTEMPTS -> terminal failed."""
    import httpx

    from app.einvoicing.eta_client import EtaClient
    from app.einvoicing.submitter import MAX_ATTEMPTS

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        return httpx.Response(503, text="down")

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = EtaClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            identity_base_url="https://fake", api_base_url="https://fake",
            client_id="c", client_secret="s",
        )
        for _ in range(MAX_ATTEMPTS):
            await _set_backoff(invoice_id, None)  # due again immediately
            async with SessionLocal() as session:
                await submit_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "failed"
            assert log.attempts == MAX_ATTEMPTS
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_poll_errors_never_fail_a_received_document(client):
    """ETA has the receipt (202 stored); poll trouble only ever defers —
    manual resubmission of a received document is the risky path."""
    import httpx

    from app.einvoicing.eta_client import EtaClient
    from app.einvoicing.submitter import MAX_ATTEMPTS

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            return httpx.Response(202, json={"submissionUUID": "SUB-XYZ", "acceptedDocuments": [], "rejectedDocuments": []})
        return httpx.Response(500, text="details endpoint down")

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = EtaClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            identity_base_url="https://fake", api_base_url="https://fake",
            client_id="c", client_secret="s",
        )
        async with SessionLocal() as session:
            await submit_due(session, client=eta, branch_id=branch_id)  # ETA takes the receipt
        for _ in range(MAX_ATTEMPTS + 3):
            await _set_backoff(invoice_id, None)
            async with SessionLocal() as session:
                await poll_due(session, client=eta, branch_id=branch_id)

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "submitted"  # still in flight, never failed
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def _forbidden_handler(request):
    raise AssertionError("no HTTP call expected when the signer is unavailable")


async def test_submit_attaches_cades_signature_and_fills_uuid(client, monkeypatch):
    """#30: with an eSeal configured the worker signs the serialized wire
    document and posts it in signatures[] alongside the uuid-filled receipt."""
    import base64  # noqa: F401
    import hashlib  # noqa: F401
    import json

    import httpx

    from app.core.config import settings
    from app.einvoicing.eta_client import EtaClient
    from app.einvoicing.toolkit import serialize

    assert settings.eta_key_path and settings.eta_cert_path  # autouse fixture
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            seen["body"] = json.loads(request.content)
            return httpx.Response(202, json={
                "submissionUUID": "SUB-SIGNED",
                "acceptedDocuments": [],
                "rejectedDocuments": [],
            })
        return httpx.Response(404)

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        eta = EtaClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            identity_base_url="https://fake", api_base_url="https://fake",
            client_id="c", client_secret="s",
        )
        async with SessionLocal() as session:
            handled = await submit_due(session, client=eta, branch_id=branch_id)
        assert handled == 1

        log = (
            await session.execute(
                select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
            )
        ).scalar_one()
        body = seen["body"]
        receipt = body["receipts"][0]
        assert receipt["header"]["uuid"] == log.uuid
        (sig_entry,) = body["signatures"]
        assert sig_entry["signatureType"] == "I"
        # the value is a real CAdES-BES over THIS document's serialization
        from asn1crypto import cms as asn1cms

        info = asn1cms.ContentInfo.load(base64.b64decode(sig_entry["value"]))
        si = info["content"]["signer_infos"][0]
        digest = hashlib.sha256(
            serialize(receipt).encode("utf-8")
        ).digest()
        attrs = {str(a["type"]): a for a in si["signed_attrs"]}
        assert attrs["1.2.840.113549.1.9.4"]["values"][0].native == digest
        assert log.status == "submitted" and "SUB-SIGNED" in log.response
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_submit_without_eseal_defers_pass_with_audit_not_attempts(client, monkeypatch):
    """No key configured ⇒ the whole pass refuses: rows deferred shortly with
    a signed audit row, retry budget untouched, worker loop unharmed."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "eta_key_path", None)
    monkeypatch.setattr(settings, "eta_cert_path", None)
    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    try:
        import httpx as _httpx

        from app.einvoicing.eta_client import EtaClient

        eta = EtaClient(
            _httpx.AsyncClient(transport=_httpx.MockTransport(_forbidden_handler)),
            identity_base_url="https://fake", api_base_url="https://fake",
            client_id="c", client_secret="s",
        )
        async with SessionLocal() as session:
            handled = await submit_due(session, client=eta, branch_id=branch_id)
        assert handled == 0

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "pending"
            assert log.attempts == 0
            assert log.next_attempt_at is not None
            assert "eSeal" in log.last_error or "signer" in log.last_error.lower()
            audits = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity == "einvoice_log",
                        AuditLog.entity_id == log.id,
                    )
                )
            ).scalars().all()
            assert any("eSeal" in (a.new_value or "") for a in audits)
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)
