"""GS1/EGS item-code resolution for ETA documents (S4.3, #30).

Egyptian pharmacies already scan EDA/GS1 barcodes at the POS and EDTS (#47)
mandates GS1 DataMatrix next — so ``itemData.itemCode`` resolves by
precedence anchored to existing data (issue decision 2026-08-24):

1. a check-digit-valid **GS1 GTIN** (13–14 digits) among the drug's
   ``drug_barcodes`` rows
2. else the drug's registered EGS code (nullable ``drugs.egs_code``,
   migration 025)
3. else the documented fallback ``EGS-{branchCode}-{drugId}``

Bulk EGS registration with the ETA portal is a later decision ticket; until
then the fallback keeps submissions structurally valid. internalCode always
stays the internal drug id.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DrugBarcode


def gtin_check_digit(payload_digits: str) -> str:
    """GS1 mod-10 check digit for a numeric payload (weights 3/1 from right)."""
    total = 0
    for offset, char in enumerate(reversed(payload_digits)):
        total += int(char) * (3 if offset % 2 == 0 else 1)
    return str((10 - total % 10) % 10)


def is_gtin(code: str) -> bool:
    """A 13–14 digit string whose last digit passes the GS1 mod-10 check."""
    if len(code) not in (13, 14) or not code.isdigit():
        return False
    return code[-1] == gtin_check_digit(code[:-1])


def fallback_code(branch_code: str, drug_id: int) -> str:
    """The documented no-registration fallback."""
    return f"EGS-{branch_code}-{drug_id}"


async def resolve_item_codes(
    session: AsyncSession,
    *,
    branch_code: str,
    drugs: list,
) -> dict[int, str]:
    """One ETA itemCode per drug id, by GTIN → EGS column → fallback.

    One batched barcode query for the whole invoice's drugs — this runs
    inside the sale transaction, so it must stay cheap.
    """
    ids = [drug.id for drug in drugs]
    codes: dict[int, str] = {}
    egs_by_id = {
        drug.id: (drug.egs_code or "").strip()
        for drug in drugs
        if drug.egs_code and drug.egs_code.strip()
    }

    if ids:
        rows = (
            await session.execute(
                select(DrugBarcode.drug_id, DrugBarcode.barcode)
                .where(DrugBarcode.drug_id.in_(ids), DrugBarcode.barcode != "")
                .order_by(DrugBarcode.drug_id.asc(), DrugBarcode.id.asc())
            )
        ).all()
        for drug_id, barcode in rows:
            if is_gtin(barcode):
                codes[drug_id] = barcode

    for drug in drugs:
        if drug.id not in codes:
            codes[drug.id] = egs_by_id.get(drug.id) or fallback_code(
                branch_code, drug.id
            )
    return codes
