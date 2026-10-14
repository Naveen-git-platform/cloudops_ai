"use client";

import { RotateCw, ServerCrash } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { tapPress } from "@/lib/motion";

/** Re-runs the server fetch for live data without a full page reload. */
function RetryButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <motion.button
      type="button"
      whileTap={tapPress}
      disabled={pending}
      onClick={() => startTransition(() => router.refresh())}
      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5 text-xs font-medium text-fg transition-colors hover:bg-white/[0.05] disabled:cursor-wait disabled:opacity-60"
    >
      <RotateCw className={`size-3.5 ${pending ? "motion-safe:animate-spin" : ""}`} aria-hidden="true" />
      {pending ? "Retrying…" : "Retry"}
    </motion.button>
  );
}

interface RegistryErrorProps {
  title: string;
  detail: string;
  /** Single-line banner for the overview instead of the full panel state. */
  compact?: boolean;
}

export function RegistryError({ title, detail, compact = false }: RegistryErrorProps) {
  if (compact) {
    return (
      <div
        role="alert"
        className="flex flex-col gap-3 rounded-xl border border-crit/25 bg-crit/[0.06] px-4 py-3 sm:flex-row sm:items-center"
      >
        <ServerCrash className="hidden size-4 shrink-0 text-crit sm:block" aria-hidden="true" />
        <p className="min-w-0 flex-1 text-sm">
          <span className="font-medium text-fg">Live service data is unavailable.</span>{" "}
          <span className="text-muted">{title}. Service counts below can&apos;t be shown.</span>
        </p>
        <RetryButton />
      </div>
    );
  }
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-4 py-10 text-center">
      <span className="grid size-10 place-items-center rounded-full border border-crit/25 bg-crit/10 text-crit">
        <ServerCrash className="size-5" aria-hidden="true" />
      </span>
      <div>
        <p className="text-sm font-medium text-fg">{title}</p>
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">{detail}</p>
      </div>
      <RetryButton />
    </div>
  );
}

export function ServiceListSkeleton() {
  return (
    <div role="status" aria-label="Loading services">
      <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3" aria-hidden="true">
        {Array.from({ length: 6 }, (_, i) => (
          <li key={i} className="flex items-center gap-3 rounded-lg border border-line px-3.5 py-3">
            <span className="size-2 rounded-full bg-white/10" />
            <span className="flex-1 space-y-2">
              <span className="block h-3 w-1/2 rounded bg-white/[0.07] motion-safe:animate-pulse" />
              <span className="block h-2.5 w-3/4 rounded bg-white/[0.05] motion-safe:animate-pulse" />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Placeholder for a single stat value while it loads. */
export function ValueSkeleton() {
  return (
    <span role="status" aria-label="Loading" className="inline-block h-7 w-16 rounded bg-white/[0.07] align-middle motion-safe:animate-pulse" />
  );
}
