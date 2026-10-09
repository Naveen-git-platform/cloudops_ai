"use client";

import { motion } from "motion/react";
import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { formatRelative } from "@/lib/format";
import { fadeUp, staggerContainer } from "@/lib/motion";
import { deploymentStyles } from "@/lib/status";
import type { Deployment } from "@/types";

export function DeploymentsList({ deployments }: { deployments: Deployment[] }) {
  return (
    <Panel id="deployments" title="Recent deployments" description="Across all environments" className="scroll-mt-20">
      <motion.ul variants={staggerContainer} className="divide-y divide-line">
        {deployments.map((d) => {
          const style = deploymentStyles[d.status];
          return (
            <motion.li key={d.id} variants={fadeUp} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
              <div className="min-w-0">
                <p className="truncate text-sm">
                  <span className="font-mono">{d.service}</span> <span className="font-mono text-muted">{d.version}</span>
                </p>
                <p className="text-xs text-faint">
                  {d.environment} · {d.author} · {formatRelative(d.deployedAt)}
                </p>
              </div>
              <Badge tone={style.badge}>{style.label}</Badge>
            </motion.li>
          );
        })}
      </motion.ul>
    </Panel>
  );
}
