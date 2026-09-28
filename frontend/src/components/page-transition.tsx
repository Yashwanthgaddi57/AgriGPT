"use client";

/**
 * Shared page-transition wrapper (prompt §5).
 *
 * Navigating between major screens uses a subtle fade + slight upward
 * movement — NOT a dramatic slide. Duration 220ms, ease-out.
 *
 * framer-motion is already a dependency. The parent supplies `key` (the
 * route pathname) so AnimatePresence treats each route as a distinct child
 * and animates the exit of the old page and the entrance of the new one.
 */
import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";

export function PageTransition({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, translateY: 8 }}
      animate={{ opacity: 1, translateY: 0 }}
      exit={{ opacity: 0, translateY: -8, transition: { duration: 0.18, ease: "easeIn" } }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** Wrap a route's content so AnimatePresence can animate page changes. */
export function PageAnimatePresence({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AnimatePresence initial={false}>{children}</AnimatePresence>;
}

/** Card entrance — fade + rise, optional stagger delay (prompt §5). */
export function FadeIn({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, translateY: 8 }}
      animate={{ opacity: 1, translateY: 0 }}
      transition={{ duration: 0.25, ease: "easeOut", delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}