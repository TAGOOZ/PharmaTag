"""S2.1 chart of accounts (ticket #16): per-branch account tree + CRUD.

The rev-009 seed turns the flat chart into the hierarchical legacy tree
(wzaccfreetree mapping — feature_balances.md §9). These tests exercise the
`/api/v1/accounts` surface: tree navigation, CRUD with branch scoping, the
`accounts.manage` gate (legacy floor 7 + accountant role), posting-safety
guards (referenced accounts can't be deactivated/renamed/deleted), and the
posting seam (a created account is usable by `money.journal.post_journal`).
"""

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import Account, AuditLog, Balance, Journal, JournalLine
from tests.accounts_test_utils import (
    _account_id,
    _cleanup_accounts,
    _delete_other_branch,
    _delete_users,
    _login_token,
    _make_other_branch,
    _make_user,
    _token_for,
    _uniq,
)


def _by_code(nodes: list[dict]) -> dict:
    return {n["code"]: n for n in nodes}


async def test_tree_reflects_the_legacy_hierarchy(client):
    """The seeded chart is a real tree: five roots, and the existing leaf codes
    sit under the legacy parents (اصول.متداولة etc.)."""
    token = await _login_token(client)
    r = await client.get("/api/v1/accounts/tree", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    roots = _by_code(r.json()["tree"])
    assert set(roots) == {"100", "200", "300", "400", "500"}

    assets = _by_code(roots["100"]["children"])
    assert set(assets) == {"110", "1300"}  # متداولة + ثابتة
    current = _by_code(assets["110"]["children"])
    assert set(current) == {"1000", "1001", "1010", "1100", "1110", "1200"}

    liab = _by_code(roots["200"]["children"])
    assert set(liab) == {"210", "220"}
    assert set(_by_code(liab["210"]["children"])) == {"2000", "2100", "2110"}
    assert set(_by_code(roots["300"]["children"])) == {"3000"}
    assert set(_by_code(roots["400"]["children"])) == {"4000"}
    assert set(_by_code(roots["500"]["children"])) == {"5000", "5900", "6000"}


async def test_flat_list_is_branch_scoped(client):
    """Branch-1 callers see branch-1 accounts; a branch-2 caller (whose branch
    has no chart yet) sees an empty list, never branch-1's."""
    token = await _login_token(client)
    r = await client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    accounts = r.json()["accounts"]
    assert len(accounts) == 23
    assert all(a["branch_id"] == 1 for a in accounts)

    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("other"), permission_level=9, branch_id=other_branch)
    try:
        g = await client.get(
            "/api/v1/accounts", headers={"Authorization": f"Bearer {_token_for(other, other_branch)}"}
        )
        assert g.status_code == 200
        assert g.json()["accounts"] == []
    finally:
        await _delete_other_branch(other_branch)
        await _delete_users([other])


async def test_flat_list_search_and_filters(client):
    """search is a case-insensitive substring across code/name_ar/name_en;
    type + active_only filters narrow the list."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/accounts?search=متداولة", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    hits = r.json()["accounts"]
    assert hits and all("متداولة" in (a["name_ar"] or "") for a in hits)

    r = await client.get(
        "/api/v1/accounts?search=100", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert all("100" in a["code"] for a in r.json()["accounts"])

    r = await client.get(
        "/api/v1/accounts?type=equity", headers={"Authorization": f"Bearer {token}"}
    )
    assert {a["code"] for a in r.json()["accounts"]} == {"300", "3000"}


async def test_create_account_round_trips_and_audits(client):
    token = await _login_token(client)
    parent = await _account_id("110")
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": _uniq("acc"),
            "name_ar": "حساب تجريبي",
            "name_en": "Test Account",
            "type": "expense",
            "parent_id": parent,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    account_id = body["id"]
    try:
        assert body["branch_id"] == 1
        assert body["parent_id"] == parent
        assert body["is_active"] is True
        assert body["master"] == "110"
        assert body["fary"] == body["code"]
        async with SessionLocal() as session:
            row = await session.get(Account, account_id)
            assert row.master == "110" and row.fary == row.code
            audit_rows = (
                await session.execute(
                    AuditLog.__table__.select().where(
                        AuditLog.entity == "accounts",
                        AuditLog.entity_id == account_id,
                    )
                )
            ).scalars().all()
            assert len(audit_rows) == 1
    finally:
        await _cleanup_accounts([account_id])


async def test_create_duplicate_code_is_409(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "9999", "name_ar": "a", "type": "asset"},
    )
    assert r.status_code == 201, r.text
    created = r.json()["id"]
    try:
        r2 = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "9999", "name_ar": "b", "type": "asset"},
        )
        assert r2.status_code == 409, r2.text
    finally:
        await _cleanup_accounts([created])


async def test_create_validation_400(client):
    token = await _login_token(client)
    for payload in [
        {"name_ar": "no code", "type": "asset"},
        {"code": "9001", "type": "asset"},
        {"code": "9002", "name_ar": "bad type", "type": "beer"},
    ]:
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert r.status_code == 400, payload


async def test_create_account_rejects_type_mismatch_with_inherited_chart(client):
    """The ميزان groups a code's merged balances by the own account's type, so
    a branch account created for a code that already exists on the inherited
    branch-1 chart must keep that code's company-wide type — a re-typed shadow
    account would silently regroup the merged balance into the wrong
    balance-sheet section."""
    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("other"), permission_level=9, branch_id=other_branch)
    token = _token_for(other, other_branch)
    try:
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "4000", "name_ar": "ايراد خاطئ", "type": "asset"},
        )
        assert r.status_code == 400, r.text
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "4000", "name_ar": "ايراد فرع", "type": "income"},
        )
        assert r.status_code == 201, r.text
        assert r.json()["type"] == "income"
        # a code absent from the inherited chart is free to pick any type
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "7100", "name_ar": "إيراد آخر", "type": "income"},
        )
        assert r.status_code == 201, r.text
    finally:
        await _delete_users([other])
        await _delete_other_branch(other_branch)


async def test_update_account_cannot_retype_or_rename_against_inherited_chart(client):
    """Patching a branch account's type (or renaming it) to a code whose
    inherited branch-1 type differs is refused — the merged balance would move
    statement sections — while a matching rename stays allowed."""
    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("other"), permission_level=9, branch_id=other_branch)
    token = _token_for(other, other_branch)
    try:
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "3000", "name_ar": "رأس مال الفرع", "type": "equity"},
        )
        assert r.status_code == 201, r.text
        equity_id = r.json()["id"]
        r = await client.patch(
            f"/api/v1/accounts/{equity_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"type": "liability"},
        )
        assert r.status_code == 400, r.text

        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "7100", "name_ar": "مصروف فرع", "type": "expense"},
        )
        assert r.status_code == 201, r.text
        exp_id = r.json()["id"]
        # renaming a non-inherited expense account onto the income code 4000
        # would re-type the shadow row — refused
        r = await client.patch(
            f"/api/v1/accounts/{exp_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "4000"},
        )
        assert r.status_code == 400, r.text
        # a rename onto an inherited code with a matching type is fine
        r = await client.patch(
            f"/api/v1/accounts/{exp_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "6000"},
        )
        assert r.status_code == 200, r.text
    finally:
        await _delete_users([other])
        await _delete_other_branch(other_branch)


async def test_create_parent_outside_branch_is_404(client):
    token = await _login_token(client)
    other_branch = await _make_other_branch()
    try:
        async with SessionLocal() as session:
            other_acct = Account(
                branch_id=other_branch, code="7000", name_ar="other", type="asset"
            )
            session.add(other_acct)
            await session.flush()
            other_acct_id = other_acct.id
            await session.commit()
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "9003", "name_ar": "x", "type": "asset", "parent_id": other_acct_id},
        )
        assert r.status_code == 404, r.text
    finally:
        await _delete_other_branch(other_branch)


async def test_account_writes_gated_by_level_7_and_accountant_role(client):
    """accounts.manage floor 7: a level-6 user is forbidden, level-7 allowed;
    the accountant role also holds the granular permission."""
    low = await _make_user(_uniq("low"), permission_level=6, branch_id=1)
    high = await _make_user(_uniq("high"), permission_level=7, branch_id=1)
    created: list[int] = []
    try:
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {_token_for(low, 1)}"},
            json={"code": _uniq("nope"), "name_ar": "x", "type": "asset"},
        )
        assert r.status_code == 403
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {_token_for(high, 1)}"},
            json={"code": _uniq("yes"), "name_ar": "x", "type": "asset"},
        )
        assert r.status_code == 201, r.text
        created.append(r.json()["id"])
    finally:
        await _delete_users([low, high])
        await _cleanup_accounts(created)


async def test_detail_and_cross_branch_404(client):
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/accounts", headers={"Authorization": f"Bearer {token}"}
    )
    account = next(a for a in r.json()["accounts"] if a["code"] == "110")
    g = await client.get(
        f"/api/v1/accounts/{account['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert g.status_code == 200, g.text
    assert g.json()["code"] == "110"
    assert {c["code"] for c in g.json()["children"]} == {
        "1000", "1001", "1010", "1100", "1110", "1200",
    }

    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("other"), permission_level=9, branch_id=other_branch)
    try:
        g2 = await client.get(
            f"/api/v1/accounts/{account['id']}",
            headers={"Authorization": f"Bearer {_token_for(other, other_branch)}"},
        )
        assert g2.status_code == 404
    finally:
        await _delete_other_branch(other_branch)
        await _delete_users([other])


async def test_patch_renames_reparents_and_audits(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("pat"), "name_ar": "before", "type": "expense", "parent_id": await _account_id("500")},
    )
    account_id = r.json()["id"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name_ar": "after", "parent_id": await _account_id("100")},
        )
        assert p.status_code == 200, p.text
        assert p.json()["name_ar"] == "after"
        assert p.json()["parent_id"] == await _account_id("100")
        assert p.json()["master"] == "100"
    finally:
        await _cleanup_accounts([account_id])


async def test_patch_cycle_is_rejected(client):
    token = await _login_token(client)
    created: list[int] = []
    try:
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": _uniq("cyc"), "name_ar": "cyc", "type": "asset", "parent_id": await _account_id("110")},
        )
        child = r.json()["id"]
        created.append(child)
        # make the child a parent too
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": _uniq("grand"), "name_ar": "grand", "type": "asset", "parent_id": child},
        )
        grand = r.json()["id"]
        created.append(grand)
        # reparent child under its own descendant -> cycle
        p = await client.patch(
            f"/api/v1/accounts/{child}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parent_id": grand},
        )
        assert p.status_code == 409, p.text
        # reparent onto itself -> cycle
        p = await client.patch(
            f"/api/v1/accounts/{child}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parent_id": child},
        )
        assert p.status_code == 409, p.text
    finally:
        await _cleanup_accounts(created)


async def test_patch_duplicate_code_and_clear_parent(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("dup"), "name_ar": "x", "type": "asset", "parent_id": await _account_id("100")},
    )
    a_id = r.json()["id"]
    other_code = _uniq("clr")
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": other_code, "name_ar": "y", "type": "asset"},
    )
    b_id = r.json()["id"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{a_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": other_code},
        )
        assert p.status_code == 409, p.text
        p = await client.patch(
            f"/api/v1/accounts/{a_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parent_id": None},
        )
        assert p.status_code == 200, p.text
        assert p.json()["parent_id"] is None
        assert p.json()["master"] == ""
        assert p.json()["has_children"] is False
    finally:
        await _cleanup_accounts([a_id, b_id])


async def test_posted_account_cannot_be_renamed_or_deactivated(client):
    """An account the journal engine has posted to is 'used': renaming it,
    changing its type, deactivating it, or deleting it is refused (409)."""
    from datetime import date
    from decimal import Decimal

    from app.money.journal import post_journal

    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("post"), "name_ar": "posted", "type": "expense"},
    )
    account_id = r.json()["id"]
    try:
        async with SessionLocal() as session:
            await post_journal(
                session,
                branch_id=1,
                user_id=1,
                datee=date.today(),
                entry_no=999998,
                description="posting-seam test",
                source="manual",
                entries=[("1000", Decimal("0"), Decimal("0")), (r.json()["code"], Decimal("1.00"), Decimal("0"))],
            )
            await session.commit()
        for payload in [
            {"name_ar": "renamed"},
            {"type": "asset"},
            {"is_active": False},
        ]:
            p = await client.patch(
                f"/api/v1/accounts/{account_id}",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            assert p.status_code == 409, payload
        d = await client.delete(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert d.status_code == 409, d.text
    finally:
        await _cleanup_accounts([account_id])


async def test_deactivate_with_children_is_409(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("par"), "name_ar": "par", "type": "asset"},
    )
    parent_id = r.json()["id"]
    r2 = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("kid"), "name_ar": "kid", "type": "asset", "parent_id": parent_id},
    )
    child_id = r2.json()["id"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{parent_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )
        assert p.status_code == 409, p.text
    finally:
        await _cleanup_accounts([parent_id, child_id])


async def test_delete_unreferenced_account_succeeds(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("del"), "name_ar": "del", "type": "asset"},
    )
    account_id = r.json()["id"]
    d = await client.delete(
        f"/api/v1/accounts/{account_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert d.status_code == 204, d.text
    g = await client.get(
        f"/api/v1/accounts/{account_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert g.status_code == 404


async def test_unauthenticated_401(client):
    r = await client.get("/api/v1/accounts")
    assert r.status_code == 401
    r = await client.post("/api/v1/accounts", json={"code": "1", "name_ar": "x", "type": "asset"})
    assert r.status_code == 401


async def test_inactive_accounts_stay_visible_with_used_flag(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("off"), "name_ar": "off", "type": "expense"},
    )
    account_id = r.json()["id"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )
        assert p.status_code == 200, p.text
        # still listed by default, with is_active false
        g = await client.get(
            "/api/v1/accounts", headers={"Authorization": f"Bearer {token}"}
        )
        row = next(a for a in g.json()["accounts"] if a["id"] == account_id)
        assert row["is_active"] is False
        # hidden when filtering active_only
        g = await client.get(
            "/api/v1/accounts?active_only=true", headers={"Authorization": f"Bearer {token}"}
        )
        assert all(a["id"] != account_id for a in g.json()["accounts"])
    finally:
        await _cleanup_accounts([account_id])


async def test_cross_branch_fallback_posting_marks_branch1_account_used(client):
    """A branch-2 posting that falls back to a branch-1 account (the journal
    engine inherits branch-1's chart for chart-less branches) makes that
    account 'used': a branch-1 admin must not be able to rename or delete it."""
    import random
    from datetime import date
    from decimal import Decimal

    from app.money.journal import post_journal

    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("cb"), "name_ar": "cross-branch", "type": "expense"},
    )
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]
    code = r.json()["code"]
    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("other"), permission_level=9, branch_id=other_branch)
    try:
        async with SessionLocal() as session:
            await post_journal(
                session,
                branch_id=other_branch,
                user_id=other,
                datee=date.today(),
                entry_no=random.randint(1_000_000, 8_000_000),
                description="cross-branch fallback test",
                source="manual",
                entries=[
                    ("1000", Decimal("0"), Decimal("0")),
                    (code, Decimal("1.00"), Decimal("0")),
                ],
            )
            await session.commit()

        g = await client.get(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200, g.text
        assert g.json()["used"] is True
        p = await client.patch(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": _uniq("cb2")},
        )
        assert p.status_code == 409, p.text
        d = await client.delete(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert d.status_code == 409, d.text
    finally:
        # the branch-2 fallback posting wrote journal lines/balance rows on the
        # throwaway branch — clear them before the branch can be dropped
        async with SessionLocal() as session:
            await session.execute(
                delete(JournalLine).where(JournalLine.branch_id == other_branch)
            )
            await session.execute(
                delete(Journal).where(Journal.branch_id == other_branch)
            )
            await session.execute(
                delete(Balance).where(Balance.branch_id == other_branch)
            )
            await session.commit()
        await _delete_users([other])
        await _delete_other_branch(other_branch)
        await _cleanup_accounts([account_id])


async def test_tree_children_sorted_by_code(client):
    """Children under a root come back code-sorted, not in insertion order."""
    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("tree"), permission_level=9, branch_id=other_branch)
    token = _token_for(other, other_branch)
    try:
        r = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "9000", "name_ar": "root", "type": "expense"},
        )
        assert r.status_code == 201, r.text
        root_id = r.json()["id"]
        for code in ["9000-z", "9000-a", "9000-m"]:  # deliberately scrambled
            r = await client.post(
                "/api/v1/accounts",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "code": code,
                    "name_ar": code,
                    "type": "expense",
                    "parent_id": root_id,
                },
            )
            assert r.status_code == 201, r.text
        g = await client.get(
            "/api/v1/accounts/tree", headers={"Authorization": f"Bearer {token}"}
        )
        assert g.status_code == 200, g.text
        root = next(n for n in g.json()["tree"] if n["code"] == "9000")
        codes = [c["code"] for c in root["children"]]
        assert codes == ["9000-a", "9000-m", "9000-z"], codes
    finally:
        await _delete_users([other])
        await _delete_other_branch(other_branch)


async def test_rename_account_with_children_is_409(client):
    """Renaming a parent's code would orphan its children's `master` links, so
    it is refused — same protection as delete."""
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("par"), "name_ar": "parent", "type": "asset"},
    )
    assert r.status_code == 201, r.text
    parent_id = r.json()["id"]
    r2 = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": _uniq("kid"),
            "name_ar": "kid",
            "type": "asset",
            "parent_id": parent_id,
        },
    )
    assert r2.status_code == 201, r2.text
    child_id = r2.json()["id"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{parent_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": _uniq("par2")},
        )
        assert p.status_code == 409, p.text
    finally:
        await _cleanup_accounts([parent_id, child_id])


async def test_concurrent_duplicate_create_is_409_not_500(client):
    """Two creates of the same (branch, code) racing past the pre-check land on
    the unique constraint — one succeeds, the other must be a 409, not a 500."""
    import asyncio

    from fastapi import HTTPException

    from app.accounts import service
    from app.accounts.schemas import AccountCreate

    code = _uniq("race")
    created: list[int] = []

    async def _create() -> str:
        async with SessionLocal() as session:
            try:
                account = await service.create_account(
                    session,
                    branch_id=1,
                    user_id=1,
                    body=AccountCreate(code=code, name_ar="race", type="asset"),
                )
                created.append(account.id)
                return "ok"
            except HTTPException as exc:
                return str(exc.status_code)

    results = await asyncio.gather(_create(), _create())
    try:
        assert sorted(results) == ["409", "ok"], results
    finally:
        await _cleanup_accounts(created)


async def test_deactivated_account_rejects_posting(client):
    """Deactivation means 'not postable': the journal engine must refuse to
    post against a deactivated code (400 — the caller picked a code it can see,
    so a deactivated account is a client error, never an internal 500) and
    leave nothing half-written behind."""
    import random
    from datetime import date
    from decimal import Decimal

    from fastapi import HTTPException

    from app.money.journal import post_journal

    token = await _login_token(client)
    code = _uniq("inact")
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": code, "name_ar": "inactive", "type": "expense"},
    )
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )
        assert p.status_code == 200, p.text
        async with SessionLocal() as session:
            try:
                await post_journal(
                    session,
                    branch_id=1,
                    user_id=1,
                    datee=date.today(),
                    entry_no=random.randint(1_000_000, 8_000_000),
                    description="deactivated-account test",
                    source="manual",
                    entries=[
                        ("1000", Decimal("0"), Decimal("0")),
                        (code, Decimal("1.00"), Decimal("0")),
                    ],
                )
                await session.commit()
                raise AssertionError("posting to a deactivated account must fail")
            except HTTPException as exc:
                await session.rollback()
                assert exc.status_code == 400
                assert "deactivated" in exc.detail
            leftover = (
                await session.execute(
                    select(Journal.id).where(
                        Journal.description == "deactivated-account test"
                    )
                )
            ).scalars().all()
            assert leftover == []
    finally:
        await _cleanup_accounts([account_id])


async def test_codes_and_names_are_stripped(client):
    """Codes and names are trimmed on write; whitespace-only values are 400."""
    token = await _login_token(client)
    code = _uniq("pad")
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": f"  {code}  ", "name_ar": "  padded name  ", "type": "asset"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    account_id = body["id"]
    try:
        assert body["code"] == code
        assert body["name_ar"] == "padded name"
        blank = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "   ", "name_ar": "x", "type": "asset"},
        )
        assert blank.status_code == 400, blank.text
    finally:
        await _cleanup_accounts([account_id])


async def test_list_limit_zero_returns_empty(client):
    """limit <= 0 is an explicit 'no rows' request, not a floor of 1."""
    token = await _login_token(client)
    g = await client.get(
        "/api/v1/accounts?limit=0", headers={"Authorization": f"Bearer {token}"}
    )
    assert g.status_code == 200, g.text
    assert g.json()["accounts"] == []


async def test_patch_same_code_preserves_master(client):
    """Re-sending the account's own code (a no-op PATCH, common in form
    round-trips) must not wipe the parent linkage: master stays the parent's
    code, parent_id stays put."""
    token = await _login_token(client)
    parent = await _account_id("110")
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("keep"), "name_ar": "keep", "type": "asset", "parent_id": parent},
    )
    account_id = r.json()["id"]
    code = r.json()["code"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": code},
        )
        assert p.status_code == 200, p.text
        assert p.json()["parent_id"] == parent
        assert p.json()["master"] == "110"
    finally:
        await _cleanup_accounts([account_id])


async def test_code_rename_preserves_parent_master(client):
    """Renaming a childless unused account's code keeps the master (parent
    code) intact; only fary follows the new code."""
    token = await _login_token(client)
    parent = await _account_id("110")
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("old"), "name_ar": "old", "type": "asset", "parent_id": parent},
    )
    account_id = r.json()["id"]
    new_code = _uniq("new")
    try:
        p = await client.patch(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": new_code},
        )
        assert p.status_code == 200, p.text
        assert p.json()["parent_id"] == parent
        assert p.json()["master"] == "110"
        assert p.json()["fary"] == new_code
    finally:
        await _cleanup_accounts([account_id])


async def test_create_under_inactive_parent_is_409(client):
    """An active child under a deactivated parent would be postable despite the
    parent's 'not postable' state — creating one is refused."""
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("par"), "name_ar": "par", "type": "asset"},
    )
    parent_id = r.json()["id"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{parent_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )
        assert p.status_code == 200, p.text
        c = await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": _uniq("kid"), "name_ar": "kid", "type": "asset", "parent_id": parent_id},
        )
        assert c.status_code == 409, c.text
    finally:
        await _cleanup_accounts([parent_id])


async def test_reparent_onto_inactive_parent_is_409(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("dead"), "name_ar": "dead", "type": "asset"},
    )
    dead_id = r.json()["id"]
    r2 = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("mov"), "name_ar": "mov", "type": "asset"},
    )
    mov_id = r2.json()["id"]
    try:
        p = await client.patch(
            f"/api/v1/accounts/{dead_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )
        assert p.status_code == 200, p.text
        p = await client.patch(
            f"/api/v1/accounts/{mov_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parent_id": dead_id},
        )
        assert p.status_code == 409, p.text
    finally:
        await _cleanup_accounts([dead_id, mov_id])


async def test_reactivation_requires_active_ancestors(client):
    """Reactivating an account whose parent chain is inactive is refused; the
    chain must be restored top-down first."""
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("par"), "name_ar": "par", "type": "asset"},
    )
    parent_id = r.json()["id"]
    r2 = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("kid"), "name_ar": "kid", "type": "asset", "parent_id": parent_id},
    )
    child_id = r2.json()["id"]
    try:
        for account_id in (child_id, parent_id):  # children-first deactivation
            p = await client.patch(
                f"/api/v1/accounts/{account_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"is_active": False},
            )
            assert p.status_code == 200, p.text
        p = await client.patch(
            f"/api/v1/accounts/{child_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": True},
        )
        assert p.status_code == 409, p.text
        p = await client.patch(
            f"/api/v1/accounts/{parent_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": True},
        )
        assert p.status_code == 200, p.text
        p = await client.patch(
            f"/api/v1/accounts/{child_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": True},
        )
        assert p.status_code == 200, p.text
    finally:
        await _cleanup_accounts([parent_id, child_id])


async def test_reparent_used_account_is_409(client):
    """Reparenting changes master (the legacy grouping key), so — like rename/
    retype/deactivate/delete — a referenced account refuses a parent change."""
    import random
    from datetime import date
    from decimal import Decimal

    from app.money.journal import post_journal

    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("used"), "name_ar": "used", "type": "expense"},
    )
    account_id = r.json()["id"]
    try:
        async with SessionLocal() as session:
            await post_journal(
                session,
                branch_id=1,
                user_id=1,
                datee=date.today(),
                entry_no=random.randint(1_000_000, 8_000_000),
                description="reparent-used test",
                source="manual",
                entries=[("1000", Decimal("0"), Decimal("0")), (r.json()["code"], Decimal("1.00"), Decimal("0"))],
            )
            await session.commit()
        p = await client.patch(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parent_id": await _account_id("500")},
        )
        assert p.status_code == 409, p.text
    finally:
        await _cleanup_accounts([account_id])


async def test_blank_name_on_used_account_is_400(client):
    """A blank-after-strip name is a validation error (400) even when the
    account is referenced — not a 409 rename conflict."""
    import random
    from datetime import date
    from decimal import Decimal

    from app.money.journal import post_journal

    token = await _login_token(client)
    r = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": _uniq("bn"), "name_ar": "bn", "type": "expense"},
    )
    account_id = r.json()["id"]
    try:
        async with SessionLocal() as session:
            await post_journal(
                session,
                branch_id=1,
                user_id=1,
                datee=date.today(),
                entry_no=random.randint(1_000_000, 8_000_000),
                description="blank-name-used test",
                source="manual",
                entries=[("1000", Decimal("0"), Decimal("0")), (r.json()["code"], Decimal("1.00"), Decimal("0"))],
            )
            await session.commit()
        p = await client.patch(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name_ar": "   "},
        )
        assert p.status_code == 400, p.text
    finally:
        await _cleanup_accounts([account_id])