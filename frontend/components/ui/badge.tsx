import type { ReactNode } from "react";

/** Small pill label. `tone` is a class string from lib/status.ts. */
export function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset whitespace-nowrap ${tone}`}
    >
      {children}
    </span>
  );
}
