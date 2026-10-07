"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Loader2, MapPin, TrendingUp } from "lucide-react";

import { AlertTriangle, BadgeCheck, Database } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useAnalyzeMarket,
  useMarketCompare,
  useMarketPredictions,
  useMyLocation,
  useNearbyMandis,
} from "@/hooks/use-api";
import { apiErrorMessage } from "@/lib/api";
import { trackEvent, EVENTS } from "@/lib/events";
import { useToast } from "@/hooks/use-toast";
import { formatDate, formatINR } from "@/lib/utils";

const RECOMMENDATION_VARIANT: Record<string, "success" | "warning" | "secondary"> = {
  sell_now: "success",
  wait_1_week: "warning",
  wait_2_weeks: "warning",
  hold: "secondary",
};

export default function MarketPage() {
  const analyze = useAnalyzeMarket();
  const { toast } = useToast();
  const [page, setPage] = React.useState(1);
  const { data: history } = useMarketPredictions(page);
  const { data: myLoc } = useMyLocation();

  const [crop, setCrop] = React.useState("");
  const [market, setMarket] = React.useState("");
  const result = analyze.data;

  React.useEffect(() => {
    trackEvent(EVENTS.marketPageViewed);
  }, []);

  // "Where should I sell?" — per-mandi price comparison for the analyzed crop
  const { data: mandis } = useNearbyMandis(result?.crop || undefined);
  const { data: comparison } = useMarketCompare(result?.crop || undefined);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await analyze.mutateAsync({ crop, market: market || undefined });
      toast({ title: "Market analysis ready", variant: "success" });
    } catch (err) {
      toast({ title: "Analysis failed", description: apiErrorMessage(err), variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Market Prices</h1>
        <p className="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
          Latest prices, trends and AI sell/wait guidance per crop.
          {myLoc?.label && (
            <span className="inline-flex items-center gap-1 rounded-full bg-leaf-50 px-2.5 py-0.5 text-xs font-medium text-leaf-700">
              <MapPin className="h-3 w-3" />
              {myLoc.label}
            </span>
          )}
        </p>
      </div>

      <Tabs defaultValue="analyze">
        <TabsList>
          <TabsTrigger value="analyze">Analyze</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="analyze" className="mt-4 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-leaf-600" /> Analyze a crop
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={submit} className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label>Crop</Label>
                  <Input required placeholder="e.g. onion" value={crop} onChange={(e) => setCrop(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Market (optional)</Label>
                  <Input placeholder="e.g. Lasalgaon APMC" value={market} onChange={(e) => setMarket(e.target.value)} />
                </div>
                <div className="flex items-end">
                  <Button type="submit" disabled={analyze.isPending} className="w-full gap-2">
                    {analyze.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                    Analyze market
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {result && (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <KpiCard label="Current Price" value={`${formatINR(result.current_price)}/q`} />
                <KpiCard
                  label="Weekly Trend"
                  value={`${result.trend_weekly >= 0 ? "+" : ""}${result.trend_weekly.toFixed(1)}%`}
                  tone={result.trend_weekly >= 0 ? "up" : "down"}
                />
                <KpiCard label="7-day Forecast" value={`${formatINR(result.price_forecast_7d)}/q`} />
                <KpiCard label="30-day Forecast" value={`${formatINR(result.price_forecast_30d)}/q`} />
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <Card className="lg:col-span-2">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">90-day price history & forecast</CardTitle>
                    <CardDescription className="capitalize">
                      {result.crop} · {result.market ?? "national average"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart data={result.price_history}>
                        <defs>
                          <linearGradient id="px" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#16a34a" stopOpacity={0.35} />
                            <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis
                          dataKey="date"
                          fontSize={11}
                          tickLine={false}
                          axisLine={false}
                          tickFormatter={(d: string) =>
                            new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
                          }
                        />
                        <YAxis
                          fontSize={11}
                          tickLine={false}
                          axisLine={false}
                          domain={["auto", "auto"]}
                          tickFormatter={(v: number) => `₹${(v / 1000).toFixed(1)}k`}
                        />
                        <Tooltip formatter={(v: number) => formatINR(v)} labelFormatter={(d) => formatDate(d)} />
                        <Area type="monotone" dataKey="price" stroke="#16a34a" fill="url(#px)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">AI Recommendation</CardTitle>
                    <DataSourceBadge source={result.data_source} />
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Badge variant={RECOMMENDATION_VARIANT[result.recommendation] ?? "secondary"} className="text-sm">
                      {result.recommendation.replace(/_/g, " ").toUpperCase()}
                    </Badge>
                    <div>
                      <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                        <span>Confidence</span><span>{result.confidence.toFixed(0)}%</span>
                      </div>
                      <Progress value={result.confidence} />
                    </div>
                    <div className="space-y-2 text-sm">
                      <Row k="Monthly trend" v={`${result.trend_monthly >= 0 ? "+" : ""}${result.trend_monthly.toFixed(1)}%`} />
                      <Row k="Quarterly trend" v={`${result.trend_quarterly >= 0 ? "+" : ""}${result.trend_quarterly.toFixed(1)}%`} />
                      <Row k="Demand" v={result.demand_forecast ?? "—"} />
                      <Row k="Supply" v={result.supply_forecast ?? "—"} />
                      <Row k="14-day forecast" v={`${formatINR(result.price_forecast_14d)}/q`} />
                    </div>
                    {result.reasoning && (
                      <p className="rounded-lg bg-muted p-3 text-xs leading-relaxed text-muted-foreground">
                        {result.reasoning}
                      </p>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Where should I sell? — per-mandi price comparison */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Where should I sell?</CardTitle>
                  <CardDescription>
                    Price comparison across your nearest APMC mandis for {result.crop}.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {comparison && comparison.items.length > 0 ? (
                    <>
                      <div className="space-y-2">
                        {comparison.items.map((m, i) => (
                          <div
                            key={`${m.mandi}-${i}`}
                            className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 ${
                              i === 0 ? "border-leaf-200 bg-leaf-50" : ""
                            }`}
                          >
                            <div className="min-w-0">
                              <p className="inline-block flex items-center gap-2 truncate font-medium">
                                {i === 0 && <Badge variant="success" className="shrink-0 text-[10px]">Best price</Badge>}
                                {m.mandi}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {m.district ?? "—"} · {m.distance_km} km
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="font-bold">
                                {formatINR(m.price)}
                                <span className="ml-1 text-[10px] font-normal text-muted-foreground">/q</span>
                              </p>
                              <p className="inline-block flex items-center justify-end gap-1 text-[11px] text-muted-foreground">
                                <span className={m.trend_weekly_pct >= 0 ? "text-leaf-600" : "text-red-600"}>
                                  {m.trend_weekly_pct >= 0 ? "▲" : "▼"} {Math.abs(m.trend_weekly_pct).toFixed(1)}%
                                </span>
                                {!m.is_live && <Badge variant="warning" className="text-[9px]">est</Badge>}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                      <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{comparison.note}</p>
                    </>
                  ) : !mandis || mandis.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Save your farm location in your{" "}
                      <a href="/dashboard/profile" className="text-leaf-600 underline">profile</a>{" "}
                      to compare nearby mandis.
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">Market data currently unavailable for these mandis.</p>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-4 space-y-4">
          {(history?.items ?? []).length === 0 ? (
            <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No analyses yet.</CardContent></Card>
          ) : (
            (history?.items ?? []).map((m) => (
              <Card key={m.id}>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
                  <div>
                    <p className="font-medium capitalize">{m.crop}</p>
                    <p className="text-xs text-muted-foreground">
                      {m.market ?? "national"} · {formatDate(m.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-4 text-sm">
                    <span>{formatINR(m.current_price)}/q</span>
                    <span className={m.trend_weekly >= 0 ? "text-leaf-600" : "text-red-600"}>
                      {m.trend_weekly >= 0 ? "▲" : "▼"} {Math.abs(m.trend_weekly).toFixed(1)}%
                    </span>
                    <Badge variant={RECOMMENDATION_VARIANT[m.recommendation] ?? "secondary"}>
                      {m.recommendation.replace(/_/g, " ")}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
          {history && history.total > 10 && (
            <div className="flex justify-center gap-2">
              <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Prev</Button>
              <Button variant="outline" size="sm" disabled={page * 10 >= history.total} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function DataSourceBadge({ source }: { source?: string | null }) {
  const labels: Record<string, string> = {
    agmarknet_market: "Live Agmarknet data (mandi level)",
    agmarknet_district: "Live Agmarknet data (district level)",
    agmarknet_state: "Live Agmarknet data (state level)",
    agmarknet_national: "Live Agmarknet data (national)",
    agmarknet_scraped_state: "Live Agmarknet data (state-wide, live portal)",
  };
  const isLive = Boolean(source && labels[source]);
  return (
    <CardDescription className="flex items-center gap-1.5 pt-1">
      {isLive ? (
        <>
          <BadgeCheck className="h-3.5 w-3.5 text-leaf-600" />
          <span>{labels[source!]}</span>
        </>
      ) : (
        <>
          <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
          <span>Modeled estimate — no live market feed</span>
        </>
      )}
    </CardDescription>
  );
}

function KpiCard({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className={`font-display text-[22px] font-medium leading-tight tracking-[0.32px] ${tone === "up" ? "text-leaf-600" : tone === "down" ? "text-red-600" : ""}`}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-medium capitalize">{v}</span>
    </div>
  );
}
