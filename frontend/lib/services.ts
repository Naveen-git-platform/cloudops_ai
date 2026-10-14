import type { Integration, Service, ServiceStatus } from "@/types";

export interface ServiceSummary {
  total: number;
  healthy: number;
  degradedOrDown: number;
  unknown: number;
  /** Worst status across services; null when no services are registered. */
  overall: ServiceStatus | null;
}

export function summarizeServices(services: Service[]): ServiceSummary {
  const count = (status: ServiceStatus) => services.filter((s) => s.status === status).length;
  const healthy = count("healthy");
  const degraded = count("degraded");
  const down = count("down");
  const unknown = count("unknown");

  let overall: ServiceStatus | null = null;
  if (down > 0) overall = "down";
  else if (degraded > 0) overall = "degraded";
  else if (unknown > 0) overall = "unknown";
  else if (healthy > 0) overall = "healthy";

  return { total: services.length, healthy, degradedOrDown: degraded + down, unknown, overall };
}

export function groupIntegrationsByService(integrations: Integration[]): Map<string, Integration[]> {
  const groups = new Map<string, Integration[]>();
  for (const integration of integrations) {
    const list = groups.get(integration.service_id) ?? [];
    list.push(integration);
    groups.set(integration.service_id, list);
  }
  return groups;
}
