import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getTelemetryRecords, loadServiceRegistry } from "@/lib/api";
import { demoDashboard } from "@/lib/demo-data";

export default function Home() {
  // These promises stream independently so live API panels do not block the page.
  const registry = loadServiceRegistry();
  const telemetry = getTelemetryRecords();
  return <DashboardShell demo={demoDashboard} registry={registry} telemetry={telemetry} />;
}
