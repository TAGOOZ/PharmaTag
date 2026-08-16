"""App shell: env-driven config + health check (ticket #2 AC1)."""
import pytest

from app.core.config import Settings


def test_settings_are_env_driven(monkeypatch):
    monkeypatch.setenv("PHARMATAG_DB_URL", "postgresql+psycopg://x:y@localhost:5432/other")
    monkeypatch.setenv("PHARMATAG_JWT_SECRET", "env-secret")
    monkeypatch.setenv("PHARMATAG_ACCESS_TOKEN_EXPIRE_MINUTES", "7")
    s = Settings()
    assert s.database_url.endswith("/other")
    assert s.jwt_secret == "env-secret"
    assert s.access_token_expire_minutes == 7


def test_defaults_point_at_eg_vat_config():
    s = Settings()
    assert s.app_name == "pharmatag"
    assert s.jwt_algorithm == "HS256"


async def test_healthz_reports_ok(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"