"use client";

import { CircleCheck, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";
import { SeverityBadge } from "@/components/incidents/severity-badge";
import { formatClock, formatDuration } from "@/lib/format";
import { tapPress } from "@/lib/motion";
import { incidentStatusLabel } from "@/lib/status";
import type { Incident } from "@/types";

interface IncidentDetailPanelProps {
  incident: Incident | null;
  onClose: () => void;
  onResolve: (id: string) => void;
}

/** Slide-over drawer with incident details. */
export function IncidentDetailPanel({ incident, onClose, onResolve }: IncidentDetailPanelProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!incident) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [incident, onClose]);

  return (
    <AnimatePresence>
      {incident && (
        <>
          <motion.div
            key="backdrop"
            aria-hidden="true"
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />
          <motion.aside
            key="panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="incident-detail-title"
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-line-strong bg-surface-strong shadow-2xl shadow-black/60"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 420, damping: 42 }}
          >
            <header className="flex items-start justify-between gap-3 border-b border-line p-5">
              <div>
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={incident.severity} />
                  <span className="font-mono text-xs text-faint">{incident.id}</span>
                </div>
                <h2 id="incident-detail-title" className="mt-2 text-base font-semibold">
                  {incident.title}
                </h2>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={onClose}
                aria-label="Close incident details"
                className="grid size-8 place-items-center rounded-lg border border-line text-muted hover:text-fg"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </header>

            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              <p className="text-sm leading-relaxed text-muted">{incident.description}</p>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ["Service", incident.service],
                  ["Status", incidentStatusLabel[incident.status]],
                  ["Detected", formatClock(incident.detectedAt)],
                  ["Duration", formatDuration(incident.detectedAt, incident.resolvedAt)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-line p-3">
                    <dt className="text-xs text-faint">{label}</dt>
                    <motion.dd key={value} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-1 font-mono text-fg">
                      {value}
                    </motion.dd>
                  </div>
                ))}
              </dl>
              <p className="rounded-lg border border-dashed border-line p-3 text-xs text-faint">
                Root-cause analysis and runbook suggestions will appear here once AI Analysis is enabled.
              </p>
            </div>

            <footer className="border-t border-line p-5">
              {incident.status === "resolved" ? (
                <p className="flex items-center gap-2 text-sm text-ok">
                  <CircleCheck className="size-4" aria-hidden="true" /> Resolved {incident.resolvedAt && `at ${formatClock(incident.resolvedAt)}`}
                </p>
              ) : (
                <motion.button
                  type="button"
                  whileTap={tapPress}
                  onClick={() => onResolve(incident.id)}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-fg px-4 py-2.5 text-sm font-medium text-canvas transition-opacity hover:opacity-90"
                >
                  <CircleCheck className="size-4" aria-hidden="true" /> Mark as resolved
                </motion.button>
              )}
              <p className="mt-2 text-center text-[11px] text-faint">Demo mode: changes are local and reset on reload.</p>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
