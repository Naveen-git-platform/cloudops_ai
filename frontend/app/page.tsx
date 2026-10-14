import { DashboardShell } from "@/components/layout/dashboard-shell";
import { loadServiceRegistry } from "@/lib/api";
import { demoDashboard } from "@/lib/demo-data";

export default function Home() {
  // Not awaited: the result streams into the dashboard's Suspense boundaries,
  // so the rest of the page renders immediately with loading placeholders.
  const registry = loadServiceRegistry();
  return <DashboardShell demo={demoDashboard} registry={registry} />;
}
