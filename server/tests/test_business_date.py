"""S1.7 edge pass (ticket #13): the ledger business date is derived from the
server's UTC clock in the configured business timezone (edge pass #8)."""
from datetime import date, datetime, timezone

from app.core.time import business_date


def test_business_date_crosses_midnight_in_business_tz():
    """22:00 UTC is already next day in Africa/Cairo (+2/+3) — the journal
    must post under tomorrow's date, not the prior UTC day."""
    dt = datetime(2026, 1, 15, 22, 0, 0, tzinfo=timezone.utc)
    assert business_date(dt) == date(2026, 1, 16)


def test_business_date_midday_is_same_day():
    """12:00 UTC stays the same business day in Cairo."""
    dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert business_date(dt) == date(2026, 1, 15)


def test_business_date_defaults_to_now_utc():
    """With no argument, business_date reflects the current UTC instant."""
    assert business_date() == business_date(datetime.now(timezone.utc))


def test_business_date_naive_input_treated_as_utc():
    assert business_date(datetime(2026, 1, 15, 22, 0, 0)) == date(2026, 1, 16)