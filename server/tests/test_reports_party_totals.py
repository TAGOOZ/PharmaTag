"""S3.4 supplier/customer totals by period (ticket #26): RPT-C01/SUP01/02.

إجمالي العملاء والموردين aggregates the party-tagged journal legs on AR
(1100) and AP (2000) over a date range — period debit/credit and the closing
balance per party. The closing balance MUST equal the receivables register
(`/receivables`) for every listed party — that is the ticket's "totals match
balances" acceptance criterion.
"""
from sqlalchemy import delete
from uuid import uuid4

from app.core.db import SessionLocal
from app.core.time import business_date
from app.models import Party

from tests.receivables_test_utils import _cleanup_vouchers
from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


_TAG = f"__t2_s34_pt_{id(dict)}__"


async def _make_party(client, token: str, kind: str) -> int:
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": kind, "namee": f"t2 s34 pt {kind}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _drop_party(party_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == party_id))
        await session.commit()


async def test_party_totals_match_period_activity_and_balances(client):
    """A part-credit sale + receipt to customer X and a part-credit purchase +
    payment to supplier Y show exact period legs; closings equal /receivables;
    a party-less walk-in sale never appears."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    customer_id = None
    supplier_id = None
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        customer_id = await _make_party(client, token, "customer")
        supplier_id = await _make_party(client, token, "supplier")
        today = business_date().isoformat()

        # credit sale to X: 50 gross, paid 20 cash, 30 on credit → AR Dr 30
        s = await client.post(
            "/api/v1/sales", headers=auth,
            json={
                "party_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [
                    {"method": "cash", "amount": "20.00"},
                    {"method": "credit", "amount": "30.00"},
                ],
            },
        )
        assert s.status_code == 201, s.text
        invoice_ids.append(s.json()["id"])

        # walk-in cash sale: no AR line, must not create a party row
        s2 = await client.post(
            "/api/v1/sales", headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert s2.status_code == 201, s2.text
        invoice_ids.append(s2.json()["id"])

        # سند قبض receipt from X: 10 → AR Cr 10
        v = await client.post(
            "/api/v1/receivables/vouchers", headers=auth,
            json={
                "voucher_type": "receipt",
                "party_id": customer_id,
                "datee": today,
                "method": "cash",
                "amount": "10.00",
                "description": _TAG,
            },
        )
        assert v.status_code == 201, v.text

        # credit purchase from Y: 40 net + 5.60 vat, paid 15.60 cash,
        # 30 on credit → AP Cr 30
        p = await client.post(
            "/api/v1/purchases", headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "4.0000"}],
                "payments": [
                    {"method": "cash", "amount": "15.60"},
                    {"method": "credit", "amount": "30.00"},
                ],
            },
        )
        assert p.status_code == 201, p.text
        invoice_ids.append(p.json()["id"])

        # سند صرف payment to Y: 12 → AP Dr 12
        v2 = await client.post(
            "/api/v1/receivables/vouchers", headers=auth,
            json={
                "voucher_type": "payment",
                "party_id": supplier_id,
                "datee": today,
                "method": "cash",
                "amount": "12.00",
                "description": _TAG,
            },
        )
        assert v2.status_code == 201, v2.text

        rep = await client.get(
            "/api/v1/reports/party_totals",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        customers = {row["party_id"]: row for row in body["customers"]}
        assert set(customers) == {customer_id}
        xrow = customers[customer_id]
        assert xrow["namee"] == f"t2 s34 pt customer"
        assert xrow["period_debit"] == "30.00"
        assert xrow["period_credit"] == "10.00"
        assert xrow["closing"] == "20.00"

        suppliers = {row["party_id"]: row for row in body["suppliers"]}
        assert set(suppliers) == {supplier_id}
        yrow = suppliers[supplier_id]
        assert yrow["period_credit"] == "30.00"
        assert yrow["period_debit"] == "12.00"
        assert yrow["closing"] == "18.00"

        # AC: totals match balances — closing equals the receivables register
        rec = await client.get(
            "/api/v1/receivables", headers=auth
        )
        assert rec.status_code == 200, rec.text
        by_party = {
            row["party_id"]: row["balance"] for row in rec.json()["receivables"]
        }
        assert by_party[customer_id] == xrow["closing"]
    finally:
        await _cleanup_vouchers(_TAG)
        await _cleanup([drug_id], invoice_ids)
        for party_id in (customer_id, supplier_id):
            if party_id:
                await _drop_party(party_id)


async def test_party_totals_includes_pinned_receivable_account(client):
    """A customer pinned to a non-default AR account (receivable_account_id,
    e.g. code 1199) must show the same closing here as in /receivables — the
    register unions the pin into its account set, so the report must too."""
    from decimal import Decimal

    from app.models import Account, Journal, JournalLine

    async with SessionLocal() as session:
        tag = uuid4().hex[:12]
        party = Party(
            branch_id=1,
            kind="customer",
            namee=f"__t2_s34_pin_{tag}__",
            randomid=f"__t2_s34_pin_pty_{tag}__",
        )
        session.add(party)
        await session.flush()
        account = Account(
            branch_id=1,
            code=f"1199_{tag}",
            name_ar="t2 s34 pinned ar",
            type="asset",
            is_active=True,
        )
        session.add(account)
        await session.flush()
        party.receivable_account_id = account.id
        journal = Journal(
            branch_id=1,
            datee=business_date(),
            entry_no=999_000_000 + int(tag[:4], 16),
            description=f"pinned AR debt {tag}",
            source="manual",
            status="posted",
        )
        session.add(journal)
        await session.flush()
        session.add(
            JournalLine(
                journal_id=journal.id,
                branch_id=1,
                account_id=account.id,
                debit=Decimal("30.00"),
                credit=Decimal("0"),
                contra_party_id=party.id,
                datee=business_date(),
                month=business_date().month,
                year=business_date().year,
                creditdebit="debit",
            )
        )
        await session.commit()
        party_id, account_id, journal_id = (
            party.id,
            account.id,
            journal.id,
        )

    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        today = business_date().isoformat()

        rep = await client.get(
            "/api/v1/reports/party_totals",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        customers = {row["party_id"]: row for row in rep.json()["customers"]}
        assert customers[party_id]["period_debit"] == "30.00"
        assert customers[party_id]["closing"] == "30.00"

        rec = await client.get("/api/v1/receivables", headers=auth)
        by_id = {x["party_id"]: x for x in rec.json()["receivables"]}
        assert rec.json()["receivables"], "register empty"
        assert customers[party_id]["closing"] == by_id[party_id]["balance"]
    finally:
        async with SessionLocal() as session:
            p = await session.get(Party, party_id)
            if p is not None:
                p.receivable_account_id = None
            await session.execute(
                delete(JournalLine).where(JournalLine.journal_id == journal_id)
            )
            await session.execute(delete(Journal).where(Journal.id == journal_id))
            if p is not None:
                await session.delete(p)
            await session.commit()
            await session.execute(
                delete(Account).where(Account.id == account_id)
            )
            await session.commit()


async def test_party_totals_window_vs_all_time_closing(client):
    """The headline identity needs distinguishing power: a day-1 credit sale
    outside the window must NOT appear in period legs but MUST stay in the
    closing; a day-2 receipt shows only in the window's credit."""
    from datetime import timedelta

    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    customer_id = None
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        customer_id = await _make_party(client, token, "customer")
        yesterday = (business_date() - timedelta(days=1)).isoformat()
        today = business_date().isoformat()

        # day 1: full-credit sale → AR Dr 30 tagged X
        s = await client.post(
            "/api/v1/sales", headers=auth,
            json={
                "party_id": customer_id,
                "datee": yesterday,
                "lines": [{"drug_id": drug_id, "qty": "3"}],
                "payments": [{"method": "credit", "amount": "30.00"}],
            },
        )
        assert s.status_code == 201, s.text
        invoice_ids.append(s.json()["id"])

        # day 2: سند قبض receipt 10 → AR Cr 10 tagged X
        v = await client.post(
            "/api/v1/receivables/vouchers", headers=auth,
            json={
                "voucher_type": "receipt",
                "party_id": customer_id,
                "datee": today,
                "method": "cash",
                "amount": "10.00",
                "description": "__t2_s34_win__",
            },
        )
        assert v.status_code == 201, v.text

        rep = await client.get(
            "/api/v1/reports/party_totals",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        xrow = next(
            r
            for r in rep.json()["customers"]
            if r["party_id"] == customer_id
        )
        assert xrow["period_debit"] == "0.00"
        assert xrow["period_credit"] == "10.00"
        assert xrow["closing"] == "20.00"

        # window covering both days: period legs == the full history
        both = await client.get(
            "/api/v1/reports/party_totals",
            params={"date_from": yesterday, "date_to": today},
            headers=auth,
        )
        xboth = next(
            r
            for r in both.json()["customers"]
            if r["party_id"] == customer_id
        )
        assert xboth["period_debit"] == "30.00"
        assert xboth["closing"] == "20.00"
    finally:
        await _cleanup_vouchers("__t2_s34_win__")
        await _cleanup([drug_id], invoice_ids)
        if customer_id:
            await _drop_party(customer_id)
