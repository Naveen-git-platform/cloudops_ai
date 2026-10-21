from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Database, IntegrationRecord, ServiceRecord
from scripts.seed_demo import seed_demo


def test_shopstack_demo_seed_is_repeatable_and_creates_sample_workload(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'shopstack-demo.db'}"

    assert seed_demo(database_url) == {"services": 4, "integrations": 5}
    assert seed_demo(database_url) == {"services": 0, "integrations": 0}

    database = Database(database_url)
    try:
        with Session(database.engine) as session:
            services = list(session.scalars(select(ServiceRecord).order_by(ServiceRecord.id)))
            integrations = list(session.scalars(select(IntegrationRecord).order_by(IntegrationRecord.id)))

        assert len(services) == 4
        assert len(integrations) == 5
        assert {service.environment.value for service in services} == {"production"}
        assert all("ShopStack Demo project" in service.description for service in services)
        assert {service.status.value for service in services} == {"healthy", "degraded"}
        assert all(integration.service_id in {service.id for service in services} for integration in integrations)
    finally:
        database.dispose()
