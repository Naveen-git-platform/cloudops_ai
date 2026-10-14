/**
 * DEMO DATA — for UI development only.
 *
 * Static sample data for dashboard sections whose backend endpoints don't
 * exist yet: incidents, deployments, activity and telemetry. Services and
 * integrations come from the API (see lib/api.ts). Replace each export here
 * once its endpoint ships.
 */
import type { ActivityEvent, DemoDashboardData, Deployment, Incident, TelemetryPoint } from "@/types";

// Timestamps are fixed relative to a reference time so server and client
// renders match (no hydration mismatch from Date.now()).
export const DEMO_NOW = new Date("2026-10-10T14:30:00Z");
const minutesAgo = (m: number) => new Date(DEMO_NOW.getTime() - m * 60_000).toISOString();

const incidents: Incident[] = [
  {
    id: "INC-1042",
    title: "Elevated 5xx error rate on checkout",
    severity: "critical",
    status: "investigating",
    service: "checkout-api",
    detectedAt: minutesAgo(18),
    resolvedAt: null,
    description:
      "Error rate climbed to 7.4% after connection pool exhaustion on the primary payments database replica.",
  },
  {
    id: "INC-1041",
    title: "p95 latency above SLO for search",
    severity: "warning",
    status: "identified",
    service: "search-service",
    detectedAt: minutesAgo(52),
    resolvedAt: null,
    description:
      "Index rebuild is saturating CPU on two of five search nodes. p95 latency is 840 ms against a 500 ms SLO.",
  },
  {
    id: "INC-1040",
    title: "Consumer lag on order events queue",
    severity: "warning",
    status: "monitoring",
    service: "order-worker",
    detectedAt: minutesAgo(95),
    resolvedAt: null,
    description:
      "Lag peaked at 48k messages. Autoscaling added 3 workers and lag is now draining steadily.",
  },
  {
    id: "INC-1039",
    title: "TLS certificate expiry on edge gateway",
    severity: "resolved",
    status: "resolved",
    service: "edge-gateway",
    detectedAt: minutesAgo(310),
    resolvedAt: minutesAgo(262),
    description:
      "Certificate auto-renewal failed due to a DNS challenge timeout. Renewed manually and expiry alerting added.",
  },
];

const deployments: Deployment[] = [
  { id: "dep-879", service: "checkout-api", version: "v3.8.1", environment: "production", status: "in_progress", deployedAt: minutesAgo(8), author: "sam.k" },
  { id: "dep-881", service: "catalog-api", version: "v2.14.0", environment: "production", status: "succeeded", deployedAt: minutesAgo(35), author: "priya.n" },
  { id: "dep-880", service: "auth-service", version: "v5.3.2", environment: "production", status: "succeeded", deployedAt: minutesAgo(140), author: "marcus.l" },
  { id: "dep-878", service: "search-service", version: "v1.22.0", environment: "staging", status: "failed", deployedAt: minutesAgo(220), author: "ana.r" },
];

const activity: ActivityEvent[] = [
  { id: "evt-6", kind: "incident_detected", title: "Incident INC-1042 detected", detail: "checkout-api · 5xx rate 7.4%", timestamp: minutesAgo(18) },
  { id: "evt-5", kind: "deployment", title: "Deployment completed", detail: "catalog-api v2.14.0 → production", timestamp: minutesAgo(35) },
  { id: "evt-4", kind: "pr_merged", title: "PR #214 merged", detail: "fix: raise payments DB pool size", timestamp: minutesAgo(41) },
  { id: "evt-3", kind: "incident_detected", title: "Incident INC-1041 detected", detail: "search-service · p95 840 ms", timestamp: minutesAgo(52) },
  { id: "evt-2", kind: "service_recovered", title: "edge-gateway recovered", detail: "TLS certificate renewed", timestamp: minutesAgo(262) },
];

const telemetry: TelemetryPoint[] = Array.from({ length: 48 }, (_, i) => ({
  timestamp: minutesAgo((47 - i) * 30),
  requestRate: Math.round(1800 + Math.sin(i / 5) * 420 + Math.cos(i / 2.3) * 90),
  errorRate: Number((0.3 + (i > 42 ? (i - 42) * 1.2 : Math.abs(Math.sin(i / 3)) * 0.4)).toFixed(2)),
}));

export const demoDashboard: DemoDashboardData = {
  incidents,
  deployments,
  activity,
  telemetry,
};
