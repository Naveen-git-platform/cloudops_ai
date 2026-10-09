/**
 * Shared domain types. These mirror the shapes the FastAPI backend will
 * return, so components can switch from demo data to API data unchanged.
 */

export type HealthStatus = "healthy" | "degraded" | "down";
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

export interface Service {
  id: string;
  name: string;
  status: HealthStatus;
  /** p95 latency in milliseconds */
  latencyMs: number;
  /** 30-day uptime percentage */
  uptimePct: number;
  /** Recent latency samples for the sparkline */
  latencyHistory: number[];
}

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

export interface DashboardSummary {
  activeIncidents: number;
  servicesHealthy: number;
  servicesDegraded: number;
  deploymentsLast24h: number;
  overallStatus: HealthStatus;
}

export interface DashboardData {
  summary: DashboardSummary;
  incidents: Incident[];
  services: Service[];
  deployments: Deployment[];
  activity: ActivityEvent[];
  telemetry: TelemetryPoint[];
}
