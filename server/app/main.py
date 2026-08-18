"""FastAPI application factory (ticket #2 AC1: boots, env config, health).

Run: uvicorn app.main:app --reload   (from server/)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.drawer.router import router as drawer_router
from app.drugs.router import router as drugs_router
from app.parties.router import router as parties_router
from app.plugins.registry import registry
from app.plugins.router import router as plugins_router
from app.purchases.router import router as purchases_router
from app.sales.router import router as sales_router
from app.stock.router import router as stock_router
from app.sync.router import router as sync_router
from app.users.router import router as users_router


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
    application.include_router(
        users_router, prefix="/api/v1/users", tags=["users"]
    )
    application.include_router(
        sales_router, prefix="/api/v1/sales", tags=["sales"]
    )
    application.include_router(
        purchases_router, prefix="/api/v1/purchases", tags=["purchases"]
    )
    application.include_router(
        parties_router, prefix="/api/v1/parties", tags=["parties"]
    )
    application.include_router(
        sync_router, prefix="/api/v1/sync", tags=["sync"]
    )
    application.include_router(
        stock_router, prefix="/api/v1/stock", tags=["stock"]
    )
    application.include_router(
        drawer_router, prefix="/api/v1/drawer", tags=["drawer"]
    )

    # plan/02 §3: validation failures surface as 400 (not FastAPI's 422).
    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": jsonable_encoder(exc.errors())},
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