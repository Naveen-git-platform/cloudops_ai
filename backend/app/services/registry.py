"""In-memory service and integration registry.

This is the only place that holds state. It will be replaced by a
PostgreSQL-backed repository in a later issue; routes depend only on the
public methods below.
"""

import re
from collections.abc import Container
from datetime import UTC, datetime
from threading import Lock

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


def _unique_id(base: str, taken: Container[str]) -> str:
    candidate, n = base, 2
    while candidate in taken:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


class Registry:
    def __init__(self) -> None:
        self._services: dict[str, Service] = {}
        self._integrations: dict[str, Integration] = {}
        self._lock = Lock()

    # Services

    def list_services(self) -> list[Service]:
        return list(self._services.values())

    def get_service(self, service_id: str) -> Service:
        try:
            return self._services[service_id]
        except KeyError:
            raise NotFoundError("Service", service_id) from None

    def create_service(self, data: ServiceCreate) -> Service:
        with self._lock:
            if data.id is not None and data.id in self._services:
                raise ConflictError("Service", data.id)
            service_id = data.id or _unique_id(slugify(data.name), self._services)
            service = Service(
                id=service_id,
                created_at=datetime.now(UTC),
                **data.model_dump(exclude={"id"}),
            )
            self._services[service_id] = service
            return service

    # Integrations

    def list_integrations(self, service_id: str | None = None) -> list[Integration]:
        items = self._integrations.values()
        return [i for i in items if service_id is None or i.service_id == service_id]

    def get_integration(self, integration_id: str) -> Integration:
        try:
            return self._integrations[integration_id]
        except KeyError:
            raise NotFoundError("Integration", integration_id) from None

    def create_integration(self, data: IntegrationCreate) -> Integration:
        with self._lock:
            if data.service_id not in self._services:
                raise UnknownServiceError(data.service_id)
            if data.id is not None and data.id in self._integrations:
                raise ConflictError("Integration", data.id)
            base = slugify(f"{data.service_id}-{data.type}")
            integration_id = data.id or _unique_id(base, self._integrations)
            integration = Integration(
                id=integration_id,
                created_at=datetime.now(UTC),
                **data.model_dump(exclude={"id"}),
            )
            self._integrations[integration_id] = integration
            return integration
