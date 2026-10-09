"use client";

import { CircleCheck, OctagonAlert, TriangleAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Badge } from "@/components/ui/badge";
import { severityStyles } from "@/lib/status";
import type { Severity } from "@/types";

const icons = { critical: OctagonAlert, warning: TriangleAlert, resolved: CircleCheck } as const;

/** Severity pill with icon + label; cross-fades when severity changes. */
export function SeverityBadge({ severity }: { severity: Severity }) {
  const Icon = icons[severity];
  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.span
        key={severity}
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.85 }}
        transition={{ duration: 0.2 }}
        className="inline-flex"
      >
        <Badge tone={severityStyles[severity].badge}>
          <Icon className="size-3" aria-hidden="true" />
          {severityStyles[severity].label}
        </Badge>
      </motion.span>
    </AnimatePresence>
  );
}
