"use client";

import { CircleCheck, OctagonAlert, Rocket, Siren, TriangleAlert, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { fadeUp, hoverLift, staggerContainer } from "@/lib/motion";
import { healthStyles } from "@/lib/status";
import type { DashboardSummary } from "@/types";

interface StatCardProps {
  label: string;
  icon: LucideIcon;
  tone: string;
  children: React.ReactNode;
  hint: string;
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

export function SummaryCards({ summary, totalServices }: { summary: DashboardSummary; totalServices: number }) {
  const overall = healthStyles[summary.overallStatus];
  const OverallIcon = summary.overallStatus === "healthy" ? CircleCheck : summary.overallStatus === "down" ? OctagonAlert : TriangleAlert;

  return (
    <motion.ul
      variants={staggerContainer}
      className="grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
      aria-label="System summary"
    >
      <StatCard label="System status" icon={OverallIcon} tone={overall.text} hint="Worst service state across production">
        <span className={overall.text}>{summary.overallStatus === "down" ? "Partial outage" : overall.label}</span>
      </StatCard>
      <StatCard label="Active incidents" icon={Siren} tone="text-crit" hint="Investigating, identified or monitoring">
        <AnimatedNumber value={summary.activeIncidents} />
      </StatCard>
      <StatCard label="Services healthy" icon={CircleCheck} tone="text-ok" hint="Passing health checks and SLOs">
        <AnimatedNumber value={summary.servicesHealthy} />
        <span className="text-base font-normal text-faint"> / {totalServices}</span>
      </StatCard>
      <StatCard label="Degraded or down" icon={TriangleAlert} tone="text-warn" hint="Breaching latency or error SLOs">
        <AnimatedNumber value={summary.servicesDegraded} />
      </StatCard>
      <StatCard label="Deployments" icon={Rocket} tone="text-accent" hint="Last 24 hours, all environments">
        <AnimatedNumber value={summary.deploymentsLast24h} />
      </StatCard>
    </motion.ul>
  );
}
