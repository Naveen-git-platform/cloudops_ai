/**
 * Typed server-side client for the CloudOps FastAPI backend.
 * Never expose the API URL or access token to browser code.
 */
import { connection } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { Deployment, HealthResponse, Incident, Integration, Service, ServiceRegistryResult, TelemetryRecord, TelemetryResult } from "@/types";

// Use the deployed API as the safe production fallback. Local development can
// override this with CLOUDOPS_API_URL=http://127.0.0.1:8000 in its local env.
export const API_BASE_URL = (
  process.env.CLOUDOPS_API_URL ??
  (process.env.NODE_ENV === "production"
    ? "https://cloudops-ai-api.onrender.com"
    : "http://127.0.0.1:8000")
).replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 30_000;
const TELEMETRY_LIMIT = 1000;

export class ApiError extends Error {
  constructor(public readonly path: string, public readonly status: number | null, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string): Promise<T> {
  let res: Response;
  try {
    const supabase = await createSupabaseServerClient();
    const { data: { session } } = await supabase.auth.getSession();
    res = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        Accept: "application/json",
        ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
      },
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (cause) {
    if (cause instanceof ApiError) throw cause;
    const timedOut = cause instanceof DOMException && cause.name === "TimeoutError";
    throw new ApiError(path, null, timedOut ? "timed out" : "could not connect");
  }
  if (!res.ok) throw new ApiError(path, res.status, `responded with HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const getHealth = () => request<HealthResponse>("/health");
export const getServices = () => request<Service[]>("/services");
export const getIntegrations = (serviceId?: string) =>
  request<Integration[]>(serviceId ? `/integrations?service_id=${encodeURIComponent(serviceId)}` : "/integrations");
export const getIncidents = () => request<Incident[]>("/incidents");
export const getDeployments = () => request<Deployment[]>("/deployments");

/** Fetch stored telemetry from the protected API, bounded to the last 24 hours and 1,000 records. */
export async function getTelemetryRecords(): Promise<TelemetryResult> {
  await connection();
  const end = new Date();
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  const params = new URLSearchParams({
    start: start.toISOString(),
    end: end.toISOString(),
    limit: String(TELEMETRY_LIMIT),
  });
  const path = `/telemetry/records?${params.toString()}`;
  try {
    const records = await request<TelemetryRecord[]>(path);
    return { ok: true, records, truncated: records.length === TELEMETRY_LIMIT };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return { ok: false, error: { title: "Sign in to view telemetry", detail: "Your session is missing or expired. Sign in again to query stored telemetry." } };
    }
    if (error instanceof ApiError && error.status === 403) {
      return { ok: false, error: { title: "Telemetry access denied", detail: "Your account is not authorized to read stored telemetry." } };
    }
    if (error instanceof ApiError && error.status === null) {
      return { ok: false, error: { title: "Can't reach the CloudOps API", detail: `The request to ${API_BASE_URL} ${error.message}. Check that the backend is running and CLOUDOPS_API_URL is correct.` } };
    }
    if (error instanceof ApiError) {
      return { ok: false, error: { title: "Telemetry API returned an error", detail: `GET ${error.path} ${error.message}. Check backend logs for details.` } };
    }
    return { ok: false, error: { title: "Unable to read telemetry", detail: "The API response could not be read." } };
  }
}

function describeError(error: unknown): ServiceRegistryResult & { ok: false } {
  if (error instanceof ApiError && error.status === null) {
    return { ok: false, error: { title: "Can't reach the CloudOps API", detail: `The request to ${API_BASE_URL} ${error.message}. Check that the backend is running and CLOUDOPS_API_URL is correct.` } };
  }
  if (error instanceof ApiError && error.status === 401) {
    return { ok: false, error: { title: "Your session needs refreshing", detail: "Sign in again to continue loading service data." } };
  }
  if (error instanceof ApiError) {
    return { ok: false, error: { title: "The CloudOps API returned an error", detail: `GET ${error.path} ${error.message}. Check the backend logs for details.` } };
  }
  return { ok: false, error: { title: "Something went wrong loading services", detail: "The API response could not be read." } };
}

export async function loadServiceRegistry(): Promise<ServiceRegistryResult> {
  await connection();
  const [services, integrations] = await Promise.allSettled([getServices(), getIntegrations()]);
  if (services.status === "rejected") {
    console.error("Failed to load services from the CloudOps API:", services.reason instanceof ApiError ? services.reason.name : "request failed");
    return describeError(services.reason);
  }
  if (integrations.status === "rejected") {
    console.error("Failed to load integrations from the CloudOps API:", integrations.reason instanceof ApiError ? integrations.reason.name : "request failed");
  }
  return { ok: true, services: services.value, integrations: integrations.status === "fulfilled" ? integrations.value : null };
}
