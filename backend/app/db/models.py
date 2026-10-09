"""SQLAlchemy table definitions.

Enum columns are stored as plain strings with a CHECK constraint
(`native_enum=False`, `create_constraint=True`) so new values can be added without altering a
PostgreSQL enum type.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime
from app.models.enums import Environment, IntegrationStatus, IntegrationType, ServiceStatus


def _str_enum[E: StrEnum](enum_type: type[E], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
        create_constraint=True,
    )


class ServiceRecord(Base):
    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    environment: Mapped[Environment] = mapped_column(_str_enum(Environment, "ck_services_environment"))
    status: Mapped[ServiceStatus] = mapped_column(_str_enum(ServiceStatus, "ck_services_status"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)

    integrations: Mapped[list["IntegrationRecord"]] = relationship(back_populates="service")


class IntegrationRecord(Base):
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[IntegrationType] = mapped_column(_str_enum(IntegrationType, "ck_integrations_type"))
    status: Mapped[IntegrationStatus] = mapped_column(_str_enum(IntegrationStatus, "ck_integrations_status"))
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)

    service: Mapped[ServiceRecord] = relationship(back_populates="integrations")
