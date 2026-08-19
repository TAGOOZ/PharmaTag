"""S1.5 sales-return money + split behavior (ticket #11): the refund split
mirrors the original payment methods proportionally, explicit payments override
it, header discounts reverse proportionally, and a full return reverses the
original exactly — journal always balanced (SUM debit == SUM credit).
"""
from decimal import Decimal

from app.core.db import SessionLocal
from app.models import Invoice
from tests.returns_test_utils import (
    _cleanup,
    _journal_totals,
    _login_token,
    _make_drug_and_stock,
    _return_batches,
    _sale,
    _stock_qty,
)


async def test_return_refund_split_mirrors_original_payments(client):
    """Original paid 50 cash + 50 credit; a half return refunds 25/25."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(
            client, token,
            [{"drug_id": drug_id, "qty": "10"}],
            payments=[{"method": "cash", "amount": "50.00"},
                      {"method": "credit", "amount": "50.00"}],
        )
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])
        assert ret["totalvalue"] == "50.00"
        assert ret["payed"] == "25.00"
        assert ret["agel"] == "25.00"
        assert {"cash", "credit"} == {p["method"] for p in ret["payments"]}
        assert sum(Decimal(p["amount"]) for p in ret["payments"]) == Decimal("50.00")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_explicit_payments_override(client):
    """Client-provided payments override the proportional mirror."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(
            client, token, [{"drug_id": drug_id, "qty": "10"}],
            payments=[{"method": "credit", "amount": "100.00"}],
        )
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"ref_invoice_line_id": line_id, "qty": "4"}],
                "payments": [{"method": "credit", "amount": "40.00"}],
            },
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])
        assert ret["totalvalue"] == "40.00"
        assert ret["payed"] == "0.00"
        assert ret["agel"] == "40.00"
        assert [p["method"] for p in ret["payments"]] == ["credit"]
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_explicit_payments_mismatch_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"ref_invoice_line_id": line_id, "qty": "4"}],
                "payments": [{"method": "cash", "amount": "1.00"}],
            },
        )
        assert r.status_code == 400
        assert "payment total does not match" in r.json()["detail"]
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_reverses_header_discount_proportionally(client):
    """Original: 10 × 10.00 with 10% header discount (total 90.00). Returning
    4 keeps the SAME per-line split; the header discount reverses at the same
    proportion (round2(10 × 40/100) = 4.00) and the VAT re-splits on the
    discounted total, mirroring the sale's engine."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(
            client, token,
            [{"drug_id": drug_id, "qty": "10"}],
            disc_percent="10",
        )
        assert sale["discount"] == "10.00"
        assert sale["totalvalue"] == "90.00"
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "4"}]},
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "40.00"
        assert ret["discount"] == "4.00"
        assert ret["vat"] == "4.42"  # split_vat(36.00, 14%) = 31.58 / 4.42
        assert ret["totalvalue"] == "36.00"
        assert ret["net"] == "31.58"
        assert ret["payed"] == "36.00"
        assert ret["agel"] == "0.00"
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("56.00")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_line_discount_is_money_not_percent(client):
    """Regression: the sale stores the line discount as an AMOUNT, so a return
    must reverse it as an amount too. Feeding 10.00 back as a '10% percent'
    would double-discount the line (100 → 81 instead of 90)."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="100.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(
            client, token,
            [{"drug_id": drug_id, "qty": "1", "disc_percent": "10"}],
        )
        invoice_ids.append(sale["id"])
        assert sale["totalvalue"] == "90.00"
        assert sale["lines"][0]["line_total"] == "90.00"  # 10.00 discount in money
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "100.00"
        assert ret["discount"] == "10.00"  # the line discount reversed as money
        assert ret["totalvalue"] == "90.00"
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_full_return_reverses_original_exactly(client):
    """Returning everything reverses the original sale 1:1."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "10"}]},
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "100.00"
        assert ret["vat"] == "12.28"
        assert ret["totalvalue"] == "100.00"
        assert ret["net"] == "87.72"
        assert ret["payed"] == "100.00"
        batches = await _return_batches(drug_id)
        assert len(batches) == 1
        assert str(batches[0].qty) == "10.0000"
        assert await _stock_qty(drug_id) == Decimal("10.0000")
        # balanced reversal journal: Dr sales 87.72 + vat 12.28 + stock 50 vs
        # Cr drawer 100 + cogs 50
        debit, credit = await _journal_totals(ret["id"])
        assert debit == Decimal("150.00")
        assert credit == Decimal("150.00")
        assert debit == credit
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_keeps_original_untouched(client):
    """The original sale row keeps its status/totals; only a version snapshot
    is appended to it."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "4"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        async with SessionLocal() as session:
            orig = await session.get(Invoice, sale["id"])
            assert orig.status == "saved"
            assert orig.totalvalue == Decimal("100.00")
            assert orig.payed == Decimal("100.00")
    finally:
        await _cleanup([drug_id], invoice_ids)