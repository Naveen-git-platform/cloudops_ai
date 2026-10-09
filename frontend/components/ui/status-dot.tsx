import { healthStyles } from "@/lib/status";
import type { HealthStatus } from "@/types";

/** Coloured dot; pulses for non-healthy states. Decorative — pair with a text label. */
export function StatusDot({ status }: { status: HealthStatus }) {
  const { dot } = healthStyles[status];
  return (
    <span aria-hidden="true" className="relative inline-flex size-2">
      {status !== "healthy" && (
        <span className={`absolute inset-0 rounded-full opacity-60 motion-safe:animate-ping ${dot}`} />
      )}
      <span className={`relative inline-flex size-2 rounded-full ${dot}`} />
    </span>
  );
}
