"""The submission worker loop (S4.2, #29).

Runs submit_due + poll_due once per interval while the site gate is on
(``PHARMATAG_ETA_SUBMIT_ENABLED`` + credentials). Started from the app
lifespan; safe under multiple uvicorn workers because row claims are
FOR UPDATE SKIP LOCKED.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal
from app.einvoicing.eta_client import (
    PREPROD_IDENTITY_URL,
    PROD_IDENTITY_URL,
    EtaClient,
)
from app.einvoicing.submitter import poll_due, submit_due

logger = logging.getLogger("pharmatag.einvoicing")

PREPROD_API_URL = "https://api.preprod.invoicing.eta.gov.eg"
PROD_API_URL = "https://api.invoicing.eta.gov.eg"


def build_eta_client(http: httpx.AsyncClient | None = None) -> EtaClient | None:
    """The client for this environment, or None while unconfigured."""
    if not settings.eta_client_id.strip() or not settings.eta_client_secret.strip():
        return None
    preprod = settings.environment == "preprod"
    return EtaClient(
        http or httpx.AsyncClient(timeout=30),
        identity_base_url=PREPROD_IDENTITY_URL if preprod else PROD_IDENTITY_URL,
        api_base_url=PREPROD_API_URL if preprod else PROD_API_URL,
        client_id=settings.eta_client_id,
        client_secret=settings.eta_client_secret,
    )


async def run_once(
    session: AsyncSession | None = None,
    *,
    eta: EtaClient | None = None,
) -> tuple[int, int]:
    """One submit+poll pass. (0, 0) while the gate is off or unconfigured.

    Pass ``eta`` (with its httpx client) to reuse a cached OAuth token
    across passes — run_forever does."""
    if not settings.eta_submit_enabled:
        return (0, 0)
    owned_http = httpx.AsyncClient(timeout=30) if eta is None else None
    try:
        client = eta or build_eta_client(owned_http)
        if client is None:
            return (0, 0)
        owned_session = session is None
        session = session or SessionLocal()
        try:
            submitted = await submit_due(session, client=client)
            polled = await poll_due(session, client=client)
            return (submitted, polled)
        finally:
            if owned_session:
                await session.close()
    finally:
        if owned_http is not None:
            await owned_http.aclose()


async def run_forever(stop: asyncio.Event) -> None:
    """The loop's core promise: a bad night at ETA never kills it. One HTTP
    client lives for the whole process so the OAuth token cache works."""
    http = httpx.AsyncClient(timeout=30)
    try:
        while not stop.is_set():
            try:
                eta = build_eta_client(http)
                if eta is not None and settings.eta_submit_enabled:
                    async with SessionLocal() as session:
                        await submit_due(session, client=eta)
                        await poll_due(session, client=eta)
            except Exception:  # noqa: BLE001
                logger.exception("einvoice worker pass failed")
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=settings.einvoice_worker_interval_seconds
                )
            except (TimeoutError, asyncio.TimeoutError):
                pass
    finally:
        await http.aclose()
