"""S3.5 دفتر الأستاذ لحساب — ledger by account (ticket #27).

ONE chart account over ONE period: opening balance → chronological journal
movements with a running balance → closing. Built purely from `journal_lines`
(the statements/mizan source), aggregated across every account row a code maps
to (own-branch + inherited branch-1 — the S2.3 code-shadowing rule). AR/AP
movements carry طرف (the tagged contra party).
"""
from datetime import date

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import Party

from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)

_SALE_DAY = "2026-08-10"

_SUPPLIERS: list[int] = []
_seq = [0]


async def _make_supplier() -> int:
    _seq[0] += 1
    async with SessionLocal() as session:
        party = Party(
            branch_id=1,
            kind="supplier",
            namee=f"__t27_led_sup_{_seq[0]}__",
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


async def _drop_party(party_id: int | None) -> None:
    if not party_id:
        return
    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == party_id))
        await session.commit()


async def test_ledger_account_renders_vat_movements_with_running_balance(client):
    """A 14% cash sale of 50 gross posts Cr 2100 6.14; the ledger of 2100 for
    that month shows the movement chronologically with a signed running
    balance (debit − credit) and closing == opening + Σmovements."""
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
                "datee": _SALE_DAY,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/ledger_account",
            params={"account_code": "2100", "month": "8", "year": "2026"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        assert body["account"]["code"] == "2100"
        assert body["period"]["month"] == 8
        assert body["period"]["year"] == 2026
        assert body["opening_balance"] == "0.00"

        assert len(body["movements"]) == 1
        mv = body["movements"][0]
        assert mv["datee"] == _SALE_DAY
        assert mv["debit"] == "0.00"
        assert mv["credit"] == "6.14"
        assert mv["running_balance"] == "-6.14"
        assert mv["party"] is None

        assert body["credit_total"] == "6.14"
        assert body["closing_balance"] == "-6.14"
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_ledger_account_window_opening_and_running_balance(client):
    """A day-1 sale outside the window must NOT appear as a movement but MUST
    set the opening; day-2/day-3 movements run chronologically and the closing
    equals opening + Σmovements."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        # day 1: cash sale 20 gross → Cr2100 2.46
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"datee": "2026-08-01", "lines": [{"drug_id": drug_id, "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        # day 2: cash sale 100 gross → Cr2100 12.28
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"datee": "2026-08-02", "lines": [{"drug_id": drug_id, "qty": "10"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        # day 3: purchase with input VAT 14% of 50 net = Dr2100 7.00
        r = await client.post(
            "/api/v1/purchases",
            headers=auth,
            json={
                "datee": "2026-08-03",
                "supplier_id": await _make_supplier(),
                "lines": [{"drug_id": drug_id, "qty": "5", "unit_cost": "10.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/ledger_account",
            params={"account_code": "2100", "date_from": "2026-08-02", "date_to": "2026-08-31"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        assert body["period"]["month"] is None
        assert body["period"]["date_from"] == "2026-08-02"
        assert body["opening_balance"] == "-2.46"

        moves = body["movements"]
        assert [m["datee"] for m in moves] == ["2026-08-02", "2026-08-03"]
        assert moves[0]["credit"] == "12.28"
        assert moves[0]["running_balance"] == "-14.74"
        assert moves[1]["debit"] == "7.00"
        assert moves[1]["running_balance"] == "-7.74"

        assert body["debit_total"] == "7.00"
        assert body["credit_total"] == "12.28"
        assert body["closing_balance"] == "-7.74"
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _drop_parties()


async def test_ledger_account_ar_rows_carry_contra_party(client):
    """A credit sale to customer X lands Dr 1100 tagged X; the receipt that
    follows credits 1100 also tagged X — both rows show طرف in the ledger."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
        stock_qty="20.0000",
    )
    customer_id = None
    invoice_ids: list[int] = []
    voucher_desc = f"__t27_led_rcpt_{_seq[0] + 1}__"
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/parties",
            headers=auth,
            json={"kind": "customer", "namee": "__t27_led_cust__"},
        )
        assert r.status_code == 201, r.text
        customer_id = r.json()["id"]

        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={
                "datee": "2026-08-10",
                "party_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [{"method": "credit", "amount": "50.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers=auth,
            json={
                "voucher_type": "receipt",
                "party_id": customer_id,
                "datee": "2026-08-11",
                "method": "cash",
                "amount": "20.00",
                "description": voucher_desc,
            },
        )
        assert r.status_code == 201, r.text

        rep = await client.get(
            "/api/v1/reports/ledger_account",
            params={"account_code": "1100", "month": "8", "year": "2026"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        moves = rep.json()["movements"]
        assert len(moves) == 2
        assert all(m["party"] == "__t27_led_cust__" for m in moves)
        assert moves[0]["debit"] == "50.00"
        assert moves[0]["running_balance"] == "50.00"
        assert moves[1]["credit"] == "20.00"
        assert moves[1]["running_balance"] == "30.00"
        assert rep.json()["closing_balance"] == "30.00"
    finally:
        from tests.receivables_test_utils import _cleanup_vouchers

        await _cleanup_vouchers(voucher_desc)
        await _cleanup([drug_id], invoice_ids)
        await _drop_party(customer_id)


async def test_ledger_closing_reconciles_to_trial_balance(client):
    """AC: for the SAME window, ledger_account.closing == the ميزان's
    closing_balance for every chart code with activity — sale, return and
    purchase documents included."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("60.0000", "5.0000", "2027-01-01")],
        stock_qty="60.0000",
    )
    customer_id = None
    supplier_id = None
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/parties",
            headers=auth,
            json={"kind": "customer", "namee": "__t27_rec_cust__"},
        )
        customer_id = r.json()["id"]
        r = await client.post(
            "/api/v1/parties",
            headers=auth,
            json={"kind": "supplier", "namee": "__t27_rec_sup__"},
        )
        supplier_id = r.json()["id"]

        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={
                "datee": "2026-08-10",
                "party_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "6"}],
                "payments": [
                    {"method": "cash", "amount": "30.00"},
                    {"method": "credit", "amount": "30.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        sale_id = r.json()["id"]
        invoice_ids.append(sale_id)
        sale_lines = r.json()["lines"]

        r = await client.post(
            f"/api/v1/sales/{sale_id}/return",
            headers=auth,
            json={"lines": [{"ref_invoice_line_id": sale_lines[0]["id"], "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.post(
            "/api/v1/purchases",
            headers=auth,
            json={
                "datee": "2026-08-12",
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "8", "unit_cost": "5.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        tb = await client.get(
            "/api/v1/accounts/trial-balance",
            params={"month": "8", "year": "2026"},
            headers=auth,
        )
        assert tb.status_code == 200, tb.text
        by_code = {row["code"]: row for row in tb.json()["accounts"]}

        checked = 0
        for code in ("1000", "1100", "1200", "2000", "2100", "4000", "6000"):
            rep = await client.get(
                "/api/v1/reports/ledger_account",
                params={"account_code": code, "month": "8", "year": "2026"},
                headers=auth,
            )
            assert rep.status_code == 200, rep.text
            body = rep.json()
            # opening + Σmovements == closing holds on the page itself
            from decimal import Decimal

            moves = sum(
                (Decimal(m["debit"]) - Decimal(m["credit"]))
                for m in body["movements"]
            )
            assert (
                Decimal(body["opening_balance"]) + moves
                == Decimal(body["closing_balance"])
            ), code
            assert body["closing_balance"] == by_code[code]["closing_balance"], code
            assert body["debit_total"] == by_code[code]["debit"], code
            assert body["credit_total"] == by_code[code]["credit"], code
            checked += 1
        assert checked == 7
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _drop_party(customer_id)
        await _drop_party(supplier_id)


async def test_ledger_account_param_guards(client):
    """Unknown chart code → 404; missing or malformed account_code,
    month/year mixed with a range, and an inverted range → 400 — never a
    silent empty page."""
    token = await _login_token(client)
    auth = {"Authorization": f"Bearer {token}"}

    r = await client.get(
        "/api/v1/reports/ledger_account",
        params={"account_code": "9999", "month": "8", "year": "2026"},
        headers=auth,
    )
    assert r.status_code == 404, r.text

    r = await client.get(
        "/api/v1/reports/ledger_account",
        params={"month": "8", "year": "2026"},
        headers=auth,
    )
    assert r.status_code == 400, r.text

    r = await client.get(
        "/api/v1/reports/ledger_account",
        params={"account_code": "2100; DROP TABLE x", "month": "8", "year": "2026"},
        headers=auth,
    )
    assert r.status_code == 400, r.text

    r = await client.get(
        "/api/v1/reports/ledger_account",
        params={
            "account_code": "2100",
            "month": "8",
            "date_from": "2026-08-01",
        },
        headers=auth,
    )
    assert r.status_code == 400, r.text

    r = await client.get(
        "/api/v1/reports/ledger_account",
        params={
            "account_code": "2100",
            "date_from": "2026-08-31",
            "date_to": "2026-08-01",
        },
        headers=auth,
    )
    assert r.status_code == 400, r.text


async def test_ledger_account_queue_and_grid_render(client):
    """The queue validates at enqueue (missing/malformed account_code and
    month-vs-range mixes never queue) and a valid job's report also renders
    as a well-formed grid."""
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
            json={"datee": "2026-08-10", "lines": [{"drug_id": drug_id, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        # missing required param → no queue
        r = await client.post(
            "/api/v1/reports/ledger_account/print-queue",
            headers=auth,
            json={"params": {"month": "8", "year": "2026"}},
        )
        assert r.status_code == 400, r.text

        # malformed code → no queue
        r = await client.post(
            "/api/v1/reports/ledger_account/print-queue",
            headers=auth,
            json={"params": {"account_code": "2100 drop", "month": "8"}},
        )
        assert r.status_code == 400, r.text

        # month mixed with a range → no queue
        r = await client.post(
            "/api/v1/reports/ledger_account/print-queue",
            headers=auth,
            json={"params": {"account_code": "2100", "month": "8", "date_from": "2026-08-01"}},
        )
        assert r.status_code == 400, r.text

        # out-of-bounds month → no queue
        r = await client.post(
            "/api/v1/reports/ledger_account/print-queue",
            headers=auth,
            json={"params": {"account_code": "2100", "month": "13"}},
        )
        assert r.status_code == 400, r.text

        # a valid snapshot queues fine
        r = await client.post(
            "/api/v1/reports/ledger_account/print-queue",
            headers=auth,
            json={"params": {"account_code": "2100", "month": "8", "year": "2026"}},
        )
        assert r.status_code == 201, r.text
        job = r.json()
        assert job["params"] == {"account_code": "2100", "month": "8", "year": "2026"}

        # grid render: foot aligns with columns, rows carry the movement
        g = await client.get(
            "/api/v1/reports/ledger_account",
            params={
                "account_code": "2100",
                "month": "8",
                "year": "2026",
                "format": "grid",
            },
            headers=auth,
        )
        assert g.status_code == 200, g.text
        grid = g.json()
        assert len(grid["foot"]) == len(grid["columns"]) == 7
        assert any("6.14" in row for row in grid["rows"])
        assert grid["foot"][-1] == "-6.14"
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_ledger_account_opening_only_window_and_month_default(client):
    """A window AFTER all activity shows the carried opening with no
    movements; omitting `year` defaults to the current business year."""
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
            json={"datee": "2026-08-10", "lines": [{"drug_id": drug_id, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        after = await client.get(
            "/api/v1/reports/ledger_account",
            params={
                "account_code": "2100",
                "date_from": "2026-09-01",
                "date_to": "2026-09-30",
            },
            headers=auth,
        )
        assert after.status_code == 200, after.text
        body = after.json()
        assert body["movements"] == []
        assert body["opening_balance"] == "-6.14"
        assert body["closing_balance"] == "-6.14"

        # month without year → current business year supplies the year
        from app.core.time import business_date

        r = await client.get(
            "/api/v1/reports/ledger_account",
            params={"account_code": "2100", "month": "8"},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        assert r.json()["period"]["year"] == business_date().year
    finally:
        await _cleanup([drug_id], invoice_ids)
