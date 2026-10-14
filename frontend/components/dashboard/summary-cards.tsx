"use client";

import { CircleCheck, CircleHelp, OctagonAlert, Rocket, Siren, TriangleAlert, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { Suspense, use } from "react";
import { ValueSkeleton } from "@/components/services/registry-states";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { fadeUp, hoverLift, staggerContainer } from "@/lib/motion";
import { summarizeServices, type ServiceSummary } from "@/lib/services";
import { healthStyles } from "@/lib/status";
import type { ServiceRegistryResult } from "@/types";

interface StatCardProps {
  label: string;
  icon: LucideIcon;
  tone: string;
  children: React.ReactNode;
  hint: React.ReactNode;
}

function StatCard({ label, icon: Icon, tone, children, hint }: StatCardProps) {
  return (
    <motion.li
      variants={fadeUp}
      whileHover={hoverLift}
      className="rounded-xl border border-line bg-surface p-4 backdrop-blur-sm transition-colors hover:border-line-strong"
    >
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{label}</span>
        <Icon className={`size-4 ${tone}`} aria-hidden="true" />
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight">{children}</div>
      <p className="mt-1 text-xs text-faint">{hint}</p>
    </motion.li>
  );
}

const DemoHint = ({ children }: { children: React.ReactNode }) => (
  <>
    <span className="font-medium text-muted">Demo data</span> · {children}
  </>
);

/** Reads the streamed registry and renders one value from its summary. */
function LiveValue({
  registry,
  render,
}: {
  registry: Promise<ServiceRegistryResult>;
  render: (summary: ServiceSummary) => React.ReactNode;
}) {
  const result = use(registry);
  if (!result.ok) return <span className="text-base font-normal text-faint">Unavailable</span>;
  return render(summarizeServices(result.services));
}

const overallIcons = { healthy: CircleCheck, degraded: TriangleAlert, down: OctagonAlert, unknown: CircleHelp } as const;

function OverallStatus({ summary }: { summary: ServiceSummary }) {
  if (summary.overall === null) return <span className="text-muted">No services</span>;
  const style = healthStyles[summary.overall];
  const Icon = overallIcons[summary.overall];
  return (
    <span className={`inline-flex items-center gap-2 ${style.text}`}>
      <Icon className="size-5" aria-hidden="true" />
      {summary.overall === "down" ? "Partial outage" : style.label}
    </span>
  );
}

interface SummaryCardsProps {
  registry: Promise<ServiceRegistryResult>;
  activeIncidents: number;
  deployments: number;
}

export function SummaryCards({ registry, activeIncidents, deployments }: SummaryCardsProps) {
  const live = (render: (summary: ServiceSummary) => React.ReactNode) => (
    <Suspense fallback={<ValueSkeleton />}>
      <LiveValue registry={registry} render={render} />
    </Suspense>
  );

  return (
    <motion.ul
      variants={staggerContainer}
      className="grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
      aria-label="System summary"
    >
      <StatCard label="System status" icon={CircleCheck} tone="text-muted" hint="Worst status across registered services">
        {live((s) => <OverallStatus summary={s} />)}
      </StatCard>
      <StatCard label="Active incidents" icon={Siren} tone="text-crit" hint={<DemoHint>open incidents</DemoHint>}>
        <AnimatedNumber value={activeIncidents} />
      </StatCard>
      <StatCard label="Services healthy" icon={CircleCheck} tone="text-ok" hint="Reporting healthy">
        {live((s) => (
          <>
            <AnimatedNumber value={s.healthy} />
            <span className="text-base font-normal text-faint"> / {s.total}</span>
          </>
        ))}
      </StatCard>
      <StatCard label="Degraded or down" icon={TriangleAlert} tone="text-warn" hint="Services reporting problems">
        {live((s) => <AnimatedNumber value={s.degradedOrDown} />)}
      </StatCard>
      <StatCard label="Deployments" icon={Rocket} tone="text-accent" hint={<DemoHint>last 24 hours</DemoHint>}>
        <AnimatedNumber value={deployments} />
      </StatCard>
    </motion.ul>
  );
}
