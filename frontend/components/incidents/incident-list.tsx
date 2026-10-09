"use client";

import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { useState } from "react";
import { IncidentCard } from "@/components/incidents/incident-card";
import { Panel } from "@/components/ui/panel";
import type { Incident } from "@/types";

const filters = [
  { id: "active", label: "Active", match: (i: Incident) => i.status !== "resolved" },
  { id: "resolved", label: "Resolved", match: (i: Incident) => i.status === "resolved" },
  { id: "all", label: "All", match: () => true },
] as const;

type FilterId = (typeof filters)[number]["id"];

export function IncidentList({ incidents, onOpen }: { incidents: Incident[]; onOpen: (id: string) => void }) {
  const [filter, setFilter] = useState<FilterId>("all");
  const visible = incidents.filter(filters.find((f) => f.id === filter)!.match);

  return (
    <Panel
      id="incidents"
      title="Incidents"
      description="Select an incident for details and actions"
      className="scroll-mt-20 lg:col-span-2"
      action={
        <div role="group" aria-label="Filter incidents" className="flex rounded-lg border border-line p-0.5 text-xs">
          <LayoutGroup id="incident-filter">
            {filters.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                aria-pressed={filter === f.id}
                className={`relative rounded-md px-2.5 py-1 transition-colors ${filter === f.id ? "text-fg" : "text-muted hover:text-fg"}`}
              >
                {filter === f.id && (
                  <motion.span layoutId="incident-filter-pill" className="absolute inset-0 rounded-md bg-white/[0.07]" />
                )}
                <span className="relative">{f.label}</span>
              </button>
            ))}
          </LayoutGroup>
        </div>
      }
    >
      <ul className="grid gap-3 md:grid-cols-2">
        <AnimatePresence mode="popLayout" initial={false}>
          {visible.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} onOpen={onOpen} />
          ))}
        </AnimatePresence>
      </ul>
      {visible.length === 0 && (
        <p className="py-8 text-center text-sm text-muted">No incidents match the current filter.</p>
      )}
    </Panel>
  );
}
