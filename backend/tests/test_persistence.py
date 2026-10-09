from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import Database, IntegrationRecord, ServiceRecord
from app.main import create_app
from app.models import Environment, IntegrationStatus, IntegrationType, ServiceStatus
from app.schemas import IntegrationCreate, ServiceCreate
from app.services.registry import Registry


def test_data_survives_app_restart(settings: Settings, database: Database):
    with TestClient(create_app(settings)) as first:
        service = first.post("/services", json={"name": "Payment Service", "environment": "production"}).json()
        integration = first.post(
            "/integrations", json={"name": "Stripe", "type": "stripe", "service_id": service["id"]}
        ).json()

    with TestClient(create_app(settings)) as second:
        assert second.get(f"/services/{service['id']}").json() == service
        assert second.get(f"/integrations/{integration['id']}").json() == integration
        assert second.get("/services").json() == [service]


def test_registry_writes_rows(database: Database):
    with Session(database.engine) as session:
        registry = Registry(session)
        created = registry.create_service(ServiceCreate(name="Search API", environment=Environment.STAGING))
        registry.create_integration(
            IntegrationCreate(name="Redis cache", type=IntegrationType.REDIS, service_id=created.id)
        )

    with Session(database.engine) as session:
        row = session.get(ServiceRecord, "search-api")
        assert row is not None
        assert row.environment is Environment.STAGING
        assert row.status is ServiceStatus.UNKNOWN
        integrations = session.scalars(select(IntegrationRecord)).all()
        assert [(i.id, i.service_id) for i in integrations] == [("search-api-redis", "search-api")]


def test_created_at_round_trips_as_utc(client: TestClient, payment_service: dict):
    stored = datetime.fromisoformat(client.get("/services/payment-service").json()["created_at"])
    assert stored.utcoffset() == timedelta(0)
    assert abs((datetime.now(UTC) - stored).total_seconds()) < 60


def _service(service_id: str) -> ServiceRecord:
    return ServiceRecord(
        id=service_id,
        name="Payment Service",
        description="",
        environment=Environment.PRODUCTION,
        status=ServiceStatus.HEALTHY,
        created_at=datetime.now(UTC),
    )


def test_database_rejects_integration_for_missing_service(database: Database):
    with Session(database.engine) as session:
        session.add(
            IntegrationRecord(
                id="orphan",
                name="GitHub",
                type=IntegrationType.GITHUB,
                status=IntegrationStatus.PENDING,
                service_id="missing",
                created_at=datetime.now(UTC),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_database_rejects_duplicate_service_id(database: Database):
    with Session(database.engine) as session:
        session.add(_service("payment-service"))
        session.commit()
    with Session(database.engine) as session:
        session.add(_service("payment-service"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)  # make sure no local .env file is picked up
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_settings_read_database_url_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:secret@db.internal:5432/cloudops")
    assert Settings().database_url == "postgresql+psycopg://user:secret@db.internal:5432/cloudops"  # type: ignore[call-arg]


def test_database_rejects_unknown_enum_value(database: Database):
    # Raw SQL bypasses SQLAlchemy's own validation, so this exercises the CHECK constraint.
    insert = text(
        "INSERT INTO services (id, name, description, environment, status, created_at) "
        "VALUES ('bad', 'Bad', '', 'moon', 'healthy', :now)"
    )
    with database.engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(insert, {"now": datetime.now(UTC).isoformat()})
