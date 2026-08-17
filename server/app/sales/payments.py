"""Payment split resolution for sales.

`payed` (cash/card) + `agel` (credit) must reconcile to the invoice total —
the invoice CHECK `payed + agel = totalvalue` enforces this at the DB too.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status

from app.core.money import round2

PRICE_MISMATCH = HTTPException(
    status.HTTP_400_BAD_REQUEST, "payment total does not match sale total"
)


class _Payment:
    """Minimal payment duck-type (pydantic models or this default)."""

    def __init__(self, *, cash: Decimal) -> None:
        self.method = "cash"
        self.amount = cash


def _resolve_payments(
    payments, total: Decimal
) -> tuple[Decimal, Decimal, list[tuple[str, Decimal]]]:
    """Resolve payment splits; payed (cash/card) + agel (credit) == total."""
    total = round2(total)
    if payments is None or not payments:
        payments = [_Payment(cash=total)]
    paid_sum = Decimal("0")
    credit_sum = Decimal("0")
    splits: list[tuple[str, Decimal]] = []
    for p in payments:
        method = getattr(p, "method", "cash")
        amount = getattr(p, "amount", None)
        if amount is None:
            amount = round2(total - paid_sum - credit_sum)
        else:
            amount = round2(amount)
        if amount > 0:
            splits.append((method, amount))
        if method == "credit":
            credit_sum += amount
        else:
            paid_sum += amount
    payed = round2(paid_sum)
    agel = round2(credit_sum)
    if round2(payed + agel) != total:
        raise PRICE_MISMATCH
    return payed, agel, splits