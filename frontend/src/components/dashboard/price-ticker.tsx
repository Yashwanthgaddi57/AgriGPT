"use client";

import Link from "next/link";
import { Activity, MapPin, Radio } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { usePriceTicker } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

/**
 * Mandi price ticker. Header honestly reflects data state: "Live mandi
 * prices" only when at least one row comes from the real Agmarknet feed;
 * otherwise "Latest available mandi prices" (baseline estimates flagged).
 */
export function DashboardTicker() {
  const { data, isLoading, isError } = usePriceTicker();

  if (isLoading) {
    return (
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-40 shrink-0" />
        ))}
      </div>
    );
  }

  if (isError || !data) return null; // ticker is a nice-to-have; never block the dashboard

  const liveCount = data.items.filter((i) => i.is_live).length;
  const allLive = liveCount === data.items.length && data.items.length > 0;

  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-max items-center gap-3 pb-1">
        <span className="flex shrink-0 items-center gap-1.5 pr-1 text-xs font-medium text-muted-foreground">
          <Radio className={cn("h-3.5 w-3.5 text-leaf-600", allLive && "animate-pulse")} />
          {allLive ? "Live mandi prices" : "Latest available mandi prices"}
        </span>
        {data.location?.label && (
          <span className="flex shrink-0 items-center gap-1 rounded-full bg-leaf-50 px-2.5 py-1 text-xs font-medium text-leaf-700">
            <MapPin className="h-3 w-3" />
            {data.location.label}
          </span>
        )}
        {data.items.map((item) => {
          const up = item.trend_weekly_pct >= 0;
          return (
            <Link
              key={item.crop}
              href={`/dashboard/market?crop=${encodeURIComponent(item.crop)}`}
              className="group flex shrink-0 items-center gap-3 rounded-lg border bg-card px-3 py-2 transition-colors hover:border-leaf-300"
              title={`${item.crop} — ${item.source} — as of ${item.as_of}`}
            >
              <div>
                <p className="text-xs font-medium capitalize leading-tight">{item.crop}</p>
                <p className="text-sm font-bold leading-tight">
                  ₹{item.price.toLocaleString("en-IN")}
                  <span className="ml-1 text-[10px] font-normal text-muted-foreground">/q</span>
                </p>
              </div>
              <span
                className={cn(
                  "flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-medium",
                  up ? "bg-leaf-100 text-leaf-700" : "bg-red-100 text-red-700"
                )}
              >
                {up ? "▲" : "▼"} {Math.abs(item.trend_weekly_pct).toFixed(1)}%
              </span>
              {!item.is_live && (
                <span className="text-[10px] text-muted-foreground" title="Estimated (no live feed)">
                  est
                </span>
              )}
            </Link>
          );
        })}
        {liveCount === 0 && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Activity className="h-3.5 w-3.5" />
            Showing modeled estimates — live feed unavailable
          </span>
        )}
      </div>
    </div>
  );
}
