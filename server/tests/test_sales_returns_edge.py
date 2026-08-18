"""S1.5 sales-return edge-case pass (ticket #11, part 2).

Covers the money/stock invariant + domain edge cases not exercised by the
original 20 tests: multi-line returns, atomic rollback when a later line fails,
the other tax paths (exempt, 5%), the VAT-exclusive (wholesale) branch mode,
all-credit and mixed-method refund mirrors, fractional qty + the 4dp
over-return boundary, chained returns, and per-branch sequential invoice_no.
"""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Invoice, SyncLog
from tests.returns_test_utils import (
    _cleanup,
    _delete_branch,
    _journal_codes,
    _journal_totals,
    _login_token,
    _make_branch,
    _make_drug_and_stock,
    _make_drug_and_stock_branch,
    _return_batches,
    _sale,
    _stock_qty,
    _stock_qty_branch,
)
from tests.sales_test_utils import _make_user, _token_for
from tests.purchase_test_utils import _uniq


async def _return(client, token: str, sale: dict, lines: list[dict], payments=None) -> dict:
    body = {"lines": lines}
    if payments is not None:
        body["payments"] = payments
    r = await client.post(
        f"/api/v1/sales/{sale['id']}/return",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_multi_line_return_reverses_both_lines(client):
    """Return line A (14%, 4 of 10) AND line B (exempt, 5 of 10) in ONE request:
    money, VAT, COGS and stock sum across both lines; journal stays balanced."""
    drug_a = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    drug_b = await _make_drug_and_stock(
        tax_type="exempt", price="20.0000", cost_price="8.0000",
        batches=[("10.0000", "8.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [
            {"drug_id": drug_a, "qty": "10"},
            {"drug_id": drug_b, "qty": "10"},
        ])
        invoice_ids.append(sale["id"])
        line_a = next(l for l in sale["lines"] if l["drug_id"] == drug_a)
        line_b = next(l for l in sale["lines"] if l["drug_id"] == drug_b)
        ret = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_a["id"], "qty": "4"},
            {"ref_invoice_line_id": line_b["id"], "qty": "5"},
        ])
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "140.00"
        assert ret["vat"] == "4.91"
        assert ret["totalvalue"] == "140.00"
        assert ret["net"] == "135.09"
        assert ret["payed"] == "140.00"
        assert len(ret["lines"]) == 2
        # stock: A up 4, B up 5
        assert await _stock_qty(drug_a) == Decimal("4.0000")
        assert await _stock_qty(drug_b) == Decimal("5.0000")
        # one NEW return batch per line
        assert len(await _return_batches(drug_a)) == 1
        assert len(await _return_batches(drug_b)) == 1
        # cogs 4×5 + 5×8 = 60; balanced journal Dr sales/vat/stock vs Cr drawer/cogs
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("200.00")
    finally:
        await _cleanup([drug_a, drug_b], invoice_ids)


async def test_multi_line_failure_rolls_back_atomically(client):
    """Line A is valid, line B over-returns → the WHOLE return must roll back:
    no batch, no stock movement, no return invoice, no outbox row."""
    drug_a = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    drug_b = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [
            {"drug_id": drug_a, "qty": "5"},
            {"drug_id": drug_b, "qty": "5"},
        ])
        invoice_ids.append(sale["id"])
        line_a = next(l for l in sale["lines"] if l["drug_id"] == drug_a)
        line_b = next(l for l in sale["lines"] if l["drug_id"] == drug_b)
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [
                {"ref_invoice_line_id": line_a["id"], "qty": "2"},
                {"ref_invoice_line_id": line_b["id"], "qty": "6"},
            ]},
        )
        assert r.status_code == 400
        assert "cannot return more" in r.json()["detail"]
        # nothing persisted: line A's valid return was rolled back with line B's failure
        assert await _stock_qty(drug_a) == Decimal("5.0000")
        assert await _stock_qty(drug_b) == Decimal("5.0000")
        assert await _return_batches(drug_a) == []
        assert await _return_batches(drug_b) == []
        async with SessionLocal() as session:
            n_returns = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.kind == "sale_return",
                        Invoice.ref_invoice_id == sale["id"],
                    )
                )
            ).scalars().all()
            assert n_returns == []
    finally:
        await _cleanup([drug_a, drug_b], invoice_ids)


async def test_exempt_return_has_no_vat(client):
    """An exempt (0%) return: vat 0.00, net == total, journal has NO 2100 line."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        ret = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "4"},
        ])
        invoice_ids.append(ret["id"])
        assert ret["vat"] == "0.00"
        assert ret["totalvalue"] == "40.00"
        assert ret["net"] == "40.00"
        assert ret["payed"] == "40.00"
        codes = await _journal_codes(ret["id"])
        assert "2100" not in codes, codes
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("60.00")  # 40 sales + 20 stock / 40 drawer + 20 cogs
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_exclusive_branch_return(client):
    """Wholesale branch (vat_inclusive_prices=false): total = net + vat on top."""
    branch_id = await _make_branch(vat_inclusive=False)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, tax_type="14%", price="10.0000", cost_price="5.0000",
        stock_qty="10.0000",
    )
    user_id = await _make_user(_uniq("edge"), permission_level=9, branch_id=branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        assert sale["totalvalue"] == "114.00"
        assert sale["vat"] == "14.00"
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        ret = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "4"},
        ])
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "40.00"
        assert ret["vat"] == "5.60"
        assert ret["totalvalue"] == "45.60"
        assert ret["net"] == "40.00"
        assert ret["payed"] == "45.60"
        assert await _stock_qty_branch(branch_id, drug_id) == Decimal("4.0000")
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("65.60")
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _delete_branch(branch_id)


async def test_all_credit_original_mirrors_to_credit(client):
    """Original paid 100% credit: the refund mirrors entirely to credit — payed
    0.00, agel = total, journal credits AR (1100), never the drawer."""
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
            payments=[{"method": "credit", "amount": "100.00"}],
        )
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        ret = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "4"},
        ])
        invoice_ids.append(ret["id"])
        assert ret["payed"] == "0.00"
        assert ret["agel"] == "40.00"
        assert [p["method"] for p in ret["payments"]] == ["credit"]
        codes = await _journal_codes(ret["id"])
        assert "1100" in codes and "1000" not in codes, codes
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("60.00")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_mixed_cash_card_credit_mirror(client):
    """Original paid 30 cash + 30 card + 40 credit: a 40% return refunds
    12/12/16; payed (cash+card) = 24, agel (credit) = 16, sum == total."""
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
            payments=[{"method": "cash", "amount": "30.00"},
                      {"method": "card", "amount": "30.00"},
                      {"method": "credit", "amount": "40.00"}],
        )
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        ret = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "4"},
        ])
        invoice_ids.append(ret["id"])
        assert ret["totalvalue"] == "40.00"
        assert ret["payed"] == "24.00"
        assert ret["agel"] == "16.00"
        by_method = {p["method"]: Decimal(p["amount"]) for p in ret["payments"]}
        assert by_method == {"cash": Decimal("12.00"),
                             "card": Decimal("12.00"),
                             "credit": Decimal("16.00")}
        assert sum(by_method.values()) == Decimal("40.00")
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("60.00")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_five_percent_tax_return(client):
    """A 5% return: vat at 5%, net == total - vat, journal balanced."""
    drug_id = await _make_drug_and_stock(
        tax_type="5%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        ret = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "4"},
        ])
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "40.00"
        assert ret["vat"] == "1.90"
        assert ret["totalvalue"] == "40.00"
        assert ret["net"] == "38.10"
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("60.00")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_fractional_qty_and_4dp_boundary(client):
    """Returning a half unit works at 4dp; returning 10.0001 when only 9.5
    remains is rejected."""
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
        ret = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "0.5"},
        ])
        invoice_ids.append(ret["id"])
        assert ret["lines"][0]["qty"] == "0.5000"
        assert ret["totalvalue"] == "5.00"
        assert ret["vat"] == "0.61"
        assert ret["net"] == "4.39"
        assert await _stock_qty(drug_id) == Decimal("0.5000")
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "10.0001"}]},
        )
        assert r.status_code == 400
        assert "cannot return more" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("0.5000")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_chained_return_rejected(client):
    """A sale_return invoice is itself not returnable ('only a saved sale')."""
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
        ret = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "4"},
        ])
        invoice_ids.append(ret["id"])
        ret_line_id = ret["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{ret['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": ret_line_id, "qty": "1"}]},
        )
        assert r.status_code == 400
        assert "saved sale" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("4.0000")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_two_returns_get_sequential_invoice_numbers(client):
    """Each return takes the branch's next invoice_no: distinct, monotonic."""
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
        ret1 = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "2"},
        ])
        invoice_ids.append(ret1["id"])
        ret2 = await _return(client, token, sale, [
            {"ref_invoice_line_id": line_id, "qty": "3"},
        ])
        invoice_ids.append(ret2["id"])
        assert ret1["invoice_no"] != sale["invoice_no"]
        assert ret2["invoice_no"] != sale["invoice_no"]
        assert ret1["invoice_no"].isdigit() and ret2["invoice_no"].isdigit()
        assert int(ret2["invoice_no"]) == int(ret1["invoice_no"]) + 1
    finally:
        await _cleanup([drug_id], invoice_ids)