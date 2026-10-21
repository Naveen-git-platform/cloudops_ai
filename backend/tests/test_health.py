from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_expected_payload():
    response = client.get("/health")
    assert response.json() == {
        "status": "healthy",
        "service": "cloudops-api",
        "version": "0.1.0",
    }


def test_health_rejects_post():
    response = client.post("/health")
    assert response.status_code == 405


def test_readiness_returns_ready_when_database_is_available(client: TestClient):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "cloudops-api",
        "version": "0.1.0",
        "database": "available",
    }


def test_readiness_returns_safe_503_when_database_is_unavailable(
    client: TestClient, monkeypatch
):
    def fail_connect():
        raise SQLAlchemyError("postgresql://user:secret@database.invalid/cloudops is offline")

    monkeypatch.setattr(client.app.state.database.engine, "connect", fail_connect)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "cloudops-api",
        "version": "0.1.0",
        "database": "unavailable",
    }
    assert "secret" not in response.text
    assert "database.invalid" not in response.text


def test_readiness_log_does_not_include_database_exception_details(
    client: TestClient, monkeypatch, caplog
):
    secret_dsn = "postgresql://test_user:fake_password@db.internal/testdb"

    def fail_connect():
        raise SQLAlchemyError(secret_dsn)

    monkeypatch.setattr(client.app.state.database.engine, "connect", fail_connect)

    with caplog.at_level("WARNING"):
        response = client.get("/ready")

    assert response.status_code == 503
    assert secret_dsn not in caplog.text
    assert "SQLAlchemyError" in caplog.text
