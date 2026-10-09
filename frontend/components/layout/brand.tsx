import { Cloud } from "lucide-react";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-line-strong bg-accent/10 text-accent">
        <Cloud className="size-4" aria-hidden="true" />
      </span>
      <span className={`text-sm font-semibold tracking-tight ${compact ? "sr-only" : ""}`}>
        CloudOps <span className="text-accent">AI</span>
      </span>
    </div>
  );
}
