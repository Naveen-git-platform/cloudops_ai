/**
 * Typed client for the CloudOps FastAPI backend.
 *
 * Requests are made from the Next.js server, never the browser, so the API
 * URL stays server-side and the backend needs no CORS configuration.
 *
 * Implemented by the backend: GET /health, /services, /integrations.
 * Planned (not called yet): /incidents, /deployments, /telemetry — those
 * dashboard sections still read lib/demo-data.ts.
 */
import { connection } from "next/server";
import type {
  Deployment,
  HealthResponse,
  Incident,
  Integration,
  Service,
  ServiceRegistryResult,
  TelemetryPoint,
} from "@/types";

/** Base URL of the FastAPI backend, from the CLOUDOPS_API_URL environment variable. */
export const API_BASE_URL = (process.env.CLOUDOPS_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

const REQUEST_TIMEOUT_MS = 5_000;

export class ApiError extends Error {
  constructor(
    public readonly path: string,
    /** HTTP status, or null when the request never got a response. */
    public readonly status: number | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (cause) {
    const timedOut = cause instanceof DOMException && cause.name === "TimeoutError";
    throw new ApiError(path, null, timedOut ? "timed out" : "could not connect");
  }
  if (!res.ok) throw new ApiError(path, res.status, `responded with HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** GET /health */
export const getHealth = () => request<HealthResponse>("/health");

/** GET /services */
export const getServices = () => request<Service[]>("/services");

/** GET /integrations, optionally only those for one service. */
export const getIntegrations = (serviceId?: string) =>
  request<Integration[]>(serviceId ? `/integrations?service_id=${encodeURIComponent(serviceId)}` : "/integrations");

/** GET /incidents — planned, not yet implemented by the backend. */
export const getIncidents = () => request<Incident[]>("/incidents");

/** GET /deployments — planned, not yet implemented by the backend. */
export const getDeployments = () => request<Deployment[]>("/deployments");

/** GET /telemetry — planned, not yet implemented by the backend. */
export const getTelemetry = () => request<TelemetryPoint[]>("/telemetry");

function describeError(error: unknown): ServiceRegistryResult & { ok: false } {
  if (error instanceof ApiError && error.status === null) {
    return {
      ok: false,
      error: {
        title: "Can't reach the CloudOps API",
        detail: `The request to ${API_BASE_URL} ${error.message}. Check that the backend is running and that CLOUDOPS_API_URL is correct.`,
      },
    };
  }
  if (error instanceof ApiError) {
    return {
      ok: false,
      error: {
        title: "The CloudOps API returned an error",
        detail: `GET ${error.path} ${error.message}. Check the backend logs for details.`,
      },
    };
  }
  return {
    ok: false,
    error: { title: "Something went wrong loading services", detail: "The API response could not be read." },
  };
}

/**
 * Loads services and their integrations for the dashboard. Never rejects:
 * failures become a user-facing error description.
 */
export async function loadServiceRegistry(): Promise<ServiceRegistryResult> {
  // Fetch per request, not at build time.
  await connection();

  const [services, integrations] = await Promise.allSettled([getServices(), getIntegrations()]);
  if (services.status === "rejected") {
    console.error("Failed to load services from the CloudOps API:", services.reason);
    return describeError(services.reason);
  }
  if (integrations.status === "rejected") {
    console.error("Failed to load integrations from the CloudOps API:", integrations.reason);
  }
  return {
    ok: true,
    services: services.value,
    integrations: integrations.status === "fulfilled" ? integrations.value : null,
  };
}
