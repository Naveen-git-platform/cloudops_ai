"""Regression tests for protected service and integration registry routes."""
from fastapi.testclient import TestClient


def test_registry_rejects_missing_bearer_token(client: TestClient) -> None:
    client.app.dependency_overrides.clear()
    client.app.state.settings.supabase_url = "https://example.supabase.co"

    response = client.get("/services")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Not authenticated"}


def test_registry_fails_closed_when_auth_is_not_configured(client: TestClient) -> None:
    client.app.dependency_overrides.clear()
    client.app.state.settings.supabase_url = None

    response = client.get("/integrations")

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is not configured"}
