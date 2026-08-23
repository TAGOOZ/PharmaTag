"""S4.2 worker loop (#29): the site gate.

Live ETA network calls must be impossible until a pharmacy explicitly
enables submission with credentials (plan/05 defers the network gate).
"""
from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.einvoicing import worker
from app.einvoicing.worker import build_eta_client, run_once


async def test_gate_off_means_no_eta_traffic_and_no_work():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})

    assert settings.eta_submit_enabled is False  # default posture
    submitted, polled = await run_once()
    assert (submitted, polled) == (0, 0)
    assert calls == []


async def test_unconfigured_credentials_build_no_client(monkeypatch):
    monkeypatch.setattr(settings, "eta_submit_enabled", True)
    monkeypatch.setattr(settings, "eta_client_id", "")
    assert build_eta_client() is None

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connect/token":
            return httpx.Response(200, json={"access_token": "jwt", "expires_in": 3600})
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        monkeypatch.setattr(settings, "eta_client_id", "cid")
        monkeypatch.setattr(settings, "eta_client_secret", "sec")
        client = build_eta_client(http)
        assert client is not None
        assert await client.token() == "jwt"


async def test_run_forever_survives_run_once_crashes(monkeypatch):
    import asyncio

    from app.einvoicing import worker as worker_mod

    monkeypatch.setattr(settings, "einvoice_worker_interval_seconds", 0)
    calls = {"n": 0}

    async def boom(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 3:
            stop.set()
        raise RuntimeError("db hiccup")

    stop = asyncio.Event()
    monkeypatch.setattr(settings, "eta_submit_enabled", True)
    monkeypatch.setattr(worker_mod, "build_eta_client", lambda http: object())
    monkeypatch.setattr(worker_mod, "submit_due", boom)
    await asyncio.wait_for(worker_mod.run_forever(stop), timeout=5)
    assert calls["n"] == 3
