"""S3.2 money reports reconcile against the journal (ticket #24).

The reports read invoices/drawer movements; the ledger of record is
`journal_lines`. These tests drive real documents through the API (cash and
card sales, a cash sale return, a cash-paid purchase) and then aggregate
`journal_lines` directly, asserting every money-report figure equals its
journal identity:

- day_profit.net_revenue  == Δ4000 (credit − debit)
- day_profit.cogs         == Δ6000 (debit − credit)
- day_profit.vat_sales    == Δ2100 over sale/sale_return sources
- day_profit.net_profit   == Δ4000 − Δ6000 − Δ5900 (document-only window)
- day_totals drawer-in    == ΣDr(1000, source=sale); drawer-out == ΣCr(1000,
  source=sale_return) — payed is cash+card and credit never touches the drawer
- period_totals gross     == the document's own debit+credit legs
- drawer_handover roll-up == ΣDr(1000, source=sale) too
"""
import os
from datetime import date

from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.models import Account, Journal, JournalLine, Party

from tests.reports_test_utils import _cleanup, _login_token, _make_drug_and_stock

D1, D2, D3 = "2026-01-06", "2026-01-07", "2026-01-08"

_seq = [0]


async def _make_supplier() -> int:
    _seq[0] += 1
    async with SessionLocal() as session:
        party = Party(
            branch_id=1,
            kind="supplier",
            namee=f"__t2_rec_{os.getpid()}_sup_{_seq[0]}__",
        )
        session.add(party)
        await session.flush()
        party_id = party.id
        await session.commit()
        return party_id


async def _drop_supplier(party_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == party_id))
        await session.commit()


async def _journal_totals(
    code: str, sources: tuple[str, ...] = ()
) -> dict[str, str]:
    """Σdebit/Σcredit on an account code over the test window (optionally
    restricted to journal sources)."""
    async with SessionLocal() as session:
        where = [
            Account.code == code,
            JournalLine.branch_id == 1,
            JournalLine.datee >= date.fromisoformat(D1),
            JournalLine.datee <= date.fromisoformat(D3),
        ]
        if sources:
            where.append(Journal.source.in_(sources))
        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(JournalLine.debit), 0),
                    func.coalesce(func.sum(JournalLine.credit), 0),
                )
                .join(Account, Account.id == JournalLine.account_id)
                .join(Journal, Journal.id == JournalLine.journal_id)
                .where(*where)
            )
        ).one()
        return {"debit": f"{row[0]:.2f}", "credit": f"{row[1]:.2f}"}


def _delta(totals: dict[str, str], side: str) -> str:
    """The account's natural-side net: debit-norm or credit-norm."""
    from decimal import Decimal

    if side == "debit":
        return str(Decimal(totals["debit"]) - Decimal(totals["credit"]))
    return str(Decimal(totals["credit"]) - Decimal(totals["debit"]))


async def test_money_reports_reconcile_against_the_journal(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}

        # D1: cash sale of 12 → Dr1000 120 / Cr4000 net / Cr2100 vat / COGS pair
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "12"}], "datee": D1},
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])

        # D2: card sale of 5 + cash refund of 4 units off the D1 sale
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [{"method": "card", "amount": "50.00"}],
                "datee": D2,
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers=auth,
            json={
                "lines": [
                    {"ref_invoice_line_id": sale["lines"][0]["id"], "qty": "4"}
                ]
            },
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])
        assert ret["payed"] == "40.00"

        # D3: cash-paid purchase of 10 @ 10 → Dr1200 100 / Dr2100 14 / Cr1000 114
        r = await client.post(
            "/api/v1/purchases",
            headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "datee": D3,
            },
        )
        assert r.status_code == 201, r.text
        purchase = r.json()
        invoice_ids.append(purchase["id"])

        window = {"date_from": D1, "date_to": D3}

        # --- day_profit vs the journal -----------------------------------
        rep = await client.get(
            "/api/v1/reports/day-profit", params=window, headers=auth
        )
        assert rep.status_code == 200, rep.text
        profit = rep.json()

        sales_4000 = await _journal_totals(
            "4000", sources=("sale", "sale_return")
        )
        assert profit["net_revenue"] == _delta(sales_4000, "credit")

        cogs_6000 = await _journal_totals(
            "6000", sources=("sale", "sale_return")
        )
        assert profit["cogs"] == _delta(cogs_6000, "debit")

        vat_2100 = await _journal_totals("2100", sources=("sale", "sale_return"))
        assert profit["vat_sales"] == _delta(vat_2100, "credit")

        corr_5900 = await _journal_totals("5900")
        from decimal import Decimal

        expected_np = (
            Decimal(_delta(sales_4000, "credit"))
            - Decimal(_delta(cogs_6000, "debit"))
            - Decimal(_delta(corr_5900, "debit"))
        )
        assert profit["net_profit"] == f"{expected_np:.2f}"

        # --- day_totals drawer columns vs the cash account ---------------
        rep = await client.get(
            "/api/v1/reports/day_totals", params=window, headers=auth
        )
        assert rep.status_code == 200, rep.text
        totals = rep.json()["totals"]

        drawer_sale = await _journal_totals("1000", sources=("sale",))
        drawer_ret = await _journal_totals("1000", sources=("sale_return",))

        cash_in = Decimal(totals["cash_sales"]) + Decimal(totals["network_sales"])
        assert cash_in == Decimal(drawer_sale["debit"])
        cash_out = Decimal(totals["cash_returns"]) + Decimal(
            totals["network_returns"]
        )
        assert cash_out == Decimal(drawer_ret["credit"])
        # the purchases column is the invoice gross: stock + input-VAT debits
        stock_1200 = await _journal_totals("1200", sources=("purchase",))
        pur_vat_2100 = await _journal_totals("2100", sources=("purchase",))
        assert Decimal(totals["purchases"]) == Decimal(stock_1200["debit"]) + Decimal(
            pur_vat_2100["debit"]
        )

        # --- period_totals gross legs vs the journal ---------------------
        rep = await client.get(
            "/api/v1/reports/period_totals", params=window, headers=auth
        )
        assert rep.status_code == 200, rep.text
        kinds = rep.json()["kinds"]

        ar_1100 = await _journal_totals("1100", sources=("sale",))
        sale_gross = Decimal(drawer_sale["debit"]) + Decimal(ar_1100["debit"])
        assert Decimal(kinds["sale"]["total"]) == sale_gross

        assert Decimal(kinds["purchase"]["total"]) == Decimal(stock_1200["debit"]) + Decimal(pur_vat_2100["debit"])

        # --- drawer_handover rolls up to the same cash account -----------
        rep = await client.get(
            "/api/v1/reports/drawer-handover", params=window, headers=auth
        )
        assert rep.status_code == 200, rep.text
        handover = rep.json()["totals"]
        assert Decimal(handover["cash_sales_in"]) + Decimal(
            handover["card_sales_in"]
        ) == Decimal(drawer_sale["debit"])
        assert Decimal(handover["returns_out"]) + Decimal(
            handover["card_returns_out"]
        ) == Decimal(drawer_ret["credit"])
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _drop_supplier(supplier_id)
