"""S1.6 purchase-return edge-case pass (ticket #12, part 2).

Covers the money/stock invariant + domain edge cases not exercised by the
original tests: multi-line returns, atomic rollback when a later line fails,
the other tax paths (exempt), the VAT-exclusive (wholesale) branch mode,
fractional qty + the 4dp over-return boundary, per-branch sequential invoice_no,
and the proportional per-line discount reversal.
"""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Invoice, SyncLog
from tests.purchase_returns_test_utils import (
    _batches,
    _cleanup,
    _journal_codes,
    _journal_totals,
    _login_token,
    _make_drug,
    _make_supplier,
    _purchase,
    _return,
    _stock_qty,
)
from tests.purchase_test_utils import (
    _make_other_branch,
    _make_user,
    _token_for,
    _uniq,
)
from tests.returns_test_utils import _delete_branch


async def _stock_qty_branch(branch_id: int, drug_id: int) -> Decimal:
    from app.models import BranchStock

    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == branch_id,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one_or_none()
        return row.qty if row is not None else Decimal("0")


async def test_multi_line_return_reverses_both_lines(client):
    """Return line A (14%, 4 of 10) AND line B (exempt, 5 of 10) in ONE request:
    money, VAT and stock sum across both lines; journal stays balanced."""
    drug_a = await _make_drug(tax_type="14%")
    drug_b = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id,
            [
                {"drug_id": drug_a, "qty": "10", "unit_cost": "10.0000"},
                {"drug_id": drug_b, "qty": "10", "unit_cost": "20.0000"},
            ],
        )
        invoice_ids.append(pur["id"])
        line_a = next(l for l in pur["lines"] if l["drug_id"] == drug_a)
        line_b = next(l for l in pur["lines"] if l["drug_id"] == drug_b)
        ret = await _return(client, token, pur, [
            {"ref_invoice_line_id": line_a["id"], "qty": "4"},
            {"ref_invoice_line_id": line_b["id"], "qty": "5"},
        ])
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "140.00"
        assert ret["vat"] == "5.60"  # only the 14% line carries VAT (B2B exclusive)
        assert ret["totalvalue"] == "145.60"
        assert ret["net"] == "140.00"
        assert ret["payed"] == "145.60"
        assert len(ret["lines"]) == 2
        assert await _stock_qty(drug_a) == Decimal("6.0000")
        assert await _stock_qty(drug_b) == Decimal("5.0000")
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("145.60")
    finally:
        await _cleanup([drug_a, drug_b], invoice_ids, [supplier_id])


async def test_multi_line_failure_rolls_back_atomically(client):
    """Line A is valid, line B over-returns → the WHOLE return must roll back:
    no batch movement, no stock movement, no return invoice, no outbox row."""
    drug_a = await _make_drug(tax_type="exempt")
    drug_b = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id,
            [
                {"drug_id": drug_a, "qty": "5", "unit_cost": "10.0000"},
                {"drug_id": drug_b, "qty": "5", "unit_cost": "10.0000"},
            ],
        )
        invoice_ids.append(pur["id"])
        line_a = next(l for l in pur["lines"] if l["drug_id"] == drug_a)
        line_b = next(l for l in pur["lines"] if l["drug_id"] == drug_b)
        r = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [
                {"ref_invoice_line_id": line_a["id"], "qty": "2"},
                {"ref_invoice_line_id": line_b["id"], "qty": "6"},
            ]},
        )
        assert r.status_code == 400
        assert "cannot return more" in r.json()["detail"]
        assert await _stock_qty(drug_a) == Decimal("5.0000")
        assert await _stock_qty(drug_b) == Decimal("5.0000")
        async with SessionLocal() as session:
            n_returns = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.kind == "purchase_return",
                        Invoice.ref_invoice_id == pur["id"],
                    )
                )
            ).scalars().all()
            assert n_returns == []
    finally:
        await _cleanup([drug_a, drug_b], invoice_ids, [supplier_id])


async def test_exempt_return_has_no_vat(client):
    """An exempt (0%) return: vat 0.00, net == total, journal has NO 2100 line."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["vat"] == "0.00"
        assert ret["totalvalue"] == "40.00"
        assert ret["net"] == "40.00"
        assert ret["payed"] == "40.00"
        codes = await _journal_codes(ret["id"])
        assert "2100" not in codes, codes
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("40.00")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_exclusive_branch_purchase_return(client):
    """Wholesale branch (vat_inclusive_prices=false): total = net + vat on top."""
    from tests.returns_test_utils import _make_branch

    branch_id = await _make_branch(vat_inclusive=False)
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier(branch_id=branch_id)
    user_id = await _make_user(_uniq("edge"), permission_level=9, branch_id=branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        assert pur["totalvalue"] == "114.00"
        assert pur["vat"] == "14.00"
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "40.00"
        assert ret["vat"] == "5.60"
        assert ret["totalvalue"] == "45.60"
        assert ret["net"] == "40.00"
        assert ret["payed"] == "45.60"
        assert await _stock_qty_branch(branch_id, drug_id) == Decimal("6.0000")
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("45.60")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])
        await _delete_branch(branch_id)


async def test_fractional_qty_and_4dp_boundary(client):
    """Returning a half unit works at 4dp; returning 10.0001 when only 9.5
    remains is rejected."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        line_id = pur["lines"][0]["id"]
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": line_id, "qty": "0.5"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["lines"][0]["qty"] == "0.5000"
        assert ret["totalvalue"] == "5.70"
        assert ret["vat"] == "0.70"
        assert ret["net"] == "5.00"
        assert await _stock_qty(drug_id) == Decimal("9.5000")
        r = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "10.0001"}]},
        )
        assert r.status_code == 400
        assert "cannot return more" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("9.5000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_two_returns_get_sequential_invoice_numbers(client):
    """Each return takes the branch's next invoice_no: distinct, monotonic."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        line_id = pur["lines"][0]["id"]
        ret1 = await _return(
            client, token, pur, [{"ref_invoice_line_id": line_id, "qty": "2"}]
        )
        invoice_ids.append(ret1["id"])
        ret2 = await _return(
            client, token, pur, [{"ref_invoice_line_id": line_id, "qty": "3"}]
        )
        invoice_ids.append(ret2["id"])
        assert ret1["invoice_no"] != pur["invoice_no"]
        assert ret2["invoice_no"] != pur["invoice_no"]
        assert ret1["invoice_no"].isdigit() and ret2["invoice_no"].isdigit()
        assert int(ret2["invoice_no"]) == int(ret1["invoice_no"]) + 1
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_return_reverses_line_discount_proportionally(client):
    """Original: 10 × 10.00 with a 10% PER-LINE discount (stored as the amount
    10.00). Returning 4 reverses the discount at the same proportion: 4.00."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id,
            [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000", "disc_percent": "10"}],
        )
        assert pur["discount"] == "10.00"
        assert pur["totalvalue"] == "102.60"
        assert pur["vat"] == "12.60"  # 14% on the discounted net 90.00
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "40.00"
        assert ret["discount"] == "4.00"
        assert ret["vat"] == "5.04"
        assert ret["totalvalue"] == "41.04"
        assert ret["net"] == "36.00"
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("41.04")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])