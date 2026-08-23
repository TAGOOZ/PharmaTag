"""S4.2 ETA transport client (#29): OAuth token management + submission calls
against a fake ETA (httpx.MockTransport). Wire shapes follow sdk.invoicing.
eta.gov.eg/ereceiptapi 01-authenticate-pos & 02-submit-receipt.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.einvoicing.eta_client import PREPROD_IDENTITY_URL, EtaClient


def _fake_eta(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://fake")


async def test_token_is_fetched_once_and_reused():
    token_requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            form = dict(pair.split(b"=") for pair in request.content.split(b"&"))
            token_requests.append({k.decode(): v.decode() for k, v in form.items()})
            return httpx.Response(200, json={"access_token": "jwt-1", "token_type": "Bearer", "expires_in": 3600})
        return httpx.Response(404)

    async with _fake_eta(handler) as http:
        client = EtaClient(http, identity_base_url="https://fake", client_id="cid", client_secret="sec")
        assert await client.token() == "jwt-1"
        assert await client.token() == "jwt-1"

    assert len(token_requests) == 1
    body = token_requests[0]
    assert body["grant_type"] == "client_credentials"
    assert body["client_id"] == "cid"
    assert body["client_secret"] == "sec"


def test_preprod_identity_host_is_the_default_for_preprod_environment():
    assert "preprod" in PREPROD_IDENTITY_URL


async def test_submit_receipts_posts_bearer_and_pos_headers_and_parses_result():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt-1", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            seen["auth"] = request.headers.get("Authorization")
            seen["posserial"] = request.headers.get("posserial")
            seen["body"] = json.loads(request.content)
            return httpx.Response(202, json={
                "submissionUUID": "SUB123",
                "acceptedDocuments": [{"uuid": "a" * 64, "longId": "L1", "receiptNumber": "R1"}],
                "rejectedDocuments": [],
            })
        return httpx.Response(404)

    async with _fake_eta(handler) as http:
        client = EtaClient(
            http,
            identity_base_url="https://fake",
            client_id="cid",
            client_secret="sec",
            pos_headers={"posserial": "SER1", "pososversion": "os", "posmodelframework": "1", "presharedkey": "key"},
        )
        result = await client.submit_receipts([{"header": {}}])

    assert seen["auth"] == "Bearer jwt-1"
    assert seen["posserial"] == "SER1"
    assert seen["body"] == {"receipts": [{"header": {}}], "signatures": []}
    assert result.submission_uuid == "SUB123"
    assert result.rejected == []


async def test_expired_token_is_renewed_not_reused():
    tokens = ["jwt-1", "jwt-2"]

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": tokens.pop(0), "expires_in": 0})
        return httpx.Response(404)

    async with _fake_eta(handler) as http:
        client = EtaClient(http, identity_base_url="https://fake", client_id="c", client_secret="s")
        assert await client.token() == "jwt-1"
        assert await client.token() == "jwt-2"


async def test_submit_receipts_carries_signature_entries_when_provided():
    """#30: the CAdES-BES entry rides the submission body; without one the
    body keeps the historical empty list (pre-cert behavior)."""
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        if request.url.path == "/api/v1/receiptsubmissions":
            seen["body"] = json.loads(request.content)
            return httpx.Response(202, json={"submissionUUID": "S", "acceptedDocuments": [], "rejectedDocuments": []})
        return httpx.Response(404)

    async with _fake_eta(handler) as http:
        client = EtaClient(http, identity_base_url="https://fake", client_id="c", client_secret="s")
        await client.submit_receipts(
            [{"header": {}}],
            signatures=[{"signatureType": "I", "value": "QQ=="}],
        )
    assert seen["body"] == {
        "receipts": [{"header": {}}],
        "signatures": [{"signatureType": "I", "value": "QQ=="}],
    }

    async with _fake_eta(handler) as http:
        client = EtaClient(http, identity_base_url="https://fake", client_id="c", client_secret="s")
        await client.submit_receipts([{"header": {}}])
    assert seen["body"]["signatures"] == []
