"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { fadeUp } from "@/lib/motion";

interface PanelProps {
  id?: string;
  title?: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** Glass panel used for every dashboard section. Animates in as a stagger child. */
export function Panel({ id, title, description, action, className = "", children }: PanelProps) {
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
            <h2 id={headingId} className="text-sm font-semibold tracking-tight text-fg">
              {title}
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
