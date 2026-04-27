import uuid


def _email() -> str:
    return f"u-{uuid.uuid4().hex[:10]}@example.com"


def test_signup_returns_user(client):
    email = _email()
    r = client.post("/auth/signup", json={"email": email, "password": "pw12345678"})
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == email
    assert "id" in body
    assert "password_hash" not in body
    assert "password" not in body


def test_signup_duplicate_email_conflicts(client):
    email = _email()
    p = {"email": email, "password": "pw12345678"}
    assert client.post("/auth/signup", json=p).status_code == 201
    r = client.post("/auth/signup", json=p)
    assert r.status_code == 409


def test_signup_short_password_rejected(client):
    r = client.post("/auth/signup", json={"email": _email(), "password": "short"})
    assert r.status_code == 422


def test_signup_invalid_email_rejected(client):
    r = client.post("/auth/signup", json={"email": "not-an-email", "password": "pw12345678"})
    assert r.status_code == 422


def test_login_without_tenant_slug_returns_token_with_no_tenant(client, fresh_user):
    r = client.post(
        "/auth/login",
        json={"email": fresh_user.email, "password": fresh_user.password},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["tenant_id"] is None
    assert body["role"] is None


def test_login_with_unknown_tenant_slug_returns_403(client, fresh_user):
    r = client.post(
        "/auth/login",
        json={
            "email": fresh_user.email,
            "password": fresh_user.password,
            "tenant_slug": "nonexistent-slug-xyz",
        },
    )
    assert r.status_code == 403


def test_login_wrong_password_returns_401(client, fresh_user):
    r = client.post(
        "/auth/login",
        json={"email": fresh_user.email, "password": "WRONGPASSWORD"},
    )
    assert r.status_code == 401


def test_login_unknown_user_returns_401(client):
    r = client.post(
        "/auth/login",
        json={"email": _email(), "password": "anything12345"},
    )
    assert r.status_code == 401


def test_me_requires_bearer_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_garbage_token(client, auth_header):
    r = client.get("/auth/me", headers=auth_header("not-a-real-jwt"))
    assert r.status_code == 401


def test_me_returns_current_user(client, fresh_user, auth_header):
    r = client.get("/auth/me", headers=auth_header(fresh_user.token))
    assert r.status_code == 200
    assert r.json()["id"] == fresh_user.user_id
    assert r.json()["email"] == fresh_user.email
