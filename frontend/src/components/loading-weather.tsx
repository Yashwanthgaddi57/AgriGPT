"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Branded loading animation for dashboard boot: a rain cloud over a sprout —
 * the farmer reads it as "AgriGPT is gathering your weather & crop data",
 * not a generic spin. Pure CSS (no framer-motion needed at boot), so it
 * renders instantly on slow phones. Honors prefers-reduced-motion.
 */
export function LoadingWeather({ className, label = "Loading your farm…" }: { className?: string; label?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3", className)} role="status" aria-label={label}>
      <div className="agri-load relative flex h-24 w-28 items-end justify-center">
        {/* Cloud */}
        <div className="agri-cloud absolute top-1 left-1/2 -translate-x-1/2">
          <span className="agri-cloud__puff agri-cloud__puff--m" />
          <span className="agri-cloud__puff agri-cloud__puff--l" />
          <span className="agri-cloud__puff agri-cloud__puff--r" />
        </div>
        {/* Raindrops */}
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="agri-drop absolute"
            style={{ left: `${22 + i * 14}%`, animationDelay: `${i * 0.22}s` }}
            aria-hidden
          />
        ))}
        {/* Sprout in soil */}
        <div className="agri-sprout relative mb-0.5" aria-hidden>
          <span className="agri-sprout__stem" />
          <span className="agri-sprout__leaf agri-sprout__leaf--l" />
          <span className="agri-sprout__leaf agri-sprout__leaf--r" />
          <span className="agri-sprout__seed" />
        </div>
        <div className="agri-soil absolute bottom-1 left-1/2 -translate-x-1/2" aria-hidden />
      </div>
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}
