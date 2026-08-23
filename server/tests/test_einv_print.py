"""S4.1 tax-document print templates (ticket #28 AC4): ضريبية / مبسطة /
أجل / مرتجع render via the print_html pattern with QR data-URI, seller
RIN/branch block, internal invoice_no + counter and VAT breakdown by rate."""
import re

from app.einvoicing.chain import verify_chain  # noqa: F401  (context import cost)
from tests.einv_test_utils import (
    RIN,
    _clear_rin,
    _make_tax_party,
    _make_user,
    _set_rin,
    _uniq,
)
from tests.sales_test_utils import _token_for
from tests.returns_test_utils import (
    _make_branch,
    _make_drug_and_stock_branch,
)
from tests.test_einv_issue import _cleanup


def _img_srcs(html: str) -> list[str]:
    return re.findall(r'src="([^"]+)"', html)


async def _sale(client, token: str, drug_id: int, *, party_id=None, payments=None):
    body: dict = {"lines": [{"drug_id": drug_id, "qty": "2"}]}
    if party_id is not None:
        body["party_id"] = party_id
    if payments is not None:
        body["payments"] = payments
    r = await client.post(
        "/api/v1/sales",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _print(client, token: str, invoice_id: int):
    return await client.get(
        f"/api/v1/sales/{invoice_id}/tax-document/print",
        headers={"Authorization": f"Bearer {token}"},
    )


async def test_all_four_variants_render_with_qr_rin_and_vat_breakdown(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug14 = await _make_drug_and_stock_branch(
        branch_id, tax_type="14%", price="100.0000", stock_qty="40.0000"
    )
    drug5 = await _make_drug_and_stock_branch(
        branch_id, tax_type="5%", price="50.0000", stock_qty="40.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    rin_party = await _make_tax_party(branch_id, rin="300123456")
    plain_party = await _make_tax_party(branch_id, rin=None)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)

        cash_sale = await _sale(client, token, drug14)
        invoice_ids.append(cash_sale["id"])
        r_simplified = await _print(client, token, cash_sale["id"])
        assert r_simplified.status_code == 200
        html = r_simplified.text
        assert "فاتورة مبسطة" in html
        assert "فارما تاج" in html  # brand header
        assert RIN in html  # seller RIN block prints from app_config eta.rin
        assert cash_sale["invoice_no"] in html
        assert "السجل الضريبي" in html  # the labelled RIN row
        imgs = [s for s in _img_srcs(html) if s.startswith("data:image/png;base64,")]
        assert len(imgs) == 1  # the QR
        assert 'dir="rtl"' in html
        # VAT breakdown by rate present (14% line)
        assert "14%" in html
        # submission status echo (offline rows stay pending)
        assert "معلقة" in html or "pending" in html

        credit_rin = await _sale(
            client,
            token,
            drug14,
            party_id=rin_party,
            payments=[{"method": "credit", "amount": "200.00"}],
        )
        invoice_ids.append(credit_rin["id"])
        html_b2b = (await _print(client, token, credit_rin["id"])).text
        assert "فاتورة ضريبية" in html_b2b
        assert "300123456" in html_b2b  # buyer registration number printed
        assert "data:image/png;base64," in html_b2b

        credit_plain = await _sale(
            client,
            token,
            drug5,
            party_id=plain_party,
            payments=[{"method": "credit", "amount": "100.00"}],
        )
        invoice_ids.append(credit_plain["id"])
        html_agel = (await _print(client, token, credit_plain["id"])).text
        assert "فاتورة أجل" in html_agel
        assert "5%" in html_agel  # mixed-rate VAT breakdown renders per rate

        # a return prints the مرتجع variant referencing its original
        line_id = cash_sale["lines"][0]["id"]
        r_ret = await client.post(
            f"/api/v1/sales/{cash_sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
        )
        assert r_ret.status_code == 201, r_ret.text
        ret = r_ret.json()
        invoice_ids.append(ret["id"])
        html_ret = (await _print(client, token, ret["id"])).text
        assert "فاتورة مرتجع" in html_ret
        assert ret["invoice_no"] in html_ret
        # the return references the invoice it corrects
        assert "مرتجع للفاتورة" in html_ret
        assert cash_sale["invoice_no"] in html_ret
        assert "data:image/png;base64," in html_ret
    finally:
        await _clear_rin()
        await _cleanup([drug14, drug5], invoice_ids, branch_id)


async def test_print_endpoint_gates_and_errors(client):
    """No auth → 401; unknown invoice → 404; other-branch invoice → 404."""
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("u"), branch_id)
    other_branch = await _make_branch(vat_inclusive=True)
    try:
        token = _token_for(user_id, branch_id)
        anon = await client.get("/api/v1/sales/999999/tax-document/print")
        assert anon.status_code == 401

        not_found = await _print(client, token, 987654321)
        assert not_found.status_code == 404
    finally:
        from app.core.db import SessionLocal

        from app.models import Branch as B

        async with SessionLocal() as s:
            b = await s.get(B, other_branch)
            if b is not None:
                await s.delete(b)
                await s.commit()
        await _cleanup([drug_id], [], branch_id)


async def test_vat_breakdown_reconciles_to_invoice_totals(client):
    """The template's per-rate breakdown sums to the invoice VAT column."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug14 = await _make_drug_and_stock_branch(
        branch_id, tax_type="14%", price="114.0000", stock_qty="30.0000"
    )
    drug_exempt = await _make_drug_and_stock_branch(
        branch_id, tax_type="exempt", price="20.0000", stock_qty="30.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        sale = await _sale(
            client,
            token,
            drug14,
            payments=[{"method": "cash", "amount": "228.00"}],
        )
        invoice_ids.append(sale["id"])

        sale2_body: dict = {"lines": [{"drug_id": drug_exempt, "qty": "1"}]}
        r2 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json=sale2_body,
        )
        assert r2.status_code == 201, r2.text
        sale2 = r2.json()
        invoice_ids.append(sale2["id"])

        html = (await _print(client, token, sale2["id"])).text
        assert "معفاة / 0%" in html  # exempt lines render their own breakdown row
    finally:
        await _clear_rin()
        await _cleanup([drug14, drug_exempt], invoice_ids, branch_id)


async def test_vat_breakdown_on_exclusive_vat_branch_keeps_full_net_base(client):
    """Exclusive-VAT pricing (wholesale): line_total is ALREADY ex-VAT, so the
    breakdown's صافي must equal it — subtracting VAT again understates the
    taxable base (100.00 net / 14.00 VAT, never 86.00)."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=False)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, tax_type="14%", price="100.0000", stock_qty="10.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        sale = await _sale(
            client,
            token,
            drug_id,
            payments=[{"method": "cash", "amount": "228.00"}],
        )
        assert sale["subtotal"] == "200.00"
        assert sale["vat"] == "28.00"
        assert sale["totalvalue"] == "228.00"
        invoice_ids.append(sale["id"])

        html = (await _print(client, token, sale["id"])).text
        assert "صافي 200.00" in html  # full ex-VAT base, not 172.00
        assert "صافي 172.00" not in html
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)
