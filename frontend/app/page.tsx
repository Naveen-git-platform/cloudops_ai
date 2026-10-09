import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getDashboardData } from "@/lib/api";

export default async function Home() {
  const data = await getDashboardData();
  return <DashboardShell data={data} />;
}
