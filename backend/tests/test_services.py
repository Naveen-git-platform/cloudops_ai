from datetime import datetime

import pytest
from fastapi.testclient import TestClient


def test_list_services_empty(client: TestClient):
    response = client.get("/services")
    assert response.status_code == 200
    assert response.json() == []


def test_list_services_returns_created(client: TestClient, payment_service: dict):
    response = client.get("/services")
    assert response.status_code == 200
    assert response.json() == [payment_service]


def test_create_service(client: TestClient, payment_service: dict):
    assert payment_service["id"] == "payment-service"
    assert payment_service["name"] == "Payment Service"
    assert payment_service["description"] == "Handles customer payment processing"
    assert payment_service["environment"] == "production"
    assert payment_service["status"] == "healthy"
    datetime.fromisoformat(payment_service["created_at"])


def test_create_service_generates_id_and_defaults(client: TestClient):
    response = client.post("/services", json={"name": "Search API", "environment": "staging"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "search-api"
    assert body["status"] == "unknown"
    assert body["description"] == ""


def test_generated_ids_are_unique(client: TestClient):
    first = client.post("/services", json={"name": "Search API", "environment": "staging"}).json()
    second = client.post("/services", json={"name": "Search API", "environment": "production"}).json()
    assert first["id"] == "search-api"
    assert second["id"] == "search-api-2"


def test_create_service_duplicate_id_returns_409(client: TestClient, payment_service: dict):
    response = client.post(
        "/services",
        json={"id": "payment-service", "name": "Other", "environment": "production"},
    )
    assert response.status_code == 409


def test_get_service(client: TestClient, payment_service: dict):
    response = client.get("/services/payment-service")
    assert response.status_code == 200
    assert response.json() == payment_service


def test_get_unknown_service_returns_404(client: TestClient):
    response = client.get("/services/does-not-exist")
    assert response.status_code == 404
    assert "does-not-exist" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"environment": "production"},
        {"name": "", "environment": "production"},
        {"name": "   ", "environment": "production"},
        {"name": "Svc", "environment": "moon"},
        {"name": "Svc", "environment": "production", "status": "on-fire"},
        {"name": "Svc", "environment": "production", "id": "Not A Slug"},
        {"name": "Svc", "environment": "production", "unexpected": True},
        {"name": "x" * 101, "environment": "production"},
    ],
)
def test_create_service_invalid_payload_returns_422(client: TestClient, payload: dict):
    response = client.post("/services", json=payload)
    assert response.status_code == 422
