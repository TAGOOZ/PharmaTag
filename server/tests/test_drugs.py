"""S0.3 drug-master read slice (ticket #6): login → GET branch drug list.

The branch drug master is a read: no money/stock mutation, so no audit/outbox
rows are involved (AGENTS.md — reads follow plain read conventions). Branch
scope comes from the authenticated user's `branch_id` (seed admin → branch 1
MAIN); drugs are global (wzdrugs) so the read returns the active catalog for
that branch.
"""
async def test_login_then_get_drug_list_returns_seeded_drugs_for_branch(client):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    r = await client.get(
        "/api/v1/drugs", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()

    # branch scope resolves from the authenticated user (admin → MAIN, branch 1)
    assert body["branch"]["id"] == 1
    assert body["branch"]["pharname"] == "Main Pharmacy"

    # the seeded drug master for that branch (rev 003_drug_seeds)
    names = [d["drugname"] for d in body["drugs"]]
    assert "Panadol Extra" in names
    panadol = next(d for d in body["drugs"] if d["drugname"] == "Panadol Extra")
    assert panadol["drugnamear"] == "بانادول إكسترا"
    assert panadol["price"] == "12.50"
    assert panadol["tax_type"] == "exempt"


async def test_drug_list_requires_authentication(client):
    r = await client.get("/api/v1/drugs")
    assert r.status_code == 401


async def test_drugs_endpoint_allows_web_preflight(client):
    """The web app (localhost:300x) must be able to call the API cross-origin."""
    r = await client.options(
        "/api/v1/drugs",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3001"