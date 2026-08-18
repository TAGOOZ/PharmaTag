"""Business-date helpers (S1.7 edge pass, ticket #13).

The ledger posts journals under a *business date* (`journal.datee`), which is
what month/day bucketing and `entry_no` are keyed on. All server timestamps are
UTC; the business date is the same instant in the branch's business timezone
(`settings.timezone`, default `Africa/Cairo` for the single-country Egypt
domain). A correction decided at 22:00 UTC is 00:00 next day in Cairo and must
post under tomorrow's date, not yesterday's UTC date.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from zoneinfo import ZoneInfo

from app.core.config import settings


def business_date(dt: datetime | None = None) -> date:
    """Local business date for `dt` (default now) in the configured tz."""
    now = dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ZoneInfo(settings.timezone)).date()
