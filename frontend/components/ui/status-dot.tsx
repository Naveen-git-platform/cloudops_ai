import { healthStyles } from "@/lib/status";
import type { ServiceStatus } from "@/types";

/** Coloured dot; pulses for degraded or down. Decorative — pair with a text label. */
export function StatusDot({ status }: { status: ServiceStatus }) {
  const { dot } = healthStyles[status];
  const alerting = status === "degraded" || status === "down";
  return (
    <span aria-hidden="true" className="relative inline-flex size-2">
      {alerting && <span className={`absolute inset-0 rounded-full opacity-60 motion-safe:animate-ping ${dot}`} />}
      <span className={`relative inline-flex size-2 rounded-full ${dot}`} />
    </span>
  );
}
