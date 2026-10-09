"use client";

import { motion } from "motion/react";
import { navItems } from "@/components/layout/nav-items";

interface SidebarNavProps {
  activeId: string;
  /** Icon-only layout used for the tablet rail. */
  compact?: boolean;
  /** Distinguishes the shared-layout indicator between desktop and mobile instances. */
  layoutScope: string;
  onNavigate?: () => void;
}

export function SidebarNav({ activeId, compact = false, layoutScope, onNavigate }: SidebarNavProps) {
  return (
    <nav aria-label="Primary">
      <ul className="space-y-0.5">
        {navItems.map(({ label, icon: Icon, sectionId }) => {
          const active = sectionId === activeId;
          const base = `relative flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors ${
            compact ? "justify-center lg:justify-start" : ""
          }`;
          const content = (
            <>
              {active && (
                <motion.span
                  layoutId={`nav-active-${layoutScope}`}
                  className="absolute inset-0 rounded-lg border border-line-strong bg-white/[0.05]"
                  transition={{ type: "spring", stiffness: 500, damping: 40 }}
                />
              )}
              <Icon className="relative size-4 shrink-0" aria-hidden="true" />
              <span className={`relative flex-1 text-left ${compact ? "sr-only lg:not-sr-only" : ""}`}>{label}</span>
              {!sectionId && (
                <span
                  className={`relative rounded border border-line px-1.5 text-[10px] uppercase tracking-wide text-faint ${
                    compact ? "hidden lg:inline" : ""
                  }`}
                >
                  Soon
                </span>
              )}
            </>
          );

          return (
            <li key={label}>
              {sectionId ? (
                <motion.a
                  href={`#${sectionId}`}
                  onClick={onNavigate}
                  aria-current={active ? "location" : undefined}
                  title={compact ? label : undefined}
                  whileHover={{ x: compact ? 0 : 2 }}
                  whileTap={{ scale: 0.98 }}
                  className={`${base} ${active ? "text-fg" : "text-muted hover:bg-white/[0.03] hover:text-fg"}`}
                >
                  {content}
                </motion.a>
              ) : (
                <button
                  type="button"
                  disabled
                  title={`${label} — coming soon`}
                  aria-label={`${label} (coming soon)`}
                  className={`${base} cursor-not-allowed text-faint`}
                >
                  {content}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
