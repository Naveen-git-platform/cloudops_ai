import { DEMO_NOW } from "@/lib/demo-data";

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});

/** "14:12 UTC" */
export const formatClock = (iso: string) => `${timeFormatter.format(new Date(iso))} UTC`;

/** "18m", "2h 05m". `now` defaults to the demo reference time until live data lands. */
export function formatDuration(fromIso: string, toIso: string | null, now = DEMO_NOW): string {
  const end = toIso ? new Date(toIso) : now;
  const mins = Math.max(0, Math.round((end.getTime() - new Date(fromIso).getTime()) / 60_000));
  if (mins < 60) return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, "0")}m`;
}

/** "18m ago" */
export const formatRelative = (iso: string, now = DEMO_NOW) => `${formatDuration(iso, null, now)} ago`;
