"""S2.4 settlements (سند قبض / سند صرف) + receivables tests (issue #19).

A settlement voucher posts one balanced journal (source `settlement`) through
the shared engine, records the drawer movement, and updates the party's AR/AP
ledger: a receipt (قبض) credits the customer's AR via the drawer; a payment
(صرف) debits the supplier's AP via the drawer. Reversals are A07-style (a fresh
opposite journal, one-shot). The receivables register mirrors the payables view
for the AR side and the credit-sale builder enforces the party's credit limit.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    Account,
    AuditLog,
    Balance,
    BranchStock,
    DrawerMovement,
    Drug,
    Journal,
    JournalLine,
    Party,
    SettlementVoucher,
    StockBatch,
)
from tests.drawer_test_utils import _cleanup_drawer, _close_day, _mark_closed
from tests.receivables_test_utils import (
    _cleanup_party,
    _cleanup_vouchers,
    _credit_sale,
    _delete_other_branch,
    _delete_users,
    _login_token,
    _make_customer,
    _make_drug_and_stock,
    _make_other_branch,
    _make_supplier,
    _make_user,
    _token_for,
    _uniq,
    _uniq_id,
    _voucher,
    _voucher_date,
)
from tests.sales_test_utils import _cleanup as _cleanup_sale

BRANCH_ID = 1


async def _statement(client, token, party_id: int, datee: str) -> dict:
    d = date.fromisoformat(datee)
    r = await client.get(
        f"/api/v1/parties/{party_id}/statement?month={d.month}&year={d.year}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _last_voucher_id() -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(SettlementVoucher.id).order_by(SettlementVoucher.id.desc()).limit(1)
            )
        ).scalar_one()


async def _journal_of(voucher_id: int) -> Journal:
    async with SessionLocal() as session:
        voucher = await session.get(SettlementVoucher, voucher_id)
        return await session.get(Journal, voucher.journal_id)


async def test_receipt_voucher_posts_balanced_journal_and_reduces_statement(client):
    """A سند قبض (receipt) against a credit-sale customer: one balanced journal
    (Dr 1000 / Cr 1100, source settlement), the cash drawer movement, and the
    statement closing drops from 50.00 to 20.00."""
    datee = _voucher_date(0)
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    voucher_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee=datee
        )
        invoice_ids.append(sale["id"])

        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "voucher_type": "receipt",
                "party_id": customer_id,
                "datee": datee,
                "method": "cash",
                "amount": "30.00",
                "description": _uniq("rec"),
            },
        )
        assert r.status_code == 201, r.text
        v = r.json()
        voucher_ids.append(v["id"])
        assert v["voucher_no"] >= 1
        assert v["voucher_type"] == "receipt"
        assert v["method"] == "cash"
        assert v["amount"] == "30.00"
        assert v["party"]["id"] == customer_id
        assert v["reverses_voucher_id"] is None

        journal = await _journal_of(v["id"])
        assert journal.source == "settlement"
        assert journal.status == "posted"
        assert "سند قبض" in journal.description
        lines = await session_lines(journal.id)
        assert sum(Decimal(l.debit) for l in lines) == sum(
            Decimal(l.credit) for l in lines
        )
        accounts = await session_accounts(lines)
        # Dr 1000 / Cr 1100, the AR credit tagged to the customer
        drawer_line = next(l for l in lines if accounts[l.account_id].code == "1000")
        ar_line = next(l for l in lines if accounts[l.account_id].code == "1100")
        assert Decimal(drawer_line.debit) == Decimal("30.00")
        assert Decimal(ar_line.credit) == Decimal("30.00")
        assert ar_line.contra_party_id == customer_id

        st = await _statement(client, token, customer_id, datee)
        assert st["closing_balance"] == "20.00"
        assert st["credit_total"] == "30.00"

        rows = await movement_rows(datee)
        assert any(
            m.reason == "customer_settlement"
            and m.direction == "in"
            and m.method == "cash"
            and Decimal(m.amount) == Decimal("30.00")
            for m in rows
        )
    finally:
        await _cleanup_vouchers("rec")
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_payment_voucher_pays_down_supplier_payable(client):
    """A سند صرف (payment voucher) against a credit-purchase supplier: balanced
    journal (Dr 2000 / Cr 1000, source settlement), the network drawer movement
    out, and the supplier statement closing drops from 114.00 to 57.00."""
    datee = _voucher_date(1)
    drug_id = await _make_drug_for_purchase()
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    voucher_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "datee": datee,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        v = await _voucher(
            client, token,
            voucher_type="payment",
            party_id=supplier_id,
            datee=datee,
            amount="57.00",
            method="network",
            description=_uniq("pay"),
        )
        voucher_ids.append(v["id"])
        assert v["voucher_no"] >= 1
        assert v["method"] == "network"

        journal = await _journal_of(v["id"])
        assert "سند صرف" in journal.description
        lines = await session_lines(journal.id)
        accounts = await session_accounts(lines)
        ap_line = next(l for l in lines if accounts[l.account_id].code == "2000")
        assert Decimal(ap_line.debit) == Decimal("57.00")
        assert ap_line.contra_party_id == supplier_id

        st = await _statement(client, token, supplier_id, datee)
        assert st["side"] == "ap"
        assert st["closing_balance"] == "57.00"
        assert st["debit_total"] == "57.00"

        rows = await movement_rows(datee)
        assert any(
            m.reason == "supplier_pay"
            and m.direction == "out"
            and m.method == "network"
            and Decimal(m.amount) == Decimal("57.00")
            for m in rows
        )
    finally:
        await _cleanup_vouchers("pay")
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(supplier_id)


async def test_card_method_normalizes_to_network_movement(client):
    """method=card posts a network drawer movement (card is the legacy drawer
    word; the voucher row stores the normalized drawer method)."""
    datee = _voucher_date(2)
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(client, token, drug_id, party_id=customer_id, datee=datee)
        invoice_ids.append(sale["id"])
        v = await _voucher(
            client, token,
            voucher_type="receipt",
            party_id=customer_id,
            datee=datee,
            amount="20.00",
            method="card",
            description=_uniq("card"),
        )
        assert v["method"] == "network"
        rows = await movement_rows(datee)
        assert any(m.reason == "customer_settlement" and m.method == "network" for m in rows)
    finally:
        await _cleanup_vouchers("card")
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_reversal_of_receipt_is_one_shot_and_restores_balance(client):
    """Reversing a receipt posts the opposite journal (Cr 1000 / Dr 1100), the
    opposite drawer movement, and returns the statement to the pre-settlement
    debt; a reversal cannot be reversed again (409)."""
    datee = _voucher_date(3)
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(client, token, drug_id, party_id=customer_id, datee=datee)
        invoice_ids.append(sale["id"])
        v = await _voucher(
            client, token,
            voucher_type="receipt",
            party_id=customer_id,
            datee=datee,
            amount="25.00",
            description=_uniq("rev"),
        )
        st = await _statement(client, token, customer_id, datee)
        assert st["closing_balance"] == "25.00"

        r = await client.post(
            f"/api/v1/receivables/vouchers/{v['id']}/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text
        rev = r.json()
        assert rev["reverses_voucher_id"] == v["id"]
        assert rev["voucher_type"] == "receipt"
        assert rev["amount"] == "25.00"
        assert rev["voucher_no"] > v["voucher_no"]
        journal = await _journal_of(rev["id"])
        assert "إلغاء" in journal.description

        st = await _statement(client, token, customer_id, datee)
        assert st["closing_balance"] == "50.00"

        rows = await movement_rows(datee)
        assert any(
            m.reason == "customer_settlement"
            and m.direction == "out"
            and Decimal(m.amount) == Decimal("25.00")
            for m in rows
        )

        r = await client.post(
            f"/api/v1/receivables/vouchers/{rev['id']}/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, r.text
    finally:
        await _cleanup_vouchers("rev")
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_receivables_register_lists_customers_sorted_with_total(client):
    """The receivables register covers every active customer/both party with its
    all-time net AR balance (a settled customer nets down), sorted descending,
    with the grand total counting only positive balances; suppliers never appear."""
    datee = _voucher_date(4)
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    a = await _make_customer()          # 50 debt, no settlement
    b = await _make_customer()          # 50 debt, 30 settled → 20
    c = await _make_customer()          # zero balance
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        for pid in (a, b):
            sale = await _credit_sale(client, token, drug_id, party_id=pid, datee=datee)
            invoice_ids.append(sale["id"])
        await _voucher(
            client, token,
            voucher_type="receipt",
            party_id=b,
            datee=datee,
            amount="30.00",
            description=_uniq("reg"),
        )

        r = await client.get(
            "/api/v1/receivables", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        reg = r.json()
        assert reg["total"] == "70.00"
        by_id = {x["party_id"]: x for x in reg["receivables"]}
        assert set(by_id) >= {a, b, c}
        assert by_id[a]["balance"] == "50.00"
        assert by_id[b]["balance"] == "20.00"
        assert by_id[c]["balance"] == "0.00"
        assert by_id[a]["credit_limit"] == "0.00"
        assert supplier_id not in by_id
        # 50 sorts above 20, which sorts above 0
        positions = [i for i, x in enumerate(reg["receivables"]) if x["party_id"] in {a, b, c}]
        assert positions == sorted(
            positions, key=lambda i: -float(reg["receivables"][i]["balance"])
        )
    finally:
        await _cleanup_vouchers("reg")
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(a)
        await _cleanup_party(b)
        await _cleanup_party(c)
        await _cleanup_party(supplier_id)


async def test_credit_limit_blocks_sale_above_limit_and_zero_is_unlimited(client):
    """A credit sale is blocked when the customer's debt + new agel would exceed
    credit_limit (400); credit_limit 0 = unlimited keeps the existing behavior."""
    datee = _voucher_date(5)
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("40.0000", "5.0000", "2026-01-01")],
        stock_qty="40.0000",
    )
    capped = await _make_customer(credit_limit="70")
    open_ = await _make_customer()  # default 0 → unlimited
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(client, token, drug_id, party_id=capped, datee=datee)
        invoice_ids.append(sale["id"])
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": capped,
                "datee": datee,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [{"method": "credit", "amount": "50.00"}],
            },
        )
        assert r.status_code == 400, r.text
        assert "credit limit" in r.json()["detail"].lower()

        for _ in range(2):  # 50 + 50 = 100 debt, both allowed at limit 0
            s = await _credit_sale(client, token, drug_id, party_id=open_, datee=datee)
            invoice_ids.append(s["id"])
    finally:
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(capped)
        await _cleanup_party(open_)


async def test_voucher_permission_gates_and_branch_scope(client):
    """Voucher posting/reversal need receivables.manage (floor 7): anonymous is
    401, a level-1 user is 403. A cross-branch voucher id is a 404."""
    datee = _voucher_date(6)
    customer_id = await _make_customer()
    low_user_id = None
    other_branch_id = None
    try:
        r = await client.post(
            "/api/v1/receivables/vouchers",
            json={"voucher_type": "receipt", "party_id": customer_id, "datee": datee, "amount": "1.00"},
        )
        assert r.status_code == 401, r.text

        low_user_id = await _make_user(_uniq("low"), 1, branch_id=BRANCH_ID)
        low_token = _token_for(low_user_id, BRANCH_ID)
        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {low_token}"},
            json={"voucher_type": "receipt", "party_id": customer_id, "datee": datee, "amount": "1.00"},
        )
        assert r.status_code == 403, r.text

        other_branch_id = await _make_other_branch()
        other_token = _token_for(1, other_branch_id)  # any authenticated caller
        r = await client.get(
            "/api/v1/receivables/vouchers/999999",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert r.status_code == 404, r.text
    finally:
        if low_user_id is not None:
            await _delete_users([low_user_id])
        if other_branch_id is not None:
            await _delete_other_branch(other_branch_id)
        await _cleanup_party(customer_id)


async def test_voucher_validation_edges(client):
    """Wrong party kind, unknown/inactive party, zero amount, and a closed day
    are all rejected (400/404/409) without writing anything."""
    datee = _voucher_date(7)
    token = await _login_token(client)

    r = await client.get(
        "/api/v1/receivables", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["receivables"] == []
    assert body["total"] == "0.00"

    supplier_id = await _make_supplier()
    inactive = await _make_customer(active=False)
    customer_id = await _make_customer()
    try:
        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={"voucher_type": "receipt", "party_id": supplier_id, "datee": datee, "amount": "10.00"},
        )
        assert r.status_code == 400, r.text

        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={"voucher_type": "receipt", "party_id": inactive, "datee": datee, "amount": "10.00"},
        )
        assert r.status_code == 400, r.text

        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={"voucher_type": "receipt", "party_id": 999999, "datee": datee, "amount": "10.00"},
        )
        assert r.status_code == 404, r.text

        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={"voucher_type": "receipt", "party_id": customer_id, "datee": datee, "amount": "0.00"},
        )
        assert r.status_code == 400, r.text

        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={"voucher_type": "receipt", "party_id": customer_id, "datee": datee, "amount": "-5.00"},
        )
        assert r.status_code == 400, r.text

        _mark_closed(_voucher_date(8))
        closed = await _close_day(client, token, datee=_voucher_date(8), counted_cash="0")
        assert closed.status_code == 200, closed.text
        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={"voucher_type": "receipt", "party_id": customer_id, "datee": _voucher_date(8), "amount": "10.00"},
        )
        assert r.status_code == 409, r.text
        assert not await voucher_rows()
    finally:
        await _cleanup_drawer()
        await _cleanup_party(supplier_id)
        await _cleanup_party(inactive)
        await _cleanup_party(customer_id)


async def test_overpayment_receipt_allowed_as_advance(client):
    """A receipt beyond the current debt is allowed — the customer's balance
    just goes negative (a pre-payment/advance), which the register reports."""
    datee = _voucher_date(9)
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(client, token, drug_id, party_id=customer_id, datee=datee)
        invoice_ids.append(sale["id"])
        await _voucher(
            client, token,
            voucher_type="receipt",
            party_id=customer_id,
            datee=datee,
            amount="60.00",
            description=_uniq("adv"),
        )
        st = await _statement(client, token, customer_id, datee)
        assert st["closing_balance"] == "-10.00"
        r = await client.get(
            "/api/v1/receivables", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        by_id = {x["party_id"]: x for x in r.json()["receivables"]}
        assert by_id[customer_id]["balance"] == "-10.00"
    finally:
        await _cleanup_vouchers("adv")
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_receivables_html_print(client):
    """format=html returns an A4 printable receivables page (RTL Arabic)."""
    datee = _voucher_date(10)
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(client, token, drug_id, party_id=customer_id, datee=datee)
        invoice_ids.append(sale["id"])
        r = await client.get(
            "/api/v1/receivables?format=html", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/html")
        assert "أرصدة العملاء" in r.text
        assert "50.00" in r.text
    finally:
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_voucher_list_and_detail_are_branch_scoped(client):
    """GET /vouchers lists branch vouchers newest-first with their journal
    entry_no; GET /vouchers/{id} returns one. Cross-branch is 404."""
    datee = _voucher_date(11)
    customer_id = await _make_customer()
    try:
        token = await _login_token(client)
        drug_id = await _make_drug_and_stock(
            tax_type="14%", price="10.0000",
            batches=[("10.0000", "5.0000", "2026-01-01")], stock_qty="20.0000",
        )
        sale = await _credit_sale(client, token, drug_id, party_id=customer_id, datee=datee)
        invoice_ids = [sale["id"]]
        try:
            v = await _voucher(
                client, token,
                voucher_type="receipt",
                party_id=customer_id,
                datee=datee,
                amount="5.00",
                description=_uniq("lst"),
            )
            r = await client.get(
                "/api/v1/receivables/vouchers", headers={"Authorization": f"Bearer {token}"}
            )
            assert r.status_code == 200, r.text
            rows = r.json()["vouchers"]
            assert any(x["id"] == v["id"] for x in rows)
            detail = next(x for x in rows if x["id"] == v["id"])
            assert detail["entry_no"] == v["entry_no"]
            r = await client.get(
                f"/api/v1/receivables/vouchers/{v['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["amount"] == "5.00"
            r = await client.get(
                "/api/v1/receivables/vouchers/999999",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 404, r.text
        finally:
            await _cleanup_vouchers("lst")
            await _cleanup_sale([drug_id], invoice_ids)
    finally:
        await _cleanup_party(customer_id)


async def test_credit_limit_counts_debt_after_code_shadowing(client):
    """A branch's own "1100" account must not let the credit-limit guard
    under-read the debt sitting on the inherited MAIN account (#19 review fix)."""
    datee = _voucher_date(13)
    other_branch_id = await _make_other_branch()
    user_id = None
    customer_id = None
    drug_id = None
    invoice_ids: list[int] = []
    try:
        user_id = await _make_user(_uniq("b2mgr2"), 7, branch_id=other_branch_id)
        token = _token_for(user_id, other_branch_id)
        customer_id = await _make_customer_on(other_branch_id, credit_limit="70")
        drug_id = await _make_drug_stock_on(
            other_branch_id,
            tax_type="14%",
            price="10.0000",
            batches=[("40.0000", "5.0000", "2026-01-01")],
            stock_qty="40.0000",
        )
        sale = await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee=datee
        )
        invoice_ids.append(sale["id"])

        await _shadow_account(client, token, "1100", "asset")

        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": customer_id,
                "datee": datee,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [{"method": "credit", "amount": "50.00"}],
            },
        )
        assert r.status_code == 400, r.text
        assert "credit limit" in r.json()["detail"].lower()
    finally:
        await _cleanup_sale([drug_id] if drug_id else [], invoice_ids)
        await _cleanup_branch_balances(other_branch_id)
        if customer_id is not None:
            await _cleanup_party(customer_id)
        if user_id is not None:
            await _delete_users([user_id])
        await _delete_other_branch(other_branch_id)


async def test_payables_register_survives_code_shadowing(client):
    """The payables view must keep the AP posted to the inherited MAIN account
    once the branch configured its own "2000" (#19 review fix)."""
    datee = _voucher_date(15)
    other_branch_id = await _make_other_branch()
    user_id = None
    supplier_id = None
    drug_id = None
    invoice_ids: list[int] = []
    try:
        user_id = await _make_user(_uniq("b2mgr4"), 7, branch_id=other_branch_id)
        token = _token_for(user_id, other_branch_id)
        supplier_id = await _make_customer_on(other_branch_id, kind="supplier")
        drug_id = await _make_drug_for_purchase()
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "datee": datee,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        await _shadow_account(client, token, "2000", "liability")

        r = await client.get(
            "/api/v1/parties/payables", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        by_id = {x["party_id"]: x for x in r.json()["payables"]}
        assert by_id[supplier_id]["balance"] == "114.00"
    finally:
        await _cleanup_sale([drug_id] if drug_id else [], invoice_ids)
        await _cleanup_branch_balances(other_branch_id)
        if supplier_id is not None:
            await _cleanup_party(supplier_id)
        if user_id is not None:
            await _delete_users([user_id])
        await _delete_other_branch(other_branch_id)


async def test_statement_ledger_keeps_inherited_lines_after_code_shadowing(client):
    """The كشف حساب must still show lines posted to the inherited MAIN account
    once the branch configured its own "1100" (#19 review fix)."""
    datee = _voucher_date(14)
    other_branch_id = await _make_other_branch()
    user_id = None
    customer_id = None
    drug_id = None
    invoice_ids: list[int] = []
    try:
        user_id = await _make_user(_uniq("b2mgr3"), 7, branch_id=other_branch_id)
        token = _token_for(user_id, other_branch_id)
        customer_id = await _make_customer_on(other_branch_id)
        drug_id = await _make_drug_stock_on(
            other_branch_id,
            tax_type="14%",
            price="10.0000",
            batches=[("10.0000", "5.0000", "2026-01-01")],
            stock_qty="20.0000",
        )
        sale = await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee=datee
        )
        invoice_ids.append(sale["id"])

        await _shadow_account(client, token, "1100", "asset")

        st = await _statement(client, token, customer_id, datee)
        assert st["closing_balance"] == "50.00"
        assert st["movements"][0]["account_code"] == "1100"
    finally:
        await _cleanup_sale([drug_id] if drug_id else [], invoice_ids)
        await _cleanup_branch_balances(other_branch_id)
        if customer_id is not None:
            await _cleanup_party(customer_id)
        if user_id is not None:
            await _delete_users([user_id])
        await _delete_other_branch(other_branch_id)


async def test_reversal_of_payment_restores_supplier_payable(client):
    """Reversing a payment voucher posts the opposite journal (Cr 2000 / Dr
    1000), the opposite drawer movement (in), and returns the supplier statement
    to the pre-payment payable — the mirror of the receipt reversal (#19 review
    coverage gap)."""
    datee = _voucher_date(16)
    drug_id = await _make_drug_for_purchase()
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "datee": datee,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        v = await _voucher(
            client, token,
            voucher_type="payment",
            party_id=supplier_id,
            datee=datee,
            amount="57.00",
            description=_uniq("payrev"),
        )
        st = await _statement(client, token, supplier_id, datee)
        assert st["closing_balance"] == "57.00"

        r = await client.post(
            f"/api/v1/receivables/vouchers/{v['id']}/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text
        rev = r.json()
        assert rev["reverses_voucher_id"] == v["id"]
        journal = await _journal_of(rev["id"])
        assert "إلغاء" in journal.description

        st = await _statement(client, token, supplier_id, datee)
        assert st["closing_balance"] == "114.00"

        # the reversal's AP credit leg carries the supplier as contra, attached
        # to the exact account row the original payment touched (review #5: the
        # reversal must not re-derive the contra from a code constant)
        rev_journal = await _journal_of(rev["id"])
        rev_lines = await session_lines(rev_journal.id)
        ap_legs = [l for l in rev_lines if l.credit > 0]
        assert len(ap_legs) == 1
        assert ap_legs[0].contra_party_id == supplier_id

        rows = await movement_rows(datee)
        assert any(
            m.reason == "supplier_pay"
            and m.direction == "in"
            and Decimal(m.amount) == Decimal("57.00")
            for m in rows
        )

        r = await client.post(
            f"/api/v1/receivables/vouchers/{rev['id']}/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, r.text
    finally:
        await _cleanup_vouchers("payrev")
        await _cleanup_sale([drug_id], invoice_ids)
        await _cleanup_party(supplier_id)


async def test_kind_both_party_nets_ar_and_ap_in_both_registers(client):
    """A party that is both customer and supplier: the credit sale and receipt
    move its AR (receivables register), the credit purchase and payment move its
    AP (payables register), and each register shows only its own side."""
    datee = _voucher_date(17)
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    pur_drug_id = await _make_drug_for_purchase()
    both_id = await _make_customer(kind="both")
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(
            client, token, drug_id, party_id=both_id, datee=datee
        )
        invoice_ids.append(sale["id"])
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": both_id,
                "datee": datee,
                "lines": [{"drug_id": pur_drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        await _voucher(
            client, token,
            voucher_type="receipt", party_id=both_id, datee=datee,
            amount="20.00", description=_uniq("both_rec"),
        )
        await _voucher(
            client, token,
            voucher_type="payment", party_id=both_id, datee=datee,
            amount="14.00", description=_uniq("both_pay"),
        )

        r = await client.get(
            "/api/v1/receivables", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        rec = {x["party_id"]: x for x in r.json()["receivables"]}
        assert rec[both_id]["balance"] == "30.00"

        r = await client.get(
            "/api/v1/parties/payables", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        pay = {x["party_id"]: x for x in r.json()["payables"]}
        assert pay[both_id]["balance"] == "100.00"
    finally:
        await _cleanup_vouchers("both")
        await _cleanup_sale([drug_id, pur_drug_id], invoice_ids)
        await _cleanup_party(both_id)


async def test_receivables_register_aggregates_pinned_receivable_account(client):
    """A party whose receivable_account_id pins a custom AR account (different
    from the branch default code) is counted in the register from that account
    — locks the register's single-aggregate no-N+1 behavior across per-party
    account sets."""
    customer_id = await _make_customer()
    account_id = None
    journal_id = None
    try:
        async with SessionLocal() as session:
            acc = Account(
                branch_id=BRANCH_ID,
                code="1199",
                name_ar=_uniq("pin"),
                type="asset",
                is_active=True,
            )
            session.add(acc)
            await session.flush()
            account_id = acc.id
            party = await session.get(Party, customer_id)
            party.receivable_account_id = account_id
            j = Journal(
                branch_id=BRANCH_ID,
                datee=date(2026, 8, 20),
                entry_no=999001,
                description="pinned AR debt",
                source="manual",
                status="posted",
            )
            session.add(j)
            await session.flush()
            journal_id = j.id
            session.add(
                JournalLine(
                    journal_id=j.id,
                    branch_id=BRANCH_ID,
                    account_id=account_id,
                    debit=Decimal("30"),
                    credit=Decimal("0"),
                    contra_party_id=customer_id,
                    datee=date(2026, 8, 20),
                    month=8,
                    year=2026,
                    creditdebit="debit",
                )
            )
            await session.commit()

        token = await _login_token(client)
        r = await client.get(
            "/api/v1/receivables", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        by_id = {x["party_id"]: x for x in r.json()["receivables"]}
        assert by_id[customer_id]["balance"] == "30.00"
    finally:
        await _cleanup_branch_balances(BRANCH_ID)
        async with SessionLocal() as session:
            if journal_id is not None:
                await session.execute(
                    delete(JournalLine).where(JournalLine.journal_id == journal_id)
                )
                await session.execute(delete(Journal).where(Journal.id == journal_id))
            await session.execute(
                delete(AuditLog).where(
                    AuditLog.entity == "parties", AuditLog.entity_id == customer_id
                )
            )
            await session.execute(delete(Party).where(Party.id == customer_id))
            if account_id is not None:
                await session.execute(delete(Account).where(Account.id == account_id))
            await session.commit()


async def test_receivables_register_survives_code_shadowing(client):
    """A branch that inherits its AR from MAIN and later creates its own "1100"
    account must not lose the debt posted to the inherited account: the register
    reads the code's own AND inherited account rows (#19 review fix)."""
    datee = _voucher_date(12)
    other_branch_id = await _make_other_branch()
    user_id = None
    customer_id = None
    drug_id = None
    invoice_ids: list[int] = []
    try:
        user_id = await _make_user(_uniq("b2mgr"), 7, branch_id=other_branch_id)
        token = _token_for(user_id, other_branch_id)
        customer_id = await _make_customer_on(other_branch_id)
        drug_id = await _make_drug_stock_on(
            other_branch_id,
            tax_type="14%",
            price="10.0000",
            batches=[("10.0000", "5.0000", "2026-01-01")],
            stock_qty="20.0000",
        )
        sale = await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee=datee
        )
        invoice_ids.append(sale["id"])

        await _shadow_account(client, token, "1100", "asset")

        r = await client.get(
            "/api/v1/receivables", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        by_id = {x["party_id"]: x for x in r.json()["receivables"]}
        assert by_id[customer_id]["balance"] == "50.00"
    finally:
        await _cleanup_sale([drug_id] if drug_id else [], invoice_ids)
        await _cleanup_branch_balances(other_branch_id)
        if customer_id is not None:
            await _cleanup_party(customer_id)
        if user_id is not None:
            await _delete_users([user_id])
        await _delete_other_branch(other_branch_id)


async def _make_customer_on(
    branch_id: int,
    *,
    kind: str = "customer",
    active: bool = True,
    credit_limit: str = "0",
) -> int:
    """A throwaway customer/supplier/both party on `branch_id` (the shared
    `_make_customer` is hardcoded to branch 1)."""
    async with SessionLocal() as session:
        party = Party(
            branch_id=branch_id,
            kind=kind,
            namee=_uniq("b2pty"),
            randomid=_uniq_id(),
            active=active,
            credit_limit=Decimal(credit_limit),
        )
        session.add(party)
        await session.flush()
        party_id = party.id
        await session.commit()
        return party_id


async def _make_drug_stock_on(
    branch_id: int,
    *,
    tax_type: str = "14%",
    price: str = "10.0000",
    batches: list | None = None,
    stock_qty: str = "20.0000",
) -> int:
    """A throwaway drug with branch stock + batches on `branch_id`."""
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq("b2drug"),
            tax_type=tax_type,
            price=Decimal(price),
            price_wholesale=Decimal("8.0000"),
            price_cost=Decimal("5.0000"),
        )
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=branch_id, drug_id=drug_id, qty=Decimal(stock_qty), minimum=0
            )
        )
        for i, (qty, cost, expire) in enumerate(batches or []):
            session.add(
                StockBatch(
                    branch_id=branch_id,
                    drug_id=drug_id,
                    randomid=f"{_uniq('b2b')}{i}",
                    qty=Decimal(qty),
                    cost=Decimal(cost),
                    expire=date.fromisoformat(expire) if expire else None,
                )
            )
        await session.commit()
        return drug_id


async def _shadow_account(client, token, code: str, type: str) -> int:
    """Create the branch's own account for `code` via the chart API — the
    branch inherits the MAIN chart until it configures its own, and the per-branch
    duplicate check lets it shadow an inherited code (the #19 review finding).
    The type must match the company chart's type for the code (S2.5 guard)."""
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code,
            "name_ar": _uniq(f"sh_{code}"),
            "type": type,
            "is_active": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _cleanup_branch_balances(branch_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Balance).where(Balance.branch_id == branch_id))
        await session.commit()


# ---- raw helpers (kept out of the shared utils: only this slice reads them) ----

async def session_lines(journal_id: int) -> list:
    async with SessionLocal() as session:
        return list(
            (
                await session.execute(
                    select(JournalLine).where(JournalLine.journal_id == journal_id)
                )
            ).scalars().all()
        )


async def session_accounts(lines) -> dict[int, Account]:
    async with SessionLocal() as session:
        accounts = (
            await session.execute(
                select(Account).where(Account.id.in_({l.account_id for l in lines}))
            )
        ).scalars().all()
        return {a.id: a for a in accounts}


async def movement_rows(datee: str) -> list[DrawerMovement]:
    d = date.fromisoformat(datee)
    async with SessionLocal() as session:
        return list(
            (
                await session.execute(
                    select(DrawerMovement)
                    .where(DrawerMovement.branch_id == BRANCH_ID, DrawerMovement.datee == d)
                    .order_by(DrawerMovement.id)
                )
            ).scalars().all()
        )


async def voucher_rows() -> list:
    async with SessionLocal() as session:
        return list(
            (await session.execute(select(SettlementVoucher))).scalars().all()
        )


async def _make_drug_for_purchase() -> int:
    from app.models import Drug

    async with SessionLocal() as session:
        drug = Drug(drugname=_uniq("pur_drug"), tax_type="14%", price=Decimal("0.0000"))
        session.add(drug)
        await session.flush()
        did = drug.id
        await session.commit()
        return did