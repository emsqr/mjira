import uuid

from .conftest import signup


def _slug() -> str:
    return f"t-{uuid.uuid4().hex[:10]}"


def test_create_tenant_makes_caller_owner(client, fresh_user, auth_header):
    slug = _slug()
    r = client.post(
        "/tenants",
        headers=auth_header(fresh_user.token),
        json={"name": "Acme", "slug": slug},
    )
    assert r.status_code == 201
    tenant = r.json()
    assert tenant["slug"] == slug

    # Re-login with the new tenant -> token now carries owner role
    body = client.post(
        "/auth/login",
        json={
            "email": fresh_user.email,
            "password": fresh_user.password,
            "tenant_slug": slug,
        },
    ).json()
    assert body["tenant_id"] == tenant["id"]
    assert body["role"] == "owner"


def test_create_tenant_duplicate_slug_conflicts(client, fresh_user, auth_header):
    slug = _slug()
    p = {"name": "X", "slug": slug}
    assert client.post("/tenants", headers=auth_header(fresh_user.token), json=p).status_code == 201
    r = client.post("/tenants", headers=auth_header(fresh_user.token), json=p)
    assert r.status_code == 409


def test_create_tenant_invalid_slug_rejected(client, fresh_user, auth_header):
    r = client.post(
        "/tenants",
        headers=auth_header(fresh_user.token),
        json={"name": "X", "slug": "Invalid Slug With Spaces"},
    )
    assert r.status_code == 422


def test_list_my_tenants_only_includes_membership(client, tenant_user, auth_header):
    r = client.get("/tenants", headers=auth_header(tenant_user.token))
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert tenant_user.tenant_id in ids


def test_get_tenant_requires_membership(client, two_tenants, auth_header):
    a, b = two_tenants
    # Owner of A can read A
    assert client.get(f"/tenants/{a.tenant_id}", headers=auth_header(a.token)).status_code == 200
    # Owner of B cannot see A — non-members get 404 (not 403; no existence leak)
    r = client.get(f"/tenants/{a.tenant_id}", headers=auth_header(b.token))
    assert r.status_code == 404


def test_owner_can_add_member(client, tenant_user, auth_header):
    # Sign up another user to add as member
    other = signup(client)
    r = client.post(
        f"/tenants/{tenant_user.tenant_id}/members",
        headers=auth_header(tenant_user.token),
        json={"user_id": other.user_id, "role": "member"},
    )
    assert r.status_code == 201

    # That user can now login with the tenant slug
    body = client.post(
        "/auth/login",
        json={
            "email": other.email,
            "password": other.password,
            "tenant_slug": tenant_user.tenant_slug,
        },
    ).json()
    assert body["role"] == "member"


def test_non_owner_cannot_add_member(client, tenant_user, auth_header):
    # Sign up a second user, add them as a regular 'member'
    other = signup(client)
    client.post(
        f"/tenants/{tenant_user.tenant_id}/members",
        headers=auth_header(tenant_user.token),
        json={"user_id": other.user_id, "role": "member"},
    ).raise_for_status()

    # Get tenant-scoped token for the member
    member_tok = client.post(
        "/auth/login",
        json={
            "email": other.email,
            "password": other.password,
            "tenant_slug": tenant_user.tenant_slug,
        },
    ).json()["access_token"]

    # A 'member' cannot add new members (only owner/admin can)
    third = signup(client)
    r = client.post(
        f"/tenants/{tenant_user.tenant_id}/members",
        headers=auth_header(member_tok),
        json={"user_id": third.user_id, "role": "member"},
    )
    assert r.status_code == 403


def test_create_tenant_requires_auth(client):
    r = client.post("/tenants", json={"name": "x", "slug": _slug()})
    assert r.status_code == 401
