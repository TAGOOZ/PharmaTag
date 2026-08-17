"""FastAPI application factory (ticket #2 AC1: boots, env config, health).

Run: uvicorn app.main:app --reload   (from server/)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.drugs.router import router as drugs_router
from app.plugins.registry import registry
from app.plugins.router import router as plugins_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with SessionLocal() as session:
        await registry.load(session)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name, lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    application.include_router(
        drugs_router, prefix="/api/v1/drugs", tags=["drugs"]
    )
    application.include_router(
        plugins_router, prefix="/api/v1/system/plugins", tags=["plugins"]
    )

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