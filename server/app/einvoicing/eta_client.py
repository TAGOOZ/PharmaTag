"""ETA transport client (S4.2, #29) — OAuth token management and submission
calls. Wire contract per the official SDK (sdk.invoicing.eta.gov.eg,
ereceiptapi/01-authenticate-pos + 02-submit-receipt, re-verified 2026-08-23):

* ``POST {identity}/connect/token`` — OAuth 2.0 client_credentials with POS
  headers (posserial / pososversion / posmodelframework / presharedkey);
  returns a Bearer token valid ~3600s.
* Receipt submissions go to the eReceipt API host, B2B documents to the
  eInvoicing API host — both accept the same Bearer token.

The httpx AsyncClient is injected so tests run against a MockTransport fake;
production wiring binds it to settings-derived hosts.
"""
from __future__ import annotations

import time
from typing import NamedTuple

import httpx

PREPROD_IDENTITY_URL = "https://id.preprod.invoicing.eta.gov.eg"
PROD_IDENTITY_URL = "https://id.invoicing.eta.gov.eg"

_TOKEN_SAFETY_MARGIN = 60  # renew this many seconds before real expiry


class SubmissionResult(NamedTuple):
    """The 202 answer of POST /api/v1/receiptsubmissions."""

    submission_uuid: str
    accepted: list[dict]
    rejected: list[dict]  # [{receiptNumber, uuid, error{...}}, ...]


class EtaAuthError(RuntimeError):
    """ETA refused our credentials (invalid_clientsecret, expired POS...)."""


class EtaClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        identity_base_url: str,
        client_id: str,
        client_secret: str,
        api_base_url: str = "",
        pos_headers: dict[str, str] | None = None,
    ) -> None:
        self._http = http
        self._identity_base_url = identity_base_url.rstrip("/")
        self._api_base_url = api_base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._pos_headers = pos_headers or {}
        self._access_token: str = ""
        self._expires_at: float = 0.0

    async def token(self) -> str:
        """A cached Bearer token, renewed before expiry."""
        if self._access_token and time.monotonic() < self._expires_at:
            return self._access_token
        response = await self._http.post(
            f"{self._identity_base_url}/connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if response.status_code != 200:
            raise EtaAuthError(
                f"ETA identity rejected credentials ({response.status_code}): "
                f"{response.text[:200]}"
            )
        payload = response.json()
        self._access_token = payload["access_token"]
        self._expires_at = time.monotonic() + int(payload.get("expires_in", 3600)) - _TOKEN_SAFETY_MARGIN
        return self._access_token

    async def submit_receipts(
        self, receipts: list[dict], signatures: list[dict] | None = None
    ) -> SubmissionResult:
        """POST /api/v1/receiptsubmissions — one batch. ``signatures`` carries
        the CAdES-BES entries built by #30's signer; without one (no eSeal
        configured yet) the body keeps the historical empty list."""
        token = await self.token()
        response = await self._http.post(
            f"{self._api_base_url}/api/v1/receiptsubmissions",
            json={"receipts": receipts, "signatures": list(signatures or [])},
            headers={"Authorization": f"Bearer {token}", **self._pos_headers},
        )
        if response.status_code != 202:
            raise _error(response)
        payload = response.json()
        return SubmissionResult(
            submission_uuid=payload["submissionUUID"],
            accepted=payload.get("acceptedDocuments", []),
            rejected=payload.get("rejectedDocuments", []),
        )

    async def receipt_submission_details(self, submission_uuid: str) -> dict:
        """GET /api/v1/receiptsubmissions/{uuid}/details — processing status
        (InProgress | Valid | Invalid) plus per-receipt verdicts and errors."""
        token = await self.token()
        response = await self._http.get(
            f"{self._api_base_url}/api/v1/receiptsubmissions/{submission_uuid}/details",
            headers={"Authorization": f"Bearer {token}", **self._pos_headers},
        )
        if response.status_code != 200:
            raise _error(response)
        return response.json()


def _error(response: httpx.Response) -> EtaSubmissionError:
    retry_after = response.headers.get("Retry-After")
    try:
        seconds = int(retry_after) if retry_after else None
    except ValueError:
        seconds = None
    return EtaSubmissionError(response.status_code, response.text[:400], seconds)


class EtaSubmissionError(RuntimeError):
    """ETA refused the submission/poll itself (BadStructure, throttling...)."""

    def __init__(self, status_code: int, body: str, retry_after: int | None = None) -> None:
        super().__init__(f"ETA submission failed ({status_code}): {body}")
        self.status_code = status_code
        self.retry_after = retry_after
