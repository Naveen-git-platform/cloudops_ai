import {
  Activity,
  GitPullRequest,
  LayoutDashboard,
  Rocket,
  Server,
  Settings,
  Siren,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  icon: LucideIcon;
  /** Section id on the dashboard. Items without one ship in a later issue. */
  sectionId?: string;
}

export const navItems: NavItem[] = [
  { label: "Overview", icon: LayoutDashboard, sectionId: "overview" },
  { label: "Incidents", icon: Siren, sectionId: "incidents" },
  { label: "Services", icon: Server, sectionId: "services" },
  { label: "Deployments", icon: Rocket, sectionId: "deployments" },
  { label: "GitHub", icon: GitPullRequest },
  { label: "Telemetry", icon: Activity, sectionId: "telemetry" },
  { label: "AI Analysis", icon: Sparkles },
  { label: "Settings", icon: Settings },
];

export const sectionIds = navItems.flatMap((item) => (item.sectionId ? [item.sectionId] : []));
