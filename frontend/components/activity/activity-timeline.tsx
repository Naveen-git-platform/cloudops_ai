"use client";

import { CircleCheck, GitMerge, Rocket, Siren, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { Panel } from "@/components/ui/panel";
import { formatClock, formatRelative } from "@/lib/format";
import type { ActivityEvent, ActivityKind } from "@/types";

const kindStyles: Record<ActivityKind, { icon: LucideIcon; tone: string }> = {
  deployment: { icon: Rocket, tone: "text-accent" },
  incident_detected: { icon: Siren, tone: "text-crit" },
  pr_merged: { icon: GitMerge, tone: "text-fg" },
  service_recovered: { icon: CircleCheck, tone: "text-ok" },
};

export function ActivityTimeline({ events }: { events: ActivityEvent[] }) {
  return (
    <Panel id="activity" title="Recent activity" description="Deploys, incidents and code changes">
      <ol className="relative">
        {events.map((event, index) => {
          const { icon: Icon, tone } = kindStyles[event.kind];
          return (
            <motion.li
              key={event.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.25 + index * 0.07, duration: 0.3 }}
              className="relative flex gap-3 pb-5 last:pb-0"
            >
              {index < events.length - 1 && (
                <span aria-hidden="true" className="absolute top-8 bottom-1 left-[15px] w-px bg-line" />
              )}
              <span className={`grid size-8 shrink-0 place-items-center rounded-full border border-line bg-surface-strong ${tone}`}>
                <Icon className="size-3.5" aria-hidden="true" />
              </span>
              <div className="min-w-0 pt-1">
                <p className="text-sm text-fg">{event.title}</p>
                <p className="truncate text-xs text-muted">{event.detail}</p>
                <time dateTime={event.timestamp} title={formatClock(event.timestamp)} className="text-[11px] text-faint">
                  {formatRelative(event.timestamp)}
                </time>
              </div>
            </motion.li>
          );
        })}
      </ol>
    </Panel>
  );
}
