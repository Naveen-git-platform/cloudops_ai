"use client";

import { motion } from "motion/react";
import { Panel } from "@/components/ui/panel";
import { Sparkline } from "@/components/ui/sparkline";
import { StatusDot } from "@/components/ui/status-dot";
import { fadeUp, hoverLift, staggerContainer } from "@/lib/motion";
import { healthStyles } from "@/lib/status";
import type { Service } from "@/types";

export function ServiceHealthList({ services }: { services: Service[] }) {
  return (
    <Panel id="services" title="Service health" description="p95 latency and 30-day uptime" className="scroll-mt-20">
      {services.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">No services match the current filter.</p>
      ) : (
        <motion.ul variants={staggerContainer} initial="hidden" animate="show" className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {services.map((s) => {
            const style = healthStyles[s.status];
            return (
              <motion.li
                key={s.id}
                variants={fadeUp}
                whileHover={hoverLift}
                className="flex items-center gap-3 rounded-lg border border-line bg-white/[0.015] px-3.5 py-3 transition-colors hover:border-line-strong"
              >
                <StatusDot status={s.status} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-sm">{s.name}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    <span className={style.text}>{style.label}</span>
                    <span className="text-faint"> · </span>
                    <span className="tabular-nums">{s.latencyMs.toLocaleString("en-US")} ms</span>
                    <span className="text-faint"> · </span>
                    <span className="tabular-nums">{s.uptimePct}%</span>
                    <span className="sr-only"> uptime</span>
                  </p>
                </div>
                <Sparkline values={s.latencyHistory} className={`shrink-0 ${style.text}`} />
              </motion.li>
            );
          })}
        </motion.ul>
      )}
    </Panel>
  );
}
