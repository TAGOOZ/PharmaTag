"""The e-invoice issue path (S4.1, #28; ADR-0002).

`issue_for_invoice` runs INSIDE the invoice's transaction and writes the tax
document atomically with it (G12): the einvoice_log row, the counter bump,
the audit row. STRICT per A09 — if any of it fails the whole sale rolls back
(no un-hashable invoices). Offline rides the legal 24-hour window: the row
stays ``pending`` until S4.2's submission worker picks it up.

`apply_einvoice_block` is the replay twin: it re-inserts a document from an
outbox snapshot VERBATIM (counter/uuid/chain included — never re-generated)
and is idempotent through uq_einvoice_log_invoice.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.einvoicing.documents import build_document, canonical, route_kind
from app.models.einvoicing import KIND_CREDIT_NOTE, KIND_RETURN_RECEIPT
from app.einvoicing.toolkit import (
    PREPROD_PORTAL_URL,
    PROD_PORTAL_URL,
    qr_string,
    receipt_uuid,
)
from app.models import (
    AppConfig,
    Branch,
    EInvoiceCounter,
    EInvoiceLog,
    Invoice,
    Party,
)

SELLER_RIN_KEY = "eta.rin"
SELLER_TRADE_NAME_KEY = "eta.trade_name"
SELLER_ACTIVITY_CODE_KEY = "eta.activity_code"


def _portal_url() -> str:
    from app.core.config import settings

    return PREPROD_PORTAL_URL if settings.environment == "preprod" else PROD_PORTAL_URL


async def seller_identity(session: AsyncSession) -> dict:
    """Taxpayer-level identity from app_config (RIN is company-wide; branch
    code/address come from the branches row). Empty until configured — S4.2
    refuses submission on an empty RIN, but issuing never blocks on config."""
    rows = (
        await session.execute(
            select(AppConfig).where(
                AppConfig.key.in_(
                    (SELLER_RIN_KEY, SELLER_TRADE_NAME_KEY, SELLER_ACTIVITY_CODE_KEY)
                )
            )
        )
    ).scalars().all()
    cfg = {row.key: row.value for row in rows}
    return {
        "rin": cfg.get(SELLER_RIN_KEY, ""),
        "trade_name": cfg.get(SELLER_TRADE_NAME_KEY, ""),
        "activity_code": cfg.get(SELLER_ACTIVITY_CODE_KEY, ""),
    }


async def _allocate_counter(
    session: AsyncSession, *, branch_id: int, kind: str
) -> EInvoiceCounter:
    """SELECT ... FOR UPDATE on the chain state (created on first use); the
    branch advisory lock already held by the caller serializes numbering."""
    row = (
        await session.execute(
            select(EInvoiceCounter)
            .where(
                EInvoiceCounter.branch_id == branch_id,
                EInvoiceCounter.kind == kind,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = EInvoiceCounter(branch_id=branch_id, kind=kind, last_counter=0, last_uuid="")
        session.add(row)
        await session.flush()
    return row


async def _original_log(
    session: AsyncSession, invoice: Invoice
) -> Optional[EInvoiceLog]:
    if invoice.ref_invoice_id is None:
        return None
    return (
        await session.execute(
            select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice.ref_invoice_id)
        )
    ).scalar_one_or_none()


async def issue_for_invoice(
    session: AsyncSession,
    *,
    invoice: Invoice,
    branch: Branch,
    lines: list[dict],
    totals: dict,
    splits: Optional[list[tuple[str, Any]]] = None,
    party: Optional[Party] = None,
) -> EInvoiceLog:
    """Write the tax document for `invoice` in the caller's transaction."""
    original_log = await _original_log(session, invoice)
    kind = route_kind(invoice, party, original_log)

    counter_row = await _allocate_counter(session, branch_id=invoice.branch_id, kind=kind)
    counter = counter_row.last_counter + 1
    previous_uuid = counter_row.last_uuid or ""
    reference_uuid = original_log.uuid if original_log else ""

    original_buyer = None
    if kind in (KIND_RETURN_RECEIPT, KIND_CREDIT_NOTE) and original_log is not None:
        original_buyer = (original_log.payload_json or {}).get("buyer")

    # canonicalize BEFORE hashing/storing so the JSONB outbox transport can
    # never reorder keys behind the hash (see documents.canonical)
    document = canonical(build_document(
        kind=kind,
        invoice=invoice,
        branch=branch,
        party=party,
        lines=lines,
        totals=totals,
        splits=splits or [],
        seller=await seller_identity(session),
        device_serial=counter_row.device_serial,
        counter=counter,
        previous_uuid=previous_uuid,
        reference_uuid=reference_uuid,
        original_buyer=original_buyer,
    ))
    uuid = receipt_uuid(document)
    qr_data = qr_string(
        uuid=uuid,
        datetime_issued_utc=document["header"]["dateTimeIssued"],
        total=document["totalAmount"],
        issuer_rin=document["seller"]["rin"],
        portal_url=_portal_url(),
    )

    log = EInvoiceLog(
        invoice_id=invoice.id,
        branch_id=invoice.branch_id,
        kind=kind,
        status="pending",
        counter=counter,
        uuid=uuid,
        previous_uuid=previous_uuid,
        reference_uuid=reference_uuid,
        device_serial=counter_row.device_serial,
        qr_data=qr_data,
        payload_json=document,
    )
    session.add(log)
    await session.flush()

    counter_row.last_counter = counter
    counter_row.last_uuid = uuid

    invoice_no = invoice.invoice_no
    await audit(
        session,
        branch_id=invoice.branch_id,
        user_id=invoice.created_by,
        entity="einvoice_log",
        entity_id=log.id,
        action=ACTION_INSERT,
        new_value=(
            f"kind={kind} counter={counter} uuid={uuid[:16]} "
            f"invoice_no={invoice_no}"
        ),
        typevalue=invoice_no,
    )
    return log


def einvoice_block(log: EInvoiceLog) -> dict[str, Any]:
    """The JSON-primitive snapshot embedded in the sale/return outbox payload."""
    return {
        "kind": log.kind,
        "status": log.status,
        "counter": int(log.counter),
        "uuid": log.uuid,
        "previous_uuid": log.previous_uuid,
        "reference_uuid": log.reference_uuid,
        "device_serial": log.device_serial,
        "qr_data": log.qr_data,
        "payload_json": log.payload_json,
    }


async def apply_einvoice_block(
    session: AsyncSession,
    *,
    branch_id: int,
    invoice_id: int,
    block: dict[str, Any],
) -> Optional[EInvoiceLog]:
    """Replay-side twin of issue_for_invoice: insert the snapshot verbatim.

    Idempotent: an existing document for the invoice is returned untouched;
    otherwise the row lands at its ORIGINAL chain position and the branch
    counter rolls forward to it (max, never backwards).
    """
    existing = (
        await session.execute(
            select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    counter = int(block["counter"])
    payload_json = canonical(block.get("payload_json") or {})
    log = EInvoiceLog(
        invoice_id=invoice_id,
        branch_id=branch_id,
        kind=block["kind"],
        status=block.get("status", "pending"),
        counter=counter,
        uuid=block["uuid"],
        previous_uuid=block.get("previous_uuid", ""),
        reference_uuid=block.get("reference_uuid", ""),
        device_serial=block.get("device_serial"),
        qr_data=block.get("qr_data", ""),
        payload_json=payload_json,
    )
    session.add(log)
    await session.flush()

    counter_row = await _allocate_counter(session, branch_id=branch_id, kind=log.kind)
    if counter > counter_row.last_counter:
        counter_row.last_counter = counter
        counter_row.last_uuid = log.uuid
    return log
