"""FastAPI application factory (ticket #2 AC1: boots, env config, health).

Run: uvicorn app.main:app --reload   (from server/)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.db import SessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name, lifespan=lifespan)

    application.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

    @application.get("/healthz", tags=["ops"])
    async def healthz():
        try:
            async with SessionLocal() as session:
                await session.execute(text("SELECT 1"))
            db = "ok"
        except Exception:
            db = "error"
        return {"status": "ok" if db == "ok" else "degraded", "database": db}

    return application


app = create_app()