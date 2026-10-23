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



def test_registry_rejects_invalid_token_without_leaking_details(client: TestClient, monkeypatch) -> None:
    import jwt
    import app.auth as auth

    class FakeSigningKey:
        key = "synthetic-public-key"

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
            assert token == "not-a-valid-token"
            return FakeSigningKey()

    client.app.dependency_overrides.clear()
    client.app.state.settings.supabase_url = "https://example.supabase.co"
    monkeypatch.setattr(auth, "_jwks_client", lambda _: FakeJwksClient())

    def reject_token(*args, **kwargs):
        raise jwt.InvalidTokenError("synthetic internal verification detail")

    monkeypatch.setattr(auth.jwt, "decode", reject_token)
    response = client.get("/services", headers={"Authorization": "Bearer not-a-valid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}
    assert "synthetic internal verification detail" not in response.text


def test_telemetry_records_rejects_missing_bearer_token(client: TestClient) -> None:
    client.app.dependency_overrides.clear()
    client.app.state.settings.supabase_url = "https://example.supabase.co"

    response = client.get("/telemetry/records")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Not authenticated"}
