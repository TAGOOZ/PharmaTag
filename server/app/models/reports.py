"""Reports models: RPT catalog + print queue (S3.1, ticket #23)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReportCatalog(Base):
    """`report_catalog` — one row per RPT report the framework renders.

    The catalog IS the menu and the dispatch key: a later report slice adds
    rows here plus a query/view pair in `app/reports`, never new endpoints.
    `paper` is the default print paper (A4/A5); `params` lists the query
    parameters the screen must ask for, in order.
    """

    __tablename__ = "report_catalog"
    __table_args__ = (
        CheckConstraint("paper IN ('A4', 'A5')", name="ck_report_catalog_paper"),
    )

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    params: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    paper: Mapped[str] = mapped_column(String(2), nullable=False, server_default="A4")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class PrintJob(Base):
    """`print_jobs` — the durable print queue (legacy ModPrint's job side).

    A branch-scoped row per queued print/export of a catalog report with its
    snapshot params + paper; flipped queued→done when the client confirms it
    printed. Survives restarts so an offline desktop can drain it later.
    """

    __tablename__ = "print_jobs"
    __table_args__ = (
        CheckConstraint("paper IN ('A4', 'A5')", name="ck_print_jobs_paper"),
        CheckConstraint(
            "status IN ('queued', 'done', 'failed')", name="ck_print_jobs_status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    report_code: Mapped[str] = mapped_column(
        String(64), ForeignKey("report_catalog.code"), nullable=False
    )
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    paper: Mapped[str] = mapped_column(String(2), nullable=False, server_default="A4")
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="queued")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    done_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
