import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    """A client backed by a fresh app, so each test starts with an empty registry."""
    return TestClient(create_app())


@pytest.fixture
def payment_service(client: TestClient) -> dict:
    response = client.post(
        "/services",
        json={
            "id": "payment-service",
            "name": "Payment Service",
            "description": "Handles customer payment processing",
            "environment": "production",
            "status": "healthy",
        },
    )
    assert response.status_code == 201
    return response.json()
