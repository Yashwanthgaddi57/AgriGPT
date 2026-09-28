"use client";

/**
 * Farm Home — the farmer's daily screen. Mobile-first hierarchy (prompt §3/§27):
 * greeting + farm summary → urgent alerts → TODAY'S FARM PLAN → weather →
 * crop health → market → economics. Every number comes from the decision
 * engine / live APIs — nothing is invented; sections hide when data is absent.
 */
import * as React from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Bug,
  Calculator,
  Camera,
  CloudRain,
  CloudSun,
  Coins,
  Droplets,
  Mic,
  ScanSearch,
  Sprout,
  Sun,
  TrendingUp,
  Wallet,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DashboardTicker } from "@/components/dashboard/price-ticker";
import { FadeIn } from "@/components/page-transition";
import { useProfile, useTodayPlan, useWeather } from "@/hooks/use-api";
import { formatCompactINR, formatINR, cn } from "@/lib/utils";
import type { WeatherDay } from "@/types";

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  health: ScanSearch,
  weather: CloudRain,
  crop: Sprout,
  market: TrendingUp,
  economics: Wallet,
};

const LEVEL_META: Record<string, { dot: string; label: string }> = {
  high: { dot: "🔴", label: "High priority" },
  medium: { dot: "🟡", label: "Watch" },
  low: { dot: "⚪", label: "Good to do" },
};

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function dayLabel(date: string, index: number) {
  if (index === 0) return "Today";
  if (index === 1) return "Tomorrow";
  return new Date(date).toLocaleDateString("en-IN", { weekday: "short" });
}

function weatherIcon(condition: string) {
  const c = (condition || "").toLowerCase();
  if (c.includes("rain") || c.includes("drizzle") || c.includes("thunder")) return CloudRain;
  if (c.includes("clear")) return Sun;
  return CloudSun;
}

/** "Today, 10:30 AM" when the timestamp is today; otherwise a short date. */
function asOfLabel(asOf: string) {
  const d = new Date(asOf);
  if (Number.isNaN(d.getTime())) return "—";
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return `Today, ${d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}`;
  }
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export default function FarmHomePage() {
  const { data: profile } = useProfile();
  const { data: plan, isLoading, error, refetch } = useTodayPlan();
  const { data: weather, isLoading: weatherLoading } = useWeather(profile?.district ?? undefined);
  const [showFullPlan, setShowFullPlan] = React.useState(false);
  // Per-priority "Why this recommendation?" collapsible state (prompt §9).
  const [whyOpen, setWhyOpen] = React.useState<Record<string, boolean>>({});
  const toggleWhy = (rank: number | string) =>
    setWhyOpen((prev) => ({ ...prev, [rank]: !prev[rank] }));

  const name = profile?.name?.split(" ")[0] ?? "Farmer";
  const farm = plan?.farm;
  const health = plan?.crop_health;

  const quickActions = [
    { href: "/dashboard/disease", label: "Scan Crop", icon: Camera, primary: true },
    { href: "/dashboard/copilot", label: "Ask AgriGPT", icon: Mic, primary: false },
    { href: "/dashboard/farm-log", label: "Add Expense", icon: Coins, primary: false },
    { href: "/dashboard/profit", label: "Farm Profit", icon: Calculator, primary: false },
  ];

  // Urgent alerts — only from real data, never invented (prompt §3, §19).
  const alerts: { icon: React.ComponentType<{ className?: string }>; text: string; href: string; cta: string }[] = [];
  if (plan?.weather && (plan.weather.rain_probability ?? 0) >= 70) {
    alerts.push({
      icon: CloudRain,
      text: `Rain likely today (${plan.weather.rain_probability}% chance). ${plan.weather.summary}`,
      href: "/dashboard/weather",
      cta: "View forecast",
    });
  }
  if (health?.has_open_issue) {
    alerts.push({
      icon: Bug,
      text: `${health.possible_issue} flagged on ${health.crop ?? "your crop"} — ${health.followup_status ?? "needs a look"}.`,
      href: "/dashboard/disease",
      cta: "Check crop",
    });
  }
  if (plan?.market && plan.market.trend_weekly_pct <= -8) {
    alerts.push({
      icon: TrendingUp,
      text: `${plan.market.crop} price is down ${Math.abs(plan.market.trend_weekly_pct).toFixed(1)}% this week.`,
      href: "/dashboard/market",
      cta: "View market",
    });
  }

  const visiblePriorities = showFullPlan ? (plan?.priorities ?? []) : (plan?.priorities ?? []).slice(0, 3);
  const forecast = (weather?.days ?? []).slice(0, 3);
  const today = forecast[0];
  const TodayIcon = today ? weatherIcon(today.condition) : CloudSun;

  return (
    <div className="space-y-4 lg:space-y-6">
      {/* ---------- Header: greeting + compact farm summary (§3) ---------- */}
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-[20px] font-medium tracking-[0.24px]">
            {greeting()}, {name} 👋
          </h1>
          {farm && (farm.size_acres > 0 || farm.crop || farm.district) ? (
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-muted-foreground">
              <span>🌱 {farm.size_acres} acres</span>
              {farm.crop && (
                <>
                  <span aria-hidden>·</span>
                  <span className="capitalize">🌾 {farm.crop}</span>
                </>
              )}
              {farm.crop_age_days != null && (
                <>
                  <span aria-hidden>·</span>
                  <span>📅 Day {farm.crop_age_days}</span>
                </>
              )}
              {farm.district && (
                <>
                  <span aria-hidden>·</span>
                  <span className="truncate">📍 {farm.district}</span>
                </>
              )}
            </p>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">
              Set up your farm to personalize this page —{" "}
              <Link href="/dashboard/plan" className="text-leaf-600 underline">
                Plan My Farm
              </Link>
            </p>
          )}
        </div>
        <Button asChild size="icon" variant="outline" className="h-11 w-11 shrink-0 rounded-full" aria-label="Ask AgriGPT by voice">
          <Link href="/dashboard/copilot">
            <Mic className="h-5 w-5" />
          </Link>
        </Button>
      </header>

      {/* Desktop "Farm at a glance" summary row (§9) — hidden on mobile where the
          greeting already shows the same facts. */}
      {farm && farm.size_acres > 0 && (
        <div className="hidden grid-cols-3 gap-3 lg:grid">
          <div className="rounded-xl border bg-card p-3">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Farm</p>
            <p className="mt-0.5 text-sm font-bold">
              🌱 {farm.size_acres} acres{farm.crop ? ` · ${farm.crop}` : ""}
            </p>
          </div>
          <div className="rounded-xl border bg-card p-3">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Crop age</p>
            <p className="mt-0.5 text-sm font-bold">
              📅 Day {farm.crop_age_days ?? "—"}
            </p>
          </div>
          <div className="rounded-xl border bg-card p-3">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Location</p>
            <p className="mt-0.5 truncate text-sm font-bold">
              📍 {farm.district ?? "India"}
            </p>
          </div>
        </div>
      )}

      {/* ---------- Quick Actions (§6: 1-tap reach, right after farm context) ---------- */}
      <FadeIn delay={0}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
          {quickActions.map((a) => (
            <Link
              key={a.href}
              href={a.href}
              className={cn(
                "tap-subtle flex min-h-[72px] flex-col items-center justify-center gap-2 rounded-xl border bg-card p-4 text-center text-sm font-medium hover:-translate-y-0.5 hover:shadow-md",
                a.primary ? "border-leaf-200 bg-leaf-50 text-leaf-700" : "hover:border-leaf-300"
              )}
            >
              <span className={cn("flex h-10 w-10 items-center justify-center rounded-lg", a.primary ? "bg-leaf-600 text-white" : "bg-leaf-100 text-leaf-600")}>
                <a.icon className="h-5 w-5" />
              </span>
              {a.label}
            </Link>
          ))}
        </div>
        </FadeIn>

      {/* ---------- Urgent alerts (only when something needs attention) ---------- */}
      {alerts.length > 0 ? (
        <FadeIn delay={0}>
          <section aria-label="Urgent alerts" className="space-y-2">
          {alerts.map((a, i) => {
            const Icon = a.icon;
            return (
              <div
                key={i}
                className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-50 p-3"
              >
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
                  <Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-1.5 text-sm font-medium">
                    <span aria-hidden>⚠️</span> Needs attention
                  </p>
                  <p className="mt-0.5 text-sm text-foreground/90">{a.text}</p>
                  <Link href={a.href} className="mt-1 inline-flex min-h-[36px] items-center text-sm font-medium text-leaf-700 underline">
                    {a.cta} <ArrowRight className="ml-0.5 h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            );
          })}
        </section>
        </FadeIn>
      ) : (
        plan && <p className="text-sm text-muted-foreground">Nothing urgent today 👍</p>
      )}

      {/* ---------- TODAY'S FARM PLAN — the most important section (§3) ---------- */}
      <FadeIn delay={0}>
        <Card className="border-leaf-300 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
            <span>🌱 Today&apos;s Farm Plan</span>
            {plan?.priorities[0] && (
              <Badge variant={plan.priorities[0].level === "high" ? "danger" : plan.priorities[0].level === "medium" ? "warning" : "secondary"} className="text-[10px]">
                {LEVEL_META[plan.priorities[0].level]?.label ?? plan.priorities[0].level}
              </Badge>
            )}
          </CardTitle>
          <CardDescription>What should I do today? — based on your farm, weather and prices</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading && (
            <div className="space-y-2" aria-live="polite">
              <p className="text-sm text-muted-foreground">Loading today&apos;s plan…</p>
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          )}
          {error && (
            <div className="space-y-2" role="alert">
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                We couldn&apos;t load today&apos;s plan. The server may be waking up.
              </p>
              <Button variant="outline" size="sm" onClick={() => refetch()} className="min-h-[40px]">
                Retry
              </Button>
            </div>
          )}
          {plan && plan.priorities.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No special tasks today. Check your crop and weather below. 👍
            </p>
          )}
          {plan && plan.priorities.map((p, idx) => {
            const Icon = ICONS[p.icon] ?? Sprout;
            const meta = LEVEL_META[p.level] ?? { dot: "⚪", label: p.level };
            const whyExpanded = whyOpen[p.rank] ?? false;
            const showWhy = showFullPlan || idx < 3;
            return (
              <div key={p.rank} className="rounded-xl border bg-card p-3">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-leaf-100 text-leaf-600">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="inline-block flex flex-wrap items-center gap-2 font-medium">
                      <span aria-hidden>{meta.dot}</span>
                      <span>{p.title}</span>
                      <Badge variant="outline" className="text-[10px]">{meta.label}</Badge>
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">{p.detail}</p>
                    {showWhy && p.basis && (
                      <button
                        type="button"
                        onClick={() => toggleWhy(p.rank)}
                        aria-expanded={whyExpanded}
                        className="mt-1 flex items-center gap-1 text-[11px] font-medium text-leaf-700 hover:text-leaf-800"
                      >
                        <span aria-hidden>{whyExpanded ? "▲" : "▼"}</span>
                        {whyExpanded ? "Hide reasoning" : "Why this recommendation?"}
                      </button>
                    )}
                    {showWhy && whyExpanded && p.basis && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2, ease: "easeOut" }}
                        className="overflow-hidden"
                      >
                        <p className="mt-1.5 rounded-lg bg-muted/60 p-2.5 text-[11px] leading-relaxed text-muted-foreground">
                          <span className="font-medium text-foreground">Why: </span>
                          {p.basis}
                        </p>
                      </motion.div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {plan && plan.priorities.length > 3 && (
            <Button variant="outline" className="w-full" onClick={() => setShowFullPlan((v) => !v)} aria-expanded={showFullPlan}>
              {showFullPlan ? "Show less" : `View Full Plan (${plan.priorities.length})`}
            </Button>
          )}
          {plan && <p className="text-[11px] leading-relaxed text-muted-foreground/80">{plan.disclaimer}</p>}
          {plan && (
            <Button asChild className="w-full gap-2">
              <Link href="/dashboard/copilot">
                <Mic className="h-4 w-4" /> Discuss today&apos;s plan with AgriGPT
              </Link>
            </Button>
          )}
        </CardContent>
      </Card>
      </FadeIn>

      {/* ---------- Weather — simple 3-day card (§3) ---------- */}
      <FadeIn delay={40}>
        <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between text-base">
            <span>🌦️ Weather</span>
            {weather?.location && (
              <span className="truncate text-xs font-normal text-muted-foreground">{weather.location}</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {weatherLoading && (
            <p className="text-sm text-muted-foreground" aria-live="polite">Loading today&apos;s weather…</p>
          )}
          {today ? (
            <>
              <div className="flex items-center gap-4">
                <TodayIcon className="h-10 w-10 shrink-0 text-sky-500" aria-hidden />
                <div className="min-w-0">
                  <p className="font-display text-[22px] font-medium leading-tight tracking-[0.32px] leading-tight">{today.temp_c ?? "—"}°C</p>
                  <p className="truncate text-sm text-muted-foreground capitalize">{today.condition}</p>
                </div>
                <div className="ml-auto space-y-0.5 text-right text-xs text-muted-foreground">
                  <p className="flex items-center justify-end gap-1">
                    <Droplets className="h-3.5 w-3.5" aria-hidden /> {today.precip_probability ?? 0}% rain
                  </p>
                  <p className="flex items-center justify-end gap-1">
                    <Droplets className="h-3.5 w-3.5 opacity-0" aria-hidden /> {today.humidity ?? "—"}% humidity
                  </p>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {forecast.map((d: WeatherDay, i: number) => {
                  const Icon = weatherIcon(d.condition);
                  return (
                    <div key={d.date} className="rounded-lg border p-2 text-center">
                      <p className="text-xs font-medium text-muted-foreground">{dayLabel(d.date, i)}</p>
                      <Icon className="mx-auto my-1 h-5 w-5 text-sky-500" aria-hidden />
                      <p className="text-sm font-bold">{d.temp_c ?? "—"}°C</p>
                      <p className="text-[10px] text-muted-foreground">{d.precip_probability ?? 0}% rain</p>
                    </div>
                  );
                })}
              </div>
              <Button asChild variant="outline" className="mt-3 w-full">
                <Link href="/dashboard/weather">View Forecast</Link>
              </Button>
            </>
          ) : (
            !weatherLoading && (
              <p className="text-sm text-muted-foreground">
                Forecast unavailable right now.{" "}
                <Link href="/dashboard/weather" className="text-leaf-600 underline">Open weather</Link>
              </p>
            )
          )}
        </CardContent>
      </Card>
      </FadeIn>

      {/* ---------- Crop health — prominent scan CTA (§3, §7) ---------- */}
      <FadeIn delay={80}>
        <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">🌿 Crop Health</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {health?.has_open_issue ? (
            <p className="flex items-start gap-2 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden />
              <span>
                Last scan: {health.days_ago != null ? `${health.days_ago} day${health.days_ago === 1 ? "" : "s"} ago` : "recent"} —{" "}
                <strong>{health.possible_issue}</strong> on <span className="capitalize">{health.crop}</span>.
                Status: 🔴 Needs attention ({health.followup_status ?? "open"}).
              </span>
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              {plan
                ? health
                  ? "No open crop issues in the last 30 days. 👍"
                  : "Have a crop problem? Take a photo and we'll help you check it."
                : "Loading your crop status…"}
            </p>
          )}
          <div className="grid grid-cols-2 gap-2">
            <Button asChild className="min-h-[44px] gap-2">
              <Link href="/dashboard/disease">
                <Camera className="h-4 w-4" /> 📷 Scan Crop
              </Link>
            </Button>
            <Button asChild variant="outline" className="min-h-[44px]">
              <Link href="/dashboard/disease">View scans</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
      </FadeIn>

      {/* ---------- Market — price with unit, timestamp and source (§3, §13) ---------- */}
      <FadeIn delay={120}>
        <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">📈 Market</CardTitle>
        </CardHeader>
        <CardContent>
          {plan?.market ? (
            <>
              <div className="flex items-end justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm capitalize text-muted-foreground">{plan.market.crop}</p>
                  <p className="font-display text-[22px] font-medium leading-tight tracking-[0.32px] leading-tight">
                    ₹{plan.market.price.toLocaleString("en-IN")}
                    <span className="ml-1 text-xs font-normal text-muted-foreground">/ {plan.market.unit || "quintal"}</span>
                  </p>
                </div>
                <Badge variant={plan.market.is_live ? "success" : "warning"} className="shrink-0 text-[10px]">
                  {plan.market.is_live ? "Live price" : "Estimate"}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Latest available price · Updated: {asOfLabel(plan.market.as_of)}
              </p>
              <Button asChild variant="outline" className="mt-3 w-full">
                <Link href="/dashboard/market">View Market</Link>
              </Button>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              {isLoading ? "Loading latest prices…" : "Market data isn't available for your crop right now."}
            </p>
          )}
        </CardContent>
      </Card>
      </FadeIn>

      {/* ---------- Farm economics — 3 numbers + details (§3, §14) ---------- */}
      <FadeIn delay={160}>
        <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">💰 Farm Economics</CardTitle>
        </CardHeader>
        <CardContent>
          {plan && plan.economics.estimated_cost > 0 ? (
            <>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg border p-2">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Expenses</p>
                  <p className="mt-0.5 text-sm font-bold sm:text-base">{formatCompactINR(plan.economics.estimated_cost)}</p>
                </div>
                <div className="rounded-lg border p-2">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Expected earnings</p>
                  <p className="mt-0.5 text-sm font-bold sm:text-base">{formatCompactINR(plan.economics.estimated_revenue)}</p>
                </div>
                <div className={cn("rounded-lg border p-2", plan.economics.estimated_profit >= 0 ? "border-leaf-200 bg-leaf-50" : "border-red-500/30 bg-red-50")}>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Est. profit</p>
                  <p className={cn("mt-0.5 text-sm font-bold sm:text-base", plan.economics.estimated_profit >= 0 ? "text-leaf-700" : "text-red-600")}>
                    {formatCompactINR(plan.economics.estimated_profit)}
                  </p>
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">Estimates, not guarantees. Recorded expenses: {formatINR(plan.economics.recorded_expenses_total)}.</p>
            </>
          ) : (
            plan && (
              <p className="text-sm text-muted-foreground">
                Run a profit estimate to see your expected cost, earnings and profit here.
              </p>
            )
          )}
          <Button asChild variant="outline" className="mt-3 w-full">
            <Link href="/dashboard/profit">View Details</Link>
          </Button>
        </CardContent>
      </Card>
      </FadeIn>

{/* ---------- Realtime mandi price ticker (supporting info) ---------- */}
      <FadeIn delay={200}>
        <DashboardTicker />
      </FadeIn>
    </div>
  );
}
