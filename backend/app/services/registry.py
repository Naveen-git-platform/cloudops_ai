"""Service and integration registry backed by the database.

Routes depend only on the public methods below; all SQL lives here.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import IntegrationRecord, ServiceRecord
from app.models import Integration, Service
from app.schemas import IntegrationCreate, ServiceCreate


class RegistryError(Exception):
    """Base class for registry errors."""


class NotFoundError(RegistryError):
    def __init__(self, kind: str, resource_id: str) -> None:
        super().__init__(f"{kind} '{resource_id}' not found")


class ConflictError(RegistryError):
    def __init__(self, kind: str, resource_id: str) -> None:
        super().__init__(f"{kind} '{resource_id}' already exists")


class UnknownServiceError(RegistryError):
    def __init__(self, service_id: str) -> None:
        super().__init__(f"Service '{service_id}' does not exist")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:56].rstrip("-") or "item"


class Registry:
    def __init__(self, session: Session) -> None:
        self._session = session

    # Services

    def list_services(self) -> list[Service]:
        rows = self._session.scalars(select(ServiceRecord).order_by(ServiceRecord.created_at, ServiceRecord.id))
        return [Service.model_validate(row) for row in rows]

    def get_service(self, service_id: str) -> Service:
        row = self._session.get(ServiceRecord, service_id)
        if row is None:
            raise NotFoundError("Service", service_id)
        return Service.model_validate(row)

    def create_service(self, data: ServiceCreate) -> Service:
        if data.id is not None and self._session.get(ServiceRecord, data.id) is not None:
            raise ConflictError("Service", data.id)
        service_id = data.id or self._unique_id(ServiceRecord, slugify(data.name))
        row = ServiceRecord(id=service_id, created_at=datetime.now(UTC), **data.model_dump(exclude={"id"}))
        self._insert(row, ConflictError("Service", service_id))
        return Service.model_validate(row)

    # Integrations

    def list_integrations(self, service_id: str | None = None) -> list[Integration]:
        query = select(IntegrationRecord).order_by(IntegrationRecord.created_at, IntegrationRecord.id)
        if service_id is not None:
            query = query.where(IntegrationRecord.service_id == service_id)
        return [Integration.model_validate(row) for row in self._session.scalars(query)]

    def get_integration(self, integration_id: str) -> Integration:
        row = self._session.get(IntegrationRecord, integration_id)
        if row is None:
            raise NotFoundError("Integration", integration_id)
        return Integration.model_validate(row)

    def create_integration(self, data: IntegrationCreate) -> Integration:
        if self._session.get(ServiceRecord, data.service_id) is None:
            raise UnknownServiceError(data.service_id)
        if data.id is not None and self._session.get(IntegrationRecord, data.id) is not None:
            raise ConflictError("Integration", data.id)
        base = slugify(f"{data.service_id}-{data.type}")
        integration_id = data.id or self._unique_id(IntegrationRecord, base)
        row = IntegrationRecord(id=integration_id, created_at=datetime.now(UTC), **data.model_dump(exclude={"id"}))
        self._insert(row, ConflictError("Integration", integration_id))
        return Integration.model_validate(row)

    # Helpers

    def _unique_id(self, model: type[ServiceRecord] | type[IntegrationRecord], base: str) -> str:
        """`base`, or `base-2`, `base-3`, ... if taken."""
        taken = set(self._session.scalars(select(model.id).where(model.id.startswith(base, autoescape=True))))
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    def _insert(self, row: ServiceRecord | IntegrationRecord, on_conflict: RegistryError) -> None:
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError:
            # A concurrent request inserted the same ID (or deleted the parent service).
            self._session.rollback()
            if isinstance(row, IntegrationRecord) and self._session.get(ServiceRecord, row.service_id) is None:
                raise UnknownServiceError(row.service_id) from None
            raise on_conflict from None
