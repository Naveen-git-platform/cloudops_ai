"""Test fixtures.

Tests run against PostgreSQL when TEST_DATABASE_URL is set, for example:

    TEST_DATABASE_URL=postgresql+psycopg://cloudops:cloudops@localhost:5432/cloudops_test

Otherwise they fall back to a temporary SQLite file so the suite runs anywhere.
The test database is wiped before every test, so never point it at real data.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Base, Database
from app.main import create_app


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    path: Path = tmp_path_factory.mktemp("db") / "test.sqlite3"
    return f"sqlite:///{path.as_posix()}"


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(database_url=database_url)


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    """A database with freshly created, empty tables."""
    db = Database(settings.database_url)
    Base.metadata.drop_all(db.engine)
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


@pytest.fixture
def client(settings: Settings, database: Database) -> Iterator[TestClient]:
    """A client for an app connected to the (empty) test database."""
    with TestClient(create_app(settings)) as test_client:
        yield test_client


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
