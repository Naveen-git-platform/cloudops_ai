"use client";

import { motion } from "motion/react";
import { useState } from "react";
import { Panel } from "@/components/ui/panel";
import { formatClock } from "@/lib/format";
import type { TelemetryPoint } from "@/types";

const W = 600;
const H = 180;
const PAD = { top: 12, right: 8, bottom: 22, left: 8 };

/** Lightweight SVG chart: request rate (area) with error rate (line) on its own scale. */
export function SystemHealthChart({ points }: { points: TelemetryPoint[] }) {
  const [hover, setHover] = useState<number | null>(null);

  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const maxRate = Math.max(...points.map((p) => p.requestRate)) * 1.1;
  const maxErr = Math.max(5, ...points.map((p) => p.errorRate));
  const x = (i: number) => PAD.left + (i / (points.length - 1)) * innerW;
  const yRate = (v: number) => PAD.top + innerH - (v / maxRate) * innerH;
  const yErr = (v: number) => PAD.top + innerH - (v / maxErr) * innerH;

  const ratePath = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${yRate(p.requestRate).toFixed(1)}`).join(" ");
  const areaPath = `${ratePath} L${x(points.length - 1)},${PAD.top + innerH} L${x(0)},${PAD.top + innerH} Z`;
  const errPath = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${yErr(p.errorRate).toFixed(1)}`).join(" ");

  const latest = points[points.length - 1];
  const shown = hover !== null ? points[hover] : latest;
  const ticks = [0, Math.floor(points.length / 2), points.length - 1];

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((rel - PAD.left) / innerW) * (points.length - 1));
    setHover(Math.min(points.length - 1, Math.max(0, i)));
  };

  return (
    <Panel
      id="telemetry"
      title="System health"
      description="Request rate and error rate across production, last 24h"
      className="scroll-mt-20 lg:col-span-2"
      action={
        <dl className="flex gap-4 text-right text-xs" aria-live="polite">
          <div>
            <dt className="flex items-center justify-end gap-1.5 text-muted">
              <span aria-hidden="true" className="h-0.5 w-3 rounded bg-accent" /> Requests
            </dt>
            <dd className="font-mono text-sm text-fg tabular-nums">{shown.requestRate.toLocaleString("en-US")} rps</dd>
          </div>
          <div>
            <dt className="flex items-center justify-end gap-1.5 text-muted">
              <span aria-hidden="true" className="h-0.5 w-3 rounded border-t border-dashed border-crit" /> Errors
            </dt>
            <dd className="font-mono text-sm text-crit tabular-nums">{shown.errorRate.toFixed(2)}%</dd>
          </div>
        </dl>
      }
    >
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full touch-none select-none"
        role="img"
        aria-label={`Request rate is ${latest.requestRate} requests per second. Error rate rose to ${latest.errorRate}% in the last 2 hours.`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="rate-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={PAD.left}
            x2={W - PAD.right}
            y1={PAD.top + innerH * (1 - f)}
            y2={PAD.top + innerH * (1 - f)}
            stroke="var(--color-line)"
          />
        ))}

        <motion.path
          d={areaPath}
          fill="url(#rate-fill)"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.3 }}
        />
        <motion.path
          d={ratePath}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth={1.75}
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
        <motion.path
          d={errPath}
          fill="none"
          stroke="var(--color-crit)"
          strokeWidth={1.5}
          strokeDasharray="4 3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.9 }}
          transition={{ duration: 0.6, delay: 0.6 }}
        />

        {hover !== null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} stroke="var(--color-line-strong)" />
            <circle cx={x(hover)} cy={yRate(points[hover].requestRate)} r={3.5} fill="var(--color-accent)" />
            <circle cx={x(hover)} cy={yErr(points[hover].errorRate)} r={3} fill="var(--color-crit)" />
          </g>
        )}

        {ticks.map((i) => (
          <text
            key={i}
            x={x(i)}
            y={H - 6}
            fontSize={10}
            fill="var(--color-faint)"
            textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
            fontFamily="var(--font-mono)"
          >
            {hover === null ? formatClock(points[i].timestamp) : i === ticks[1] ? formatClock(points[hover].timestamp) : ""}
          </text>
        ))}
      </svg>
    </Panel>
  );
}
