def test_create_project(client, tenant_user, auth_header):
    r = client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "ENG", "name": "Engineering"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["key"] == "ENG"
    assert body["name"] == "Engineering"
    assert body["tenant_id"] == tenant_user.tenant_id
    assert body["created_by"] == tenant_user.user_id


def test_create_project_lowercases_key_to_upper(client, tenant_user, auth_header):
    r = client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "mkt", "name": "Marketing"},
    )
    assert r.status_code == 201
    assert r.json()["key"] == "MKT"


def test_create_project_invalid_key_rejected(client, tenant_user, auth_header):
    r = client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "1BAD", "name": "x"},
    )
    assert r.status_code == 422


def test_create_project_duplicate_key_per_tenant_conflicts(client, tenant_user, auth_header):
    p = {"key": "DUP", "name": "first"}
    first = client.post("/projects", headers=auth_header(tenant_user.token), json=p)
    assert first.status_code == 201
    r = client.post("/projects", headers=auth_header(tenant_user.token), json=p)
    assert r.status_code == 409


def test_same_key_allowed_in_different_tenants(client, two_tenants, auth_header):
    a, b = two_tenants
    p = {"key": "SHARED", "name": "n"}
    assert client.post("/projects", headers=auth_header(a.token), json=p).status_code == 201
    # Same key in a different tenant is fine — tenant_id is part of the unique
    assert client.post("/projects", headers=auth_header(b.token), json=p).status_code == 201


def test_list_projects_only_returns_caller_tenant(client, tenant_user, auth_header):
    client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "ENG", "name": "x"},
    ).raise_for_status()
    r = client.get("/projects", headers=auth_header(tenant_user.token))
    assert r.status_code == 200
    ids = {p["tenant_id"] for p in r.json()}
    assert ids == {tenant_user.tenant_id}


def test_get_project(client, tenant_user, auth_header):
    pid = client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "GET", "name": "x"},
    ).json()["id"]
    r = client.get(f"/projects/{pid}", headers=auth_header(tenant_user.token))
    assert r.status_code == 200
    assert r.json()["id"] == pid


def test_delete_project(client, tenant_user, auth_header):
    pid = client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "DEL", "name": "x"},
    ).json()["id"]
    r = client.delete(f"/projects/{pid}", headers=auth_header(tenant_user.token))
    assert r.status_code == 204
    assert client.get(f"/projects/{pid}", headers=auth_header(tenant_user.token)).status_code == 404


def test_projects_endpoints_require_tenant_context(client, fresh_user, auth_header):
    """Token without tenant_id (signup-only login) must be rejected."""
    r = client.get("/projects", headers=auth_header(fresh_user.token))
    assert r.status_code == 403


def test_projects_require_auth(client):
    assert client.get("/projects").status_code == 401
