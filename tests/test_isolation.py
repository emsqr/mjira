"""The tenant isolation invariant — the most important test in the suite.

From the design spec:

    Write at least one test that:
    1. Creates tenant A with user A1.
    2. Creates tenant B with user B1.
    3. A1 creates a project.
    4. B1 calls GET /projects with their JWT -> should return 0 projects,
       never A1's project.
    5. B1 calls GET /projects/{a1_project_id} -> should return 404, not 403
       (don't reveal existence).

    This one test catches almost every tenant-leak bug.

We extend it to issues, PATCH, and DELETE for the same reasons.
"""


def test_tenant_isolation_full(client, two_tenants, auth_header):
    a, b = two_tenants

    # 1. A creates a project
    a_proj = client.post(
        "/projects",
        headers=auth_header(a.token),
        json={"key": "AAA", "name": "A's project"},
    ).json()
    a_proj_id = a_proj["id"]
    assert a_proj["tenant_id"] == a.tenant_id

    # 2. A creates an issue inside that project
    a_issue = client.post(
        "/issues",
        headers=auth_header(a.token),
        json={"project_id": a_proj_id, "title": "A's issue"},
    ).json()
    a_issue_id = a_issue["id"]
    assert a_issue["tenant_id"] == a.tenant_id

    # 3. B's project list does NOT include A's project
    b_projects = client.get("/projects", headers=auth_header(b.token)).json()
    assert a_proj_id not in {p["id"] for p in b_projects}

    # 4. B's issue list does NOT include A's issue
    b_issues = client.get("/issues", headers=auth_header(b.token)).json()
    assert a_issue_id not in {i["id"] for i in b_issues}

    # 5. B fetching A's resources by id returns 404 — NOT 403
    #    (the existence of the resource must not leak across tenants)
    assert client.get(
        f"/projects/{a_proj_id}", headers=auth_header(b.token)
    ).status_code == 404
    assert client.get(
        f"/issues/{a_issue_id}", headers=auth_header(b.token)
    ).status_code == 404

    # 6. B trying to mutate A's issue also returns 404, not 403
    assert client.patch(
        f"/issues/{a_issue_id}",
        headers=auth_header(b.token),
        json={"status": "done"},
    ).status_code == 404
    assert client.delete(
        f"/issues/{a_issue_id}", headers=auth_header(b.token)
    ).status_code == 404

    # 7. B trying to delete A's project also returns 404, not 403
    assert client.delete(
        f"/projects/{a_proj_id}", headers=auth_header(b.token)
    ).status_code == 404

    # 8. Listing issues with project_id=A's project from B's token returns []
    #    (the project_id filter must not leak A's data)
    cross = client.get(
        "/issues",
        headers=auth_header(b.token),
        params={"project_id": a_proj_id},
    )
    assert cross.status_code == 200
    assert cross.json() == []

    # 9. After all cross-tenant attacks, A's resources are still intact
    a_issue_after = client.get(
        f"/issues/{a_issue_id}", headers=auth_header(a.token)
    ).json()
    assert a_issue_after["status"] == "open"  # B's PATCH did NOT take effect
    assert client.get(
        f"/projects/{a_proj_id}", headers=auth_header(a.token)
    ).status_code == 200


def test_tenant_id_in_body_is_ignored(client, two_tenants, auth_header):
    """A malicious client sending tenant_id=B in the request body must NOT
    trick projects-service into writing into tenant B. The service takes
    tenant_id ONLY from the JWT."""
    a, b = two_tenants
    r = client.post(
        "/projects",
        headers=auth_header(a.token),
        json={
            "key": "ATK",
            "name": "trying to hijack",
            "tenant_id": b.tenant_id,  # extraneous — must be ignored
        },
    )
    assert r.status_code == 201
    # The created project belongs to A, NOT B
    assert r.json()["tenant_id"] == a.tenant_id


def test_tenant_isolation_for_tenant_resources(client, two_tenants, auth_header):
    """Cross-tenant access to /tenants/{id} and its members must also 404."""
    a, b = two_tenants
    assert client.get(
        f"/tenants/{a.tenant_id}", headers=auth_header(b.token)
    ).status_code == 404
    assert client.get(
        f"/tenants/{a.tenant_id}/members", headers=auth_header(b.token)
    ).status_code == 404
