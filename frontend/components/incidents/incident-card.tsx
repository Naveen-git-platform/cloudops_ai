"use client";

import { Clock, Timer } from "lucide-react";
import { motion } from "motion/react";
import { SeverityBadge } from "@/components/incidents/severity-badge";
import { formatClock, formatDuration } from "@/lib/format";
import { hoverLift, tapPress } from "@/lib/motion";
import { incidentStatusLabel, severityStyles } from "@/lib/status";
import type { Incident } from "@/types";

export function IncidentCard({ incident, onOpen }: { incident: Incident; onOpen: (id: string) => void }) {
  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.25 }}
    >
      <motion.button
        type="button"
        onClick={() => onOpen(incident.id)}
        whileHover={hoverLift}
        whileTap={tapPress}
        aria-label={`${incident.id}: ${incident.title}. ${severityStyles[incident.severity].label}, ${incidentStatusLabel[incident.status]}. Open details`}
        className="relative w-full overflow-hidden rounded-lg border border-line bg-white/[0.015] p-4 text-left transition-colors hover:border-line-strong hover:bg-white/[0.03]"
      >
        <motion.span
          aria-hidden="true"
          layout
          className={`absolute inset-y-0 left-0 w-0.5 ${severityStyles[incident.severity].accent}`}
        />
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={incident.severity} />
          <span className="font-mono text-xs text-faint">{incident.id}</span>
          <span className="ml-auto text-xs text-muted">{incidentStatusLabel[incident.status]}</span>
        </div>
        <h3 className="mt-2.5 text-sm font-medium text-fg">{incident.title}</h3>
        <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{incident.description}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-faint">
          <span className="font-mono text-muted">{incident.service}</span>
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3" aria-hidden="true" />
            Detected {formatClock(incident.detectedAt)}
          </span>
          <span className="inline-flex items-center gap-1">
            <Timer className="size-3" aria-hidden="true" />
            {formatDuration(incident.detectedAt, incident.resolvedAt)}
          </span>
        </div>
      </motion.button>
    </motion.li>
  );
}
