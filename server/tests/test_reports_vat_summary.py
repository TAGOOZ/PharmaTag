"""S3.5 ملخص ضريبة القيمة المضافة — VAT/tax summary (ticket #27).

The Egyptian monthly return mirror (Form 10 / نموذج 10 ق.ض.ق.م): output
(ضريبة المخرجات) and input (ضريبة المدخلات) sections × rate buckets
(exempt/5%/14%) with net + VAT columns. Direction derives from the document
kind (= the journal source, ADR-0001): sale/sale_return legs are output,
purchase/purchase_return legs are input; returns net NEGATIVE inside their
bucket. Rate splits come from `invoice_lines.tax_type`, never from the chart.
Foot: output − input = صافي الضريبة المستحقة (negative → رصيد دائن).
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import Party

from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)

_SUPPLIERS: list[int] = []
_seq = [0]


async def _make_supplier() -> int:
    _seq[0] += 1
    async with SessionLocal() as session:
        party = Party(
            branch_id=1,
            kind="supplier",
            namee=f"__t27_vat_sup_{_seq[0]}__",
        )
        session.add(party)
        await session.flush()
        _SUPPLIERS.append(party.id)
        await session.commit()
        return party.id


async def _drop_parties() -> None:
    for pid in _SUPPLIERS:
        async with SessionLocal() as session:
            await session.execute(delete(Party).where(Party.id == pid))
            await session.commit()
    _SUPPLIERS.clear()


def _rates_by(body: dict, section: str) -> dict[str, dict]:
    return {row["tax_type"]: row for row in body[section]["rates"]}


async def test_vat_summary_output_section_from_a_taxable_sale(client):
    """A 14% cash sale of 50 gross lands on the OUTPUT side's 14% bucket:
    taxable net 43.86 + VAT 6.14; exempt stays zero; input is empty and the
    net-VAT foot equals the output VAT."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/vat_summary",
            params={"month": "8", "year": "2026"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        assert body["period"]["month"] == 8
        out_14 = _rates_by(body, "output")["14%"]
        assert out_14["net"] == "43.86"
        assert out_14["vat"] == "6.14"
        assert _rates_by(body, "output")["exempt"]["vat"] == "0.00"

        inp = _rates_by(body, "input")
        assert all(row["vat"] == "0.00" for row in inp.values())
        assert body["input"]["total_vat"] == "0.00"

        assert body["output"]["total_vat"] == "6.14"
        assert Decimal(body["net_vat_payable"]) == Decimal("6.14")
        assert body["credit_balance"] is False
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_vat_summary_buckets_returns_negative_and_net_vat_foot(client):
    """Full Form-10 shape: exempt output (medicine sale), a 14% sale whose
    return nets NEGATIVE inside its bucket, input VAT from a purchase and its
    return; the foot nets output − input."""
    drug14 = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("60.0000", "5.0000", "2027-01-01")],
        stock_qty="60.0000",
    )
    drug_exempt = await _make_drug_and_stock(
        tax_type="exempt",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        supplier_id = await _make_supplier()

        # sale 14%: 50 gross → net 43.86 / vat 6.14
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"datee": "2026-08-10", "lines": [{"drug_id": drug14, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])
        # its return: 2 units → −(net 17.54 / vat 2.46)
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return", headers=auth,
            json={"lines": [{"ref_invoice_line_id": sale["lines"][0]["id"], "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        # exempt medicine sale: 100 gross → net 100 / vat 0
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"datee": "2026-08-11", "lines": [{"drug_id": drug_exempt, "qty": "10"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        # purchase 14% @8 × 5 → input net 40 / vat 5.60
        r = await client.post(
            "/api/v1/purchases", headers=auth,
            json={
                "datee": "2026-08-12",
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug14, "qty": "5", "unit_cost": "8.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        purchase = r.json()
        invoice_ids.append(purchase["id"])
        # purchase return of 2 units → −(net 16 / vat 2.24)
        r = await client.post(
            f"/api/v1/purchases/{purchase['id']}/return", headers=auth,
            json={"lines": [{"ref_invoice_line_id": purchase["lines"][0]["id"], "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/vat_summary",
            params={"month": "8", "year": "2026"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        out = _rates_by(body, "output")
        assert out["exempt"]["net"] == "100.00"
        assert out["exempt"]["vat"] == "0.00"
        # 43.86 − 17.54 and 6.14 − 2.46 inside the bucket
        assert out["14%"]["net"] == "26.32"
        assert out["14%"]["vat"] == "3.68"
        assert body["output"]["total_vat"] == "3.68"

        inp = _rates_by(body, "input")
        # 40 − 16 and 5.60 − 2.24 inside the bucket
        assert inp["14%"]["net"] == "24.00"
        assert inp["14%"]["vat"] == "3.36"

        assert Decimal(body["net_vat_payable"]) == Decimal("0.32")
        assert body["credit_balance"] is False
    finally:
        await _cleanup([drug14, drug_exempt], invoice_ids)
        await _drop_parties()


async def test_vat_summary_credit_balance_when_input_exceeds_output(client):
    """A purchase-heavy window leaves input VAT above output: the foot flips
    to a رصيد دائن (credit carried forward)."""
    drug14 = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("60.0000", "5.0000", "2027-01-01")],
        stock_qty="60.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        supplier_id = await _make_supplier()

        # big purchase: input VAT 140 on net 1000
        r = await client.post(
            "/api/v1/purchases", headers=auth,
            json={
                "datee": "2026-08-12",
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug14, "qty": "125", "unit_cost": "8.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/vat_summary",
            params={"month": "8", "year": "2026"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["input"]["total_vat"] == "140.00"
        assert body["output"]["total_vat"] == "0.00"
        assert Decimal(body["net_vat_payable"]) == Decimal("-140.00")
        assert body["credit_balance"] is True
    finally:
        await _cleanup([drug14], invoice_ids)
        await _drop_parties()


async def test_vat_summary_reconciles_to_journal_and_period_totals(client):
    """AC invariants on a mixed window:
    - ΣVAT(lines) per direction == Δ journal(2100) restricted to that
      direction's sources (sale/sale_return credit-norm; purchase/
      purchase_return debit-norm);
    - Σ across rate buckets == period_totals' net VAT sales/purchases."""
    drug14 = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("60.0000", "5.0000", "2027-01-01")],
        stock_qty="60.0000",
    )
    drug_exempt = await _make_drug_and_stock(
        tax_type="exempt",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        supplier_id = await _make_supplier()

        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"datee": "2026-08-10", "lines": [{"drug_id": drug14, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return", headers=auth,
            json={"lines": [{"ref_invoice_line_id": sale["lines"][0]["id"], "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"datee": "2026-08-11", "lines": [{"drug_id": drug_exempt, "qty": "10"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.post(
            "/api/v1/purchases", headers=auth,
            json={
                "datee": "2026-08-12",
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug14, "qty": "6", "unit_cost": "10.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/vat_summary",
            params={"month": "8", "year": "2026"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        async def _delta_2100(sources: tuple[str, ...]) -> Decimal:
            from sqlalchemy import func, select

            from app.models import Account, Journal, JournalLine

            async with SessionLocal() as session:
                dr, cr = (
                    await session.execute(
                        select(
                            func.coalesce(func.sum(JournalLine.debit), 0),
                            func.coalesce(func.sum(JournalLine.credit), 0),
                        )
                        .select_from(JournalLine)
                        .join(Account, Account.id == JournalLine.account_id)
                        .join(Journal, Journal.id == JournalLine.journal_id)
                        .where(
                            Account.code == "2100",
                            JournalLine.branch_id == 1,
                            Journal.source.in_(sources),
                            JournalLine.datee >= date(2026, 8, 1),
                            JournalLine.datee <= date(2026, 8, 31),
                        )
                    )
                ).one()
                return Decimal(dr) - Decimal(cr)

        # AC: ΣVAT(lines) per direction == Δ journal(2100) per direction
        # (output legs are credits → credit-norm delta; input legs debits)
        out_delta = await _delta_2100(("sale", "sale_return"))
        assert Decimal(body["output"]["total_vat"]) == -out_delta
        in_delta = await _delta_2100(("purchase", "purchase_return"))
        assert Decimal(body["input"]["total_vat"]) == in_delta

        # AC: Σ across rates == period_totals net VAT figures
        pt = await client.get(
            "/api/v1/reports/period_totals",
            params={"date_from": "2026-08-01", "date_to": "2026-08-31"},
            headers=auth,
        )
        assert pt.status_code == 200, pt.text
        totals = pt.json()
        assert Decimal(body["output"]["total_vat"]) == Decimal(
            totals["net_vat_sales"]
        )
        assert Decimal(body["input"]["total_vat"]) == Decimal(
            totals["net_vat_purchases"]
        )
    finally:
        await _cleanup([drug14, drug_exempt], invoice_ids)
        await _drop_parties()


async def test_vat_summary_grid_and_queue_guards(client):
    """The Form-10 grid renders with aligned foot; the queue refuses a
    month/year-vs-range mix and out-of-bounds month at enqueue."""
    drug14 = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"datee": "2026-08-10", "lines": [{"drug_id": drug14, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        g = await client.get(
            "/api/v1/reports/vat_summary",
            params={"month": "8", "year": "2026", "format": "grid"},
            headers=auth,
        )
        assert g.status_code == 200, g.text
        grid = g.json()
        assert len(grid["columns"]) == 3
        assert len(grid["foot"]) == 3
        labels = [row[0] for row in grid["rows"]]
        assert any("المخرجات" in label for label in labels)
        assert any("المدخلات" in label for label in labels)

        r = await client.post(
            "/api/v1/reports/vat_summary/print-queue",
            headers=auth,
            json={"params": {"month": "8", "date_from": "2026-08-01"}},
        )
        assert r.status_code == 400, r.text

        r = await client.post(
            "/api/v1/reports/vat_summary/print-queue",
            headers=auth,
            json={"params": {"year": "nope"}},
        )
        assert r.status_code == 400, r.text

        r = await client.post(
            "/api/v1/reports/vat_summary/print-queue",
            headers=auth,
            json={"params": {"month": "8", "year": "2026"}},
        )
        assert r.status_code == 201, r.text

        # unknown param on the new catalog rows still rejected by the dispatcher
        r = await client.get(
            "/api/v1/reports/vat_summary",
            params={"month": "8", "account_code": "2100"},
            headers=auth,
        )
        assert r.status_code == 400, r.text
    finally:
        await _cleanup([drug14], invoice_ids)


async def test_vat_summary_ignores_manual_legs_on_2100(client):
    """ADR-0001 direction rule: a MANUAL journal debiting 2100 is neither
    output nor input — the summary ignores it (while the ledger by account
    still shows the movement)."""
    drug14 = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    tag = f"__t27_vat_manual_{_seq[0] + 1}__"
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"datee": "2026-08-10", "lines": [{"drug_id": drug14, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.post(
            "/api/v1/journals/manual",
            headers=auth,
            json={
                "datee": "2026-08-15",
                "description": tag,
                "lines": [
                    {"account_code": "2100", "debit": "100.00"},
                    {"account_code": "4000", "credit": "100.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text

        rep = await client.get(
            "/api/v1/reports/vat_summary",
            params={"month": "8", "year": "2026"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["output"]["total_vat"] == "6.14"  # manual leg not counted
        assert body["input"]["total_vat"] == "0.00"

        led = await client.get(
            "/api/v1/reports/ledger_account",
            params={"account_code": "2100", "month": "8", "year": "2026"},
            headers=auth,
        )
        assert led.status_code == 200, led.text
        ledger_body = led.json()
        # …but the ledger of the account shows both movements
        assert len(ledger_body["movements"]) == 2
        assert Decimal(ledger_body["debit_total"]) == Decimal("100.00")
        assert Decimal(ledger_body["closing_balance"]) == Decimal("-6.14") + Decimal(
            "100.00"
        )
    finally:
        from tests.manual_journal_test_utils import _cleanup_journals

        await _cleanup_journals(tag)
        await _cleanup([drug14], invoice_ids)


async def test_vat_summary_splits_one_invoices_lines_by_tax_type(client):
    """G06 per-line engine: ONE invoice carrying an exempt medicine line and
    a 14% cosmetics line feeds TWO separate buckets, never blended."""
    drug_exempt = await _make_drug_and_stock(
        tax_type="exempt",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
        stock_qty="20.0000",
    )
    drug14 = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={
                "datee": "2026-08-10",
                "lines": [
                    {"drug_id": drug_exempt, "qty": "10"},
                    {"drug_id": drug14, "qty": "5"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/vat_summary",
            params={"month": "8", "year": "2026"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        out = _rates_by(rep.json(), "output")
        assert out["exempt"]["net"] == "100.00"
        assert out["exempt"]["vat"] == "0.00"
        assert out["14%"]["net"] == "43.86"
        assert out["14%"]["vat"] == "6.14"
    finally:
        await _cleanup([drug_exempt, drug14], invoice_ids)


async def test_vat_summary_defaults_to_the_business_month(client):
    """No params → the current business month (mizan convention); a window
    after all activity carries an EMPTY section set at zero."""
    token = await _login_token(client)
    auth = {"Authorization": f"Bearer {token}"}

    rep = await client.get("/api/v1/reports/vat_summary", headers=auth)
    assert rep.status_code == 200, rep.text
    from app.core.time import business_date

    today = business_date()
    body = rep.json()
    assert body["period"]["month"] == today.month
    assert body["period"]["year"] == today.year

    future = await client.get(
        "/api/v1/reports/vat_summary",
        params={"date_from": "2030-01-01", "date_to": "2030-01-31"},
        headers=auth,
    )
    assert future.status_code == 200, future.text
    fbody = future.json()
    assert fbody["output"]["total_net"] == "0.00"
    assert fbody["net_vat_payable"] == "0.00"
