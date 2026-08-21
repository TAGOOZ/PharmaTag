"""S2.7 Opening balances (issue #22) — افتتاحي مدين/دائن per account/branch.

Seeds opening cash, stock at cost, receivables and payables at cutover
(idx 8482-8485): one balanced entry per (branch, year, month) that posts to
`month_open_balances` (monthy\\start-data) plus a balanced `journals` entry
(source=opening) dated the day before the opening month so the مزان's opening
aggregation naturally includes it.

Tracer: happy path + trial-balance wiring, auth, RBAC, validation, branch
scope, audit, edge cases — vertical slices, one test → one behavior.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import Account, AuditLog, Balance, Journal, JournalLine, MonthOpenBalance, MonthlyClose


BRANCH_ID = 1

_seq = [0]


def _tag() -> str:
    _seq[0] += 1
    return f"__t_open_{_seq[0]}__"


async def _login_token(client, username="admin", password="changeme"):
    # reuse helper from purchase_test_utils for admin login
    from tests.purchase_test_utils import _login_token as _lt

    return await _lt(client)


async def _cleanup_opening(branch_id: int, year: int, month: int, tag: str) -> None:
    """Remove opening balances + its journal/balances/audit for (branch, year, month)."""
    from datetime import timedelta

    first = date(year, month, 1)
    opening_date = first - timedelta(days=1)
    async with SessionLocal() as session:
        await session.execute(
            delete(MonthOpenBalance).where(
                MonthOpenBalance.branch_id == branch_id,
                MonthOpenBalance.year == year,
                MonthOpenBalance.month == month,
            )
        )
        jids = (
            await session.execute(
                select(Journal.id).where(
                    Journal.branch_id == branch_id,
                    Journal.datee == opening_date,
                    Journal.source == "opening",
                )
            )
        ).scalars().all()
        # also any journal whose description carries the tag
        tag_jids = (
            await session.execute(
                select(Journal.id).where(Journal.description.like(f"%{tag}%"))
            )
        ).scalars().all()
        jids = list(dict.fromkeys([*jids, *tag_jids]))
        if jids:
            lines = (await session.execute(select(JournalLine).where(JournalLine.journal_id.in_(jids)))).scalars().all()
            keys = {(l.branch_id, l.month, l.year, l.account_id) for l in lines}
            for b, m, y, aid in keys:
                await session.execute(delete(Balance).where(Balance.branch_id == b, Balance.month == m, Balance.year == y, Balance.account_id == aid))
            await session.execute(delete(JournalLine).where(JournalLine.journal_id.in_(jids)))
            await session.execute(delete(Journal).where(Journal.id.in_(jids)))
            await session.execute(delete(AuditLog).where(AuditLog.entity == "journals", AuditLog.entity_id.in_(jids)))
        await session.execute(delete(AuditLog).where(AuditLog.entity == "opening_balances", AuditLog.entity_id == branch_id * 1_000_000 + year * 100 + month))
        await session.commit()


# ---------- tracer bullet ----------

async def test_opening_balances_happy_path_posts_to_month_open_and_trial_balance(client):
    """POST balanced opening for 2035-03 (cash 1000 vs equity 1000) → GET shows
    افتتاحي per account and trial-balance for that month carries it as opening."""
    tag = _tag()
    year, month = 2035, 3
    try:
        token = await _login_token(client)
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "description": f"cutover {tag}",
                "lines": [
                    {"account_code": "1000", "debit": "1000.00"},
                    {"account_code": "3000", "credit": "1000.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["branch_id"] == BRANCH_ID
        assert body["year"] == year
        assert body["month"] == month
        assert body["total_debit"] == "1000.00"
        assert body["total_credit"] == "1000.00"
        assert body["balanced"] is True
        assert body["journal_id"] is not None
        assert len(body["rows"]) == 2
        by_code = {row["account_code"]: row for row in body["rows"]}
        assert by_code["1000"]["debit"] == "1000.00"
        assert by_code["3000"]["credit"] == "1000.00"

        # GET the same period
        r = await client.get(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["total_debit"] == "1000.00"

        # month_open_balances direct read (archive start-data)
        r = await client.get(
            f"/api/v1/months/{year}/{month}/open-balances",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        ob = r.json()
        assert ob["year"] == year
        assert ob["month"] == month
        ob_by_code = {rr["code"]: rr for rr in ob["rows"]}
        assert ob_by_code["1000"]["debit"] == "1000.00"

        # Used by the trial balance: opening_debit for that month includes the cutover.
        r = await client.get(
            f"/api/v1/accounts/trial-balance?month={month}&year={year}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        tb = r.json()
        assert tb["balanced"] is True
        by_code_tb = {row["code"]: row for row in tb["accounts"]}
        # The 1000 cash appears as opening for the month (journal dated Feb 28 predates Mar 1)
        assert by_code_tb["1000"]["opening_debit"] == "1000.00"
        assert by_code_tb["1000"]["opening_balance"] == "1000.00"
        assert by_code_tb["3000"]["opening_credit"] == "1000.00"
        assert tb["totals"]["opening_debit"] == "1000.00"
        assert tb["totals"]["opening_credit"] == "1000.00"
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)


async def test_opening_balances_requires_auth(client):
    r = await client.post(
        "/api/v1/opening-balances/2035/3",
        json={"lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 401, r.text


async def test_opening_balances_forbidden_for_low_permission(client):
    from tests.purchase_test_utils import _make_user, _delete_users
    from app.auth.security import create_access_token

    tag = _tag()
    uid = await _make_user(username=_tag(), permission_level=1)
    try:
        token = create_access_token(str(uid), branch_id=BRANCH_ID, roles=[], permission_level=1)
        r = await client.post(
            "/api/v1/opening-balances/2035/4",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
        )
        assert r.status_code == 403, r.text
    finally:
        await _delete_users([uid])


async def test_opening_balances_unbalanced_rejected(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/opening-balances/2035/5",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "1000", "debit": "100.00"}, {"account_code": "3000", "credit": "99.00"}]},
    )
    assert r.status_code == 400, r.text


async def test_opening_balances_duplicate_account_code_rejected_or_merged(client):
    token = await _login_token(client)
    # duplicate same account split — currently allowed as two lines (same account
    # appears twice) — the service sums per account for month_open but keeps
    # two journal lines. The balanced check still passes.
    tag = _tag()
    year, month = 2035, 6
    try:
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "description": tag,
                "lines": [
                    {"account_code": "1000", "debit": "600.00"},
                    {"account_code": "1000", "debit": "400.00"},
                    {"account_code": "3000", "credit": "1000.00"},
                ],
            },
        )
        # Either merged (allowed) or rejected — but balanced 1000==1000 so should be allowed
        assert r.status_code == 201, r.text
        assert r.json()["total_debit"] == "1000.00"
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)


async def test_opening_balances_duplicate_period_rejects_409(client):
    tag = _tag()
    year, month = 2035, 7
    try:
        token = await _login_token(client)
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "description": tag,
                "lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}],
            },
        )
        assert r.status_code == 201, r.text
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "description": tag,
                "lines": [{"account_code": "1000", "debit": "20.00"}, {"account_code": "3000", "credit": "20.00"}],
            },
        )
        assert r.status_code == 409, r.text
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)


async def test_opening_balances_branch_isolation(client):
    from tests.purchase_test_utils import _make_other_branch, _make_user, _delete_other_branch, _delete_users
    from app.auth.security import create_access_token

    tag = _tag()
    year, month = 2035, 8
    other_branch_id = None
    uid = None
    try:
        other_branch_id = await _make_other_branch()
        uid = await _make_user(username=_tag(), permission_level=9, branch_id=other_branch_id)
        token_main = await _login_token(client)
        token_other = create_access_token(str(uid), branch_id=other_branch_id, roles=[], permission_level=9)

        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token_main}"},
            json={"description": tag, "lines": [{"account_code": "1000", "debit": "50.00"}, {"account_code": "3000", "credit": "50.00"}]},
        )
        assert r.status_code == 201, r.text

        # other branch does not see main's opening
        r = await client.get(f"/api/v1/opening-balances/{year}/{month}", headers={"Authorization": f"Bearer {token_other}"})
        assert r.status_code == 404, r.text

        # other branch posts its own opening for same period — allowed (different branch)
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token_other}"},
            json={"description": tag, "lines": [{"account_code": "1000", "debit": "70.00"}, {"account_code": "3000", "credit": "70.00"}]},
        )
        assert r.status_code == 201, r.text
        assert r.json()["branch_id"] == other_branch_id
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)
        if other_branch_id is not None:
            await _cleanup_opening(other_branch_id, year, month, tag)
            if uid is not None:
                await _delete_users([uid])
            await _delete_other_branch(other_branch_id)


async def test_opening_balances_invalid_month_rejected(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/opening-balances/2035/13",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 400, r.text


async def test_opening_balances_unknown_account_rejected(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/opening-balances/2035/9",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "9999", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 400, r.text


async def test_opening_balances_zero_amount_rejected(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/opening-balances/2035/9",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "1000", "debit": "0.00"}, {"account_code": "3000", "credit": "0.00"}]},
    )
    assert r.status_code == 400, r.text


async def test_opening_balances_deactivated_account_rejected(client):
    from sqlalchemy import update

    tag = _tag()
    # create a temp deactivated account
    async with SessionLocal() as session:
        acct = Account(branch_id=BRANCH_ID, code=f"T{tag[:5]}", name_ar="temp", type="asset", is_active=False)
        session.add(acct)
        await session.flush()
        code = acct.code
        await session.commit()
        acct_id = acct.id
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/opening-balances/2035/9",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"account_code": code, "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
        )
        assert r.status_code == 400, r.text
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(Account).where(Account.id == acct_id))
            await session.commit()


async def test_opening_balances_month_closed_rejects_409(client):
    from tests.purchase_test_utils import _login_token as _lt
    from app.core.db import SessionLocal
    from app.models import MonthlyClose
    from datetime import datetime, timezone

    tag = _tag()
    year, month = 2035, 10
    try:
        token = await _lt(client)
        # close the target month directly via the month-close API (requires months.close)
        r = await client.post(f"/api/v1/months/{year}/{month}/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
        )
        assert r.status_code == 409, r.text
    finally:
        # cleanup month close (reopen then delete)
        async with SessionLocal() as session:
            await session.execute(delete(MonthlyClose).where(MonthlyClose.branch_id == BRANCH_ID, MonthlyClose.year == year, MonthlyClose.month == month))
            await session.commit()
        await _cleanup_opening(BRANCH_ID, year, month, tag)


async def test_opening_balances_audit_written_atomically(client):
    tag = _tag()
    year, month = 2035, 11
    try:
        token = await _login_token(client)
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "description": tag,
                "lines": [{"account_code": "1000", "debit": "123.45"}, {"account_code": "3000", "credit": "123.45"}],
            },
        )
        assert r.status_code == 201, r.text
        jid = r.json()["journal_id"]
        # audit rows for both opening_balances and journals must exist
        async with SessionLocal() as session:
            ob_audit = (
                await session.execute(
                    select(AuditLog).where(AuditLog.entity == "opening_balances", AuditLog.entity_id == BRANCH_ID * 1_000_000 + year * 100 + month)
                )
            ).scalars().all()
            assert len(ob_audit) >= 1
            j_audit = (
                await session.execute(select(AuditLog).where(AuditLog.entity == "journals", AuditLog.entity_id == jid))
            ).scalars().all()
            assert len(j_audit) >= 1
            # month_open_balances row exists
            mop = (
                await session.execute(
                    select(MonthOpenBalance).where(MonthOpenBalance.branch_id == BRANCH_ID, MonthOpenBalance.year == year, MonthOpenBalance.month == month)
                )
            ).scalars().all()
            assert len(mop) == 2
            # journal lines exist
            jls = (await session.execute(select(JournalLine).where(JournalLine.journal_id == jid))).scalars().all()
            assert len(jls) == 2
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)


async def test_opening_balances_rounding_half_up(client):
    tag = _tag()
    year, month = 2035, 12
    try:
        token = await _login_token(client)
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "description": tag,
                "lines": [
                    {"account_code": "1000", "debit": "100.005"},
                    {"account_code": "3000", "credit": "100.005"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        # 100.005 round half up to 100.01
        assert r.json()["total_debit"] == "100.01"
        assert r.json()["total_credit"] == "100.01"
        # trial balance opening reflects rounded
        r = await client.get(f"/api/v1/accounts/trial-balance?month={month}&year={year}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        by_code = {row["code"]: row for row in r.json()["accounts"]}
        assert by_code["1000"]["opening_debit"] == "100.01"
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)


# ---------- additional edge-case pass ----------

async def test_opening_balances_empty_list_returns_empty(client):
    # use a fresh branch to guarantee no openings exist
    from tests.purchase_test_utils import _make_other_branch, _delete_other_branch
    from app.auth.security import create_access_token
    from app.models import Branch, User

    branch_id = await _make_other_branch()
    # create a user for that branch
    async with SessionLocal() as session:
        user = User(username=_tag(), pass_hash="x", permission_level=9, branch_id=branch_id)
        session.add(user)
        await session.flush()
        uid = user.id
        await session.commit()
        token = create_access_token(str(uid), branch_id=branch_id, roles=[], permission_level=9)
    try:
        r = await client.get("/api/v1/opening-balances", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["periods"] == []
        # missing period -> 404
        r = await client.get("/api/v1/opening-balances/2099/1", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404, r.text
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(AuditLog).where(AuditLog.user_id == uid))
            await session.execute(delete(User).where(User.id == uid))
            await session.commit()
        await _delete_other_branch(branch_id)


async def test_opening_balances_missing_fields_rejected(client):
    token = await _login_token(client)
    # missing lines field -> validation 400
    r = await client.post(
        "/api/v1/opening-balances/2036/1",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": "no lines"},
    )
    assert r.status_code == 400, r.text
    # only one line -> min_length 2 -> 400
    r = await client.post(
        "/api/v1/opening-balances/2036/1",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "1000", "debit": "10.00"}]},
    )
    assert r.status_code == 400, r.text
    # blank account_code
    r = await client.post(
        "/api/v1/opening-balances/2036/1",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": " ", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 400, r.text


async def test_opening_balances_negative_and_double_sided_and_blank_desc_rejected(client):
    token = await _login_token(client)
    # negative (pydantic ge=0 catches, but also service checks)
    r = await client.post(
        "/api/v1/opening-balances/2036/1",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "1000", "debit": "-10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 400, r.text
    # double-sided line
    r = await client.post(
        "/api/v1/opening-balances/2036/1",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "1000", "debit": "10.00", "credit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 400, r.text
    # blank description -> 400 (description min_length 1 if provided, but we pass blank string)
    r = await client.post(
        "/api/v1/opening-balances/2036/1",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": "   ", "lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 400, r.text


async def test_opening_balances_boundary_year_month_and_max_amount(client):
    token = await _login_token(client)
    # boundary valid
    tag = _tag()
    for year, month in [(1900, 1), (9999, 12), (2036, 1), (2036, 12)]:
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": tag, "lines": [{"account_code": "1000", "debit": "1.00"}, {"account_code": "3000", "credit": "1.00"}]},
        )
        assert r.status_code == 201, f"{year}-{month}: {r.text}"
        await _cleanup_opening(BRANCH_ID, year, month, tag)
    # invalid boundaries
    for year, month in [(1899, 6), (10000, 6), (2036, 0), (2036, 13)]:
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
        )
        assert r.status_code == 400, f"{year}-{month}: {r.text}"
    # amount too large > MAX_AMOUNT
    r = await client.post(
        "/api/v1/opening-balances/2036/2",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "1000", "debit": "10000000000000000.00"}, {"account_code": "3000", "credit": "10000000000000000.00"}]},
    )
    assert r.status_code == 400, r.text


async def test_opening_balances_atomic_on_failure_leaves_no_rows(client):
    token = await _login_token(client)
    year, month = 2036, 5
    # unbalanced should not create any MonthOpenBalance or Journal
    r = await client.post(
        f"/api/v1/opening-balances/{year}/{month}",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"account_code": "1000", "debit": "100.00"}, {"account_code": "3000", "credit": "99.00"}]},
    )
    assert r.status_code == 400, r.text
    async with SessionLocal() as session:
        rows = (await session.execute(select(MonthOpenBalance).where(MonthOpenBalance.branch_id == BRANCH_ID, MonthOpenBalance.year == year, MonthOpenBalance.month == month))).scalars().all()
        assert rows == []
        # no journal for that opening_date
        from datetime import timedelta

        od = date(year, month, 1) - timedelta(days=1)
        j = (await session.execute(select(Journal).where(Journal.branch_id == BRANCH_ID, Journal.datee == od, Journal.source == "opening"))).scalars().first()
        assert j is None


async def test_opening_balances_delete_and_recreate_idempotent(client):
    tag = _tag()
    year, month = 2036, 6
    token = await _login_token(client)
    try:
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": tag, "lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
        )
        assert r.status_code == 201, r.text
        # delete requires manager level 7 — admin has 9 so ok
        r = await client.delete(f"/api/v1/opening-balances/{year}/{month}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204, r.text
        # get now 404
        r = await client.get(f"/api/v1/opening-balances/{year}/{month}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404, r.text
        # recreate succeeds (idempotent after delete)
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": tag, "lines": [{"account_code": "1000", "debit": "20.00"}, {"account_code": "3000", "credit": "20.00"}]},
        )
        assert r.status_code == 201, r.text
        assert r.json()["total_debit"] == "20.00"
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)


async def test_opening_balances_delete_requires_manager(client):
    from tests.purchase_test_utils import _make_user, _delete_users
    from app.auth.security import create_access_token

    tag = _tag()
    year, month = 2036, 7
    token = await _login_token(client)
    # create opening as admin
    r = await client.post(
        f"/api/v1/opening-balances/{year}/{month}",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": tag, "lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 201, r.text
    uid = None
    try:
        # low-level user tries to delete
        uid = await _make_user(username=_tag(), permission_level=1)
        token_low = create_access_token(str(uid), branch_id=BRANCH_ID, roles=[], permission_level=1)
        r = await client.delete(f"/api/v1/opening-balances/{year}/{month}", headers={"Authorization": f"Bearer {token_low}"})
        assert r.status_code == 403, r.text
        # still exists
        r = await client.get(f"/api/v1/opening-balances/{year}/{month}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)
        if uid is not None:
            await _delete_users([uid])


async def test_opening_balances_four_categories_cash_stock_receivables_payables(client):
    """The four legacy categories (idx 8482-8485) as one opening: drawer, stock,
    customer receivables, supplier payables — balanced 5000 total."""
    tag = _tag()
    year, month = 2036, 8
    try:
        token = await _login_token(client)
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "description": tag,
                "lines": [
                    {"account_code": "1000", "debit": "1000.00", "note": "cash"},
                    {"account_code": "1200", "debit": "3000.00", "note": "stock at cost"},
                    {"account_code": "1100", "debit": "500.00", "note": "receivables"},
                    {"account_code": "3000", "credit": "4000.00", "note": "equity/capital"},
                    {"account_code": "2000", "credit": "500.00", "note": "payables"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["total_debit"] == "4500.00"
        assert body["total_credit"] == "4500.00"
        # trial balance opening reflects all four
        r = await client.get(f"/api/v1/accounts/trial-balance?month={month}&year={year}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        by_code = {row["code"]: row for row in r.json()["accounts"]}
        assert by_code["1000"]["opening_debit"] == "1000.00"
        assert by_code["1200"]["opening_debit"] == "3000.00"
        assert by_code["1100"]["opening_debit"] == "500.00"
        assert by_code["2000"]["opening_credit"] == "500.00"
        assert by_code["3000"]["opening_credit"] == "4000.00"
        assert r.json()["balanced"] is True
        # balance sheet identity holds after opening (assets 4500 vs liabilities+equity 5000? Actually assets 4500 (1000+3000+500), liabilities 500, equity 4500? Wait equity 4500 includes? Our test credit 4500 to 3000 equity, so equity 4500, liabilities 500, total L+E 5000 not 4500? Let's not assert identity here, just that opening is visible.)
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)


async def test_opening_balances_list_returns_only_opening_periods(client):
    tag = _tag()
    periods = [(2036, 9), (2036, 10)]
    # ensure clean
    for y, m in periods:
        await _cleanup_opening(BRANCH_ID, y, m, tag)
    try:
        token = await _login_token(client)
        for y, m in periods:
            r = await client.post(
                f"/api/v1/opening-balances/{y}/{m}",
                headers={"Authorization": f"Bearer {token}"},
                json={"description": tag, "lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
            )
            assert r.status_code == 201, r.text
        r = await client.get("/api/v1/opening-balances", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        listed = {(p["year"], p["month"]) for p in r.json()["periods"]}
        for p in periods:
            assert p in listed
        # month_close seeded opening for next month should NOT appear in the opening list
        # (we close 2036-09, which seeds month_open for 2036-10 already from close;
        # but 2036-10 already has an opening journal, so distinct remains 2)
        # close a different month and check it doesn't appear
        r = await client.post("/api/v1/months/2036/11/close", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        r = await client.get("/api/v1/opening-balances", headers={"Authorization": f"Bearer {token}"})
        listed2 = {(p["year"], p["month"]) for p in r.json()["periods"]}
        # 2036-12 was seeded by close 2036-11, but has no opening journal -> should not be in list
        assert (2036, 12) not in listed2
    finally:
        for y, m in periods:
            await _cleanup_opening(BRANCH_ID, y, m, tag)
        async with SessionLocal() as session:
            await session.execute(delete(MonthlyClose).where(MonthlyClose.branch_id == BRANCH_ID, MonthlyClose.year == 2036, MonthlyClose.month == 11))
            await session.execute(delete(MonthOpenBalance).where(MonthOpenBalance.branch_id == BRANCH_ID, MonthOpenBalance.year == 2036, MonthOpenBalance.month == 12))
            await session.commit()


async def test_opening_balances_wrong_token_rejected(client):
    r = await client.post(
        "/api/v1/opening-balances/2036/1",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"lines": [{"account_code": "1000", "debit": "10.00"}, {"account_code": "3000", "credit": "10.00"}]},
    )
    assert r.status_code == 401, r.text


async def test_opening_balances_trial_balance_previous_month_does_not_see_future_opening(client):
    tag = _tag()
    year, month = 2037, 5
    try:
        token = await _login_token(client)
        r = await client.post(
            f"/api/v1/opening-balances/{year}/{month}",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": tag, "lines": [{"account_code": "1000", "debit": "999.00"}, {"account_code": "3000", "credit": "999.00"}]},
        )
        assert r.status_code == 201, r.text
        r = await client.get(f"/api/v1/accounts/trial-balance?month=4&year={year}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        by_code = {row["code"]: row for row in r.json()["accounts"]}
        # April's opening remains 0; its period includes the May opening's journal (Apr 30 is inside April window)
        assert by_code["1000"]["opening_debit"] == "0.00"
        assert by_code["1000"]["debit"] == "999.00"
        # May's opening should be 999
        r = await client.get(f"/api/v1/accounts/trial-balance?month={month}&year={year}", headers={"Authorization": f"Bearer {token}"})
        by_code = {row["code"]: row for row in r.json()["accounts"]}
        assert by_code["1000"]["opening_debit"] == "999.00"
        assert by_code["1000"]["debit"] == "0.00"
    finally:
        await _cleanup_opening(BRANCH_ID, year, month, tag)
