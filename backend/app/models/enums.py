from enum import StrEnum


class Environment(StrEnum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"


class ServiceStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class IntegrationType(StrEnum):
    GITHUB = "github"
    AWS = "aws"
    KUBERNETES = "kubernetes"
    STRIPE = "stripe"
    POSTGRESQL = "postgresql"
    REDIS = "redis"
    OPENTELEMETRY = "opentelemetry"
    OTHER = "other"


class IntegrationStatus(StrEnum):
    PENDING = "pending"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
