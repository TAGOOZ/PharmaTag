"""S4.3 GS1/EGS item-code precedence tests (ticket #30).

``coding.resolve_item_codes`` anchors item coding to what Egyptian pharmacies
already have, by precedence:

1. a check-digit-valid GS1 GTIN (13–14 digits) among the drug's
   ``drug_barcodes`` rows — they scan these at POS today
2. else the drug's registered EGS code (nullable ``drugs.egs_code``,
   migration 025)
3. else the documented fallback ``EGS-{branchCode}-{drugId}``

internalCode stays the internal drug id everywhere.
"""
from collections.abc import Callable
from typing import Optional

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.einvoicing.coding import (
    fallback_code,
    gtin_check_digit,
    is_gtin,
    resolve_item_codes,
)
from app.models import Branch, BranchStock, Drug, DrugBarcode, StockBatch
from tests.returns_test_utils import (
    _delete_branch,
    _make_branch,
    _make_drug_and_stock_branch,
)


# --- pure mod-10 helpers ---------------------------------------------------
#
# drug_barcodes carries a partial-unique index on barcode and the test DB
# persists between runs, so DB fixtures derive their codes from the throwaway
# drug id instead of constants.


def _valid_gtin(seed: int) -> str:
    """A unique-per-seed, check-digit-valid GTIN-13."""
    payload = f"0628107{seed % 100000:05d}0"[:12]
    return payload + gtin_check_digit(payload)


def _invalid_gtin(seed: int) -> str:
    """A well-shaped 13-digit code whose check digit fails mod-10."""
    code = _valid_gtin(seed)
    return code[:-1] + str((int(code[-1]) + 1) % 10)


def test_gtin_accepts_valid_13_digit_code():
    valid = _valid_gtin(1)
    assert is_gtin(valid)
    assert valid[-1] == gtin_check_digit(valid[:-1])


def test_gtin_accepts_valid_14_digit_code_with_zero_indicator():
    gtin13 = _valid_gtin(3)
    payload14 = "0" + gtin13[:-1]  # indicator 0 + the same 12-digit base
    gtin14 = payload14 + gtin_check_digit(payload14)
    assert len(gtin14) == 14 and is_gtin(gtin14)


def test_gtin_rejects_bad_check_digit_and_wrong_shapes():
    assert not is_gtin(_invalid_gtin(2))
    assert not is_gtin("06281070261")   # 11 digits — too short
    assert not is_gtin("")              # empty barcode default rows exist
    assert not is_gtin("40063813339x")  # non-digits


def test_fallback_code_format():
    assert fallback_code("0", 501) == "EGS-0-501"


# --- DB-backed precedence --------------------------------------------------


async def _branch_drug_with(
    *,
    egs_code: Optional[str],
    barcodes_for: Callable[[int], list[str]],
):
    """A throwaway branch + one drug carrying the given coding data."""
    branch_id = await _make_branch(vat_inclusive=True)
    async with SessionLocal() as session:
        branch = await session.get(Branch, branch_id)
        pharmacyid = branch.pharmacyid
    drug_id = await _make_drug_and_stock_branch(branch_id)
    async with SessionLocal() as session:
        if egs_code is not None:
            drug = await session.get(Drug, drug_id)
            drug.egs_code = egs_code
        for barcode in barcodes_for(drug_id):
            session.add(DrugBarcode(drug_id=drug_id, barcode=barcode))
        await session.commit()
        drug = await session.get(Drug, drug_id)
    return branch_id, drug_id, drug, pharmacyid


async def _cleanup(branch_id: int, drug_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(DrugBarcode).where(DrugBarcode.drug_id == drug_id))
        await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
        await session.execute(delete(BranchStock).where(BranchStock.drug_id == drug_id))
        await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.commit()
    await _delete_branch(branch_id)


async def test_resolution_precedence_gtin_beats_egs_column_and_fallback():
    branch_id, drug_id, drug, pharmacyid = await _branch_drug_with(
        egs_code="EG-200173707-PAX24",
        barcodes_for=lambda did: [_invalid_gtin(did), _valid_gtin(did)],
    )
    try:
        async with SessionLocal() as session:
            codes = await resolve_item_codes(
                session, branch_code=pharmacyid, drugs=[drug]
            )
            assert codes[drug_id] == _valid_gtin(drug_id)
    finally:
        await _cleanup(branch_id, drug_id)


async def test_resolution_uses_egs_column_when_no_valid_gtin():
    branch_id, drug_id, drug, pharmacyid = await _branch_drug_with(
        egs_code=" EG-200173707-PAX24 ",
        barcodes_for=lambda did: [_invalid_gtin(did)],
    )
    try:
        async with SessionLocal() as session:
            codes = await resolve_item_codes(
                session, branch_code=pharmacyid, drugs=[drug]
            )
            assert codes[drug_id] == "EG-200173707-PAX24"  # trimmed
    finally:
        await _cleanup(branch_id, drug_id)


async def test_resolution_falls_back_to_branch_prefixed_internal_code():
    branch_id, drug_id, drug, pharmacyid = await _branch_drug_with(
        egs_code=None,
        barcodes_for=lambda did: [],
    )
    try:
        async with SessionLocal() as session:
            codes = await resolve_item_codes(
                session, branch_code=pharmacyid, drugs=[drug]
            )
            assert codes[drug_id] == f"EGS-{pharmacyid}-{drug_id}"
    finally:
        await _cleanup(branch_id, drug_id)
