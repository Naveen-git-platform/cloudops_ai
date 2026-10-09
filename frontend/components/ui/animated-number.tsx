"use client";

import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

/** Counts up to `value` on mount and when it changes. Renders the final value on the server. */
export function AnimatedNumber({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const previous = useRef(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (reduce) {
      node.textContent = String(value);
      previous.current = value;
      return;
    }
    const controls = animate(previous.current, value, {
      duration: 0.8,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => {
        node.textContent = String(Math.round(v));
      },
    });
    previous.current = value;
    return () => controls.stop();
  }, [value, reduce]);

  return (
    <span ref={ref} className="tabular-nums">
      {value}
    </span>
  );
}
