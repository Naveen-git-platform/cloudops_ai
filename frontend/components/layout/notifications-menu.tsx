"use client";

import { Bell } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { formatRelative } from "@/lib/format";
import { severityStyles } from "@/lib/status";
import type { Incident } from "@/types";

/** Bell button with a popover listing open incidents. */
export function NotificationsMenu({ incidents, onSelect }: { incidents: Incident[]; onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const openIncidents = incidents.filter((i) => i.status !== "resolved");

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <motion.button
        type="button"
        whileTap={{ scale: 0.94 }}
        onClick={() => setOpen((o) => !o)}
        aria-label={`Notifications, ${openIncidents.length} open incidents`}
        aria-expanded={open}
        aria-controls={menuId}
        className="relative grid size-9 place-items-center rounded-lg border border-line text-muted transition-colors hover:border-line-strong hover:text-fg"
      >
        <Bell className="size-4" aria-hidden="true" />
        {openIncidents.length > 0 && (
          <span className="absolute -top-1 -right-1 grid min-w-4 place-items-center rounded-full bg-crit px-1 text-[10px] font-semibold text-canvas tabular-nums">
            {openIncidents.length}
          </span>
        )}
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            id={menuId}
            role="dialog"
            aria-label="Open incidents"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] origin-top-right rounded-xl border border-line-strong bg-surface-strong/95 p-2 shadow-2xl shadow-black/50 backdrop-blur"
          >
            <p className="px-2 py-1.5 text-xs font-medium text-muted">Open incidents</p>
            {openIncidents.length === 0 ? (
              <p className="px-2 py-3 text-sm text-muted">All clear — no open incidents.</p>
            ) : (
              <ul>
                {openIncidents.map((incident) => (
                  <li key={incident.id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(incident.id);
                        setOpen(false);
                      }}
                      className="w-full rounded-lg px-2 py-2 text-left transition-colors hover:bg-white/[0.04]"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm text-fg">{incident.title}</span>
                        <Badge tone={severityStyles[incident.severity].badge}>{severityStyles[incident.severity].label}</Badge>
                      </span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {incident.service} · {formatRelative(incident.detectedAt)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
