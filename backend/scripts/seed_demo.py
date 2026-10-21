"""Seed a small, fictional ShopStack workload for local prototype testing.

Run from backend/ after installing requirements:
    DATABASE_URL=sqlite:///./cloudops_demo.db python -m scripts.seed_demo

For PostgreSQL, run Alembic migrations first and point DATABASE_URL at a disposable
development database. This script is additive and idempotent; it never deletes data.
"""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.db import Database, IntegrationRecord, ServiceRecord
from app.models import (
    Environment,
    IntegrationStatus,
    IntegrationType,
    ServiceStatus,
)
from app.schemas import IntegrationCreate, ServiceCreate
from app.services.registry import Registry

SAMPLE_SERVICES = (
    ServiceCreate(
        id="shopstack-checkout-api",
        name="ShopStack Checkout API",
        description="ShopStack Demo project · checkout and payment orchestration.",
        environment=Environment.PRODUCTION,
        status=ServiceStatus.DEGRADED,
    ),
    ServiceCreate(
        id="shopstack-search-service",
        name="ShopStack Search",
        description="ShopStack Demo project · product search and indexing.",
        environment=Environment.PRODUCTION,
        status=ServiceStatus.DEGRADED,
    ),
    ServiceCreate(
        id="shopstack-order-worker",
        name="ShopStack Order Worker",
        description="ShopStack Demo project · asynchronous order processing.",
        environment=Environment.PRODUCTION,
        status=ServiceStatus.HEALTHY,
    ),
    ServiceCreate(
        id="shopstack-edge-gateway",
        name="ShopStack Edge Gateway",
        description="ShopStack Demo project · public API ingress and TLS termination.",
        environment=Environment.PRODUCTION,
        status=ServiceStatus.HEALTHY,
    ),
)

SAMPLE_INTEGRATIONS = (
    IntegrationCreate(
        id="shopstack-checkout-postgresql",
        name="Checkout PostgreSQL",
        type=IntegrationType.POSTGRESQL,
        status=IntegrationStatus.DEGRADED,
        service_id="shopstack-checkout-api",
    ),
    IntegrationCreate(
        id="shopstack-checkout-stripe",
        name="Stripe Payments (demo metadata)",
        type=IntegrationType.STRIPE,
        status=IntegrationStatus.CONNECTED,
        service_id="shopstack-checkout-api",
    ),
    IntegrationCreate(
        id="shopstack-search-aws",
        name="Search AWS Runtime (demo metadata)",
        type=IntegrationType.AWS,
        status=IntegrationStatus.CONNECTED,
        service_id="shopstack-search-service",
    ),
    IntegrationCreate(
        id="shopstack-orders-redis",
        name="Order Queue Redis",
        type=IntegrationType.REDIS,
        status=IntegrationStatus.CONNECTED,
        service_id="shopstack-order-worker",
    ),
    IntegrationCreate(
        id="shopstack-edge-kubernetes",
        name="Edge Kubernetes Runtime (demo metadata)",
        type=IntegrationType.KUBERNETES,
        status=IntegrationStatus.CONNECTED,
        service_id="shopstack-edge-gateway",
    ),
)


def seed_demo(database_url: str) -> dict[str, int]:
    """Insert missing sample services/integrations; leave existing records untouched."""
    database = Database(database_url)
    try:
        # SQLite is the quick local prototype path. PostgreSQL schema changes remain
        # exclusively managed by Alembic and must exist before running this script.
        if database.engine.dialect.name == "sqlite":
            database.create_tables()

        created = {"services": 0, "integrations": 0}
        with Session(database.engine) as session:
            registry = Registry(session)
            for service in SAMPLE_SERVICES:
                if session.get(ServiceRecord, service.id) is None:
                    registry.create_service(service)
                    created["services"] += 1

            for integration in SAMPLE_INTEGRATIONS:
                if session.get(IntegrationRecord, integration.id) is None:
                    registry.create_integration(integration)
                    created["integrations"] += 1
        return created
    finally:
        database.dispose()


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required. See backend/README.md for the local demo command.")

    created = seed_demo(database_url)
    print(
        "ShopStack Demo seed complete: "
        f"{created['services']} service(s) and {created['integrations']} integration(s) created. "
        "Existing sample records were left unchanged."
    )


if __name__ == "__main__":
    main()
