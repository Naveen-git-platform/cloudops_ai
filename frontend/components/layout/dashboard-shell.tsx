"use client";

import { MotionConfig, motion } from "motion/react";
import { Suspense, use, useCallback, useState } from "react";
import { ActivityTimeline } from "@/components/activity/activity-timeline";
import { DeploymentsList } from "@/components/dashboard/deployments-list";
import { SummaryCards } from "@/components/dashboard/summary-cards";
import { SystemHealthChart } from "@/components/dashboard/system-health-chart";
import { IncidentDetailPanel } from "@/components/incidents/incident-detail-panel";
import { IncidentList } from "@/components/incidents/incident-list";
import { Brand } from "@/components/layout/brand";
import { Header } from "@/components/layout/header";
import { MobileNav } from "@/components/layout/mobile-nav";
import { sectionIds } from "@/components/layout/nav-items";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { useActiveSection } from "@/components/layout/use-active-section";
import { RegistryError } from "@/components/services/registry-states";
import { ServiceHealthList } from "@/components/services/service-health-list";
import { DEMO_NOW } from "@/lib/demo-data";
import { staggerContainer } from "@/lib/motion";
import { matchesQuery } from "@/lib/search";
import type { DemoDashboardData, Incident, ServiceRegistryResult, TelemetryResult } from "@/types";

function ServiceCount({ registry }: { registry: Promise<ServiceRegistryResult> }) {
  const result = use(registry);
  if (!result.ok) return <>Service data is currently unavailable.</>;
  const n = result.services.length;
  return <>Tracking {n} registered {n === 1 ? "service" : "services"} from the CloudOps API.</>;
}

function RegistryAlert({ registry }: { registry: Promise<ServiceRegistryResult> }) {
  const result = use(registry);
  return result.ok ? null : <RegistryError {...result.error} compact />;
}

interface DashboardShellProps {
  demo: DemoDashboardData;
  registry: Promise<ServiceRegistryResult>;
  telemetry: Promise<TelemetryResult>;
}

export function DashboardShell({ demo, registry, telemetry }: DashboardShellProps) {
  const [incidents, setIncidents] = useState<Incident[]>(demo.incidents);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [navOpen, setNavOpen] = useState(false);
  const activeId = useActiveSection(sectionIds);

  const activeIncidents = incidents.filter((i) => i.status !== "resolved").length;
  const filteredIncidents = incidents.filter((i) => matchesQuery(query, i.title, i.service, i.id));
  const selected = incidents.find((i) => i.id === selectedId) ?? null;

  const closeDetail = useCallback(() => setSelectedId(null), []);
  const closeNav = useCallback(() => setNavOpen(false), []);

  const resolveIncident = (id: string) =>
    setIncidents((prev) =>
      prev.map((i) =>
        i.id === id ? { ...i, status: "resolved", severity: "resolved", resolvedAt: DEMO_NOW.toISOString() } : i,
      ),
    );

  return (
    <MotionConfig reducedMotion="user">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-lg focus:bg-surface-strong focus:px-3 focus:py-2 focus:text-sm">
        Skip to content
      </a>
      <div className="flex min-h-screen">
        <aside className="sticky top-0 hidden h-screen w-16 shrink-0 flex-col gap-6 border-r border-line bg-canvas/60 p-3 backdrop-blur md:flex lg:w-60 lg:p-4">
          <div className="hidden lg:block"><Brand /></div>
          <div className="flex justify-center lg:hidden"><Brand compact /></div>
          <SidebarNav activeId={activeId} compact layoutScope="desktop" />
          <p className="mt-auto hidden rounded-lg border border-line p-3 text-[11px] leading-relaxed text-faint lg:block">
            Services and integrations are live from the CloudOps API. Telemetry is queried from stored backend records; incidents, activity and deployments remain demo data.
          </p>
        </aside>
        <MobileNav open={navOpen} activeId={activeId} onClose={closeNav} />
        <div className="min-w-0 flex-1">
          <Header query={query} onQueryChange={setQuery} incidents={incidents} onSelectIncident={setSelectedId} onOpenMenu={() => setNavOpen(true)} />
          <motion.main id="main" initial="hidden" animate="show" variants={staggerContainer} className="mx-auto max-w-[1440px] space-y-4 px-4 py-6 sm:px-6">
            <motion.div id="overview" className="scroll-mt-20" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
              <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
              <p className="mt-1 text-sm text-muted"><Suspense fallback="Loading services from the CloudOps API…"><ServiceCount registry={registry} /></Suspense></p>
            </motion.div>
            <Suspense fallback={null}><RegistryAlert registry={registry} /></Suspense>
            <SummaryCards registry={registry} activeIncidents={activeIncidents} deployments={demo.deployments.length} />
            <div className="grid gap-4 lg:grid-cols-3">
              <IncidentList incidents={filteredIncidents} onOpen={setSelectedId} />
              <ActivityTimeline events={demo.activity} />
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              <Suspense fallback={<div className="min-h-52 animate-pulse rounded-xl border border-line bg-surface p-5 text-xs text-muted">Loading stored telemetry…</div>}>
                <SystemHealthChart result={telemetry} />
              </Suspense>
              <DeploymentsList deployments={demo.deployments} />
            </div>
            <ServiceHealthList registry={registry} query={query} />
          </motion.main>
        </div>
      </div>
      <IncidentDetailPanel incident={selected} onClose={closeDetail} onResolve={resolveIncident} />
    </MotionConfig>
  );
}
