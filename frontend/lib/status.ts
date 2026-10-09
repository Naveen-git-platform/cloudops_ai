import type { Deployment, HealthStatus, IncidentStatus, Severity } from "@/types";

/**
 * Single source of truth for status colours and labels. Every state is also
 * shown with a text label (and usually an icon), so colour is never the only signal.
 */
export const healthStyles: Record<HealthStatus, { label: string; dot: string; text: string; badge: string }> = {
  healthy: { label: "Healthy", dot: "bg-ok", text: "text-ok", badge: "bg-ok/10 text-ok ring-ok/25" },
  degraded: { label: "Degraded", dot: "bg-warn", text: "text-warn", badge: "bg-warn/10 text-warn ring-warn/25" },
  down: { label: "Down", dot: "bg-crit", text: "text-crit", badge: "bg-crit/10 text-crit ring-crit/25" },
};

export const severityStyles: Record<Severity, { label: string; badge: string; accent: string }> = {
  critical: { label: "Critical", badge: "bg-crit/10 text-crit ring-crit/25", accent: "bg-crit" },
  warning: { label: "Warning", badge: "bg-warn/10 text-warn ring-warn/25", accent: "bg-warn" },
  resolved: { label: "Resolved", badge: "bg-ok/10 text-ok ring-ok/25", accent: "bg-ok" },
};

export const incidentStatusLabel: Record<IncidentStatus, string> = {
  investigating: "Investigating",
  identified: "Identified",
  monitoring: "Monitoring",
  resolved: "Resolved",
};

export const deploymentStyles: Record<Deployment["status"], { label: string; badge: string }> = {
  succeeded: { label: "Succeeded", badge: "bg-ok/10 text-ok ring-ok/25" },
  failed: { label: "Failed", badge: "bg-crit/10 text-crit ring-crit/25" },
  in_progress: { label: "Rolling out", badge: "bg-accent/10 text-accent ring-accent/25" },
};
