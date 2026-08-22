"""Reports endpoints (S1.9 #15 + S3.1 framework, ticket #23).

Read-only, branch-scoped, gated by the seeded `reports` permission (admin
level-9 floor or the accountant role). Money leaves as exact decimal strings
(plan/02 §2). Every catalog report answers through ONE generic dispatcher:
`GET /reports/{code}` → JSON by default, black-on-white A4/A5 page with
`format=html` (plan/09 P06). The four #15 literal paths stay as aliases so
existing screens/tests keep working; new report slices only add catalog
rows + registry entries.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import PrintJob, ReportCatalog, User
from app.reports import catalog, exports, template, views

router = APIRouter()

REPORTS = require_permission("reports")


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


def _clean_paper(paper: str) -> str:
    if paper not in template.PAPERS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"paper must be one of {', '.join(template.PAPERS)}",
        )
    return paper


async def _run_report(
    *,
    code: str,
    session: AsyncSession,
    branch_id: int,
    params: dict[str, str],
    format: str,
    paper: str = "A4",
):
    """Dispatch any catalog code through the registry → JSON/grid/printable page."""
    if format == "json":
        entry = await catalog.get_catalog_entry(session, code)
        reg = views.get_entry(code)
        if entry is None or reg is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown report '{code}'")
        try:
            return await reg["query"](session, branch_id, params)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if format == "grid":
        entry, spec = await _grid(
            code=code, session=session, branch_id=branch_id, params=params
        )
        return {
            "title_ar": entry.title_ar,
            "title_en": entry.title_en,
            "meta": [{"label": m[0], "value": str(m[1])} for m in spec["meta"]],
            "columns": list(spec["columns"]),
            "rows": [[str(v) for v in row] for row in spec["rows"]],
            "foot": [str(v) for v in spec["foot"]] if spec.get("foot") else None,
            "note": spec.get("note"),
        }
    if format != "html":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "format must be json, grid, html (pdf/xlsx via /export)",
        )
    entry, spec = await _grid(
        code=code, session=session, branch_id=branch_id, params=params
    )
    return HTMLResponse(
        content=template.render_report_page(
            title_ar=entry.title_ar,
            title_en=entry.title_en,
            meta=[tuple(m) for m in spec["meta"]],
            columns=list(spec["columns"]),
            rows=[list(r) for r in spec["rows"]],
            foot=list(spec["foot"]) if spec.get("foot") else None,
            note=spec.get("note"),
            paper=_clean_paper(paper),
        ),
        status_code=status.HTTP_200_OK,
    )


async def _grid(
    *, code: str, session: AsyncSession, branch_id: int, params: dict[str, str]
) -> tuple[ReportCatalog, views.ViewSpec]:
    """Resolve a catalog code to its (entry, grid spec) — shared by html/export."""
    entry = await catalog.get_catalog_entry(session, code)
    reg = views.get_entry(code)
    if entry is None or reg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown report '{code}'")
    try:
        payload = await reg["query"](session, branch_id, params)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return entry, reg["view"](payload)


@router.get("")
async def list_reports(
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """The report catalog (codes + bilingual titles + params) for a screen menu."""
    return {"reports": await catalog.get_catalog(session)}


# --- #15 literal aliases (typed params; behavior unchanged) ------------------


@router.get("/day-profit")
async def report_day_profit(
    datee: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    format: str = "json",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """ربح اليوم: net revenue, COGS, expenses, net profit, VAT, discounts —
    for one day (`datee`) or across a period (`date_from`/`date_to`)."""
    return await _run_report(
        code="day_profit",
        session=session,
        branch_id=_caller_branch_id(caller),
        params={
            "datee": datee.isoformat() if datee else "",
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
        },
        format=format,
    )


@router.get("/period-totals")
async def report_period_totals(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    format: str = "json",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """ملخص المبيعات والمشتريات: counts + totals per kind over a date range."""
    return await _run_report(
        code="period_totals",
        session=session,
        branch_id=_caller_branch_id(caller),
        params={
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
        },
        format=format,
    )


@router.get("/stock-minimum")
async def report_stock_minimum(
    format: str = "json",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """النواقص: branch drugs whose qty is below the reorder point (RPT-ST01)."""
    return await _run_report(
        code="stock_minimum",
        session=session,
        branch_id=_caller_branch_id(caller),
        params={},
        format=format,
    )


@router.get("/drawer-handover")
async def report_drawer_handover(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    format: str = "json",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """تسليم الدرج: per-cashier cash/network in-out totals over a period."""
    return await _run_report(
        code="drawer_handover",
        session=session,
        branch_id=_caller_branch_id(caller),
        params={
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
        },
        format=format,
    )


# --- S3.1 print queue (durable, branch-scoped) -------------------------------


class PrintQueueEnqueue(BaseModel):
    params: dict[str, str] = Field(default_factory=dict)
    paper: Optional[str] = None


def _validate_params(
    code: str, allowed: list[str], params: dict[str, str]
) -> dict[str, str]:
    """Snapshot params must be known catalog params carrying ISO dates
    (or one of the declared integer params, e.g. stock_expired's
    `horizon_days`), and required params (e.g. stock_movements' `drug_id`)
    must be present — a job that can only fail at render must not queue."""
    unknown = set(params) - set(allowed)
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unknown params: {', '.join(sorted(unknown))}",
        )
    missing = views.REQUIRED_PARAMS.get(code, set()) - set(params)
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"missing required params: {', '.join(sorted(missing))}",
        )
    for name, raw in params.items():
        try:
            if name in views.INT_PARAMS:
                views.parse_int(name, raw)
            else:
                views.parse_date(name, raw)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if "datee" in params and ("date_from" in params or "date_to" in params):
        # mirrors day_profit's resolve_window rule: a job mixing the single
        # day with a range could never render, so it must not enqueue
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "pass either datee or a date_from/date_to range, not both",
        )
    try:
        views.require_ordered_range(
            views.parse_date("date_from", params.get("date_from")),
            views.parse_date("date_to", params.get("date_to")),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {k: v for k, v in params.items() if v}


@router.get("/print-queue")
async def list_print_queue(
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """The caller's branch print queue, newest first."""
    rows = await session.execute(
        select(PrintJob)
        .where(PrintJob.branch_id == _caller_branch_id(caller))
        .order_by(PrintJob.id.desc())
        .limit(200)
    )
    return {
        "jobs": [
            {
                "id": job.id,
                "report_code": job.report_code,
                "params": dict(job.params or {}),
                "paper": job.paper,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "done_at": job.done_at.isoformat() if job.done_at else None,
            }
            for job in rows.scalars()
        ]
    }


@router.post("/{code}/print-queue", status_code=status.HTTP_201_CREATED)
async def enqueue_print_job(
    code: str,
    body: PrintQueueEnqueue,
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """Queue one print of a catalog report (params snapshot + paper)."""
    entry = await catalog.get_catalog_entry(session, code)
    if entry is None or views.get_entry(code) is None:
        # no engine behind the row → the job could never render
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown report '{code}'")
    paper = _clean_paper(body.paper or entry.paper)
    params = _validate_params(code, list(entry.params or {}), body.params)
    job = PrintJob(
        branch_id=_caller_branch_id(caller),
        user_id=caller.id,
        report_code=code,
        params=params,
        paper=paper,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return {
        "id": job.id,
        "report_code": job.report_code,
        "params": dict(job.params or {}),
        "paper": job.paper,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.post("/print-queue/{job_id}/done")
async def mark_print_job_done(
    job_id: int,
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """Confirm a queued job printed: queued→done exactly once.

    The flip is a conditional UPDATE (`WHERE status = 'queued'`) so two
    concurrent confirms cannot both win — the loser's UPDATE matches no
    row and gets the 409.
    """
    job = await session.get(PrintJob, job_id)
    if job is None or job.branch_id != _caller_branch_id(caller):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such print job")
    previous_status = job.status
    result = await session.execute(
        update(PrintJob)
        .where(
            PrintJob.id == job_id,
            PrintJob.status == "queued",
        )
        .values(status="done", done_at=func.now())
    )
    if result.rowcount == 0:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"print job already {previous_status}"
        )
    await session.commit()
    await session.refresh(job)
    return {
        "id": job.id,
        "status": job.status,
        "done_at": job.done_at.isoformat() if job.done_at else None,
    }


# --- S3.1 generic dispatcher (any catalog entry) -----------------------------


@router.get("/{code}/export")
async def report_export(
    code: str,
    request: Request,
    format: str = "xlsx",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """Export any catalog report as a real file (xlsx / pdf)."""
    if format not in ("xlsx", "pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "format must be xlsx or pdf")
    skip = {"format", "paper"}  # paper styles the page, it is not report data
    params = {k: v for k, v in request.query_params.items() if k not in skip}
    entry, spec = await _grid(
        code=code, session=session, branch_id=_caller_branch_id(caller), params=params
    )
    meta = [tuple(m) for m in spec["meta"]]
    columns = list(spec["columns"])
    rows = [list(r) for r in spec["rows"]]
    foot = list(spec["foot"]) if spec.get("foot") else None
    note = spec.get("note")
    if format == "xlsx":
        content = exports.build_xlsx(
            title_ar=entry.title_ar,
            title_en=entry.title_en,
            meta=meta,
            columns=columns,
            rows=rows,
            foot=foot,
            note=note,
        )
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        content = exports.build_pdf(
            title_ar=entry.title_ar,
            title_en=entry.title_en,
            meta=meta,
            columns=columns,
            rows=rows,
            foot=foot,
            note=note,
            paper=_clean_paper(request.query_params.get("paper", entry.paper)),
        )
        media = "application/pdf"
        ext = "pdf"
    filename = f"{code}.{ext}"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{code}")
async def report_generic(
    code: str,
    request: Request,
    format: str = "json",
    paper: str = "A4",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """Render ANY active catalog row — JSON, or printable HTML at `paper`.

    Report params (datee / date_from / date_to, …) arrive as plain query
    params and are validated by the report's own query adapter.
    """
    skip = {"format", "paper"}
    params = {k: v for k, v in request.query_params.items() if k not in skip}
    return await _run_report(
        code=code,
        session=session,
        branch_id=_caller_branch_id(caller),
        params=params,
        format=format,
        paper=paper,
    )
