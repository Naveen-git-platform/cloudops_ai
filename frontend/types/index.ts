/**
 * Shared domain types.
 *
 * `Service` and `Integration` mirror the FastAPI responses exactly (snake_case
 * included). The remaining types describe demo data for sections whose
 * backend endpoints don't exist yet.
 */

export type HealthStatus = "healthy" | "degraded" | "down";
/** Service status as stored by the backend; `unknown` until health checks exist. */
export type ServiceStatus = HealthStatus | "unknown";
export type Severity = "critical" | "warning" | "resolved";
export type IncidentStatus = "investigating" | "identified" | "monitoring" | "resolved";
export type Environment = "production" | "staging" | "development";

/** Response from GET /health */
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface Incident {
  id: string;
  title: string;
  severity: Severity;
  status: IncidentStatus;
  service: string;
  /** ISO 8601 timestamp */
  detectedAt: string;
  /** ISO 8601 timestamp, null while ongoing */
  resolvedAt: string | null;
  description: string;
}

/** Response item from GET /services */
export interface Service {
  id: string;
  name: string;
  description: string;
  environment: Environment;
  status: ServiceStatus;
  /** ISO 8601 timestamp */
  created_at: string;
}

export type IntegrationType =
  | "github"
  | "aws"
  | "kubernetes"
  | "stripe"
  | "postgresql"
  | "redis"
  | "opentelemetry"
  | "other";

export type IntegrationStatus = "pending" | "connected" | "degraded" | "disconnected";

/** Response item from GET /integrations */
export interface Integration {
  id: string;
  name: string;
  type: IntegrationType;
  status: IntegrationStatus;
  service_id: string;
  /** ISO 8601 timestamp */
  created_at: string;
}

/**
 * Result of loading services and integrations from the API. Never rejects, so
 * it can be streamed to client components and rendered as a loading/error state.
 */
export type ServiceRegistryResult =
  | {
      ok: true;
      services: Service[];
      /** null when GET /integrations failed but services loaded */
      integrations: Integration[] | null;
    }
  | { ok: false; error: { title: string; detail: string } };

export interface Deployment {
  id: string;
  service: string;
  version: string;
  environment: Environment;
  status: "succeeded" | "failed" | "in_progress";
  /** ISO 8601 timestamp */
  deployedAt: string;
  author: string;
}

export type ActivityKind = "deployment" | "incident_detected" | "pr_merged" | "service_recovered";

export interface ActivityEvent {
  id: string;
  kind: ActivityKind;
  title: string;
  detail: string;
  /** ISO 8601 timestamp */
  timestamp: string;
}

export interface TelemetryPoint {
  /** ISO 8601 timestamp */
  timestamp: string;
  /** Requests per second */
  requestRate: number;
  /** Error rate percentage */
  errorRate: number;
}

/** Demo-only data for sections without backend endpoints yet. */
export interface DemoDashboardData {
  incidents: Incident[];
  deployments: Deployment[];
  activity: ActivityEvent[];
  telemetry: TelemetryPoint[];
}
