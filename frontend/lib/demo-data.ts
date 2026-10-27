/**
 * Empty dashboard data.
 *
 * The application has not yet been connected to real incident, deployment,
 * activity, or chart data endpoints. Keep these collections empty instead of
 * presenting fabricated demo records as live production information.
 */
import type { DemoDashboardData } from "@/types";

export const demoDashboard: DemoDashboardData = {
  incidents: [],
  deployments: [],
  activity: [],
  telemetry: [],
};
