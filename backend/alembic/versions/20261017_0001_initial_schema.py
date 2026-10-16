"""Initial schema: services, integrations and telemetry_records.

Matches the schema the application created with `create_all` before Alembic
existed (Issues #4, #7 and #11), so existing databases can be stamped at this
revision. Written explicitly rather than with the application's types, so the
migration stays fixed even when the models change later.

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENVIRONMENTS = ("production", "staging", "development")
SERVICE_STATUSES = ("healthy", "degraded", "down", "unknown")
INTEGRATION_TYPES = ("github", "aws", "kubernetes", "stripe", "postgresql", "redis", "opentelemetry", "other")
INTEGRATION_STATUSES = ("pending", "connected", "degraded", "disconnected")
SIGNALS = ("traces", "metrics", "logs")


def one_of(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    """Enum columns are VARCHAR with a CHECK constraint (no native PostgreSQL enum types)."""
    allowed = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({allowed})", name=name)


def timestamptz() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", timestamptz(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="services_pkey"),
        one_of("environment", ENVIRONMENTS, "ck_services_environment"),
        one_of("status", SERVICE_STATUSES, "ck_services_status"),
    )
    op.create_index("ix_services_created_at", "services", ["created_at"])

    op.create_table(
        "integrations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("service_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", timestamptz(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="integrations_pkey"),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name="integrations_service_id_fkey", ondelete="RESTRICT"
        ),
        one_of("type", INTEGRATION_TYPES, "ck_integrations_type"),
        one_of("status", INTEGRATION_STATUSES, "ck_integrations_status"),
    )
    op.create_index("ix_integrations_created_at", "integrations", ["created_at"])
    op.create_index("ix_integrations_service_id", "integrations", ["service_id"])

    op.create_table(
        "telemetry_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),  # BIGSERIAL
        sa.Column("signal", sa.String(length=16), nullable=False),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("service_namespace", sa.String(length=255), nullable=True),
        sa.Column("service_version", sa.String(length=255), nullable=True),
        sa.Column("environment", sa.String(length=255), nullable=True),
        sa.Column("host_name", sa.String(length=255), nullable=True),
        sa.Column("scope_name", sa.String(length=255), nullable=True),
        sa.Column("scope_version", sa.String(length=255), nullable=True),
        sa.Column("timestamp", timestamptz(), nullable=False),
        sa.Column("end_timestamp", timestamptz(), nullable=True),
        sa.Column("received_at", timestamptz(), nullable=False),
        sa.Column("name", sa.String(length=1024), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=True),
        sa.Column("span_id", sa.String(length=16), nullable=True),
        sa.Column("parent_span_id", sa.String(length=16), nullable=True),
        sa.Column("span_kind", sa.String(length=16), nullable=True),
        sa.Column("status_code", sa.String(length=16), nullable=True),
        sa.Column("severity_number", sa.Integer(), nullable=True),
        sa.Column("severity_text", sa.String(length=32), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("metric_type", sa.String(length=32), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("resource_attributes", jsonb(), nullable=False),
        sa.Column("attributes", jsonb(), nullable=False),
        sa.Column("raw", jsonb(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="telemetry_records_pkey"),
        one_of("signal", SIGNALS, "ck_telemetry_signal"),
    )
    op.create_index("ix_telemetry_service_time", "telemetry_records", ["service_name", "timestamp"])
    op.create_index("ix_telemetry_service_signal_time", "telemetry_records", ["service_name", "signal", "timestamp"])
    op.create_index("ix_telemetry_trace_id", "telemetry_records", ["trace_id"])
    # Makes ingestion idempotent (see app.telemetry.normalize.fingerprint).
    op.create_index("uq_telemetry_fingerprint", "telemetry_records", ["fingerprint"], unique=True)


def downgrade() -> None:
    op.drop_table("telemetry_records")
    op.drop_table("integrations")
    op.drop_table("services")
