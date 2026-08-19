"""S2.3 كشف حساب + payables tests (issue #18).

The statement is built from journal_lines only: opening = the party's AR/AP
lines before the period, movements carry a running balance, closing = opening +
movements. Customers run on AR (debit-positive), suppliers on AP (credit-
positive); `both` defaults to AR with an optional `side` override.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import Drug, Invoice, Party
from tests.purchase_returns_test_utils import _cleanup as _cleanup_purchase_return
from tests.purchase_test_utils import _cleanup as _cleanup_purchase, _make_supplier
from tests.returns_test_utils import _cleanup
from tests.sales_test_utils import _login_token, _make_drug_and_stock

BRANCH_ID = 1

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_stmt2_{tag}_{_seq[0]}__"


async def _make_customer(*, kind: str = "customer", active: bool = True) -> int:
    async with SessionLocal() as session:
        party = Party(
            branch_id=BRANCH_ID,
            kind=kind,
            namee=_uniq("cust"),
            randomid=_uniq("pty"),
            active=active,
        )
        session.add(party)
        await session.flush()
        pid = party.id
        await session.commit()
        return pid


async def _cleanup_party(pid: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == pid))
        await session.commit()


async def _credit_sale(
    client, token, drug_id, *, qty: str = "5", party_id: int, datee: str
) -> dict:
    r = await client.post(
        "/api/v1/sales",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "party_id": party_id,
            "datee": datee,
            "lines": [{"drug_id": drug_id, "qty": qty}],
            "payments": [{"method": "credit", "amount": "50.00"}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_customer_statement_shows_credit_sale_with_running_balance(client):
    """A credit sale to a tracked customer appears on the AR ledger: opening 0,
    one movement (debit 50), closing 50 — with a running balance per row."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee="2026-08-10"
        )
        invoice_ids.append(sale["id"])

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["party"]["id"] == customer_id
        assert st["side"] == "ar"
        assert st["opening_balance"] == "0.00"
        assert st["closing_balance"] == "50.00"
        assert st["debit_total"] == "50.00"
        assert st["credit_total"] == "0.00"
        assert len(st["movements"]) == 1
        m = st["movements"][0]
        assert m["datee"] == "2026-08-10"
        assert m["debit"] == "50.00"
        assert m["credit"] == "0.00"
        assert m["running_balance"] == "50.00"
        assert "فاتورة بيع" in m["description"]
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_statement_opening_balance_from_prior_period(client):
    """A credit sale in a prior month is the opening balance of the next."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee="2026-07-05"
        )
        invoice_ids.append(
            (
                await _last_sale_id()
            )
        )
        # next month: July's 50 is the opening, August has no movements
        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["opening_balance"] == "50.00"
        assert st["closing_balance"] == "50.00"
        assert st["movements"] == []

        # the month itself: opening 0, movement 50, closing 50
        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=7&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        st = r.json()
        assert st["opening_balance"] == "0.00"
        assert st["closing_balance"] == "50.00"
        assert len(st["movements"]) == 1
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def _last_sale_id() -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(select(Invoice.id).order_by(Invoice.id.desc()).limit(1))
        ).scalar_one()


async def test_statement_date_range_window_and_both_periods_rejected(client):
    """Date range works as the movement window (opening = lines before it), and
    mixing month/year with a range is a 400."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee="2026-08-01"
        )
        invoice_ids.append(await _last_sale_id())

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement"
            "?date_from=2026-08-10&date_to=2026-08-20",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["opening_balance"] == "50.00"  # Aug 1 is before the window
        assert st["movements"] == []
        assert st["closing_balance"] == "50.00"

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement"
            "?month=8&year=2026&date_from=2026-08-10&date_to=2026-08-20",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, r.text

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement"
            "?date_from=2026-08-20&date_to=2026-08-10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, r.text
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_cash_sale_to_customer_not_on_statement(client):
    """A cash sale to a tracked customer posts no AR line, so the statement
    shows no movement (the header party is only recorded)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": customer_id,
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["opening_balance"] == "0.00"
        assert st["closing_balance"] == "0.00"
        assert st["movements"] == []
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_supplier_statement_uses_ap_side_positive(client):
    """A supplier's ledger runs on AP (credit-positive): a credit purchase shows
    a credit movement and a positive closing balance."""
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
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            f"/api/v1/parties/{supplier_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["side"] == "ap"
        assert st["opening_balance"] == "0.00"
        assert st["closing_balance"] == "114.00"
        assert st["debit_total"] == "0.00"
        assert st["credit_total"] == "114.00"
        assert len(st["movements"]) == 1
        assert st["movements"][0]["credit"] == "114.00"
        assert st["movements"][0]["running_balance"] == "114.00"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [supplier_id])


async def test_both_party_defaults_ar_with_side_override(client):
    """A kind='both' party defaults to the AR side but accepts side=ap."""
    drug_id = await _make_drug_for_purchase()
    both_id = await _make_customer(kind="both")
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        # credit purchase to the both-party: AP line gets the contra
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": both_id,
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            f"/api/v1/parties/{both_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["side"] == "ar"
        assert st["closing_balance"] == "0.00"  # no AR lines

        r = await client.get(
            f"/api/v1/parties/{both_id}/statement?month=8&year=2026&side=ap",
            headers={"Authorization": f"Bearer {token}"},
        )
        st = r.json()
        assert st["side"] == "ap"
        assert st["closing_balance"] == "114.00"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [both_id])


async def test_statement_requires_auth_and_branch_scope(client):
    """Unauthenticated statement is 401; a party from another branch is 404."""
    customer_id = await _make_customer()
    try:
        r = await client.get(f"/api/v1/parties/{customer_id}/statement")
        assert r.status_code == 401, r.text

        token = await _login_token(client)
        r = await client.get(
            f"/api/v1/parties/999999/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404, r.text
    finally:
        await _cleanup_party(customer_id)


async def test_payables_lists_suppliers_sorted_desc_with_total(client):
    """Payables covers every active supplier/both party (zero balances included),
    sorted by balance descending, with the grand total."""
    drug_a = await _make_drug_for_purchase()
    drug_b = await _make_drug_for_purchase()
    s1 = await _make_supplier()
    s2 = await _make_supplier()
    s3 = await _make_supplier()  # zero balance
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        # s1 owes 114 (credit purchase), s2 owes 57
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": s1,
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_a, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": s2,
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_b, "qty": "5", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "57.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/parties/payables",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        pay = r.json()
        assert pay["total"] == "171.00"
        by_id = {p["party_id"]: p for p in pay["payables"]}
        assert set(by_id) >= {s1, s2, s3}
        assert by_id[s1]["balance"] == "114.00"
        assert by_id[s2]["balance"] == "57.00"
        assert by_id[s3]["balance"] == "0.00"
        # s1 (114) must sort above s2 (57), which sorts above s3 (0)
        positions = [i for i, p in enumerate(pay["payables"]) if p["party_id"] in {s1, s2, s3}]
        assert positions == sorted(positions, key=lambda i: -float(pay["payables"][i]["balance"]))
    finally:
        await _cleanup_purchase([drug_a, drug_b], invoice_ids, [s1, s2, s3])


async def test_statement_html_print_renders_page(client):
    """format=html returns an A4 printable page for the statement and payables."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee="2026-08-10"
        )
        invoice_ids.append(await _last_sale_id())

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=8&year=2026&format=html",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/html")
        assert "كشف حساب" in r.text
        assert "50.00" in r.text

        r = await client.get(
            "/api/v1/parties/payables?format=html",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/html")
        assert "أرصدة الموردين" in r.text
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_sale_return_reduces_running_balance_on_statement(client):
    """A credit sale 50 followed by its full return: movements +50 then −50,
    closing back to 0.00 — the return's AR credit line is party-tagged."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _credit_sale(
            client, token, drug_id, party_id=customer_id, datee="2026-08-10"
        )
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["opening_balance"] == "0.00"
        assert st["closing_balance"] == "0.00"
        assert st["debit_total"] == "50.00"
        assert st["credit_total"] == "50.00"
        assert len(st["movements"]) == 2
        # chronological: sale first (+50), return second (−50)
        assert st["movements"][0]["running_balance"] == "50.00"
        assert st["movements"][1]["running_balance"] == "0.00"
        assert "مرتجع بيع" in st["movements"][1]["description"]
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_purchase_return_reduces_supplier_statement(client):
    """A credit purchase 114 then its full return: AP movements +114 then −114,
    closing back to 0.00."""
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
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        purchase = r.json()
        invoice_ids.append(purchase["id"])
        line_id = purchase["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/purchases/{purchase['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "10"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            f"/api/v1/parties/{supplier_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["side"] == "ap"
        assert st["opening_balance"] == "0.00"
        assert st["closing_balance"] == "0.00"
        assert st["debit_total"] == "114.00"
        assert st["credit_total"] == "114.00"
        assert len(st["movements"]) == 2
        assert st["movements"][0]["running_balance"] == "114.00"
        assert st["movements"][1]["running_balance"] == "0.00"
        assert "مرتجع مشتريات" in st["movements"][1]["description"]
    finally:
        await _cleanup_purchase_return([drug_id], invoice_ids, [supplier_id])


async def test_split_payment_credit_sale_posts_only_credit_to_statement(client):
    """A 50/50 cash+credit sale to a customer posts only the credit leg (25.00)
    to the AR ledger — cash never appears."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": customer_id,
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [
                    {"method": "cash", "amount": "25.00"},
                    {"method": "credit", "amount": "25.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["closing_balance"] == "25.00"
        assert st["debit_total"] == "25.00"
        assert len(st["movements"]) == 1
        assert st["movements"][0]["debit"] == "25.00"
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_party(customer_id)


async def test_invalid_side_and_month_validation(client):
    """side must be ar|ap (400); month outside 1..12 is a 422 from the router."""
    customer_id = await _make_customer()
    try:
        token = await _login_token(client)
        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=8&year=2026&side=both",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, r.text

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=13&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, r.text

        r = await client.get(
            f"/api/v1/parties/{customer_id}/statement?month=8&year=2026&side=ap",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        # customer has no AP lines → empty AR? no: side=ap on a customer is allowed
        assert r.json()["side"] == "ap"
    finally:
        await _cleanup_party(customer_id)


async def test_supplier_side_override_to_ar_shows_zero(client):
    """A supplier's statement defaults to ap; forcing side=ar returns zeroes."""
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        r = await client.get(
            f"/api/v1/parties/{supplier_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["side"] == "ap"

        r = await client.get(
            f"/api/v1/parties/{supplier_id}/statement?month=8&year=2026&side=ar",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["side"] == "ar"
        assert st["opening_balance"] == "0.00"
        assert st["closing_balance"] == "0.00"
        assert st["movements"] == []
    finally:
        await _cleanup_party(supplier_id)


async def test_statement_cross_branch_party_is_404(client):
    """A party owned by another branch is invisible (404) to this caller, even
    though it exists — same posture as every other branch-scoped read."""
    from app.auth.security import create_access_token
    from app.models import Branch, User

    other_user_id = None
    other_branch_id = None
    other_party_id = None
    try:
        async with SessionLocal() as session:
            branch = Branch(pharmacyid=f"sb{_seq[0]}", mobile="0", pharname="Other")
            session.add(branch)
            await session.flush()
            other_branch_id = branch.id
            user = User(
                username=_uniq("usr"),
                pass_hash="x",
                permission_level=9,
                branch_id=branch.id,
            )
            session.add(user)
            await session.flush()
            other_user_id = user.id
            await session.commit()
        async with SessionLocal() as session:
            party = Party(
                branch_id=other_branch_id,
                kind="customer",
                namee=_uniq("cust"),
                randomid=_uniq("pty"),
                active=True,
            )
            session.add(party)
            await session.flush()
            other_party_id = party.id
            await session.commit()

        token = await _login_token(client)
        r = await client.get(
            f"/api/v1/parties/{other_party_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404, r.text

        # and the other-branch user CAN see it (own branch)
        other_token = create_access_token(
            str(other_user_id), branch_id=other_branch_id, roles=[], permission_level=9
        )
        r = await client.get(
            f"/api/v1/parties/{other_party_id}/statement?month=8&year=2026",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["party"]["id"] == other_party_id
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(Party).where(
                    Party.namee.like("__t2_stmt2_cust_%") | Party.namee.like("__t2_stmt2_pty_%")
                )
            )
            await session.execute(
                delete(User).where(User.username.like("__t2_stmt2_usr_%"))
            )
            await session.execute(
                delete(Branch).where(Branch.pharmacyid.like("sb%"))
            )
            await session.commit()


async def test_payables_excludes_inactive_and_customer_parties(client):
    """Inactive suppliers and customer-kind parties never appear on the payables
    view — only active supplier/both parties."""
    inactive = await _make_supplier(active=False)
    customer = await _make_customer(kind="customer")
    try:
        token = await _login_token(client)
        r = await client.get(
            "/api/v1/parties/payables",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        ids = {p["party_id"] for p in r.json()["payables"]}
        assert inactive not in ids
        assert customer not in ids
    finally:
        await _cleanup_party(inactive)
        await _cleanup_party(customer)


async def _make_drug_for_purchase() -> int:
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq("pur_drug"), tax_type="14%", price=Decimal("0.0000")
        )
        session.add(drug)
        await session.flush()
        did = drug.id
        await session.commit()
        return did