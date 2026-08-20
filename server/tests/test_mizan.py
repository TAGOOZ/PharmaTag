"""S2.5 ميزان — trial balance + balance sheet tests (issue #20).

The trial balance is built from journal_lines per account code (own-branch
account first, merged with inherited branch-1 rows carrying this branch's
postings — the S2.3 code-shadowing rule). The balance sheet groups the same
closing balances by account type with income−expense folded in as net income.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select, update

from app.core.db import SessionLocal
from app.core.time import business_date
from app.models import Account, AuditLog, Balance, Drug, Invoice, Journal, JournalLine, Party
from app.money.journal import post_journal
from app.sales.numbering import next_journal_entry_no
from tests.purchase_returns_test_utils import _cleanup as _cleanup_purchase_return
from tests.purchase_test_utils import _cleanup as _cleanup_purchase, _make_supplier
from tests.receivables_test_utils import _cleanup_party, _cleanup_vouchers
from tests.sales_test_utils import _login_token, _make_drug_and_stock

BRANCH_ID = 1

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_mizan_{tag}_{_seq[0]}__"


async def _make_customer(*, kind: str = "customer") -> int:
    async with SessionLocal() as session:
        party = Party(
            branch_id=BRANCH_ID,
            kind=kind,
            namee=_uniq("cust"),
            randomid=_uniq("pty"),
            active=True,
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


def _by_code(payload: dict) -> dict[str, dict]:
    return {row["code"]: row for row in payload["accounts"]}


async def test_trial_balance_cash_sale_reconciles(client):
    """A cash sale posts a balanced journal; the trial balance shows it per
    account code: 1000 drawer +50, 4000 sales net 43.86, 2100 VAT 6.14,
    6000 COGS +25, 1200 stock −25. Totals debit == credit (75.00)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["balanced"] is True
        assert tb["totals"]["debit"] == "75.00"
        assert tb["totals"]["credit"] == "75.00"
        by_code = _by_code(tb)
        assert by_code["1000"]["debit"] == "50.00"
        assert by_code["1000"]["closing_balance"] == "50.00"
        assert by_code["4000"]["credit"] == "43.86"
        assert by_code["2100"]["credit"] == "6.14"
        assert by_code["6000"]["debit"] == "25.00"
        assert by_code["1200"]["credit"] == "25.00"
        assert by_code["1200"]["closing_balance"] == "-25.00"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])


async def test_trial_balance_credit_sale_and_purchase_reconcile(client):
    """A credit sale (1100 AR +50) and a credit purchase (1200 stock +100,
    2100 input-VAT +14, 2000 AP −114) land on the ميزان; totals still balance
    and the codes carry their expected debit/credit split."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    supplier_id = await _make_supplier()
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
                "payments": [{"method": "credit", "amount": "50.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "datee": "2026-08-12",
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["balanced"] is True
        assert tb["totals"]["debit"] == "189.00"
        assert tb["totals"]["credit"] == "189.00"
        by_code = _by_code(tb)
        assert by_code["1100"]["debit"] == "50.00"
        assert by_code["1100"]["closing_balance"] == "50.00"
        assert by_code["2000"]["credit"] == "114.00"
        assert by_code["2000"]["closing_balance"] == "-114.00"
        assert by_code["1200"]["debit"] == "100.00"
        assert by_code["1200"]["credit"] == "25.00"
        assert by_code["1200"]["closing_balance"] == "75.00"
        assert by_code["2100"]["debit"] == "14.00"
        assert by_code["2100"]["credit"] == "6.14"
        assert by_code["4000"]["credit"] == "43.86"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])
        await _cleanup_party(customer_id)
        await _cleanup_party(supplier_id)


async def test_trial_balance_includes_manual_journal_and_settlement(client):
    """A manual journal (Dr 5000 expenses 30, Cr 1000 drawer 30) and a سند قبض
    (Dr 1000 20, Cr 1100 20 off the customer's AR) both appear in the ميزان —
    total still balances."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    tag = _uniq("t3")
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
                "payments": [{"method": "credit", "amount": "50.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-15",
                "description": f"مصروف إيجار {tag}",
                "lines": [
                    {"account_code": "5000", "debit": "30.00"},
                    {"account_code": "1000", "credit": "30.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "voucher_type": "receipt",
                "party_id": customer_id,
                "datee": "2026-08-18",
                "method": "cash",
                "amount": "20.00",
                "description": f"قبض {tag}",
            },
        )
        assert r.status_code == 201, r.text

        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["balanced"] is True
        assert tb["totals"]["debit"] == "125.00"
        assert tb["totals"]["credit"] == "125.00"
        by_code = _by_code(tb)
        assert by_code["5000"]["debit"] == "30.00"
        assert by_code["1000"]["debit"] == "20.00"
        assert by_code["1000"]["credit"] == "30.00"
        assert by_code["1000"]["closing_balance"] == "-10.00"
        assert by_code["1100"]["debit"] == "50.00"
        assert by_code["1100"]["credit"] == "20.00"
        assert by_code["1100"]["closing_balance"] == "30.00"
    finally:
        from tests.manual_journal_test_utils import _cleanup_journals

        await _cleanup_journals(tag)
        await _cleanup_vouchers(tag)
        await _cleanup_purchase([drug_id], invoice_ids, [])
        await _cleanup_party(customer_id)


async def test_trial_balance_defaults_to_business_month(client):
    """With no period params the ميزان resolves to the business month, and the
    period is echoed back so callers know which window they got."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        bd = business_date()
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": bd.isoformat(),
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/accounts/trial-balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["period"]["month"] == bd.month
        assert tb["period"]["year"] == bd.year
        assert tb["balanced"] is True
        assert tb["totals"]["debit"] == "75.00"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])


async def test_trial_balance_period_validation(client):
    """Mixing month/year with a date range is ambiguous (400), and an inverted
    range is rejected up front (400)."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/accounts/trial-balance?month=8&year=2026&date_from=2026-08-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400, r.text
    r = await client.get(
        "/api/v1/accounts/trial-balance?date_from=2026-08-15&date_to=2026-08-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400, r.text
    r = await client.get(
        "/api/v1/accounts/balance-sheet?month=8&year=2026&date_to=2026-08-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400, r.text


async def test_trial_balance_date_range_filters(client):
    """A date range selects only the journals inside it: the August 10 sale is
    hidden from an 15–31 window, the August 20 sale is not."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-20",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/accounts/trial-balance?date_from=2026-08-15&date_to=2026-08-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["period"]["date_from"] == "2026-08-15"
        assert tb["period"]["date_to"] == "2026-08-31"
        assert tb["totals"]["debit"] == "75.00"
        assert tb["totals"]["credit"] == "75.00"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])


async def test_trial_balance_opening_balance_carries_forward(client):
    """July's closing becomes August's opening: the ميزان keeps history across
    month boundaries for the same branch chart."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-07-31",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["balanced"] is True
        by_code = _by_code(tb)
        assert by_code["1000"]["opening_debit"] == "50.00"
        assert by_code["1000"]["opening_balance"] == "50.00"
        assert by_code["1000"]["debit"] == "0.00"
        assert by_code["1000"]["closing_balance"] == "50.00"
        assert by_code["1200"]["opening_credit"] == "25.00"
        assert by_code["4000"]["opening_credit"] == "43.86"
        assert by_code["2100"]["opening_credit"] == "6.14"
        assert by_code["6000"]["opening_debit"] == "25.00"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])


async def test_balance_sheet_cash_sale_identity(client):
    """The balance sheet keeps the sale's numbers: assets 25.00 (drawer 50 +
    stock −25), liabilities 6.14 (output VAT), and equity = the 18.86 profit
    folded in as net income — total_assets == total_liabilities + equity."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/accounts/balance-sheet?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        bs = r.json()
        assert bs["balanced"] is True
        assert bs["net_income"] == "18.86"
        assert bs["total_assets"] == "25.00"
        assert bs["total_liabilities_equity"] == "25.00"
        assets = {a["code"]: a for a in bs["assets"]["accounts"]}
        assert assets["1000"]["amount"] == "50.00"
        assert assets["1200"]["amount"] == "-25.00"
        liabs = {a["code"]: a for a in bs["liabilities"]["accounts"]}
        assert liabs["2100"]["amount"] == "6.14"
        eq = {a["code"]: a for a in bs["equity"]["accounts"]}
        assert eq["__net_income__"]["amount"] == "18.86"
        assert eq["__net_income__"]["side"] == "credit"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])


async def test_balance_sheet_net_loss_identity(client):
    """When expenses exceed income the equity section goes negative and the
    identity total_assets == total_liabilities + total_equity still holds."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    tag = _uniq("t7")
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-15",
                "description": f"مصروف كبير {tag}",
                "lines": [
                    {"account_code": "5000", "debit": "60.00"},
                    {"account_code": "1000", "credit": "60.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text

        r = await client.get(
            "/api/v1/accounts/balance-sheet?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        bs = r.json()
        assert bs["balanced"] is True
        assert bs["net_income"] == "-41.14"
        eq = {a["code"]: a for a in bs["equity"]["accounts"]}
        assert eq["__net_income__"]["amount"] == "41.14"
        assert eq["__net_income__"]["side"] == "debit"
        assert bs["total_assets"] == "-35.00"
        assert bs["total_liabilities_equity"] == "-35.00"
    finally:
        from tests.manual_journal_test_utils import _cleanup_journals

        await _cleanup_journals(tag)
        await _cleanup_purchase([drug_id], invoice_ids, [])


async def test_trial_balance_own_branch_account_shadows_inherited(client):
    """The S2.3 code-shadowing rule: a branch that configures its OWN account
    for a code keeps its history on the inherited branch-1 row AND displays the
    own-branch account as the primary name/type — never both rows for the code."""
    from app.auth.security import create_access_token
    from app.models import Branch, User

    other_user_id = None
    other_branch_id = None
    other_account_id = None
    tag = _uniq("t10")
    try:
        async with SessionLocal() as session:
            branch = Branch(
                pharmacyid=f"sb{_seq[0]}", mobile=f"8{_seq[0]}", pharname="Other"
            )
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

        other_token = create_access_token(
            str(other_user_id), branch_id=other_branch_id, roles=[], permission_level=9
        )
        # the branch creates its own 1000 account with a distinctive name
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {other_token}"},
            json={
                "code": "1000",
                "name_ar": "خزينة فرعية خاصة",
                "name_en": "Subsidiary Cash",
                "type": "asset",
            },
        )
        assert r.status_code == 201, r.text
        other_account_id = r.json()["id"]

        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {other_token}"},
            json={
                "datee": "2026-08-10",
                "description": f"فرع تاني {tag}",
                "lines": [
                    {"account_code": "5000", "debit": "10.00"},
                    {"account_code": "1000", "credit": "10.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text

        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        codes = [row["code"] for row in tb["accounts"]]
        assert codes.count("1000") == 1
        row = _by_code(tb)["1000"]
        assert row["name_ar"] == "خزينة فرعية خاصة"
        assert row["credit"] == "10.00"
    finally:
        from tests.manual_journal_test_utils import _cleanup_journals

        await _cleanup_journals(tag)
        async with SessionLocal() as session:
            if other_account_id is not None:
                await session.execute(
                    delete(Account).where(Account.id == other_account_id)
                )
            await session.execute(
                delete(AuditLog).where(AuditLog.user_id == other_user_id)
            )
            await session.execute(delete(User).where(User.id == other_user_id))
            await session.execute(delete(Branch).where(Branch.id == other_branch_id))
            await session.commit()


async def test_mizan_html_print_renders(client):
    """format=html returns a printable Arabic A4 page (title + numbers), the
    same payload the JSON endpoint exposes."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-10",
                "lines": [{"drug_id": drug_id, "qty": "5"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026&format=html",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert "text/html" in r.headers["content-type"]
        assert "ميزان المراجعة" in r.text
        assert "43.86" in r.text
        assert "75.00" in r.text

        r = await client.get(
            "/api/v1/accounts/balance-sheet?month=8&year=2026&format=html",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert "text/html" in r.headers["content-type"]
        assert "ميزانية عمومية" in r.text
        assert "18.86" in r.text
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])


async def test_mizan_requires_auth(client):
    """Both ميزان endpoints are reads for any authenticated user — no token,
    no data."""
    for path in ("/api/v1/accounts/trial-balance", "/api/v1/accounts/balance-sheet"):
        r = await client.get(path)
        assert r.status_code == 401, r.text


async def test_mizan_branch_scoped(client):
    """A branch-2 caller sees only branch-2 postings (rolled into the inherited
    branch-1 chart rows by code); branch-1's own postings stay invisible."""
    from app.auth.security import create_access_token
    from app.models import Branch, User

    other_user_id = None
    other_branch_id = None
    tag = _uniq("t9")
    try:
        async with SessionLocal() as session:
            branch = Branch(
                pharmacyid=f"sb{_seq[0]}", mobile=f"9{_seq[0]}", pharname="Other"
            )
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

        other_token = create_access_token(
            str(other_user_id), branch_id=other_branch_id, roles=[], permission_level=9
        )
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {other_token}"},
            json={
                "datee": "2026-08-10",
                "description": f"فرع تاني {tag}",
                "lines": [
                    {"account_code": "5000", "debit": "10.00"},
                    {"account_code": "1000", "credit": "10.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text

        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["branch_id"] == other_branch_id
        assert tb["balanced"] is True
        by_code = _by_code(tb)
        assert by_code["1000"]["credit"] == "10.00"
        assert by_code["5000"]["debit"] == "10.00"
        assert tb["totals"]["debit"] == "10.00"
        assert tb["totals"]["credit"] == "10.00"

        # branch-1 caller never sees branch-2's posting
        token = await _login_token(client)
        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["totals"]["debit"] == "0.00"
    finally:
        from tests.manual_journal_test_utils import _cleanup_journals

        await _cleanup_journals(tag)
        async with SessionLocal() as session:
            await session.execute(
                delete(AuditLog).where(AuditLog.user_id == other_user_id)
            )
            await session.execute(delete(User).where(User.id == other_user_id))
            await session.execute(delete(Branch).where(Branch.id == other_branch_id))
            await session.commit()


async def test_mizan_reconciles_with_subsidiaries_and_balances(client):
    """The ميزان's closing figures agree with the other ledgers that read the
    same journals: 1100 == the receivables grand total, 2000 == the payables
    grand total, and every per-code closing matches the `balances` running
    totals stored by post_journal (same branch, month, year, account)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    customer_id = await _make_customer()
    supplier_id = await _make_supplier()
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
                "payments": [{"method": "credit", "amount": "50.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "datee": "2026-08-12",
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [{"method": "credit", "amount": "114.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        tb = (
            await client.get(
                "/api/v1/accounts/trial-balance?month=8&year=2026",
                headers={"Authorization": f"Bearer {token}"},
            )
        ).json()
        ar = (
            await client.get(
                "/api/v1/receivables", headers={"Authorization": f"Bearer {token}"}
            )
        ).json()
        ap = (
            await client.get(
                "/api/v1/parties/payables", headers={"Authorization": f"Bearer {token}"}
            )
        ).json()
        by_code = _by_code(tb)
        assert by_code["1100"]["closing_balance"] == ar["total"]
        assert by_code["2000"]["closing_balance"] == f"-{ap['total']}"

        async with SessionLocal() as session:
            balances = (
                await session.execute(
                    select(Balance).where(
                        Balance.branch_id == BRANCH_ID,
                        Balance.month == 8,
                        Balance.year == 2026,
                    )
                )
            ).scalars().all()
        by_account = {b.account_id: b for b in balances}
        for code, row in by_code.items():
            ids = await _account_ids_for_code(code)
            total_bal = money_sum(
                [
                    by_account.get(aid).balance if by_account.get(aid) else Decimal("0")
                    for aid in ids
                ]
            )
            assert money_dec(row["closing_balance"]) == total_bal, code
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])
        await _cleanup_party(customer_id)
        await _cleanup_party(supplier_id)


async def _account_ids_for_code(code: str) -> list[int]:
    async with SessionLocal() as session:
        return list(
            (
                await session.execute(
                    select(Account.id).where(
                        Account.branch_id.in_((BRANCH_ID, 1)), Account.code == code
                    )
                )
            ).scalars().all()
        )


def money_sum(amounts) -> Decimal:
    total = Decimal("0")
    for a in amounts:
        total += Decimal(str(a))
    return total


def money_dec(value) -> Decimal:
    return Decimal(str(value))


async def test_trial_balance_empty_period(client):
    """An empty period still returns a balanced ميزان: every chart code is
    listed with zero rows, totals are all 0.00, and balanced is True (a valid
    report, not an error)."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/accounts/trial-balance?month=1&year=1999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    tb = r.json()
    assert tb["balanced"] is True
    assert tb["totals"]["opening_debit"] == "0.00"
    assert tb["totals"]["opening_credit"] == "0.00"
    assert tb["totals"]["debit"] == "0.00"
    assert tb["totals"]["credit"] == "0.00"
    assert tb["totals"]["closing_debit"] == "0.00"
    assert tb["totals"]["closing_credit"] == "0.00"
    assert len(tb["accounts"]) > 0
    assert all(
        r["opening_debit"] == "0.00"
        and r["debit"] == "0.00"
        and r["closing_debit"] == "0.00"
        and r["credit"] == "0.00"
        for r in tb["accounts"]
    )


async def test_mizan_expired_token_is_401(client):
    """A wrong/expired bearer token is rejected exactly like a missing one."""
    for path in ("/api/v1/accounts/trial-balance", "/api/v1/accounts/balance-sheet"):
        r = await client.get(
            path,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert r.status_code == 401, r.text


async def test_trial_balance_date_range_includes_boundaries(client):
    """The range is inclusive: a posting exactly on date_from and one exactly on
    date_to both appear; one the day after date_to does not."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("20.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        for day in ("2026-08-10", "2026-08-31", "2026-09-01"):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "datee": day,
                    "lines": [{"drug_id": drug_id, "qty": "5"}],
                },
            )
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])

        r = await client.get(
            "/api/v1/accounts/trial-balance?date_from=2026-08-10&date_to=2026-08-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        # the Aug 10 and Aug 31 sales are inside the inclusive window,
        # the Sep 1 sale is not
        assert tb["totals"]["debit"] == "150.00"
        assert tb["totals"]["credit"] == "150.00"
    finally:
        await _cleanup_purchase([drug_id], invoice_ids, [])


async def test_trial_balance_inactive_account_keeps_history(client):
    """A deactivated account still aggregates its posted history — the ميزان is
    a ledger report and must never drop a code's money just because the account
    was turned off (the API guards live deactivation of a referenced account, so
    this simulates the legacy-data shape directly)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    tag = _uniq("t12")
    account_id = None
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "code": "5100",
                "name_ar": "مصروفات إضافية",
                "name_en": "Extra Expenses",
                "type": "expense",
            },
        )
        assert r.status_code == 201, r.text
        account_id = r.json()["id"]
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": "2026-08-10",
                "description": f"مصروف جديد {tag}",
                "lines": [
                    {"account_code": "5100", "debit": "20.00"},
                    {"account_code": "1000", "credit": "20.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        # legacy shape: account carries history and is already inactive
        async with SessionLocal() as session:
            await session.execute(
                update(Account).where(Account.id == account_id).values(is_active=False)
            )
            await session.commit()

        r = await client.get(
            "/api/v1/accounts/trial-balance?month=8&year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["balanced"] is True
        row = _by_code(tb)["5100"]
        assert row["debit"] == "20.00"
        assert row["closing_balance"] == "20.00"
        assert tb["totals"]["debit"] == "20.00"
        assert tb["totals"]["credit"] == "20.00"
    finally:
        from tests.manual_journal_test_utils import _cleanup_journals

        await _cleanup_journals(tag)
        async with SessionLocal() as session:
            if account_id is not None:
                await session.execute(
                    delete(Account).where(Account.id == account_id)
                )
                await session.execute(
                    delete(AuditLog).where(
                        AuditLog.entity == "accounts", AuditLog.entity_id == account_id
                    )
                )
            await session.commit()
        await _cleanup_purchase([drug_id], invoice_ids, [])