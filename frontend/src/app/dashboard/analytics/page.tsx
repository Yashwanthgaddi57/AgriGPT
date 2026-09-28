"use client";

import * as React from "react";
import {
  Activity as ActivityIcon,
  Bug,
  Gauge,
  Sprout,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useActivities, useAnalyticsKpis } from "@/hooks/use-api";
import { formatCompactINR } from "@/lib/utils";

export default function AnalyticsPage() {
  const { data: kpis, isLoading } = useAnalyticsKpis();
  const { data: activities } = useActivities();

  if (isLoading || !kpis) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Farm Analytics</h1>
        <p className="text-sm text-muted-foreground">
          KPIs computed from your prediction history and AI accuracy scores.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi icon={Wallet} label="Expected Revenue" value={formatCompactINR(kpis.expected_revenue)} />
        <Kpi icon={Sprout} label="Expected Profit" value={formatCompactINR(kpis.expected_profit)} />
        <Kpi
          icon={kpis.profit_growth >= 0 ? TrendingUp : TrendingDown}
          label="Profit Growth"
          value={`${kpis.profit_growth >= 0 ? "+" : ""}${kpis.profit_growth.toFixed(1)}%`}
          tone={kpis.profit_growth >= 0 ? "up" : "down"}
        />
        <Kpi
          icon={TrendingUp}
          label="Yield Growth"
          value={`${kpis.yield_growth >= 0 ? "+" : ""}${kpis.yield_growth.toFixed(1)}%`}
          tone={kpis.yield_growth >= 0 ? "up" : "down"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Gauge className="h-4 w-4 text-leaf-600" /> AI Accuracy Scores
            </CardTitle>
            <CardDescription>Confidence of your latest AI outputs</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Meter label="Crop recommendation" value={kpis.recommendation_accuracy} />
            <Meter label="Profit prediction" value={kpis.profit_prediction_accuracy} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Bug className="h-4 w-4 text-leaf-600" /> Disease Frequency
            </CardTitle>
            <CardDescription>Reports in the last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-display text-[28px] font-medium tracking-[0.36px]">{kpis.disease_frequency}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {kpis.disease_frequency === 0
                ? "Clean field — keep monitoring weekly."
                : kpis.disease_frequency > 3
                ? "High pressure — tighten scouting intervals."
                : "Moderate — watch hotspots closely."}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4 text-leaf-600" /> Weather Risk
            </CardTitle>
            <CardDescription>Seasonal risk index 0-100</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-display text-[28px] font-medium tracking-[0.36px]">{kpis.weather_risk.toFixed(0)}</p>
            <Progress value={kpis.weather_risk} className="mt-3" />
            <p className="mt-2 text-sm text-muted-foreground">
              {kpis.weather_risk >= 55 ? "Kharif volatility: monitor forecasts daily." : "Stable conditions expected."}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <ActivityIcon className="h-4 w-4 text-leaf-600" /> Recent Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {(activities?.items ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No activity yet.</p>
          ) : (
            <div className="space-y-2">
              {(activities?.items ?? []).map((a) => (
                <div key={a.id} className="flex items-center justify-between rounded-lg border px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{a.action.replace(/[._]/g, " ")}</p>
                    <p className="text-xs text-muted-foreground">
                      {a.entity_type ?? "platform"} · {new Date(a.created_at).toLocaleString("en-IN")}
                    </p>
                  </div>
                  <Badge variant="secondary">{a.action.split(".")[0]}</Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone?: "up" | "down";
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">{label}</span>
          <Icon className={`h-4 w-4 ${tone === "up" ? "text-leaf-600" : tone === "down" ? "text-red-500" : "text-leaf-600"}`} />
        </div>
        <p className="mt-2 font-display text-[22px] font-medium leading-tight tracking-[0.32px]">{value}</p>
      </CardContent>
    </Card>
  );
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span>{value.toFixed(0)}%</span>
      </div>
      <Progress value={value} />
    </div>
  );
}
