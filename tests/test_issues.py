import pytest


@pytest.fixture()
def project_id(client, tenant_user, auth_header) -> str:
    return client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "ENG", "name": "Engineering"},
    ).json()["id"]


def test_create_issue_defaults_to_open(client, tenant_user, auth_header, project_id):
    r = client.post(
        "/issues",
        headers=auth_header(tenant_user.token),
        json={"project_id": project_id, "title": "Setup CI"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "open"
    assert body["title"] == "Setup CI"
    assert body["project_id"] == project_id
    assert body["tenant_id"] == tenant_user.tenant_id
    assert body["created_by"] == tenant_user.user_id


def test_patch_issue_status(client, tenant_user, auth_header, project_id):
    iid = client.post(
        "/issues",
        headers=auth_header(tenant_user.token),
        json={"project_id": project_id, "title": "x"},
    ).json()["id"]
    r = client.patch(
        f"/issues/{iid}",
        headers=auth_header(tenant_user.token),
        json={"status": "in_progress"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


def test_patch_invalid_status_rejected(client, tenant_user, auth_header, project_id):
    iid = client.post(
        "/issues",
        headers=auth_header(tenant_user.token),
        json={"project_id": project_id, "title": "x"},
    ).json()["id"]
    r = client.patch(
        f"/issues/{iid}",
        headers=auth_header(tenant_user.token),
        json={"status": "totally-bogus"},
    )
    assert r.status_code == 422


def test_list_issues_filter_by_project_and_status(
    client, tenant_user, auth_header, project_id
):
    # Make a 2nd project + a few issues across both, in mixed states
    other_pid = client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "OTH", "name": "Other"},
    ).json()["id"]

    def mk(pid: str, title: str, status: str | None = None) -> str:
        iid = client.post(
            "/issues",
            headers=auth_header(tenant_user.token),
            json={"project_id": pid, "title": title},
        ).json()["id"]
        if status:
            client.patch(
                f"/issues/{iid}",
                headers=auth_header(tenant_user.token),
                json={"status": status},
            ).raise_for_status()
        return iid

    a1 = mk(project_id, "a1")
    a2 = mk(project_id, "a2", status="done")
    b1 = mk(other_pid, "b1")

    by_project = client.get(
        "/issues",
        headers=auth_header(tenant_user.token),
        params={"project_id": project_id},
    ).json()
    ids_by_project = {i["id"] for i in by_project}
    assert a1 in ids_by_project
    assert a2 in ids_by_project
    assert b1 not in ids_by_project

    by_status = client.get(
        "/issues",
        headers=auth_header(tenant_user.token),
        params={"status": "done"},
    ).json()
    assert all(i["status"] == "done" for i in by_status)
    assert a2 in {i["id"] for i in by_status}


def test_delete_issue(client, tenant_user, auth_header, project_id):
    iid = client.post(
        "/issues",
        headers=auth_header(tenant_user.token),
        json={"project_id": project_id, "title": "x"},
    ).json()["id"]
    assert client.delete(
        f"/issues/{iid}", headers=auth_header(tenant_user.token)
    ).status_code == 204
    assert client.get(
        f"/issues/{iid}", headers=auth_header(tenant_user.token)
    ).status_code == 404


def test_issues_require_tenant_context(client, fresh_user, auth_header):
    r = client.get("/issues", headers=auth_header(fresh_user.token))
    assert r.status_code == 403


def test_issues_require_auth(client):
    assert client.get("/issues").status_code == 401
