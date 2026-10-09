"use client";

import { MotionConfig, motion } from "motion/react";
import { useCallback, useMemo, useState } from "react";
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
import { ServiceHealthList } from "@/components/services/service-health-list";
import { DEMO_NOW } from "@/lib/demo-data";
import { staggerContainer } from "@/lib/motion";
import type { DashboardData, Incident } from "@/types";

const matches = (query: string, ...fields: string[]) =>
  fields.some((f) => f.toLowerCase().includes(query.trim().toLowerCase()));

export function DashboardShell({ data }: { data: DashboardData }) {
  const [incidents, setIncidents] = useState<Incident[]>(data.incidents);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [navOpen, setNavOpen] = useState(false);
  const activeId = useActiveSection(sectionIds);

  const summary = useMemo(
    () => ({ ...data.summary, activeIncidents: incidents.filter((i) => i.status !== "resolved").length }),
    [data.summary, incidents],
  );
  const filteredIncidents = incidents.filter((i) => matches(query, i.title, i.service, i.id));
  const filteredServices = data.services.filter((s) => matches(query, s.name));
  const selected = incidents.find((i) => i.id === selectedId) ?? null;

  const closeDetail = useCallback(() => setSelectedId(null), []);
  const closeNav = useCallback(() => setNavOpen(false), []);

  // Demo-only: resolves locally. Will become a PATCH /incidents/{id} call.
  const resolveIncident = (id: string) =>
    setIncidents((prev) =>
      prev.map((i) =>
        i.id === id ? { ...i, status: "resolved", severity: "resolved", resolvedAt: DEMO_NOW.toISOString() } : i,
      ),
    );

  return (
    <MotionConfig reducedMotion="user">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-lg focus:bg-surface-strong focus:px-3 focus:py-2 focus:text-sm"
      >
        Skip to content
      </a>

      <div className="flex min-h-screen">
        {/* Rail on tablet, full sidebar on desktop, hidden on mobile */}
        <aside className="sticky top-0 hidden h-screen w-16 shrink-0 flex-col gap-6 border-r border-line bg-canvas/60 p-3 backdrop-blur md:flex lg:w-60 lg:p-4">
          <div className="hidden lg:block">
            <Brand />
          </div>
          <div className="flex justify-center lg:hidden">
            <Brand compact />
          </div>
          <SidebarNav activeId={activeId} compact layoutScope="desktop" />
          <p className="mt-auto hidden rounded-lg border border-line p-3 text-[11px] leading-relaxed text-faint lg:block">
            Showing demo data. Live data will come from the CloudOps API.
          </p>
        </aside>

        <MobileNav open={navOpen} activeId={activeId} onClose={closeNav} />

        <div className="min-w-0 flex-1">
          <Header
            query={query}
            onQueryChange={setQuery}
            incidents={incidents}
            onSelectIncident={setSelectedId}
            onOpenMenu={() => setNavOpen(true)}
          />

          <motion.main
            id="main"
            initial="hidden"
            animate="show"
            variants={staggerContainer}
            className="mx-auto max-w-[1440px] space-y-4 px-4 py-6 sm:px-6"
          >
            <motion.div
              id="overview"
              className="scroll-mt-20"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
              <p className="mt-1 text-sm text-muted">Production health across {data.services.length} services in us-east-1.</p>
            </motion.div>

            <SummaryCards summary={summary} totalServices={data.services.length} />

            <div className="grid gap-4 lg:grid-cols-3">
              <IncidentList incidents={filteredIncidents} onOpen={setSelectedId} />
              <ActivityTimeline events={data.activity} />
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <SystemHealthChart points={data.telemetry} />
              <DeploymentsList deployments={data.deployments} />
            </div>

            <ServiceHealthList services={filteredServices} />
          </motion.main>
        </div>
      </div>

      <IncidentDetailPanel incident={selected} onClose={closeDetail} onResolve={resolveIncident} />
    </MotionConfig>
  );
}
