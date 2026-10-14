"use client";

import { motion } from "motion/react";
import { Suspense, use } from "react";
import { RegistryError, ServiceListSkeleton } from "@/components/services/registry-states";
import { Panel } from "@/components/ui/panel";
import { StatusDot } from "@/components/ui/status-dot";
import { fadeUp, hoverLift, staggerContainer } from "@/lib/motion";
import { matchesQuery } from "@/lib/search";
import { groupIntegrationsByService } from "@/lib/services";
import { healthStyles, integrationStyles } from "@/lib/status";
import type { Integration, Service, ServiceRegistryResult } from "@/types";

interface ServiceHealthListProps {
  registry: Promise<ServiceRegistryResult>;
  query: string;
}

export function ServiceHealthList({ registry, query }: ServiceHealthListProps) {
  return (
    <Panel id="services" title="Service health" description="Registered services and their integrations" className="scroll-mt-20">
      <Suspense fallback={<ServiceListSkeleton />}>
        <ServiceRegistryContent registry={registry} query={query} />
      </Suspense>
    </Panel>
  );
}

function ServiceRegistryContent({ registry, query }: ServiceHealthListProps) {
  const result = use(registry);
  if (!result.ok) return <RegistryError {...result.error} />;

  const { services, integrations } = result;
  if (services.length === 0) {
    return (
      <div className="px-4 py-10 text-center">
        <p className="text-sm font-medium text-fg">No services registered yet</p>
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">
          Register a service with <code className="font-mono text-fg">POST /services</code> on the CloudOps API and it
          will appear here.
        </p>
      </div>
    );
  }

  const byService = groupIntegrationsByService(integrations ?? []);
  const visible = services.filter((s) => matchesQuery(query, s.name, s.id, s.description));

  return (
    <>
      {integrations === null && (
        <p role="status" className="mb-3 rounded-lg border border-warn/25 bg-warn/[0.06] px-3 py-2 text-xs text-warn">
          Integrations couldn&apos;t be loaded, so they aren&apos;t shown below.
        </p>
      )}
      {visible.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">No services match the current filter.</p>
      ) : (
        <motion.ul variants={staggerContainer} initial="hidden" animate="show" className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((service) => (
            <ServiceRow key={service.id} service={service} integrations={byService.get(service.id) ?? []} />
          ))}
        </motion.ul>
      )}
    </>
  );
}

function ServiceRow({ service, integrations }: { service: Service; integrations: Integration[] }) {
  const style = healthStyles[service.status];
  return (
    <motion.li
      variants={fadeUp}
      whileHover={hoverLift}
      className="flex gap-3 rounded-lg border border-line bg-white/[0.015] px-3.5 py-3 transition-colors hover:border-line-strong"
    >
      <span className="pt-1.5">
        <StatusDot status={service.status} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-sm font-medium" title={service.id}>
            {service.name}
          </p>
          <span className="shrink-0 font-mono text-[11px] text-faint">{service.environment}</span>
        </div>
        <p className="mt-0.5 text-xs">
          <span className={style.text}>{style.label}</span>
          {service.description && <span className="text-muted"> · {service.description}</span>}
        </p>
        {integrations.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={`Integrations for ${service.name}`}>
            {integrations.map((integration) => {
              const status = integrationStyles[integration.status];
              return (
                <li
                  key={integration.id}
                  title={`${integration.name} (${integration.type}): ${status.label}`}
                  className="inline-flex items-center gap-1.5 rounded-md border border-line px-1.5 py-0.5 text-[11px] text-muted"
                >
                  <span aria-hidden="true" className={`size-1.5 rounded-full ${status.dot}`} />
                  {integration.name}
                  <span className="sr-only">: {status.label}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </motion.li>
  );
}
