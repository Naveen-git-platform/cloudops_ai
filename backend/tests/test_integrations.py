from datetime import datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def stripe_integration(client: TestClient, payment_service: dict) -> dict:
    response = client.post(
        "/integrations",
        json={"name": "Stripe", "type": "stripe", "service_id": payment_service["id"]},
    )
    assert response.status_code == 201
    return response.json()


def test_list_integrations_empty(client: TestClient):
    response = client.get("/integrations")
    assert response.status_code == 200
    assert response.json() == []


def test_list_integrations_returns_created(client: TestClient, stripe_integration: dict):
    response = client.get("/integrations")
    assert response.status_code == 200
    assert response.json() == [stripe_integration]


def test_list_integrations_filters_by_service(client: TestClient, stripe_integration: dict):
    client.post("/services", json={"id": "search-api", "name": "Search API", "environment": "production"})
    client.post("/integrations", json={"name": "Redis", "type": "redis", "service_id": "search-api"})

    response = client.get("/integrations", params={"service_id": "payment-service"})
    assert response.status_code == 200
    assert response.json() == [stripe_integration]


def test_create_integration(stripe_integration: dict):
    assert stripe_integration["id"] == "payment-service-stripe"
    assert stripe_integration["name"] == "Stripe"
    assert stripe_integration["type"] == "stripe"
    assert stripe_integration["status"] == "pending"
    assert stripe_integration["service_id"] == "payment-service"
    datetime.fromisoformat(stripe_integration["created_at"])


def test_create_integration_with_explicit_id(client: TestClient, payment_service: dict):
    response = client.post(
        "/integrations",
        json={
            "id": "payments-db",
            "name": "Payments DB",
            "type": "postgresql",
            "status": "connected",
            "service_id": "payment-service",
        },
    )
    assert response.status_code == 201
    assert response.json()["id"] == "payments-db"
    assert response.json()["status"] == "connected"


def test_create_integration_duplicate_id_returns_409(client: TestClient, stripe_integration: dict):
    response = client.post(
        "/integrations",
        json={"id": stripe_integration["id"], "name": "Stripe", "type": "stripe", "service_id": "payment-service"},
    )
    assert response.status_code == 409


def test_create_integration_for_unknown_service_returns_422(client: TestClient):
    response = client.post(
        "/integrations",
        json={"name": "GitHub", "type": "github", "service_id": "ghost-service"},
    )
    assert response.status_code == 422
    assert "ghost-service" in response.json()["detail"]


def test_get_integration(client: TestClient, stripe_integration: dict):
    response = client.get(f"/integrations/{stripe_integration['id']}")
    assert response.status_code == 200
    assert response.json() == stripe_integration


def test_get_unknown_integration_returns_404(client: TestClient):
    response = client.get("/integrations/does-not-exist")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "Stripe", "type": "stripe"},
        {"name": "Stripe", "service_id": "payment-service"},
        {"name": "Stripe", "type": "mainframe", "service_id": "payment-service"},
        {"name": "Stripe", "type": "stripe", "service_id": "payment-service", "status": "great"},
        {"name": "", "type": "stripe", "service_id": "payment-service"},
        {"name": "Stripe", "type": "stripe", "service_id": "payment-service", "api_key": "sk_test"},
    ],
)
def test_create_integration_invalid_payload_returns_422(client: TestClient, payment_service: dict, payload: dict):
    response = client.post("/integrations", json=payload)
    assert response.status_code == 422
