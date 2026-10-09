/**
 * Typed client for the CloudOps FastAPI backend.
 *
 * Only GET /health exists on the backend today. The other functions describe
 * endpoints planned for future issues; until they ship, the dashboard reads
 * from lib/demo-data.ts through getDashboardData().
 */
import { demoDashboard } from "@/lib/demo-data";
import type {
  DashboardData,
  Deployment,
  HealthResponse,
  Incident,
  Service,
  TelemetryPoint,
} from "@/types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly path: string,
  ) {
    super(`Request to ${path} failed with status ${status}`);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!res.ok) throw new ApiError(res.status, path);
  return (await res.json()) as T;
}

/** GET /health — implemented by the backend. */
export const getHealth = () => request<HealthResponse>("/health");

/** GET /incidents — planned, not yet implemented by the backend. */
export const getIncidents = () => request<Incident[]>("/incidents");

/** GET /services — planned, not yet implemented by the backend. */
export const getServices = () => request<Service[]>("/services");

/** GET /deployments — planned, not yet implemented by the backend. */
export const getDeployments = () => request<Deployment[]>("/deployments");

/** GET /telemetry — planned, not yet implemented by the backend. */
export const getTelemetry = () => request<TelemetryPoint[]>("/telemetry");

/**
 * Data source for the dashboard. Returns demo data for now; replace the body
 * with the API calls above once those endpoints exist.
 */
export async function getDashboardData(): Promise<DashboardData> {
  return demoDashboard;
}
