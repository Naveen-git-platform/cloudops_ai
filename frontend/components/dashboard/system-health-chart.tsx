"use client";

import { use } from "react";
import { Panel } from "@/components/ui/panel";
import { formatClock } from "@/lib/format";
import type { TelemetryRecord, TelemetryResult } from "@/types";

const SIGNALS = ["traces", "metrics", "logs"] as const;
type Signal = (typeof SIGNALS)[number];

function summarize(records: TelemetryRecord[]) {
  const now = Date.now();
  const buckets = Array.from({ length: 24 }, (_, index) => ({
    hour: new Date(now - (23 - index) * 60 * 60 * 1000),
    traces: 0,
    metrics: 0,
    logs: 0,
  }));
  const start = now - 24 * 60 * 60 * 1000;
  for (const record of records) {
    const timestamp = new Date(record.timestamp).getTime();
    if (!Number.isFinite(timestamp) || timestamp < start || timestamp > now) continue;
    const index = Math.min(23, Math.floor((timestamp - start) / (60 * 60 * 1000)));
    buckets[index][record.signal as Signal] += 1;
  }
  return buckets;
}

function TelemetryChart({ records, truncated }: { records: TelemetryRecord[]; truncated: boolean }) {
  const buckets = summarize(records);
  const max = Math.max(1, ...buckets.map((bucket) => bucket.traces + bucket.metrics + bucket.logs));
  const total = records.length;
  const latest = records.reduce<TelemetryRecord | null>(
    (current, record) => !current || new Date(record.timestamp).getTime() > new Date(current.timestamp).getTime() ? record : current,
    null,
  );

  return (
    <Panel
      id="telemetry"
      title="Telemetry activity"
      description="Stored OpenTelemetry records received in the last 24 hours"
      className="scroll-mt-20 lg:col-span-2"
      action={<div className="text-right"><div className="font-mono text-lg tabular-nums">{total.toLocaleString("en-US")}</div><div className="text-[10px] text-muted">records queried</div></div>}
    >
      {truncated && <p className="mb-3 rounded-md border border-line px-3 py-2 text-xs text-muted">Showing the newest 1,000 records. Counts may be capped by the query limit.</p>}
      {records.length === 0 ? (
        <div className="flex min-h-36 flex-col items-center justify-center rounded-lg border border-dashed border-line px-4 text-center">
          <p className="text-sm font-medium text-fg">No telemetry received yet</p>
          <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">Once an OpenTelemetry Collector exports traces, metrics, or logs to this backend, their stored records will appear here. This chart does not substitute demo values.</p>
        </div>
      ) : (
        <>
          <div className="flex h-40 items-end gap-1 border-b border-line pb-2" role="img" aria-label={`Hourly telemetry records over the last 24 hours. ${total} records in the query window.`}>
            {buckets.map((bucket, index) => {
              const count = bucket.traces + bucket.metrics + bucket.logs;
              const height = count ? Math.max(3, (count / max) * 100) : 0;
              return (
                <div key={bucket.hour.toISOString()} className="group relative flex h-full min-w-0 flex-1 items-end" title={`${formatClock(bucket.hour.toISOString())}: ${count} records`}>
                  <div className="flex w-full flex-col justify-end overflow-hidden rounded-t-sm" style={{ height: `${height}%` }}>
                    {bucket.logs > 0 && <div className="w-full bg-crit" style={{ height: `${(bucket.logs / count) * 100}%` }} />}
                    {bucket.metrics > 0 && <div className="w-full bg-accent" style={{ height: `${(bucket.metrics / count) * 100}%` }} />}
                    {bucket.traces > 0 && <div className="w-full bg-emerald-500" style={{ height: `${(bucket.traces / count) * 100}%` }} />}
                  </div>
                  {index % 6 === 0 && <span className="absolute -bottom-5 left-0 text-[9px] text-faint">{formatClock(bucket.hour.toISOString()).replace(" UTC", "")}</span>}
                </div>
              );
            })}
          </div>
          <div className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
            <span className="inline-flex items-center gap-1.5"><i className="h-2 w-2 rounded-sm bg-emerald-500" />Traces {records.filter((record) => record.signal === "traces").length}</span>
            <span className="inline-flex items-center gap-1.5"><i className="h-2 w-2 rounded-sm bg-accent" />Metrics {records.filter((record) => record.signal === "metrics").length}</span>
            <span className="inline-flex items-center gap-1.5"><i className="h-2 w-2 rounded-sm bg-crit" />Logs {records.filter((record) => record.signal === "logs").length}</span>
          </div>
          <p className="mt-3 text-[11px] text-faint">{latest ? `Latest record: ${formatClock(latest.timestamp)} · ${latest.service_name} · ${latest.signal}` : "No recent records."}</p>
        </>
      )}
    </Panel>
  );
}

export function SystemHealthChart({ result }: { result: Promise<TelemetryResult> }) {
  const telemetry = use(result);
  if (!telemetry.ok) {
    return (
      <Panel id="telemetry" title="Telemetry activity" description="Stored OpenTelemetry records · last 24 hours" className="scroll-mt-20 lg:col-span-2">
        <div className="rounded-lg border border-line px-4 py-5">
          <p className="text-sm font-medium text-fg">{telemetry.error.title}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">{telemetry.error.detail}</p>
        </div>
      </Panel>
    );
  }
  return <TelemetryChart records={telemetry.records} truncated={telemetry.truncated} />;
}
