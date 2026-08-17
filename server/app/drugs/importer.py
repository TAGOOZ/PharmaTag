"""CC0 catalog import job (ticket #8 / S1.2, plan/00 G03).

Loads a CSV from the CC0 `karem505/egyptian-drug-database` (24k+ Egyptian
medicines, CC0-1.0) into the drug master, de-duping against the existing
master and being idempotent — re-running the same file adds nothing.

Source (G03, research-verified): https://github.com/karem505/egyptian-drug-database
  raw CSV: https://raw.githubusercontent.com/karem505/egyptian-drug-database/main/data/egyptian-drugs.csv
The catalog itself is NOT bundled in this repo (network fetch / license-free
download is a deliberate step); `python -m app.drugs.importer <file.csv>`
runs it against the DB. A small representative sample is bundled under
`server/tests/fixtures/cc0_catalog_sample.csv` for tests only.

Accepted columns (karem505 native names, with PharmaTag aliases):
  commercial_name_en | drugname            -> drugname
  commercial_name_ar | drugnamear          -> drugnamear
  scientific_name    | generic             -> generic
  manufacturer       | co                  -> co
  drug_class         | classy              -> classy
  route              | unitsclass          -> unitsclass
  price_egp          | price               -> public price level (سعر الجمهور)
  price_wholesale                         -> wholesale price level (سعر الجملة)
  price_cost                              -> cost price level (سعر الشراء-التكلفة)
  tax_type                                 -> exempt / 5% / 14% (default exempt:
                                             medicines are VAT-exempt, G06)
  barcodes                                 -> comma/pipe-separated codes, <= 6

Dedupe keys (both checked per row, in order):
  1. barcode  — any of the row's barcodes already on a drug (barcode wins);
  2. normalized drugname (strip + casefold) — already in the master.
Malformed rows (missing name, garbage/negative money, bad tax_type, >6
barcodes) are skipped and reported, not fatal. The whole batch commits once:
all inserted rows + their audit rows atomically.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.audit import ACTION_INSERT, audit
from app.core.db import SessionLocal
from app.drugs.service import MAX_BARCODES, TAX_TYPES, _clean_barcodes, validate_price_levels
from app.models import Drug, DrugBarcode, PriceChangeLog, User

CATALOG_SOURCE_URL = (
    "https://github.com/karem505/egyptian-drug-database"
)
CATALOG_RAW_CSV_URL = (
    "https://raw.githubusercontent.com/karem505/egyptian-drug-database/main/data/egyptian-drugs.csv"
)

_COLUMN_ALIASES = {
    "drugname": ("commercial_name_en", "drugname", "name_en"),
    "drugnamear": ("commercial_name_ar", "drugnamear", "name_ar"),
    "generic": ("scientific_name", "generic", "scientific"),
    "co": ("manufacturer", "co"),
    "classy": ("drug_class", "classy", "category"),
    "unitsclass": ("route", "unitsclass"),
    "price": ("price_egp", "price", "price_public"),
    "price_wholesale": ("price_wholesale", "wholesale"),
    "price_cost": ("price_cost", "cost"),
    "tax_type": ("tax_type",),
    "barcodes": ("barcodes", "barcode"),
}


@dataclass
class ImportReport:
    """Result of one catalog import run (idempotent by construction)."""

    inserted: int = 0
    skipped_duplicate_barcode: int = 0
    skipped_duplicate_name: int = 0
    skipped_malformed: int = 0
    errors: list[str] = field(default_factory=list)
    inserted_names: list[str] = field(default_factory=list)


def _pick(row: dict, key: str) -> Optional[str]:
    for alias in _COLUMN_ALIASES[key]:
        value = row.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def parse_catalog_csv(csv_text: str) -> list[dict]:
    """Parse catalog CSV (UTF-8, header row) into a list of row dicts.

    Raises ValueError when the text is empty or has no header row. Row dicts
    keep the file's own column names (aliasing happens at import time).
    """
    if not csv_text or not csv_text.strip():
        raise ValueError("empty catalog file")
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("catalog CSV has no header row")
    return [dict(row) for row in reader]


def _row_money(raw: Optional[str], default: str = "0") -> Decimal:
    """Coerce a CSV money cell to an exact Decimal (float is never accepted)."""
    if raw is None or raw.strip() == "":
        return money.dec(default)
    return money.dec(raw.strip())


async def _existing_barcodes(session: AsyncSession, barcodes: set[str]) -> set[str]:
    if not barcodes:
        return set()
    result = await session.execute(
        select(DrugBarcode.barcode).where(DrugBarcode.barcode.in_(barcodes))
    )
    return set(result.scalars().all())


async def _existing_normalized_names(session: AsyncSession, names: set[str]) -> set[str]:
    if not names:
        return set()
    lowered = {n.casefold() for n in names}
    result = await session.execute(
        select(Drug.drugname).where(func.lower(Drug.drugname).in_(lowered))
    )
    return {n.strip().casefold() for n in result.scalars().all() if n}


async def import_catalog_csv(
    session: AsyncSession,
    *,
    caller: User,
    branch_id: int,
    csv_text: str,
    localimport: int = 1,
) -> ImportReport:
    """Parse + import a catalog CSV in one idempotent, atomic batch."""
    rows = parse_catalog_csv(csv_text)
    return await import_catalog_rows(
        session, caller=caller, branch_id=branch_id, rows=rows, localimport=localimport
    )


async def import_catalog_rows(
    session: AsyncSession,
    *,
    caller: User,
    branch_id: int,
    rows: list[dict],
    localimport: int = 1,
) -> ImportReport:
    """Insert catalog rows that don't already exist; skip dups + malformed."""
    report = ImportReport()

    batch_names = {
        (_pick(r, "drugname") or "").strip().casefold() for r in rows if _pick(r, "drugname")
    }
    batch_barcodes = set()
    for r in rows:
        raw = _pick(r, "barcodes")
        if raw:
            batch_barcodes.update(b for b in raw.replace("|", ",").split(",") if b.strip())
    existing_barcodes = await _existing_barcodes(session, batch_barcodes)
    existing_names = await _existing_normalized_names(session, batch_names)

    seen_names: set[str] = set()
    seen_barcodes: set[str] = set(existing_barcodes)

    try:
        for idx, row in enumerate(rows, start=2):  # 1 = header
            error = await _import_one(
                session,
                report=report,
                caller=caller,
                branch_id=branch_id,
                row=row,
                row_no=idx,
                existing_barcodes=seen_barcodes,
                existing_names=existing_names,
                seen_names=seen_names,
                localimport=localimport,
            )
            if error is not None:
                report.skipped_malformed += 1
                report.errors.append(f"row {idx}: {error}")
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise
    return report


async def _import_one(
    session: AsyncSession,
    *,
    report: ImportReport,
    caller: User,
    branch_id: int,
    row: dict,
    row_no: int,
    existing_barcodes: set[str],
    existing_names: set[str],
    seen_names: set[str],
    localimport: int,
) -> Optional[str]:
    """Insert one row; returns an error string when the row is malformed."""
    name = _pick(row, "drugname")
    if not name:
        return "missing drugname"
    try:
        price = _row_money(_pick(row, "price"))
        wholesale = _row_money(_pick(row, "price_wholesale"))
        cost = _row_money(_pick(row, "price_cost"))
        validate_price_levels(price, wholesale, cost)
    except (InvalidOperation, ValueError, TypeError) as exc:
        return f"invalid price levels ({exc})"

    tax_type = _pick(row, "tax_type") or "exempt"
    if tax_type not in TAX_TYPES:
        return f"invalid tax_type {tax_type!r}"

    barcodes = []
    raw_barcodes = _pick(row, "barcodes")
    if raw_barcodes:
        try:
            barcodes = _clean_barcodes(raw_barcodes.replace("|", ",").split(","))
        except Exception as exc:
            return str(exc)

    norm_name = name.strip().casefold()
    if norm_name in seen_names:
        report.skipped_duplicate_name += 1
        return None
    for b in barcodes:
        if b in existing_barcodes:
            report.skipped_duplicate_barcode += 1
            return None
    if norm_name in existing_names:
        report.skipped_duplicate_name += 1
        return None

    drug = Drug(
        drugname=name,
        drugnamear=_pick(row, "drugnamear") or "",
        generic=_pick(row, "generic") or "",
        classy=_pick(row, "classy") or "",
        co=_pick(row, "co") or "",
        unitsclass=_pick(row, "unitsclass") or "",
        tax_type=tax_type,
        price=price,
        price_wholesale=wholesale,
        price_cost=cost,
        price_now=price,
        active=True,
        localimport=localimport,
    )
    session.add(drug)
    await session.flush()
    for i, barcode in enumerate(barcodes):
        session.add(
            DrugBarcode(drug_id=drug.id, barcode=barcode, is_primary=(i == 0))
        )
    await session.flush()
    await audit(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        entity="drug",
        entity_id=drug.id,
        field="drugname",
        old_value="",
        new_value=drug.drugname,
        drug_id=drug.id,
        action=ACTION_INSERT,
    )
    session.add(
        PriceChangeLog(
            branch_id=branch_id,
            drug_id=drug.id,
            price=price,
            disco=money.dec("0"),
            units=drug.units,
            changed_by=caller.id,
        )
    )
    seen_names.add(norm_name)
    existing_barcodes.update(barcodes)
    report.inserted += 1
    report.inserted_names.append(drug.drugname)
    return None


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="path to the catalog CSV")
    parser.add_argument("--username", default="admin", help="user performing the import")
    args = parser.parse_args(argv)

    async def run() -> None:
        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.username == args.username))
            user = result.scalar_one_or_none()
            if user is None:
                raise SystemExit(f"user {args.username!r} not found")
            branch_id = user.branch_id or 1
            report = await import_catalog_csv(
                session, caller=user, branch_id=branch_id,
                csv_text=open(args.csv_path, encoding="utf-8").read(),
            )
            print(
                f"inserted={report.inserted} "
                f"dup_barcode={report.skipped_duplicate_barcode} "
                f"dup_name={report.skipped_duplicate_name} "
                f"malformed={report.skipped_malformed}"
            )
            for err in report.errors:
                print(f"  {err}")

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())