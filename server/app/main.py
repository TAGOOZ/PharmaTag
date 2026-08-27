"""FastAPI application factory (ticket #2 AC1: boots, env config, health).

Run: uvicorn app.main:app --reload   (from server/)
"""
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth.router import router as auth_router
from app.accounts.router import router as accounts_router
from app.branches.router import router as branches_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.drawer.router import router as drawer_router
from app.drugs.router import router as drugs_router
from app.einvoicing.router import router as einvoicing_router
from app.einvoicing.worker import run_forever
from app.money.months_router import router as months_router
from app.chain_buy.router import router as chain_buy_router
from app.needs.router import router as needs_router
from app.purchase_orders.router import router as purchase_orders_router
from app.transfers.router import router as transfers_router
from app.money.opening_router import router as opening_router
from app.money.router import router as money_router
from app.parties.router import router as parties_router
from app.plugins.registry import registry
from app.plugins.router import router as plugins_router
from app.purchases.router import router as purchases_router
from app.receivables.router import router as receivables_router
from app.reports.router import router as reports_router
from app.sales.router import router as sales_router
from app.statements.router import router as statements_router
from app.stock.router import router as stock_router
from app.sync.router import router as sync_router
from app.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with SessionLocal() as session:
        await registry.load(session)
    stop = asyncio.Event()
    worker = (
        asyncio.create_task(run_forever(stop))
        if settings.eta_submit_enabled
        else None
    )
    yield
    if worker is not None:
        stop.set()
        await worker
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
        accounts_router, prefix="/api/v1/accounts", tags=["accounts"]
    )
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
        branches_router, prefix="/api/v1/branches", tags=["branches"]
    )
    application.include_router(
        transfers_router, prefix="/api/v1/transfers", tags=["transfers"]
    )
    application.include_router(needs_router, prefix="/api/v1/needs", tags=["needs"])
    application.include_router(chain_buy_router, prefix="/api/v1/chain-buy", tags=["chain-buy"])
    application.include_router(
        purchase_orders_router, prefix="/api/v1/purchase-orders",
        tags=["purchase-orders"],
    )
    application.include_router(
        sales_router, prefix="/api/v1/sales", tags=["sales"]
    )
    application.include_router(
        purchases_router, prefix="/api/v1/purchases", tags=["purchases"]
    )
    application.include_router(
        einvoicing_router, prefix="/api/v1/einvoicing", tags=["einvoicing"]
    )
    application.include_router(
        parties_router, prefix="/api/v1/parties", tags=["parties"]
    )
    application.include_router(
        statements_router, prefix="/api/v1/parties", tags=["parties"]
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
    application.include_router(
        money_router, prefix="/api/v1/journals", tags=["journals"]
    )
    application.include_router(
        reports_router, prefix="/api/v1/reports", tags=["reports"]
    )
    application.include_router(
        receivables_router, prefix="/api/v1/receivables", tags=["receivables"]
    )
    application.include_router(
        months_router, prefix="/api/v1/months", tags=["months"]
    )
    application.include_router(
        opening_router, prefix="/api/v1/opening-balances", tags=["opening-balances"]
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