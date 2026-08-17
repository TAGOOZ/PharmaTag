"""S1.4 supplier parties (ticket #10 supporting seam): a purchase needs a
supplier, so the parties router exposes minimal create/list for suppliers
(legacy area '4' العملاء والموردين). Tests cover the create validation +
branch scoping that the purchase slice depends on.
"""
from app.core.db import SessionLocal
from tests.purchase_test_utils import (
    _cleanup,
    _delete_other_branch,
    _delete_users,
    _login_token,
    _make_other_branch,
    _make_user,
    _token_for,
    _uniq,
)


async def test_create_supplier(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "kind": "supplier",
            "namee": _uniq("مورد"),
            "name_ar": "مورد تجاري",
            "mobile": "01000000000",
            "adress": "القاهرة",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    party_id = body["id"]
    try:
        assert body["kind"] == "supplier"
        assert body["branch_id"] == 1
        assert body["active"] is True
    finally:
        await _cleanup([], [], [party_id])


async def test_list_suppliers_by_kind_and_branch(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "supplier", "namee": _uniq("sup1")},
    )
    s1 = r.json()["id"]
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "supplier", "namee": _uniq("sup2")},
    )
    s2 = r.json()["id"]
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "customer", "namee": _uniq("cust")},
    )
    c1 = r.json()["id"]
    try:
        g = await client.get(
            "/api/v1/parties?kind=supplier",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200
        names = {p["id"] for p in g.json()["parties"]}
        assert {s1, s2} <= names
        assert c1 not in names
    finally:
        await _cleanup([], [], [s1, s2, c1])


async def test_create_party_validation(client):
    token = await _login_token(client)
    for payload in [
        {"kind": "supplier"},  # missing namee
        {"kind": "wholesaler", "namee": _uniq("bad")},  # bad kind
        {"kind": "supplier", "namee": "", "mobile": "0"},  # empty name
    ]:
        r = await client.post(
            "/api/v1/parties",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert r.status_code == 400, payload


async def test_party_creation_forbidden_below_level_4(client):
    """Legacy area '4' (العملاء والموردين) needs level >= 4; a level-3 user is
    forbidden, a level-4 user is allowed."""
    low = await _make_user(_uniq("low"), permission_level=3, branch_id=1)
    high = await _make_user(_uniq("high"), permission_level=4, branch_id=1)
    created: list[int] = []
    try:
        r = await client.post(
            "/api/v1/parties",
            headers={"Authorization": f"Bearer {_token_for(low, 1)}"},
            json={"kind": "supplier", "namee": _uniq("nope")},
        )
        assert r.status_code == 403
        r = await client.post(
            "/api/v1/parties",
            headers={"Authorization": f"Bearer {_token_for(high, 1)}"},
            json={"kind": "supplier", "namee": _uniq("yes")},
        )
        assert r.status_code == 201, r.text
        created.append(r.json()["id"])
    finally:
        await _delete_users([low, high])
        await _cleanup([], [], created)


async def test_party_unauthenticated_401(client):
    r = await client.post("/api/v1/parties", json={"kind": "supplier", "namee": "x"})
    assert r.status_code == 401


async def test_party_list_scoped_to_branch(client):
    """A branch-2 caller never sees branch-1 parties."""
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "supplier", "namee": _uniq("scoped")},
    )
    created = [r.json()["id"]]
    other_branch = await _make_other_branch()
    other = await _make_user(_uniq("other"), permission_level=9, branch_id=other_branch)
    try:
        g = await client.get(
            "/api/v1/parties?kind=supplier",
            headers={"Authorization": f"Bearer {_token_for(other, other_branch)}"},
        )
        assert g.status_code == 200
        assert all(p["branch_id"] == other_branch for p in g.json()["parties"])
    finally:
        await _delete_other_branch(other_branch)
        await _cleanup([], [], created)