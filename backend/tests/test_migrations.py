"""Alembic migrations against real PostgreSQL databases.

PostgreSQL is the migration target, so these tests only run when
TEST_DATABASE_URL points at PostgreSQL. Each test gets its own temporary
database (the test user needs CREATEDB, which the CI service user has).
"""

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, make_url, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.config import Settings
from app.db import Base, Database
from app.main import create_app
from tests.otlp_helpers import PROTOBUF, fixture, to_protobuf
from tests.schema_catalog import catalog

BACKEND = Path(__file__).resolve().parent.parent
HEAD = "0001"


@pytest.fixture(scope="module")
def server_url(database_url: str) -> str:
    if make_url(database_url).get_backend_name() != "postgresql":
        pytest.skip("migrations target PostgreSQL; set TEST_DATABASE_URL to run them")
    return database_url


@pytest.fixture
def make_database(server_url: str) -> Iterator:
    """Factory for empty, uniquely named databases on the test server; all dropped afterwards."""
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    created: list[str] = []

    def make() -> str:
        name = f"cloudops_mig_{uuid.uuid4().hex[:10]}"
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        created.append(name)
        return make_url(server_url).set(database=name).render_as_string(hide_password=False)

    yield make
    with admin.connect() as connection:
        for name in created:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def alembic_config(url: str, extra_versions: Path | None = None) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logging"] = False  # keep pytest's logging intact
    if extra_versions is not None:
        locations = [str(BACKEND / "alembic" / "versions"), str(extra_versions)]
        config.set_main_option("version_locations", os.pathsep.join(locations))
    return config


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def seed(engine: Engine) -> None:
    """A service, its integration and a telemetry row, as an existing deployment would have."""
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO services (id, name, description, environment, status, created_at) "
                "VALUES ('payment-service', 'Payment Service', 'Payments', 'production', 'healthy', :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "INSERT INTO integrations (id, name, type, status, service_id, created_at) "
                "VALUES ('payment-service-stripe', 'Stripe', 'stripe', 'connected', 'payment-service', :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "INSERT INTO telemetry_records (signal, service_name, timestamp, received_at, fingerprint, "
                "resource_attributes, attributes, raw) VALUES ('logs', 'payment-service', :now, :now, :fp, "
                """'{"service.name": "payment-service"}', '{"k": 1}', '{"body": {"stringValue": "hi"}}')"""
            ),
            {"now": now, "fp": "f" * 64},
        )


def snapshot(engine: Engine) -> dict[str, list]:
    with engine.connect() as connection:
        return {
            "services": connection.execute(text("SELECT * FROM services ORDER BY id")).all(),
            "integrations": connection.execute(text("SELECT * FROM integrations ORDER BY id")).all(),
            "telemetry": connection.execute(text("SELECT * FROM telemetry_records ORDER BY id")).all(),
        }


def models_catalog(make_database) -> dict:
    """The schema the application models produce (create_all), as PostgreSQL reports it."""
    engine = create_engine(make_database())
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        result = catalog(connection)
    engine.dispose()
    return result


# Fresh database


def test_there_is_a_single_head():
    assert ScriptDirectory.from_config(alembic_config("postgresql://unused")).get_heads() == [HEAD]


def test_fresh_database_upgrade_matches_the_models_exactly(make_database):
    url = make_database()
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)

    assert current_revision(engine) == HEAD
    with engine.connect() as connection:
        migrated = catalog(connection)
        # Alembic's own model comparison finds nothing to change.
        assert (
            compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata) == []
        )
    # Byte-for-byte the same columns, constraints and indexes as create_all.
    assert migrated == models_catalog(make_database)
    engine.dispose()


def test_migrated_schema_details(make_database):
    url = make_database()
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == {"alembic_version", "services", "integrations", "telemetry_records"}

    columns = {c["name"]: c for c in inspector.get_columns("telemetry_records")}
    assert str(columns["fingerprint"]["type"]) == "VARCHAR(64)"
    assert columns["fingerprint"]["nullable"] is False
    for name in ("resource_attributes", "attributes", "raw"):
        assert type(columns[name]["type"]).__name__ == "JSONB", name
    for name in ("timestamp", "received_at"):
        assert columns[name]["type"].timezone is True

    indexes = {i["name"]: i for i in inspector.get_indexes("telemetry_records")}
    assert indexes["uq_telemetry_fingerprint"] == {
        **indexes["uq_telemetry_fingerprint"],
        "column_names": ["fingerprint"],
        "unique": True,
    }
    assert indexes["ix_telemetry_service_time"]["column_names"] == ["service_name", "timestamp"]
    assert indexes["ix_telemetry_service_signal_time"]["column_names"] == ["service_name", "signal", "timestamp"]
    assert indexes["ix_telemetry_trace_id"]["column_names"] == ["trace_id"]

    [foreign_key] = inspector.get_foreign_keys("integrations")
    assert foreign_key["constrained_columns"] == ["service_id"]
    assert (foreign_key["referred_table"], foreign_key["referred_columns"]) == ("services", ["id"])
    assert foreign_key["options"]["ondelete"] == "RESTRICT"

    checks = {
        c["name"] for t in ("services", "integrations", "telemetry_records") for c in inspector.get_check_constraints(t)
    }
    assert checks == {
        "ck_services_environment",
        "ck_services_status",
        "ck_integrations_type",
        "ck_integrations_status",
        "ck_telemetry_signal",
    }
    engine.dispose()


def test_migrated_database_enforces_constraints(make_database):
    url = make_database()
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    seed(engine)
    statements = [
        # unique fingerprint
        (
            "INSERT INTO telemetry_records (signal, service_name, timestamp, received_at, fingerprint, "
            f"resource_attributes, attributes, raw) VALUES ('logs', 's', now(), now(), '{'f' * 64}', '{{}}', '{{}}', '{{}}')"
        ),
        # foreign key: integration for a missing service
        (
            "INSERT INTO integrations (id, name, type, status, service_id, created_at) "
            "VALUES ('x', 'X', 'github', 'pending', 'missing', now())"
        ),
        # RESTRICT: can't delete a service that has integrations
        "DELETE FROM services WHERE id = 'payment-service'",
        # check constraint
        (
            "INSERT INTO services (id, name, description, environment, status, created_at) "
            "VALUES ('bad', 'Bad', '', 'moon', 'healthy', now())"
        ),
    ]
    for statement in statements:
        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(text(statement))
    engine.dispose()


def test_application_works_on_a_migrated_database(make_database, caplog: pytest.LogCaptureFixture):
    url = make_database()
    command.upgrade(alembic_config(url), "head")

    with TestClient(create_app(Settings(database_url=url))) as client:
        assert (
            client.post("/services", json={"name": "Payment Service", "environment": "production"}).status_code == 201
        )
        assert (
            client.post(
                "/integrations", json={"name": "Stripe", "type": "stripe", "service_id": "payment-service"}
            ).status_code
            == 201
        )
        body = to_protobuf("traces", fixture("traces"))
        for _ in range(2):  # resend: fingerprint de-duplication works on the migrated schema
            assert client.post("/v1/traces", content=body, headers=PROTOBUF).status_code == 200
        assert len(client.get("/telemetry/records").json()) == 3
        assert [s["id"] for s in client.get("/services").json()] == ["payment-service"]
    assert "no Alembic version" not in caplog.text


def test_cli_upgrade_reads_database_url(make_database):
    """`alembic upgrade head` from the backend directory, configured only through DATABASE_URL."""
    url = make_database()
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    history = subprocess.run(
        [sys.executable, "-m", "alembic", "current"], cwd=BACKEND, env=env, capture_output=True, text=True, check=True
    )
    assert f"{HEAD} (head)" in history.stdout


def test_downgrade_to_base_removes_the_schema(make_database):
    url = make_database()
    config = alembic_config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    assert current_revision(engine) is None
    command.upgrade(config, "head")  # and back again
    assert current_revision(engine) == HEAD
    engine.dispose()


# Existing databases


def test_existing_pre_alembic_database_is_adopted_with_stamp(make_database):
    """A database created by the app's create_all (before Alembic) keeps its data."""
    url = make_database()
    database = Database(url)
    database.create_tables()
    engine = database.engine
    seed(engine)
    before = snapshot(engine)
    assert current_revision(engine) is None

    config = alembic_config(url)
    command.stamp(config, "head")  # record that the schema is already at 0001
    command.upgrade(config, "head")  # nothing to apply

    assert current_revision(engine) == HEAD
    assert snapshot(engine) == before
    with engine.connect() as connection:
        assert (
            compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata) == []
        )
    database.verify_schema()  # the app's startup check accepts it
    database.dispose()


def test_follow_up_migration_upgrades_existing_data_safely(make_database, tmp_path: Path):
    """A later revision (temporary, test-only) applies to a populated database and can be reverted."""
    (tmp_path / "0002_test_only.py").write_text(
        """
import sqlalchemy as sa
from alembic import op

revision = "0002_test_only"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("services", sa.Column("owner_team", sa.String(64), nullable=False, server_default="unassigned"))
    op.create_index("ix_services_owner_team", "services", ["owner_team"])


def downgrade():
    op.drop_index("ix_services_owner_team", table_name="services")
    op.drop_column("services", "owner_team")
""",
        encoding="utf-8",
    )
    url = make_database()
    config = alembic_config(url, extra_versions=tmp_path)
    command.upgrade(config, "0001")
    engine = create_engine(url)
    seed(engine)
    before = snapshot(engine)

    command.upgrade(config, "head")
    assert current_revision(engine) == "0002_test_only"
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id, name, owner_team FROM services")).all()
    assert [tuple(r) for r in rows] == [("payment-service", "Payment Service", "unassigned")]
    after = snapshot(engine)
    assert after["integrations"] == before["integrations"]
    assert after["telemetry"] == before["telemetry"]

    command.downgrade(config, "0001")
    assert current_revision(engine) == HEAD
    assert snapshot(engine) == before
    engine.dispose()

    # The temporary revision exists only in tmp_path, never in the repository.
    assert ScriptDirectory.from_config(alembic_config(url)).get_heads() == [HEAD]
