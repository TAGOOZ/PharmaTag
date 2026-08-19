"""S2.2 manual journal entries (ticket #17): manager posts a balanced قيد.

The `/api/v1/journals/manual` surface lets a journals.manage holder post a
balanced manual journal (القيود اليدوية, FormAccAddQueed) that lands on the
journal engine exactly like any money document: a `journals` row (source
`manual`) + balanced `journal_lines` + `balances` + `audit_log`, plus a
`manual_journal_entries` reference row linking the ledger workflow. Imbalanced
entries are rejected with nothing half-written; accounts must exist and be
active; posting is branch-scoped; a posted entry can be reversed (manager-only,
offsetting balanced journal + audit, A07-style).
"""
from datetime import date
from decimal import Decimal

import asyncio
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    DailyClose,
    Journal,
    JournalLine,
    ManualJournalEntry,
    user_roles_table,
)
from tests.manual_journal_test_utils import (
    _cleanup_journals,
    _entry_date,
    _login_token,
    _uniq,
)


async def _post(client, token, *, lines, description, datee=None):
    return await client.post(
        "/api/v1/journals/manual",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "datee": datee or _entry_date(),
            "description": description,
            "lines": lines,
        },
    )


async def test_post_balanced_manual_journal_round_trips(client):
    """A manager posts a balanced قيد: the API returns the entry, and the DB
    holds a journals row (source manual) + balanced lines + balances + audit +
    a manual_journal_entries reference linking the ledger workflow."""
    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        description=f"pay rent {tag}",
        lines=[
            {"account_code": "5000", "debit": "150.50"},
            {"account_code": "1000", "credit": "150.50"},
        ],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["description"] == f"pay rent {tag}"
    assert body["source"] == "manual"
    assert isinstance(body["entry_no"], int) and body["entry_no"] > 0
    assert body["branch_id"] == 1
    assert body["datee"] == _entry_date()
    assert body["total"] == "150.50"

    by_code = {l["account_code"]: l for l in body["lines"]}
    assert by_code["5000"]["debit"] == "150.50"
    assert by_code["5000"]["credit"] == "0.00"
    assert by_code["1000"]["credit"] == "150.50"
    assert by_code["1000"]["debit"] == "0.00"

    entry_id = body["id"]
    journal_id = body["journal_id"]
    try:
        async with SessionLocal() as session:
            journal = await session.get(Journal, journal_id)
            assert journal is not None
            assert journal.branch_id == 1
            assert journal.source == "manual"
            assert journal.entry_no == body["entry_no"]
            assert journal.datee.isoformat() == _entry_date()
            assert journal.created_by is not None

            lines = (
                await session.execute(
                    select(JournalLine).where(JournalLine.journal_id == journal_id)
                )
            ).scalars().all()
            assert len(lines) == 2
            debits = sum(l.debit for l in lines)
            credits = sum(l.credit for l in lines)
            assert debits == Decimal("150.50") == credits
            assert all(l.creditdebit in ("debit", "credit") for l in lines)

            balances = (
                await session.execute(
                    select(Balance).where(
                        Balance.branch_id == 1,
                        Balance.month == date.today().month,
                        Balance.year == date.today().year,
                    )
                )
            ).scalars().all()
            by_account = {b.account_id: b for b in balances}
            account_ids = {l.account_id for l in lines}
            assert set(by_account) & account_ids == account_ids
            for line in lines:
                bal = by_account[line.account_id]
                assert bal.balance == line.debit - line.credit

            audit_rows = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity == "journals",
                        AuditLog.entity_id == journal_id,
                    )
                )
            ).scalars().all()
            assert len(audit_rows) == 1

            entry = await session.get(ManualJournalEntry, entry_id)
            assert entry is not None
            assert entry.journal_id == journal_id
            assert entry.branch_id == 1
            assert entry.amount == Decimal("150.50")
            assert entry.source_file == "manual"
    finally:
        await _cleanup_journals(tag)


async def test_list_and_detail_return_the_entry_with_lines(client):
    """GET /manual lists the branch's manual entries (newest first) and
    GET /manual/{id} returns the entry + its lines with account names."""
    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        description=f"second entry {tag}",
        lines=[
            {"account_code": "3000", "debit": "100.00"},
            {"account_code": "1000", "credit": "100.00"},
        ],
    )
    entry_id = r.json()["id"]
    try:
        g = await client.get(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200, g.text
        assert any(e["id"] == entry_id for e in g.json()["entries"])

        d = await client.get(
            f"/api/v1/journals/manual/{entry_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert d.status_code == 200, d.text
        assert d.json()["id"] == entry_id
        codes = {l["account_code"] for l in d.json()["lines"]}
        assert codes == {"3000", "1000"}
        assert all(l["account_name"] for l in d.json()["lines"])
    finally:
        await _cleanup_journals(tag)


async def test_imbalanced_entry_is_rejected_with_nothing_half_written(client):
    """SUM(debit) != SUM(credit) is a 400 and rolls back everything — no
    journal, lines, balances, audit, or manual entry survives."""
    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        description=f"off balance {tag}",
        lines=[
            {"account_code": "5000", "debit": "100.00"},
            {"account_code": "1000", "credit": "99.99"},
        ],
    )
    assert r.status_code == 400, r.text
    assert "balanced" in r.json()["detail"]
    async with SessionLocal() as session:
        leftover = (
            await session.execute(
                select(Journal.id).where(
                    Journal.description.like(f"%{tag}%")
                )
            )
        ).scalars().all()
        entries = (
            await session.execute(
                select(ManualJournalEntry).join(
                    Journal, Journal.id == ManualJournalEntry.journal_id
                ).where(Journal.description.like(f"%{tag}%"))
            )
        ).scalars().all()
        assert leftover == []
        assert entries == []


async def test_unknown_and_inactive_accounts_are_400(client):
    """Posting against a code outside the caller's chart is a 400 (the caller
    picked the code), as is a deactivated account."""
    from app.accounts import service as accounts_service
    from app.accounts.schemas import AccountCreate

    from tests.manual_journal_test_utils import _cleanup_journals

    token = await _login_token(client)
    tag = _uniq("mj")
    # 1. an unknown code
    r = await _post(
        client,
        token,
        description=f"bad account {tag}",
        lines=[
            {"account_code": "999999", "debit": "10.00"},
            {"account_code": "1000", "credit": "10.00"},
        ],
    )
    assert r.status_code == 400, r.text
    assert "999999" in r.json()["detail"]
    await _cleanup_journals(tag)

    # 2. a deactivated account (create one, then deactivate via the API)
    async with SessionLocal() as session:
        account = await accounts_service.create_account(
            session,
            branch_id=1,
            user_id=1,
            body=AccountCreate(
                code=f"zzz{tag[:12]}", name_ar="inactive", type="expense"
            ),
        )
        account_id = account.id
        await accounts_service.update_account(
            session,
            branch_id=1,
            user_id=1,
            account_id=account_id,
            data={"is_active": False},
        )
    code = f"zzz{tag[:12]}"
    try:
        r = await _post(
            client,
            token,
            description=f"inactive account {tag}",
            lines=[
                {"account_code": code, "debit": "10.00"},
                {"account_code": "1000", "credit": "10.00"},
            ],
        )
        assert r.status_code == 400, r.text
        assert "deactivated" in r.json()["detail"]
    finally:
        from tests.accounts_test_utils import _cleanup_accounts

        await _cleanup_journals(tag)
        await _cleanup_accounts([account_id])


async def test_validation_rejects_single_line_zero_negative_and_double_sided(client):
    """Single-line, zero, negative, and double-sided lines are 400; a balanced
    two-line entry with extra rounding digits lands rounded to 2 dp."""
    token = await _login_token(client)
    tag = _uniq("mj")

    for payload in [
        # one line cannot balance
        [{"account_code": "1000", "debit": "50.00"}],
        # zero amount
        [{"account_code": "1000", "debit": "0.00"}, {"account_code": "5000", "credit": "0.00"}],
        # negative amount
        [{"account_code": "1000", "debit": "-5.00"}, {"account_code": "5000", "credit": "5.00"}],
        # double-sided line
        [
            {"account_code": "1000", "debit": "5.00", "credit": "5.00"},
            {"account_code": "5000", "credit": "5.00"},
        ],
    ]:
        r = await _post(
            client,
            token,
            description=f"bad lines {tag}",
            lines=payload,
        )
        assert r.status_code == 400, (r.status_code, r.text, payload)

    # a balanced entry with 3-dp amounts is accepted, rounded half-up to 2 dp
    r = await _post(
        client,
        token,
        description=f"rounding {tag}",
        lines=[
            {"account_code": "5000", "debit": "10.005"},
            {"account_code": "1000", "credit": "10.005"},
        ],
    )
    assert r.status_code == 201, r.text
    assert r.json()["total"] == "10.01"
    await _cleanup_journals(tag)


async def test_blank_description_is_400(client):
    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        description="   ",
        lines=[
            {"account_code": "5000", "debit": "1.00"},
            {"account_code": "1000", "credit": "1.00"},
        ],
    )
    assert r.status_code == 400, r.text
    await _cleanup_journals(tag)


async def test_manual_journal_writes_gated_by_level_7_and_accountant_role(client):
    """journals.manage floor 7: unauthenticated is 401, level-6 is 403,
    level-7 is 201, and the accountant role (which holds the granular code)
    is 201."""
    from tests.manual_journal_test_utils import (
        _delete_users,
        _make_user,
        _token_for,
    )

    token = await _login_token(client)
    r = await client.post(
        "/api/v1/journals/manual",
        json={
            "datee": _entry_date(),
            "description": "no auth",
            "lines": [
                {"account_code": "5000", "debit": "1.00"},
                {"account_code": "1000", "credit": "1.00"},
            ],
        },
    )
    assert r.status_code == 401

    low = await _make_user(_uniq("low"), permission_level=6, branch_id=1)
    high = await _make_user(_uniq("high"), permission_level=7, branch_id=1)
    accountant = await _make_user(_uniq("acc"), permission_level=1, branch_id=1)
    async with SessionLocal() as session:
        await session.execute(
            user_roles_table.insert().values(user_id=accountant, role_id=4)
        )
        await session.commit()
    tags = [_uniq("mj") for _ in range(3)]
    try:
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {_token_for(low, 1)}"},
            json={
                "datee": _entry_date(),
                "description": f"denied {tags[0]}",
                "lines": [
                    {"account_code": "5000", "debit": "1.00"},
                    {"account_code": "1000", "credit": "1.00"},
                ],
            },
        )
        assert r.status_code == 403
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {_token_for(high, 1)}"},
            json={
                "datee": _entry_date(),
                "description": f"level7 {tags[1]}",
                "lines": [
                    {"account_code": "5000", "debit": "1.00"},
                    {"account_code": "1000", "credit": "1.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {_token_for(accountant, 1)}"},
            json={
                "datee": _entry_date(),
                "description": f"acc {tags[2]}",
                "lines": [
                    {"account_code": "5000", "debit": "1.00"},
                    {"account_code": "1000", "credit": "1.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
    finally:
        for tag in tags:
            await _cleanup_journals(tag)
        async with SessionLocal() as session:
            await session.execute(
                user_roles_table.delete().where(user_roles_table.c.user_id == accountant)
            )
            await session.commit()
        await _delete_users([low, high, accountant])


async def test_entries_are_branch_scoped(client):
    """A branch-2 caller posts to branch-2 (inheriting the branch-1 chart),
    never sees branch-1 entries, and gets 404 on a branch-1 entry id."""
    from tests.manual_journal_test_utils import (
        _delete_other_branch,
        _delete_users,
        _make_other_branch,
        _make_user,
        _token_for,
    )

    token = await _login_token(client)
    tag1 = _uniq("mj")
    tag2 = _uniq("mj")
    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("other"), permission_level=7, branch_id=other_branch)
    try:
        # branch-1 entry the other branch must not see
        r = await _post(
            client,
            token,
            description=f"branch1 only {tag1}",
            lines=[
                {"account_code": "5000", "debit": "5.00"},
                {"account_code": "1000", "credit": "5.00"},
            ],
        )
        branch1_entry = r.json()["id"]

        # branch-2 caller posts against the inherited branch-1 chart
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {_token_for(other, other_branch)}"},
            json={
                "datee": _entry_date(),
                "description": f"branch2 {tag2}",
                "lines": [
                    {"account_code": "5000", "debit": "3.00"},
                    {"account_code": "1000", "credit": "3.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["branch_id"] == other_branch
        branch2_entry = r.json()["id"]

        g = await client.get(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {_token_for(other, other_branch)}"},
        )
        assert g.status_code == 200, g.text
        assert all(e["branch_id"] == other_branch for e in g.json()["entries"])
        assert all(e["id"] != branch1_entry for e in g.json()["entries"])

        d = await client.get(
            f"/api/v1/journals/manual/{branch1_entry}",
            headers={"Authorization": f"Bearer {_token_for(other, other_branch)}"},
        )
        assert d.status_code == 404

        # the branch-1 caller cannot read the branch-2 entry either
        d = await client.get(
            f"/api/v1/journals/manual/{branch2_entry}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert d.status_code == 404
    finally:
        await _cleanup_journals(tag1)
        await _cleanup_journals(tag2)
        await _delete_users([other])
        await _delete_other_branch(other_branch)


async def test_entry_numbers_are_monotonic_per_branch_and_datee(client):
    """Within one (branch, datee) successive posts get strictly increasing
    entry numbers and each keeps its own journal + audit row."""
    token = await _login_token(client)
    tags = [_uniq("mj") for _ in range(3)]
    try:
        first = (await _post(
            client,
            token,
            description=f"first {tags[0]}",
            lines=[
                {"account_code": "5000", "debit": "1.00"},
                {"account_code": "1000", "credit": "1.00"},
            ],
        )).json()["entry_no"]
        second = (await _post(
            client,
            token,
            description=f"second {tags[1]}",
            lines=[
                {"account_code": "5000", "debit": "2.00"},
                {"account_code": "1000", "credit": "2.00"},
            ],
        )).json()["entry_no"]
        third = (await _post(
            client,
            token,
            description=f"third {tags[2]}",
            lines=[
                {"account_code": "5000", "debit": "3.00"},
                {"account_code": "1000", "credit": "3.00"},
            ],
        )).json()["entry_no"]
        assert second == first + 1
        assert third == second + 1
    finally:
        for tag in tags:
            await _cleanup_journals(tag)


async def test_concurrent_manual_entries_get_distinct_entry_numbers(client):
    """Two same-date posts racing through the branch advisory lock still get
    distinct monotonic entry numbers — the lock serializes numbering."""
    from app.money.entries import post_manual_entry
    from app.money.schemas import ManualJournalCreate
    from tests.manual_journal_test_utils import _login_token

    token = await _login_token(client)
    tag = _uniq("mj")
    body = ManualJournalCreate(
        datee=date.fromisoformat(_entry_date()),
        description=f"race {tag}",
        lines=[
            {"account_code": "5000", "debit": "1.00"},
            {"account_code": "1000", "credit": "1.00"},
        ],
    )
    try:
        async with SessionLocal() as a, SessionLocal() as b:
            async with asyncio.TaskGroup() as tg:
                ta = tg.create_task(
                    post_manual_entry(
                        a,
                        branch_id=1,
                        user_id=1,
                        datee=body.datee,
                        description=body.description,
                        lines=body.lines,
                    )
                )
                tb = tg.create_task(
                    post_manual_entry(
                        b,
                        branch_id=1,
                        user_id=1,
                        datee=body.datee,
                        description=body.description,
                        lines=body.lines,
                    )
                )
            ea, eb = ta.result(), tb.result()
        assert {ea.id, eb.id} != {eb.id}  # two distinct reference rows
        async with SessionLocal() as session:
            nos = (
                await session.execute(
                    select(Journal.entry_no)
                    .join(ManualJournalEntry, ManualJournalEntry.journal_id == Journal.id)
                    .where(ManualJournalEntry.branch_id == 1)
                )
            ).scalars().all()
        # both posts are in there with distinct numbers
        assert len(set(nos)) == len(nos)
    finally:
        await _cleanup_journals(tag)


async def test_reverse_posts_an_opposite_balanced_journal(client):
    """Reversing a posted manual entry (A07-style) posts an opposite-signed,
    balanced journal on the same datee, swaps the sides, marks the original
    with reverses_entry_id, and leaves the original untouched."""
    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        description=f"to reverse {tag}",
        lines=[
            {"account_code": "5000", "debit": "40.00"},
            {"account_code": "1000", "credit": "40.00"},
        ],
    )
    original = r.json()
    try:
        rv = await client.post(
            f"/api/v1/journals/manual/{original['id']}/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rv.status_code == 201, rv.text
        reversal = rv.json()
        assert reversal["reverses_entry_id"] == original["id"]
        assert reversal["entry_no"] > original["entry_no"]
        assert reversal["datee"] == original["datee"]
        assert reversal["total"] == "40.00"
        assert reversal["description"] == (
            f"reversal of manual entry #{original['entry_no']}"
        )
        by_code = {l["account_code"]: l for l in reversal["lines"]}
        assert by_code["5000"]["credit"] == "40.00"
        assert by_code["5000"]["debit"] == "0.00"
        assert by_code["1000"]["debit"] == "40.00"
        assert by_code["1000"]["credit"] == "0.00"
        assert all(
            reversal["lines"][i]["credit"] == original["lines"][i]["debit"]
            for i in range(2)
        )

        async with SessionLocal() as session:
            orig_row = await session.get(ManualJournalEntry, original["id"])
            assert orig_row.reverses_entry_id is None
            orig_journal = await session.get(Journal, original["journal_id"])
            assert orig_journal.status == "posted"
            assert len(
                (
                    await session.execute(
                        select(AuditLog).where(
                            AuditLog.entity == "journals",
                            AuditLog.entity_id == reversal["journal_id"],
                        )
                    )
                ).scalars().all()
            ) == 1

        # reversing the reversal is a 409 — a reversal can never be reversed
        r2 = await client.post(
            f"/api/v1/journals/manual/{reversal['id']}/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 409, r2.text
    finally:
        await _cleanup_journals(tag)


async def test_reverse_unknown_or_cross_branch_is_404_and_writes_need_permission(client):
    """Reversing a missing entry or one from another branch is 404; the
    reversal endpoint carries the same journals.manage gate as posting."""
    from tests.manual_journal_test_utils import _make_user, _token_for

    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        description=f"branch1 {tag}",
        lines=[
            {"account_code": "5000", "debit": "5.00"},
            {"account_code": "1000", "credit": "5.00"},
        ],
    )
    entry_id = r.json()["id"]
    try:
        r404 = await client.post(
            f"/api/v1/journals/manual/999999/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r404.status_code == 404, r404.text

        low = await _make_user(_uniq("low"), permission_level=6, branch_id=1)
        try:
            r = await client.post(
                f"/api/v1/journals/manual/{entry_id}/reverse",
                headers={"Authorization": f"Bearer {_token_for(low, 1)}"},
            )
            assert r.status_code == 403, r.text
        finally:
            from tests.manual_journal_test_utils import _delete_users

            await _delete_users([low])
    finally:
        await _cleanup_journals(tag)


async def test_line_note_is_persisted_and_returned(client):
    """A per-line note survives the round trip: it lands on the journal line's
    `tips` column and comes back through the detail AND list serializers."""
    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        description=f"with note {tag}",
        lines=[
            {"account_code": "5000", "debit": "10.00", "note": "rent for June"},
            {"account_code": "1000", "credit": "10.00"},
        ],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    entry_id = body["id"]
    try:
        by_code = {l["account_code"]: l for l in body["lines"]}
        assert by_code["5000"]["note"] == "rent for June"
        assert by_code["1000"]["note"] == ""

        d = await client.get(
            f"/api/v1/journals/manual/{entry_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert d.status_code == 200, d.text
        d_by_code = {l["account_code"]: l for l in d.json()["lines"]}
        assert d_by_code["5000"]["note"] == "rent for June"

        g = await client.get(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200, g.text
        listed = next(e for e in g.json()["entries"] if e["id"] == entry_id)
        listed_by_code = {l["account_code"]: l for l in listed["lines"]}
        assert listed_by_code["5000"]["note"] == "rent for June"

        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(JournalLine).where(JournalLine.journal_id == body["journal_id"])
                )
            ).scalars().all()
        tips = {l.tips for l in rows}
        assert "rent for June" in tips
    finally:
        await _cleanup_journals(tag)


async def test_oversized_amounts_are_400_not_500(client):
    """Amounts beyond the journal's Numeric(18,2) column — or with an exponent
    that overflows the decimal context during rounding — are 400, never an
    unhandled 500."""
    token = await _login_token(client)
    tag = _uniq("mj")
    for bad in ["1e50", "99999999999999999999.99"]:
        r = await _post(
            client,
            token,
            description=f"too big {tag}",
            lines=[
                {"account_code": "5000", "debit": bad},
                {"account_code": "1000", "credit": bad},
            ],
        )
        assert r.status_code == 400, (bad, r.status_code, r.text)

    # the largest amount that fits Numeric(18, 2) is still accepted
    r = await _post(
        client,
        token,
        description=f"max amount {tag}",
        lines=[
            {"account_code": "5000", "debit": "9999999999999999.99"},
            {"account_code": "1000", "credit": "9999999999999999.99"},
        ],
    )
    assert r.status_code == 201, r.text
    await _cleanup_journals(tag)


async def test_reversal_carries_the_original_line_notes(client):
    """The reversal mirrors the entry, per-line notes included: a note written
    on an original line survives onto the reversal's opposite-signed line."""
    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        description=f"note reversal {tag}",
        lines=[
            {"account_code": "5000", "debit": "10.00", "note": "rent for June"},
            {"account_code": "1000", "credit": "10.00"},
        ],
    )
    assert r.status_code == 201, r.text
    entry_id = r.json()["id"]
    try:
        rv = await client.post(
            f"/api/v1/journals/manual/{entry_id}/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rv.status_code == 201, rv.text
        by_code = {l["account_code"]: l for l in rv.json()["lines"]}
        assert by_code["5000"]["note"] == "rent for June"
        assert by_code["1000"]["note"] == ""
    finally:
        await _cleanup_journals(tag)


async def test_reversal_reuses_original_account_rows_when_a_new_code_shadows(client):
    """A reversal pins the offset to the account rows the original touched (by
    id, never by re-resolving the code): if the caller's branch creates its own
    account with the same code after posting, the reversal must still offset the
    original account, not redirect onto the new one."""
    from app.accounts import service as accounts_service
    from app.accounts.schemas import AccountCreate

    from tests.accounts_test_utils import _account_id, _cleanup_accounts
    from tests.manual_journal_test_utils import (
        _delete_other_branch,
        _delete_users,
        _make_other_branch,
        _make_user,
        _token_for,
    )

    tag = _uniq("mj")
    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("other"), permission_level=7, branch_id=other_branch)
    shadow_id = None
    try:
        # branch 2 posts against the inherited branch-1 code 5000 (its own chart
        # is empty at this point, so the line lands on the branch-1 account)
        r = await client.post(
            "/api/v1/journals/manual",
            headers={"Authorization": f"Bearer {_token_for(other, other_branch)}"},
            json={
                "datee": _entry_date(),
                "description": f"shadow {tag}",
                "lines": [
                    {"account_code": "5000", "debit": "40.00"},
                    {"account_code": "1000", "credit": "40.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        entry_id = r.json()["id"]
        inherited_5000 = await _account_id("5000", 1)

        # ...then branch 2 creates its own account shadowing code 5000 (the dup
        # guard is branch-scoped, so this is allowed)
        async with SessionLocal() as session:
            shadow = await accounts_service.create_account(
                session,
                branch_id=other_branch,
                user_id=other,
                body=AccountCreate(code="5000", name_ar="shadow", type="expense"),
            )
        shadow_id = shadow.id

        rv = await client.post(
            f"/api/v1/journals/manual/{entry_id}/reverse",
            headers={"Authorization": f"Bearer {_token_for(other, other_branch)}"},
        )
        assert rv.status_code == 201, rv.text
        async with SessionLocal() as session:
            reversal_lines = (
                await session.execute(
                    select(JournalLine).where(
                        JournalLine.journal_id == rv.json()["journal_id"]
                    )
                )
            ).scalars().all()
        by_id = {l.account_id for l in reversal_lines}
        assert shadow_id not in by_id
        assert inherited_5000 in by_id
    finally:
        await _cleanup_journals(tag)
        if shadow_id is not None:
            await _cleanup_accounts([shadow_id], branch_id=other_branch)
        await _delete_users([other])
        await _delete_other_branch(other_branch)


async def _cleanup_closed_day(datee: str) -> None:
    """Delete the daily_close row(s) + their audit for one (branch 1, datee) so
    a test's close never leaks into other slices."""
    from datetime import date as _date

    d = _date.fromisoformat(datee)
    async with SessionLocal() as session:
        close_rows = (
            await session.execute(
                select(DailyClose).where(
                    DailyClose.branch_id == 1, DailyClose.datee == d
                )
            )
        ).scalars().all()
        for cr in close_rows:
            await session.execute(
                delete(AuditLog).where(
                    AuditLog.entity == "daily_close", AuditLog.entity_id == cr.id
                )
            )
        await session.execute(
            delete(DailyClose).where(DailyClose.branch_id == 1, DailyClose.datee == d)
        )
        await session.commit()


async def test_post_into_a_closed_day_is_409(client):
    """A closed (branch, datee) refuses new manual journals (409, the same
    guard as the drawer slice) with nothing half-written; a neighboring open
    day still accepts posts."""
    from tests.drawer_test_utils import _close_day

    token = await _login_token(client)
    tag = _uniq("mj")
    try:
        rc = await _close_day(client, token, datee="2026-05-01", counted_cash="0")
        assert rc.status_code == 200, rc.text

        r = await _post(
            client,
            token,
            datee="2026-05-01",
            description=f"closed day {tag}",
            lines=[
                {"account_code": "5000", "debit": "5.00"},
                {"account_code": "1000", "credit": "5.00"},
            ],
        )
        assert r.status_code == 409, r.text

        async with SessionLocal() as session:
            leftover = (
                await session.execute(
                    select(Journal.id).where(Journal.description.like(f"%{tag}%"))
                )
            ).scalars().all()
        assert leftover == []

        r2 = await _post(
            client,
            token,
            datee="2026-05-02",
            description=f"open day {tag}",
            lines=[
                {"account_code": "5000", "debit": "3.00"},
                {"account_code": "1000", "credit": "3.00"},
            ],
        )
        assert r2.status_code == 201, r2.text
    finally:
        await _cleanup_journals(tag)
        await _cleanup_closed_day("2026-05-01")


async def test_reverse_into_a_closed_day_is_409(client):
    """Reversing an entry whose own datee is now closed is 409 (the reversal
    lands on the original's datee), with no reversal journal written."""
    from tests.drawer_test_utils import _close_day

    token = await _login_token(client)
    tag = _uniq("mj")
    r = await _post(
        client,
        token,
        datee="2026-05-03",
        description=f"to reverse closed {tag}",
        lines=[
            {"account_code": "5000", "debit": "5.00"},
            {"account_code": "1000", "credit": "5.00"},
        ],
    )
    assert r.status_code == 201, r.text
    entry_id = r.json()["id"]
    entry_no = r.json()["entry_no"]
    try:
        rc = await _close_day(client, token, datee="2026-05-03", counted_cash="0")
        assert rc.status_code == 200, rc.text

        rv = await client.post(
            f"/api/v1/journals/manual/{entry_id}/reverse",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rv.status_code == 409, rv.text

        async with SessionLocal() as session:
            reversal = (
                await session.execute(
                    select(Journal.id).where(
                        Journal.description
                        == f"reversal of manual entry #{entry_no}"
                    )
                )
            ).scalars().all()
        assert reversal == []
    finally:
        await _cleanup_journals(tag)
        await _cleanup_closed_day("2026-05-03")


async def test_list_limit_is_validated_and_respected(client):
    """The list limit is bounded (0 and >200 are 400) and a small limit caps
    the page."""
    token = await _login_token(client)
    for bad in [0, -1, 201]:
        r = await client.get(
            "/api/v1/journals/manual",
            params={"limit": bad},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, (bad, r.status_code, r.text)

    r = await client.get(
        "/api/v1/journals/manual",
        params={"limit": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["entries"]) <= 1


