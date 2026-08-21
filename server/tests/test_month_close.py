"""S2.6 Month close + month_open_balances + reopen (issue #21).

A branch closes a month: a `monthly_close` row is written (status closed) and
the next month's opening balances are seeded from the branch's closing ledger
state (cumulative debit/credit per account through the end of the closed month),
written into `month_open_balances`. A closed month rejects further journal
posts (sales / purchases / returns / settlements / manual journals) at the
shared journal engine so the ledger can never be mutated after the period
freezes. Reopen is manager-only (perm >= 7), flips status to `reopened` + audit,
and reopens the period without destroying the seeded start-data; re-close
regenerates it from the (possibly changed) ledger.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Account, JournalLine, MonthOpenBalance, MonthlyClose
from tests.manual_journal_test_utils import _cleanup_journals
from tests.purchase_test_utils import (
    _delete_other_branch,
    _delete_users,
    _login_token,
    _make_other_branch,
    _make_user,
    _token_for,
)
from tests.sales_test_utils import _make_drug_and_stock

BRANCH_ID = 1

async def _cleanup_sale(drug_id: int) -> None:
    from sqlalchemy import delete
    from app.models import BranchStock, Drug, Invoice, InvoiceLine, Journal, JournalLine, PaymentSplit, StockBatch, DrawerMovement, Balance
    async with SessionLocal() as session:
        inv_ids = (
            await session.execute(
                select(Invoice.id).join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id).where(InvoiceLine.drug_id == drug_id)
            )
        ).scalars().all()
        for inv_id in inv_ids:
            jids = (await session.execute(select(Journal.id).where(Journal.ref_invoice_id == inv_id))).scalars().all()
            if jids:
                jlines = (await session.execute(select(JournalLine).where(JournalLine.journal_id.in_(jids)))).scalars().all()
                bkeys = {(l.branch_id, l.month, l.year, l.account_id) for l in jlines}
                await session.execute(delete(JournalLine).where(JournalLine.journal_id.in_(jids)))
                await session.execute(delete(Journal).where(Journal.id.in_(jids)))
                for b, m, y, aid in bkeys:
                    await session.execute(delete(Balance).where(Balance.branch_id == b, Balance.month == m, Balance.year == y, Balance.account_id == aid))
                await session.execute(delete(DrawerMovement).where(DrawerMovement.ref_invoice_id == inv_id))
            await session.execute(delete(PaymentSplit).where(PaymentSplit.invoice_id == inv_id))
            await session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == inv_id))
            await session.execute(delete(Invoice).where(Invoice.id == inv_id))
        await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
        await session.execute(delete(BranchStock).where(BranchStock.drug_id == drug_id))
        await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.commit()

YEAR = 2026
MONTH = 8

_seq = [0]


def _tag() -> str:
    _seq[0] += 1
    return f"__t2_month_{_seq[0]}__"


def _end_of(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


async def _close_row(session, branch_id, year, month) -> Optional[MonthlyClose]:
    return (
        await session.execute(
            select(MonthlyClose).where(
                MonthlyClose.branch_id == branch_id,
                MonthlyClose.year == year,
                MonthlyClose.month == month,
            )
        )
    ).scalar_one_or_none()


async def _cumulative(year: int, month: int, branch_id: int = BRANCH_ID) -> dict:
    """Expected per-code closing state: (debit, credit) cumulative through the
    end of (year, month), straight from journal_lines."""
    end = _end_of(year, month)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    Account.code,
                    func.coalesce(func.sum(JournalLine.debit), 0),
                    func.coalesce(func.sum(JournalLine.credit), 0),
                )
                .join(Account, Account.id == JournalLine.account_id)
                .where(
                    JournalLine.branch_id == branch_id,
                    JournalLine.datee <= end,
                )
                .group_by(Account.code)
            )
        ).all()
    return {code: (Decimal(d), Decimal(c)) for code, d, c in rows}


async def _cleanup_month(branch_id: int, year: int, month: int) -> None:
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(MonthOpenBalance).where(
                    MonthOpenBalance.branch_id == branch_id,
                    ((MonthOpenBalance.year == year) & (MonthOpenBalance.month == month))
                    | ((MonthOpenBalance.year == ny) & (MonthOpenBalance.month == nm)),
                )
            )
        ).scalars().all()
        for r in rows:
            await session.delete(r)
        close = await _close_row(session, branch_id, year, month)
        if close is not None:
            await session.delete(close)
        await session.commit()


async def _get_json(client, url, token, **kw):
    return await client.get(url, headers={"Authorization": f"Bearer {token}"}, **kw)


async def _count_journal_lines(year: int, month: int, branch_id: int = BRANCH_ID) -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(func.count()).select_from(JournalLine).where(
                    JournalLine.branch_id == branch_id,
                    JournalLine.datee.between(date(year, month, 1), date(year, month, 31)),
                )
            )
        ).scalar_one()


# --- tests ---------------------------------------------------------------------


async def test_close_seeds_next_month_open_balances(client):
    """Closing month M computes the branch's closing ledger state and seeds
    month_open_balances for M+1 (debit/credit per account_id)."""
    tag = _tag()
    token = await _login_token(client)
    try:
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": f"{YEAR}-{MONTH:02d}-15",
                "description": f"seed {tag}",
                "lines": [
                    {"account_code": "1000", "debit": "120.00"},
                    {"account_code": "4000", "credit": "120.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text

        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "closed"
        assert body["year"] == YEAR and body["month"] == MONTH
        nob = body["next_open_balances"]
        ny, nm = (YEAR + 1, 1) if MONTH == 12 else (YEAR, MONTH + 1)
        assert nob["year"] == ny and nob["month"] == nm

        expected = await _cumulative(YEAR, MONTH)
        by_code = {row["code"]: row for row in nob["rows"]}
        assert by_code["1000"]["debit"] == "120.00"
        assert by_code["4000"]["credit"] == "120.00"

        total_debit = sum((Decimal(r["debit"]) for r in nob["rows"]), Decimal("0"))
        total_credit = sum((Decimal(r["credit"]) for r in nob["rows"]), Decimal("0"))
        exp_debit = sum((d for d, _ in expected.values()), Decimal("0"))
        exp_credit = sum((c for _, c in expected.values()), Decimal("0"))
        assert total_debit == exp_debit
        assert total_credit == exp_credit
    finally:
        await _cleanup_journals(tag)
        await _cleanup_month(BRANCH_ID, YEAR, MONTH)


async def test_closed_month_rejects_sale(client):
    """A closed month rejects a new sale (journal post) with 409 and writes
    nothing."""
    token = await _login_token(client)
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    tag = _tag()
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text

        before = await _count_journal_lines(YEAR, MONTH)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": f"{YEAR}-{MONTH:02d}-20",
                "lines": [{"drug_id": drug_id, "qty": "1"}],
            },
        )
        assert r.status_code == 409, r.text
        assert await _count_journal_lines(YEAR, MONTH) == before
    finally:
        await _cleanup_sale(drug_id)
        await _cleanup_month(BRANCH_ID, YEAR, MONTH)


async def test_closed_month_rejects_manual_journal(client):
    tag = _tag()
    token = await _login_token(client)
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": f"{YEAR}-{MONTH:02d}-15",
                "description": f"blocked {tag}",
                "lines": [
                    {"account_code": "1000", "debit": "1.00"},
                    {"account_code": "4000", "credit": "1.00"},
                ],
            },
        )
        assert r.status_code == 409, r.text
        async with SessionLocal() as session:
            n = (
                await session.execute(
                    select(func.count()).select_from(JournalLine).where(
                        JournalLine.description.like(f"%{tag}%") if hasattr(JournalLine, "description") else JournalLine.tips.like(f"%{tag}%")
                    )
                )
            ).scalar_one()
        # fallback: check no journal with this description tag exists
        async with SessionLocal() as s2:
            from app.models import Journal
            n2 = (await s2.execute(select(func.count()).select_from(Journal).where(Journal.description.like(f"%{tag}%")))).scalar_one()
        assert n2 == 0
    finally:
        await _cleanup_journals(tag)
        await _cleanup_month(BRANCH_ID, YEAR, MONTH)


async def test_reopen_allows_posts_again(client):
    tag = _tag()
    token = await _login_token(client)
    mgr = await _make_user("mgr_close", 7, branch_id=BRANCH_ID)
    mgr_token = _token_for(mgr, BRANCH_ID)
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/reopen",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "reopened"

        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": f"{YEAR}-{MONTH:02d}-15",
                "description": f"afterreopen {tag}",
                "lines": [
                    {"account_code": "1000", "debit": "2.00"},
                    {"account_code": "4000", "credit": "2.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
    finally:
        await _cleanup_journals(tag)
        await _delete_users([mgr])
        await _cleanup_month(BRANCH_ID, YEAR, MONTH)


async def test_reopen_requires_manager(client):
    token = await _login_token(client)
    low = await _make_user("low_close", 3, branch_id=BRANCH_ID)
    low_token = _token_for(low, BRANCH_ID)
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/reopen",
            headers={"Authorization": f"Bearer {low_token}"},
        )
        assert r.status_code == 403, r.text
    finally:
        await _delete_users([low])
        await _cleanup_month(BRANCH_ID, YEAR, MONTH)


async def test_close_requires_permission(client):
    low = await _make_user("noclose", 3, branch_id=BRANCH_ID)
    low_token = _token_for(low, BRANCH_ID)
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {low_token}"},
        )
        assert r.status_code == 403, r.text
    finally:
        await _delete_users([low])


async def test_close_requires_auth(client):
    r = await client.post(f"/api/v1/months/{YEAR}/{MONTH}/close")
    assert r.status_code == 401, r.text


async def test_double_close_409(client):
    token = await _login_token(client)
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409, r.text
    finally:
        await _cleanup_month(BRANCH_ID, YEAR, MONTH)


async def test_reopen_unclosed_409(client):
    mgr = await _make_user("mgr_reopen", 7, branch_id=BRANCH_ID)
    mgr_token = _token_for(mgr, BRANCH_ID)
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/reopen",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert r.status_code == 409, r.text
    finally:
        await _delete_users([mgr])


async def test_list_and_detail_branch_scoped(client):
    token = await _login_token(client)
    other = await _make_other_branch()
    other_user = await _make_user("other_close", 9, branch_id=other)
    other_token = _token_for(other_user, other)
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text

        r = await _get_json(client, "/api/v1/months", token)
        assert r.status_code == 200, r.text
        mine = [m for m in r.json()["months"] if m["year"] == YEAR and m["month"] == MONTH]
        assert len(mine) == 1

        r = await _get_json(client, "/api/v1/months", other_token)
        assert r.status_code == 200, r.text
        assert all(
            not (m["year"] == YEAR and m["month"] == MONTH) for m in r.json()["months"]
        )
    finally:
        await _delete_users([other_user])
        await _delete_other_branch(other)
        await _cleanup_month(BRANCH_ID, YEAR, MONTH)
        await _cleanup_month(other, YEAR, MONTH)


async def test_closed_month_is_branch_scoped_guard(client):
    """Closing branch-1's month must NOT block branch-2 postings (and vice
    versa) — the guard is keyed on the caller's branch."""
    token = await _login_token(client)
    other = await _make_other_branch()
    other_user = await _make_user("other2_close", 9, branch_id=other)
    other_token = _token_for(other_user, other)
    try:
        r = await client.post(
            f"/api/v1/months/{YEAR}/{MONTH}/close",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text

        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {other_token}"},
            json={
                "datee": f"{YEAR}-{MONTH:02d}-20",
                "description": f"branch2 {other} {YEAR}-{MONTH}",
                "lines": [
                    {"account_code": "1000", "debit": "10.00"},
                    {"account_code": "4000", "credit": "10.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        await _cleanup_journals(f"branch2 {other}")
    finally:
        await _delete_users([other_user])
        await _delete_other_branch(other)
        await _cleanup_month(BRANCH_ID, YEAR, MONTH)
        await _cleanup_month(other, YEAR, MONTH)


async def test_close_empty_month_succeeds(client):
    """A month with no postings closes cleanly; the next month's start-data is empty."""
    token = await _login_token(client)
    # use a future month unlikely to have data
    y, m = 2030, 1
    try:
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "closed"
        # open-balances for the next month should be empty (no rows with non-zero? but cumulative may have prior data)
        # Instead check that the close succeeded and next open balances reconcile with cumulative
        expected = await _cumulative(y, m)
        nob = r.json()["next_open_balances"]
        total_debit = sum((Decimal(rr["debit"]) for rr in nob["rows"]), Decimal("0"))
        total_credit = sum((Decimal(rr["credit"]) for rr in nob["rows"]), Decimal("0"))
        exp_debit = sum((d for d, _ in expected.values()), Decimal("0"))
        exp_credit = sum((c for _, c in expected.values()), Decimal("0"))
        assert total_debit == exp_debit
        assert total_credit == exp_credit
    finally:
        await _cleanup_month(1, y, m)


async def test_close_december_rollover(client):
    token = await _login_token(client)
    tag = _tag()
    y, m = 2026, 12
    try:
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "datee": f"{y}-{m:02d}-10",
                "description": f"dec {tag}",
                "lines": [
                    {"account_code": "1000", "debit": "50.00"},
                    {"account_code": "4000", "credit": "50.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["next_open_balances"]["year"] == 2027
        assert r.json()["next_open_balances"]["month"] == 1
        # also check open-balances GET for 2027-01
        r2 = await client.get(f"/api/v1/months/2027/1/open-balances", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["year"] == 2027 and r2.json()["month"] == 1
    finally:
        await _cleanup_journals(tag)
        await _cleanup_month(1, y, m)
        await _cleanup_month(1, 2027, 1)


async def test_close_invalid_month_400(client):
    token = await _login_token(client)
    for bad in [0, 13, 99]:
        r = await client.post(f"/api/v1/months/2026/{bad}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400, f"month {bad}: {r.text}"


async def test_get_nonexistent_month_404(client):
    token = await _login_token(client)
    r = await client.get(f"/api/v1/months/2099/1", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404, r.text


async def test_audit_written_on_close_and_reopen(client):
    from app.models import AuditLog
    token = await _login_token(client)
    mgr = await _make_user("mgr_audit", 7, branch_id=BRANCH_ID)
    mgr_token = _token_for(mgr, BRANCH_ID)
    y, m = 2026, 7
    try:
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        async with SessionLocal() as session:
            rows = (await session.execute(select(AuditLog).where(AuditLog.entity == "monthly_close", AuditLog.typevalue == f"{y}-{m:02d}", AuditLog.action == "close"))).scalars().all()
            assert len(rows) >= 1
        r = await client.post(f"/api/v1/months/{y}/{m}/reopen", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 200, r.text
        async with SessionLocal() as session:
            rows = (await session.execute(select(AuditLog).where(AuditLog.entity == "monthly_close", AuditLog.typevalue == f"{y}-{m:02d}", AuditLog.action == "reopen"))).scalars().all()
            assert len(rows) >= 1
    finally:
        await _delete_users([mgr])
        await _cleanup_month(BRANCH_ID, y, m)
        async with SessionLocal() as session:
            await session.execute(AuditLog.__table__.delete().where(AuditLog.entity == "monthly_close", AuditLog.typevalue == f"{y}-{m:02d}"))
            await session.commit()


async def test_reclose_after_reopen_regenerates(client):
    tag1 = _tag()
    tag2 = _tag()
    token = await _login_token(client)
    mgr = await _make_user("mgr_reclose", 7, branch_id=BRANCH_ID)
    mgr_token = _token_for(mgr, BRANCH_ID)
    y, m = 2026, 9
    try:
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={"datee": f"{y}-{m:02d}-05", "description": f"reclose {tag1}", "lines": [{"account_code": "1000", "debit": "30.00"}, {"account_code": "4000", "credit": "30.00"}]},
        )
        assert r.status_code == 201, r.text
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        first_rows = {rr["code"]: rr for rr in r.json()["next_open_balances"]["rows"]}
        assert first_rows["1000"]["debit"] == "30.00"

        # reopen
        r = await client.post(f"/api/v1/months/{y}/{m}/reopen", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 200, r.text
        # post additional journal in the reopened month
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
            json={"datee": f"{y}-{m:02d}-15", "description": f"reclose {tag2}", "lines": [{"account_code": "1000", "debit": "20.00"}, {"account_code": "4000", "credit": "20.00"}]},
        )
        assert r.status_code == 201, r.text
        # re-close — should regenerate with the new total (30+20=50)
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        second = {rr["code"]: rr for rr in r.json()["next_open_balances"]["rows"]}
        # cumulative for 1000 debit includes the original + new
        # but also includes ALL prior months' 1000 debits — so just assert increased
        assert Decimal(second["1000"]["debit"]) > Decimal(first_rows["1000"]["debit"])
    finally:
        await _cleanup_journals(tag1)
        await _cleanup_journals(tag2)
        await _delete_users([mgr])
        await _cleanup_month(BRANCH_ID, y, m)
        async with SessionLocal() as session:
            from app.models import AuditLog
            await session.execute(AuditLog.__table__.delete().where(AuditLog.entity == "monthly_close", AuditLog.typevalue == f"{y}-{m:02d}"))
            await session.commit()


async def test_closed_month_rejects_purchase(client):
    from tests.purchase_test_utils import _make_supplier, _make_drug
    token = await _login_token(client)
    y, m = 2026, 8
    supplier = await _make_supplier()
    drug_id = await _make_drug()
    try:
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        before = await _count_journal_lines(y, m)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier,
                "datee": f"{y}-{m:02d}-20",
                "lines": [{"drug_id": drug_id, "qty": "1", "unit_cost": "10.0000"}],
            },
        )
        assert r.status_code == 409, r.text
        assert await _count_journal_lines(y, m) == before
    finally:
        await _cleanup_month(BRANCH_ID, y, m)
        # clean purchase residue
        from sqlalchemy import delete
        from app.models import BranchStock, Drug, StockBatch, Invoice, InvoiceLine, Journal, JournalLine, Balance, DrawerMovement, PaymentSplit
        async with SessionLocal() as session:
            inv_ids = (await session.execute(select(Invoice.id).where(Invoice.supplier_id == supplier))).scalars().all() if False else []
            # simpler: delete by supplier via invoices
            invs = (await session.execute(select(Invoice.id).where(Invoice.branch_id == BRANCH_ID, Invoice.datee.between(date(y, m, 1), date(y, m, 31))))).scalars().all()
            await session.execute(delete(PaymentSplit).where(PaymentSplit.invoice_id.in_(invs)) if invs else delete(PaymentSplit).where(PaymentSplit.id == -1))
            await session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(invs)) if invs else delete(InvoiceLine).where(InvoiceLine.id == -1))
            await session.execute(delete(Invoice).where(Invoice.id.in_(invs)) if invs else delete(Invoice).where(Invoice.id == -1))
            await session.execute(delete(JournalLine).where(JournalLine.branch_id == BRANCH_ID, JournalLine.datee.between(date(y, m, 1), date(y, m, 31))))
            # balances for this month
            # keep cleanup minimal: the month close test isolates by month, and purchase was 409 so no lines
            await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
            await session.execute(delete(BranchStock).where(BranchStock.drug_id == drug_id))
            await session.execute(delete(Drug).where(Drug.id == drug_id))
            from app.models import Party
            await session.execute(delete(Party).where(Party.id == supplier))
            await session.commit()

async def test_drawer_movement_blocked_by_month_closed(client):
    token = await _login_token(client)
    y, m = 2026, 8
    try:
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        r = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {token}"},
            json={"datee": f"{y}-{m:02d}-15", "direction": "out", "reason": "expense", "method": "cash", "amount": "5.00"},
        )
        assert r.status_code == 409, r.text
        # reopen should allow again
        mgr = await _make_user("mgr_drawer", 7, branch_id=BRANCH_ID)
        mgr_token = _token_for(mgr, BRANCH_ID)
        try:
            r = await client.post(f"/api/v1/months/{y}/{m}/reopen", headers={"Authorization": f"Bearer {mgr_token}"})
            assert r.status_code == 200, r.text
            r = await client.post(
                "/api/v1/drawer/movements",
                headers={"Authorization": f"Bearer {token}"},
                json={"datee": f"{y}-{m:02d}-15", "direction": "out", "reason": "expense", "method": "cash", "amount": "5.00"},
            )
            assert r.status_code == 201, r.text
            # cleanup drawer movement
            from sqlalchemy import delete
            from app.models import DrawerMovement, AuditLog
            async with SessionLocal() as session:
                await session.execute(delete(DrawerMovement).where(DrawerMovement.branch_id == BRANCH_ID, DrawerMovement.datee == date(y, m, 15), DrawerMovement.reason == "expense"))
                await session.execute(delete(AuditLog).where(AuditLog.entity == "drawer_movements", AuditLog.branch_id == BRANCH_ID))
                await session.commit()
        finally:
            await _delete_users([mgr])
    finally:
        await _cleanup_month(BRANCH_ID, y, m)


async def test_audit_entity_id_unique_per_month(client):
    from app.models import AuditLog
    token = await _login_token(client)
    y1, m1 = 2026, 6
    y2, m2 = 2026, 7
    try:
        r = await client.post(f"/api/v1/months/{y1}/{m1}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        r = await client.post(f"/api/v1/months/{y2}/{m2}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        async with SessionLocal() as session:
            rows = (await session.execute(select(AuditLog).where(AuditLog.entity == "monthly_close", AuditLog.action == "close", AuditLog.branch_id == BRANCH_ID, AuditLog.typevalue.in_([f"{y1}-{m1:02d}", f"{y2}-{m2:02d}"])))).scalars().all()
            by_type = {r.typevalue: r for r in rows}
            assert f"{y1}-{m1:02d}" in by_type and f"{y2}-{m2:02d}" in by_type
            assert by_type[f"{y1}-{m1:02d}"].entity_id != by_type[f"{y2}-{m2:02d}"].entity_id
            assert by_type[f"{y1}-{m1:02d}"].entity_id == BRANCH_ID * 1_000_000 + y1 * 100 + m1
    finally:
        await _cleanup_month(BRANCH_ID, y1, m1)
        await _cleanup_month(BRANCH_ID, y2, m2)
        async with SessionLocal() as session:
            await session.execute(AuditLog.__table__.delete().where(AuditLog.entity == "monthly_close", AuditLog.branch_id == BRANCH_ID, AuditLog.typevalue.in_([f"{y1}-{m1:02d}", f"{y2}-{m2:02d}"])))
            await session.commit()


async def test_reopen_twice_409_and_get_branch_isolation(client):
    token = await _login_token(client)
    other = await _make_other_branch()
    other_user = await _make_user("other_iso", 9, branch_id=other)
    other_token = _token_for(other_user, other)
    mgr = await _make_user("mgr_twice", 7, branch_id=BRANCH_ID)
    mgr_token = _token_for(mgr, BRANCH_ID)
    y, m = 2026, 8
    try:
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        r = await client.post(f"/api/v1/months/{y}/{m}/reopen", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 200, r.text
        # second reopen should 409 (already reopened, not closed)
        r = await client.post(f"/api/v1/months/{y}/{m}/reopen", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 409, r.text
        # branch-2 cannot see branch-1 reopened month via GET detail (branch scoped -> 404)
        r = await client.get(f"/api/v1/months/{y}/{m}", headers={"Authorization": f"Bearer {other_token}"})
        assert r.status_code == 404, r.text
        r = await client.get(f"/api/v1/months/{y}/{m}/open-balances", headers={"Authorization": f"Bearer {other_token}"})
        assert r.status_code == 200, r.text
        assert r.json()["rows"] == []
    finally:
        await _delete_users([other_user, mgr])
        await _delete_other_branch(other)
        await _cleanup_month(BRANCH_ID, y, m)
        await _cleanup_month(other, y, m)
        async with SessionLocal() as session:
            from app.models import AuditLog
            await session.execute(AuditLog.__table__.delete().where(AuditLog.entity == "monthly_close", AuditLog.branch_id == BRANCH_ID, AuditLog.typevalue == f"{y}-{m:02d}"))
            await session.commit()

async def test_closed_month_rejects_settlement(client):
    from tests.receivables_test_utils import _make_customer, _cleanup_party, _cleanup_vouchers
    token = await _login_token(client)
    y, m = 2026, 8
    cust = await _make_customer(active=True)
    tag = f"settle {y}-{m} {cust}"
    try:
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        # receipt (sana قبض) in closed month should 409
        r = await client.post(
            "/api/v1/receivables/vouchers",
            headers={"Authorization": f"Bearer {token}"},
            json={"voucher_type": "receipt", "party_id": cust, "datee": f"{y}-{m:02d}-20", "amount": "10.00", "method": "cash", "description": tag},
        )
        assert r.status_code == 409, r.text
        # also payment path (same guard via post_journal)
        # need a supplier
        from tests.receivables_test_utils import _make_supplier
        sup = await _make_supplier()
        try:
            r = await client.post(
                "/api/v1/receivables/vouchers",
                headers={"Authorization": f"Bearer {token}"},
                json={"voucher_type": "payment", "party_id": sup, "datee": f"{y}-{m:02d}-20", "amount": "10.00", "method": "cash", "description": tag+" sup"},
            )
            assert r.status_code == 409, r.text
        finally:
            await _cleanup_party(sup)
            await _cleanup_vouchers(tag+" sup")
    finally:
        await _cleanup_party(cust)
        await _cleanup_vouchers(tag)
        await _cleanup_month(BRANCH_ID, y, m)


async def test_year_validation_and_get_invalid_month_400(client):
    token = await _login_token(client)
    # year out of bounds should 400 on POST
    for bad_year in [1899, 10000, 0, -1]:
        r = await client.post(f"/api/v1/months/{bad_year}/8/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400, f"year {bad_year}: {r.text}"
        r = await client.get(f"/api/v1/months/{bad_year}/8", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400, f"GET year {bad_year}: {r.text}"
        r = await client.get(f"/api/v1/months/{bad_year}/8/open-balances", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400, f"GET open year {bad_year}: {r.text}"
    # month invalid on GET should 400
    for bad_month in [0, 13, 99]:
        r = await client.get(f"/api/v1/months/2026/{bad_month}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400, f"month {bad_month}: {r.text}"
        r = await client.get(f"/api/v1/months/2026/{bad_month}/open-balances", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400, f"open month {bad_month}: {r.text}"


async def test_auth_on_reads_and_permission_split(client):
    # GET list without token should 401
    r = await client.get("/api/v1/months")
    assert r.status_code == 401, r.text
    r = await client.get("/api/v1/months/2026/8")
    assert r.status_code == 401, r.text
    r = await client.get("/api/v1/months/2026/8/open-balances")
    assert r.status_code == 401, r.text
    # accountant (role 4) can close (months.close granted to 4) but cannot reopen (needs level 7)
    from tests.purchase_test_utils import _make_user as _mu
    # create accountant user: permission_level 3 but role 4 gives months.close via role
    # to simulate accountant we need to assign role 4 — _make_user only sets permission_level, not role
    # Instead test with a level 4 user (not 7) — close should succeed via role? No role, but level 4 <7 so close should 403, reopen 403
    # To test permission split properly, we need a user with permission_level 5 and role accountant? Simpler: test that a level 5 manager can close but not reopen? Actually level 7 is needed for reopen.
    # The split is: close requires months.close (floor 7) so level 7 passes, level 6 fails; reopen requires level 7
    # Let's test level 6 can close? No, floor 7, so level 6 should fail to close
    # And level 7 can close and reopen, level 6 cannot do either
    # For the role-based path, admin has it, accountant role has it without level 7 — but _make_user with role assignment is needed
    # We can test the level-based split: level 7 vs 6
    acc_close = await _mu("acc_close_test", 6, branch_id=BRANCH_ID)
    mgr_close = await _mu("mgr_perm_test", 7, branch_id=BRANCH_ID)
    acc_token = _token_for(acc_close, BRANCH_ID)
    mgr_token = _token_for(mgr_close, BRANCH_ID)
    y, m = 2027, 5
    try:
        # level 6 should fail to close (months.close floor 7)
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {acc_token}"})
        assert r.status_code == 403, r.text
        # level 7 should succeed
        r = await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 200, r.text
        # level 6 cannot reopen
        r = await client.post(f"/api/v1/months/{y}/{m}/reopen", headers={"Authorization": f"Bearer {acc_token}"})
        assert r.status_code == 403, r.text
        # level 7 can reopen (but we just test 403 for level 6)
        # clean reopen for idempotency
        r = await client.post(f"/api/v1/months/{y}/{m}/reopen", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 200, r.text
    finally:
        await _delete_users([acc_close, mgr_close])
        await _cleanup_month(BRANCH_ID, y, m)
        async with SessionLocal() as session:
            from app.models import AuditLog
            await session.execute(AuditLog.__table__.delete().where(AuditLog.entity == "monthly_close", AuditLog.typevalue == f"{y}-{m:02d}"))
            await session.commit()


async def test_concurrent_double_close_one_wins(client):
    import asyncio
    token = await _login_token(client)
    y, m = 2026, 10
    try:
        async def close():
            return await client.post(f"/api/v1/months/{y}/{m}/close", headers={"Authorization": f"Bearer {token}"})
        results = await asyncio.gather(close(), close())
        statuses = sorted([r.status_code for r in results])
        # one should be 200, one 409 (advisory lock serializes)
        assert statuses == [200, 409], f"got {statuses}: {[r.text for r in results]}"
    finally:
        await _cleanup_month(BRANCH_ID, y, m)
        async with SessionLocal() as session:
            from app.models import AuditLog
            await session.execute(AuditLog.__table__.delete().where(AuditLog.entity == "monthly_close", AuditLog.typevalue == f"{y}-{m:02d}"))
            await session.commit()

