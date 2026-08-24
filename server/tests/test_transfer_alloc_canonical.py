"""Allocation wire canonicalization (#57, deliverable 3).

`Allocation.to_json` used `str(Decimal)`, so the emitted scale varied with the
stored value ("4" vs "4.0000" vs "4.00005"). Egyptian-market rationale: VAT
slabs are exempt/5%/14% -> always "0.00"/"5.00"/"14.00"; quantities print to
4dp like invoices (`sent_qty` already uses `_qty4`). The wire form is now
canonical: qty/cost/price exactly-4dp strings, vat exactly-2dp, expire ISO date
or None. `allocations_from_json` must still parse legacy rows of ANY scale.
"""
from datetime import date
from decimal import Decimal

from app.transfers.stock import Allocation, allocations_from_json


def _alloc(take="4", cost="5.5", vat="14", price="20", expire="2026-12-01"):
    return Allocation(
        batch_id=1,
        randomid="r1",
        take=Decimal(take),
        cost=Decimal(cost),
        expire=date.fromisoformat(expire) if expire is not None else None,
        vat=Decimal(vat),
        price=Decimal(price),
    )


def test_to_json_qty_cost_price_are_exact_4dp():
    j = _alloc().to_json()
    assert j["qty"] == "4.0000"
    assert j["cost"] == "5.5000"
    assert j["price"] == "20.0000"


def test_to_json_vat_is_exact_2dp_slab_string():
    for slab, wire in (("0", "0.00"), ("5", "5.00"), ("14", "14.00")):
        assert _alloc(vat=slab).to_json()["vat"] == wire


def test_to_json_expire_iso_or_none():
    assert _alloc(expire="2026-12-01").to_json()["expire"] == "2026-12-01"
    assert _alloc(expire=None).to_json()["expire"] is None


def test_to_json_rounds_half_up_beyond_4dp():
    # stored scale may exceed 4dp; the wire never does (round-half-up)
    j = _alloc(take="4.00005", cost="5.25005").to_json()
    assert j["qty"] == "4.0001"
    assert j["cost"] == "5.2501"


def test_from_json_parses_legacy_rows_of_any_scale():
    legacy = {
        "batch_id": 7,
        "randomid": "old-lot",
        "qty": "4.00000",
        "cost": "5.5000000",
        "expire": "2026-12-01",
        "vat": "14.000",
        "price": "20.0",
    }
    a = allocations_from_json([legacy])[0]
    assert a.take == Decimal("4")
    assert a.cost == Decimal("5.5")
    assert a.vat == Decimal("14")
    assert a.price == Decimal("20")
    assert a.expire == date(2026, 12, 1)


def test_wire_roundtrip_new_form_matches_legacy_values():
    """New canonical form parses back to the same allocation the legacy row held."""
    canonical = _alloc().to_json()
    assert allocations_from_json([canonical])[0] == _alloc()
