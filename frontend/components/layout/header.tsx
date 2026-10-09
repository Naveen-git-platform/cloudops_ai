"use client";

import { Menu, Search } from "lucide-react";
import { motion } from "motion/react";
import { Brand } from "@/components/layout/brand";
import { NotificationsMenu } from "@/components/layout/notifications-menu";
import type { Incident } from "@/types";

interface HeaderProps {
  query: string;
  onQueryChange: (q: string) => void;
  incidents: Incident[];
  onSelectIncident: (id: string) => void;
  onOpenMenu: () => void;
}

export function Header({ query, onQueryChange, incidents, onSelectIncident, onOpenMenu }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/75 backdrop-blur-md">
      <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
        <motion.button
          type="button"
          whileTap={{ scale: 0.94 }}
          onClick={onOpenMenu}
          aria-label="Open navigation"
          className="grid size-9 place-items-center rounded-lg border border-line text-muted hover:text-fg md:hidden"
        >
          <Menu className="size-4" aria-hidden="true" />
        </motion.button>

        <div className="md:hidden">
          <Brand compact />
        </div>

        <span className="hidden items-center gap-2 rounded-full border border-line px-2.5 py-1 text-xs text-muted sm:inline-flex">
          <span aria-hidden="true" className="size-1.5 rounded-full bg-ok" />
          <span>
            env: <span className="font-mono text-fg">production</span>
          </span>
          <span className="text-faint">·</span>
          <span className="font-mono">us-east-1</span>
        </span>

        <div role="search" className="relative ml-auto w-full max-w-xs">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-faint" aria-hidden="true" />
          <label htmlFor="dashboard-search" className="sr-only">
            Filter incidents and services
          </label>
          <input
            id="dashboard-search"
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Filter incidents & services"
            className="h-9 w-full rounded-lg border border-line bg-white/[0.02] pr-3 pl-9 text-sm text-fg placeholder:text-faint transition-colors hover:border-line-strong focus:border-accent/50 focus:outline-none"
          />
        </div>

        <NotificationsMenu incidents={incidents} onSelect={onSelectIncident} />

        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="grid size-9 shrink-0 place-items-center rounded-full border border-line-strong bg-accent/15 text-xs font-semibold"
          >
            JL
          </span>
          <span className="sr-only">Signed in as Jordan Lee, SRE on call</span>
          <span className="hidden leading-tight xl:block" aria-hidden="true">
            <span className="block text-sm">Jordan Lee</span>
            <span className="block text-xs text-muted">SRE · on-call</span>
          </span>
        </div>
      </div>
    </header>
  );
}
