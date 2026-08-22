"""Report window resolution shared by the accounting reports (S3.5, #27).

Same contract as the mizan (app/accounts/mizan.py): `month`/`year` is the
canonical form, an inclusive `date_from`/`date_to` range is the alternative,
mixing the two forms is rejected as ambiguous, an inverted range is rejected
up front, and NO params defaults to the current business month.
"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

from fastapi import HTTPException, status

from app.core.time import business_date

_AMBIGUOUS = HTTPException(
    status.HTTP_400_BAD_REQUEST, "pass month/year OR a date range, not both"
)
_INVERTED = HTTPException(
    status.HTTP_400_BAD_REQUEST, "date_from must not be after date_to"
)


def resolve_period(
    month: Optional[int],
    year: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> tuple[dict, date, date]:
    """(period meta for the payload, window start, window end)."""
    if (month is not None or year is not None) and (
        date_from is not None or date_to is not None
    ):
        raise _AMBIGUOUS
    if date_from is not None and date_to is not None and date_from > date_to:
        raise _INVERTED

    if month is not None or year is not None:
        today = business_date()
        m = month or today.month
        y = year or today.year
        return (
            {"month": m, "year": y, "date_from": None, "date_to": None},
            date(y, m, 1),
            date(y, m, calendar.monthrange(y, m)[1]),
        )
    if date_from is not None or date_to is not None:
        return (
            {
                "month": None,
                "year": None,
                "date_from": date_from,
                "date_to": date_to,
            },
            date_from or date(1900, 1, 1),
            date_to or date(9999, 12, 31),
        )
    today = business_date()
    y, m = today.year, today.month
    return (
        {"month": m, "year": y, "date_from": None, "date_to": None},
        date(y, m, 1),
        date(y, m, calendar.monthrange(y, m)[1]),
    )


def iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None
