/**
 * Shared domain types.
 *
 * `Service` and `Integration` mirror the FastAPI responses exactly (snake_case
 * included). Demo types describe panels whose backend endpoints don't exist yet.
 */

export type HealthStatus = "healthy" | "degraded" | "down";
export type ServiceStatus = HealthStatus | "unknown";
export type Severity = "critical" | "warning" | "resolved";
export type IncidentStatus = "investigating" | "identified" | "monitoring" | "resolved";
export type Environment = "production" | "staging" | "development";

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
  detectedAt: string;
  resolvedAt: string | null;
  description: string;
}

export interface Service {
  id: string;
  name: string;
  description: string;
  environment: Environment;
  status: ServiceStatus;
  created_at: string;
}

export type IntegrationType =
  | "github" | "aws" | "kubernetes" | "stripe" | "postgresql" | "redis" | "opentelemetry" | "other";
export type IntegrationStatus = "pending" | "connected" | "degraded" | "disconnected";

export interface Integration {
  id: string;
  name: string;
  type: IntegrationType;
  status: IntegrationStatus;
  service_id: string;
  created_at: string;
}

export type ServiceRegistryResult =
  | { ok: true; services: Service[]; integrations: Integration[] | null }
  | { ok: false; error: { title: string; detail: string } };

export interface Deployment {
  id: string;
  service: string;
  version: string;
  environment: Environment;
  status: "succeeded" | "failed" | "in_progress";
  deployedAt: string;
  author: string;
}

export type ActivityKind = "deployment" | "incident_detected" | "pr_merged" | "service_recovered";

export interface ActivityEvent {
  id: string;
  kind: ActivityKind;
  title: string;
  detail: string;
  timestamp: string;
}

/** Response item from GET /telemetry/records. */
export interface TelemetryRecord {
  id: number;
  signal: "traces" | "metrics" | "logs";
  service_name: string;
  service_namespace: string | null;
  service_version: string | null;
  environment: string | null;
  host_name: string | null;
  scope_name: string | null;
  scope_version: string | null;
  timestamp: string;
  end_timestamp: string | null;
  received_at: string;
  name: string | null;
  trace_id: string | null;
  span_id: string | null;
  parent_span_id: string | null;
  span_kind: string | null;
  status_code: string | null;
  severity_number: number | null;
  severity_text: string | null;
  body: string | null;
  metric_type: string | null;
  unit: string | null;
  value: number | null;
  resource_attributes: Record<string, unknown>;
  attributes: Record<string, unknown>;
  raw: Record<string, unknown>;
}

export type TelemetryResult =
  | { ok: true; records: TelemetryRecord[]; truncated: boolean }
  | { ok: false; error: { title: string; detail: string } };

/** Demo-only data for sections without backend endpoints yet. */
export interface DemoDashboardData {
  incidents: Incident[];
  deployments: Deployment[];
  activity: ActivityEvent[];
  telemetry: TelemetryPoint[];
}

/** Legacy chart points retained for demo-only fixtures; not a live metric contract. */
export interface TelemetryPoint {
  timestamp: string;
  requestRate: number;
  errorRate: number;
}
