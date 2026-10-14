"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { fadeUp } from "@/lib/motion";

interface PanelProps {
  id?: string;
  title?: string;
  description?: string;
  action?: ReactNode;
  /** Marks sections that still render sample data instead of API data. */
  demo?: boolean;
  className?: string;
  children: ReactNode;
}

/** Glass panel used for every dashboard section. Animates in as a stagger child. */
export function Panel({ id, title, description, action, demo = false, className = "", children }: PanelProps) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <motion.section
      id={id}
      variants={fadeUp}
      aria-labelledby={title ? headingId : undefined}
      className={`rounded-xl border border-line bg-surface p-4 backdrop-blur-sm sm:p-5 ${className}`}
    >
      {title && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id={headingId} className="flex items-center gap-2 text-sm font-semibold tracking-tight text-fg">
              {title}
              {demo && (
                <span className="rounded border border-line px-1.5 py-px text-[10px] font-medium tracking-wide text-faint uppercase">
                  Demo data
                </span>
              )}
            </h2>
            {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </motion.section>
  );
}
