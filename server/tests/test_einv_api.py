"""S4.2 einvoicing read/resubmit API (#29).

Status visibility and the manual resubmit path (rejected/failed -> pending),
with the chain identity frozen across resubmissions (A15).
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.db import SessionLocal
from app.einvoicing.submitter import poll_due, submit_due
from app.models import EInvoiceLog
from tests.einv_test_utils import _make_user, _uniq
from tests.sales_test_utils import _token_for
from tests.einv_test_utils import _set_rin as _ensure_rin
from tests.test_einv_issue import _cleanup

import pytest

from pathlib import Path as _Path

_FIXTURES = _Path(__file__).resolve().parent / "fixtures" / "einvoicing"


@pytest.fixture(autouse=True)
def _eseal_configured(monkeypatch):
    """#30: submission now signs; API-level tests assume a configured eSeal."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "eta_key_path", str(_FIXTURES / "pinned-test-key.pem"))
    monkeypatch.setattr(settings, "eta_cert_path", str(_FIXTURES / "pinned-test-cert.pem"))
from tests.returns_test_utils import _make_branch
from tests.test_einv_submitter import (
    _INVALID_DETAILS,
    _eta_with_submission_flow,
    _sale,
    _setup_branch,
)


async def _rejected_log(client):
    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    await _ensure_rin()
    eta = _eta_with_submission_flow(_INVALID_DETAILS)
    async with SessionLocal() as session:
        await submit_due(session, client=eta, branch_id=branch_id)
    async with SessionLocal() as session:
        await poll_due(session, client=eta, branch_id=branch_id)
    return branch_id, drug_id, invoice_id


async def test_rejected_document_resubmits_without_touching_the_chain(client):
    branch_id, drug_id, invoice_id = await _rejected_log(client)
    try:
        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "rejected"
            frozen = (log.counter, log.uuid, log.previous_uuid, log.qr_data)

        manager_id = await _make_user(_uniq("mgr"), branch_id)
        r = await client.post(
            f"/api/v1/einvoicing/logs/{log.id}/resubmit",
            headers={"Authorization": f"Bearer {_token_for(manager_id, branch_id)}"},
        )
        assert r.status_code == 200, r.text

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            assert log.status == "pending"
            assert log.attempts == 0
            assert (log.counter, log.uuid, log.previous_uuid, log.qr_data) == frozen
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_status_listing_shows_documents_for_a_branch(client):
    branch_id, drug_id, invoice_id = await _rejected_log(client)
    try:
        manager_id = await _make_user(_uniq("mgr"), branch_id)
        r = await client.get(
            "/api/v1/einvoicing/logs",
            headers={"Authorization": f"Bearer {_token_for(manager_id, branch_id)}"},
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        mine = [row for row in rows if row["invoice_id"] == invoice_id]
        assert len(mine) == 1
        assert mine[0]["status"] == "rejected"
        assert {"id", "kind", "counter", "uuid", "status"} <= set(mine[0])
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_cross_branch_documents_are_invisible(client):
    """A manager of another branch can neither see nor resubmit them."""
    branch_id, drug_id, invoice_id = await _rejected_log(client)
    other_branch_id = await _make_branch(vat_inclusive=True)
    try:
        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
        stranger_id = await _make_user(_uniq("stranger"), other_branch_id)

        r = await client.post(
            f"/api/v1/einvoicing/logs/{log.id}/resubmit",
            headers={"Authorization": f"Bearer {_token_for(stranger_id, other_branch_id)}"},
        )
        assert r.status_code == 404

        r = await client.get(
            "/api/v1/einvoicing/logs",
            headers={"Authorization": f"Bearer {_token_for(stranger_id, other_branch_id)}"},
        )
        assert r.status_code == 200
        assert all(row["branch_id"] != branch_id for row in r.json())
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def _accepted_log(client):
    from tests.test_einv_submitter import _VALID_DETAILS

    branch_id, drug_id, user_id = await _setup_branch()
    invoice_id = await _sale(client, branch_id, user_id, drug_id)
    eta = _eta_with_submission_flow(_VALID_DETAILS)
    async with SessionLocal() as session:
        await submit_due(session, client=eta, branch_id=branch_id)
    async with SessionLocal() as session:
        await poll_due(session, client=eta, branch_id=branch_id)
    return branch_id, drug_id, invoice_id


async def test_resubmit_rejects_non_terminal_statuses(client):
    """Only rejected/failed resubmit — an accepted document is done."""
    branch_id, drug_id, invoice_id = await _accepted_log(client)
    try:
        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
        manager_id = await _make_user(_uniq("mgr"), branch_id)
        r = await client.post(
            f"/api/v1/einvoicing/logs/{log.id}/resubmit",
            headers={"Authorization": f"Bearer {_token_for(manager_id, branch_id)}"},
        )
        assert r.status_code == 409
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_cashier_reads_logs_but_cannot_resubmit(client):
    """RBAC floors: einvoice.view=1 (everyone), einvoice.submit=7 (managers)."""
    from app.models import User

    branch_id, drug_id, invoice_id = await _rejected_log(client)
    try:
        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
                )
            ).scalar_one()
            cashier = User(
                username=_uniq("cashier"), pass_hash="x", permission_level=1,
                branch_id=branch_id,
            )
            session.add(cashier)
            await session.commit()
            cashier_id = cashier.id

        token = _token_for(cashier_id, branch_id)
        r = await client.get(
            "/api/v1/einvoicing/logs", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200

        r = await client.post(
            f"/api/v1/einvoicing/logs/{log.id}/resubmit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)


async def test_limit_parameter_is_clamped_not_a_500(client):
    branch_id, drug_id, invoice_id = await _rejected_log(client)
    try:
        manager_id = await _make_user(_uniq("mgr"), branch_id)
        headers = {"Authorization": f"Bearer {_token_for(manager_id, branch_id)}"}
        for bad in ("0", "-5", "999999"):
            r = await client.get(
                "/api/v1/einvoicing/logs", params={"limit": bad}, headers=headers
            )
            assert r.status_code == 200, (bad, r.text)
    finally:
        await _cleanup([drug_id], [invoice_id], branch_id)
