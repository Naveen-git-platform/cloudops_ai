/**
 * Typed server-side client for the CloudOps FastAPI backend.
 * Never expose the API URL or access token to browser code.
 */
import { connection } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { Deployment, HealthResponse, Incident, Integration, Service, ServiceRegistryResult, TelemetryPoint } from "@/types";

export const API_BASE_URL = (process.env.CLOUDOPS_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 5_000;

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
export const getTelemetry = () => request<TelemetryPoint[]>("/telemetry");

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
