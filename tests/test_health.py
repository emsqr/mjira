import pytest


@pytest.mark.parametrize("path", [
    "/health",
    "/auth/health",
    "/tenants/health",
    "/projects/health",
    "/issues/health",
])
def test_health_endpoints_return_ok(client, path):
    r = client.get(path)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_internal_routes_blocked_at_gateway(client):
    """The gateway must return 404 for any /internal/* path so the
    tenant-service's service-to-service lookup endpoint stays unreachable
    from outside the docker network."""
    assert client.get("/internal/foo").status_code == 404
    assert client.get("/internal/memberships/lookup").status_code == 404
