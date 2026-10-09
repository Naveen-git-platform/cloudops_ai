import type { Transition, Variants } from "motion/react";

/** Shared motion presets so animation timing stays consistent. */
export const easeOut: Transition = { duration: 0.35, ease: [0.22, 1, 0.36, 1] };

export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
};

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: easeOut },
};

export const hoverLift = { y: -2, transition: { duration: 0.15 } };
export const tapPress = { scale: 0.98 };
