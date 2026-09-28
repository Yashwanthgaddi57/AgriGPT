"use client";

import * as React from "react";
import {
  ClipboardList,
  Coins,
  Loader2,
  Scale,
  Sprout,
  Trash2,
  TrendingUp,
  Wheat,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useCreateExpense,
  useCreateHarvest,
  useDeleteExpense,
  useEstimatedVsActual,
  useExpenses,
  useFarmTimeline,
  useHarvests,
} from "@/hooks/use-api";
import { apiErrorMessage } from "@/lib/api";
import { trackEvent, EVENTS } from "@/lib/events";
import { useToast } from "@/hooks/use-toast";
import { formatINR } from "@/lib/utils";

const CATEGORIES = [
  "seed", "fertilizer", "pesticide", "labor",
  "irrigation", "machinery", "transport", "other",
];

export default function FarmLogPage() {
  const { toast } = useToast();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Farm Log</h1>
        <p className="text-sm text-muted-foreground">
          Your farm&apos;s memory: expenses, harvests, and estimated-vs-actual outcomes.
        </p>
      </div>

      <Tabs defaultValue="expenses">
        <TabsList>
          <TabsTrigger value="expenses">Expenses</TabsTrigger>
          <TabsTrigger value="harvest">Harvest</TabsTrigger>
          <TabsTrigger value="compare">Estimate vs Actual</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        <ExpensesTab />
        <HarvestTab />
        <CompareTab />
        <TimelineTab />
      </Tabs>
    </div>
  );
}

// ---------------- Expenses ----------------
function ExpensesTab() {
  const { data, isLoading } = useExpenses();
  const create = useCreateExpense();
  const remove = useDeleteExpense();
  const { toast } = useToast();
  const [category, setCategory] = React.useState("seed");
  const [amount, setAmount] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [spentOn, setSpentOn] = React.useState(new Date().toISOString().slice(0, 10));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amt = parseFloat(amount);
    if (!Number.isFinite(amt) || amt <= 0) {
      toast({ title: "Enter a valid amount", variant: "destructive" });
      return;
    }
    try {
      await create.mutateAsync({ category, amount_inr: amt, description: description || null, spent_on: spentOn });
      setAmount("");
      setDescription("");
      toast({ title: "Expense recorded", variant: "success" });
    } catch (err) {
      toast({ title: "Could not save", description: apiErrorMessage(err), variant: "destructive" });
    }
  };

  const chartData = Object.entries(data?.by_category ?? {}).map(([name, value]) => ({
    name: name.slice(0, 8),
    value: Math.round(value),
  }));

  return (
    <TabsContent value="expenses" className="mt-4 space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Coins className="h-4 w-4 text-leaf-600" /> Add expense
            </CardTitle>
            <CardDescription>Real spending — feeds your profit comparisons</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="category">Category</Label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger id="category"><SelectValue placeholder="Select category" /></SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Amount (₹)</Label>
                <Input required type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Date</Label>
                <Input required type="date" max={new Date().toISOString().slice(0, 10)} value={spentOn} onChange={(e) => setSpentOn(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Note (optional)</Label>
                <Input placeholder="e.g. urea 50kg" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />
              </div>
              <div className="sm:col-span-2">
                <Button type="submit" disabled={create.isPending} className="gap-2">
                  {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  Record expense
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Total recorded</p>
                <p className="text-xl font-bold">{formatINR(data?.total ?? 0)}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Per acre</p>
                <p className="text-xl font-bold">{formatINR(data?.per_acre ?? 0)}</p>
              </div>
            </div>
            {chartData.length > 0 && (
              <div className="mt-4">
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="name" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                    <Tooltip formatter={(v: number) => formatINR(v)} />
                    <Bar dataKey="value" fill="#16a34a" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">Recorded expenses</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="py-4 text-sm text-muted-foreground">Loading…</p>
          ) : (data?.items ?? []).length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">No expenses recorded yet.</p>
          ) : (
            <div className="divide-y">
              {(data?.items ?? []).map((e) => (
                <div key={e.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm font-medium capitalize">{e.category} · {formatINR(e.amount_inr)}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {e.spent_on}{e.description ? ` · ${e.description}` : ""}
                    </p>
                  </div>
                  <button
                    onClick={() => remove.mutate(e.id)}
                    className="shrink-0 rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-red-600"
                    aria-label="Delete expense"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </TabsContent>
  );
}

// ---------------- Harvest ----------------
function HarvestTab() {
  const { data } = useHarvests();
  const create = useCreateHarvest();
  const { toast } = useToast();
  const [crop, setCrop] = React.useState("");
  const [yieldQ, setYieldQ] = React.useState("");
  const [price, setPrice] = React.useState("");
  const [market, setMarket] = React.useState("");
  const [harvestDate, setHarvestDate] = React.useState(new Date().toISOString().slice(0, 10));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      trackEvent(EVENTS.cropPlanCompleted, { kind: "harvest" });
      await create.mutateAsync({
        crop,
        harvest_date: harvestDate || null,
        actual_yield_quintals: yieldQ ? parseFloat(yieldQ) : null,
        selling_price_per_quintal: price ? parseFloat(price) : null,
        market_name: market || null,
      });
      setCrop(""); setYieldQ(""); setPrice(""); setMarket("");
      toast({ title: "Harvest recorded", variant: "success" });
    } catch (err) {
      toast({ title: "Could not save", description: apiErrorMessage(err), variant: "destructive" });
    }
  };

  return (
    <TabsContent value="harvest" className="mt-4 space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Wheat className="h-4 w-4 text-leaf-600" /> Record a harvest
          </CardTitle>
          <CardDescription>Actual outcomes power the estimate-vs-actual comparison</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-2">
              <Label>Crop</Label>
              <Input required placeholder="e.g. groundnut" value={crop} onChange={(e) => setCrop(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Harvest date</Label>
              <Input type="date" max={new Date().toISOString().slice(0, 10)} value={harvestDate} onChange={(e) => setHarvestDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Actual yield (quintals)</Label>
              <Input type="number" step="0.1" min="0" value={yieldQ} onChange={(e) => setYieldQ(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Selling price (₹/quintal)</Label>
              <Input type="number" min="0" value={price} onChange={(e) => setPrice(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Market (optional)</Label>
              <Input placeholder="e.g. Lasalgaon APMC" value={market} onChange={(e) => setMarket(e.target.value)} />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={create.isPending} className="gap-2">
                {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Save harvest
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {(data?.items ?? []).length > 0 && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">Harvest history</CardTitle></CardHeader>
          <CardContent className="divide-y">
            {(data?.items ?? []).map((h) => (
              <div key={h.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                <div>
                  <p className="inline-block text-sm font-medium capitalize">{h.crop}{h.harvest_date ? ` · ${h.harvest_date}` : ""}</p>
                  {h.market_name && <p className="text-xs text-muted-foreground">{h.market_name}</p>}
                </div>
                <div className="text-right text-sm">
                  {h.actual_yield_quintals != null && <span>{h.actual_yield_quintals.toFixed(1)} q</span>}
                  {h.selling_price_per_quintal != null && <span> @ ₹{h.selling_price_per_quintal.toLocaleString("en-IN")}/q</span>}
                  {h.revenue_inr != null && (
                    <Badge variant="success" className="ml-2">{formatINR(h.revenue_inr)}</Badge>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </TabsContent>
  );
}

// ---------------- Estimated vs Actual ----------------
function CompareTab() {
  const { data } = useEstimatedVsActual();

  if (!data || !data.has_comparison) {
    return (
      <TabsContent value="compare" className="mt-4">
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Run a profit estimate and record a harvest to compare estimated vs actual outcomes.
          </CardContent>
        </Card>
      </TabsContent>
    );
  }

  const rows: { label: string; est: number | null; act: number | null; fmt: (v: number) => string }[] = [
    { label: "Yield (q)", est: data.estimated.yield_quintals, act: data.actual.yield_quintals, fmt: (v) => `${v.toFixed(1)} q` },
    { label: "Price (₹/q)", est: data.estimated.price_per_quintal, act: data.actual.price_per_quintal, fmt: (v) => formatINR(v) },
    { label: "Cost", est: data.estimated.cost, act: data.actual.cost, fmt: (v) => formatINR(v) },
    { label: "Revenue", est: data.estimated.revenue, act: data.actual.revenue, fmt: (v) => formatINR(v) },
    { label: "Profit", est: data.estimated.profit, act: data.actual.profit, fmt: (v) => formatINR(v) },
  ];

  return (
    <TabsContent value="compare" className="mt-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Scale className="h-4 w-4 text-leaf-600" /> Estimated vs Actual
            {data.estimated.crop && data.actual.crop && (
              <Badge variant="secondary" className="capitalize text-[10px]">{data.actual.crop}</Badge>
            )}
          </CardTitle>
          <CardDescription>Latest profit estimate vs your recorded reality</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Mobile-first: card list instead of a horizontal-scroll table (§21) */}
          <div className="space-y-2 md:hidden">
            {rows.map((r) => {
              const diff = r.est != null && r.act != null ? r.act - r.est : null;
              return (
                <div key={r.label} className="rounded-lg border p-3">
                  <p className="font-medium">{r.label}</p>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Est.</p>
                      <p>{r.est != null ? r.fmt(r.est) : "—"}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Actual</p>
                      <p>{r.act != null ? r.fmt(r.act) : "—"}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Diff</p>
                      <p className={`font-medium ${diff == null ? "" : diff >= 0 ? "text-leaf-700" : "text-red-600"}`}>
                        {diff != null ? `${diff >= 0 ? "+" : ""}${r.fmt(Math.abs(diff))}` : "—"}
                      </p>
                    </div>
                  </div>
                  {diff != null && (
                    <p className="mt-1 text-[11px] text-muted-foreground">{diff >= 0 ? "▲ above" : "▼ below"} estimate</p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Desktop: keep the full table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 pr-4">Metric</th>
                  <th className="pb-2 pr-4">Estimated</th>
                  <th className="pb-2 pr-4">Actual</th>
                  <th className="pb-2">Difference</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const diff = r.est != null && r.act != null ? r.act - r.est : null;
                  return (
                    <tr key={r.label} className="border-b last:border-0">
                      <td className="py-2.5 pr-4 font-medium">{r.label}</td>
                      <td className="py-2.5 pr-4">{r.est != null ? r.fmt(r.est) : "—"}</td>
                      <td className="py-2.5 pr-4">{r.act != null ? r.fmt(r.act) : "—"}</td>
                      <td className={`py-2.5 font-medium ${diff == null ? "" : diff >= 0 ? "text-leaf-700" : "text-red-600"}`}>
                        {diff != null ? `${diff >= 0 ? "+" : ""}${r.fmt(Math.abs(diff))}` : "—"}
                        {diff != null && <span className="ml-1 text-[10px] font-normal text-muted-foreground">{diff >= 0 ? "above" : "below"} estimate</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Actual cost = sum of your recorded expenses. Over time, these comparisons
            help calibrate future estimates for your farm.
          </p>
        </CardContent>
      </Card>
    </TabsContent>
  );
}

// ---------------- Timeline ----------------
function TimelineTab() {
  const { data, isLoading } = useFarmTimeline();

  const TYPE_META: Record<string, { icon: React.ComponentType<{ className?: string }>; label: string }> = {
    harvest: { icon: Wheat, label: "Harvest" },
    scan: { icon: TrendingUp, label: "Scan" },
    plan: { icon: Sprout, label: "Plan" },
    estimate: { icon: ClipboardList, label: "Estimate" },
  };

  return (
    <TabsContent value="timeline" className="mt-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <ClipboardList className="h-4 w-4 text-leaf-600" /> Farm timeline
          </CardTitle>
          <CardDescription>Your farm&apos;s long-term memory</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {data && data.items.length === 0 && (
            <p className="py-4 text-sm text-muted-foreground">
              No history yet — record expenses, harvests and scans to build your timeline.
            </p>
          )}
          <div className="space-y-0">
            {(data?.items ?? []).map((e, i) => {
              const meta = TYPE_META[e.type] ?? TYPE_META.plan;
              const Icon = meta.icon;
              return (
                <div key={`${e.date}-${i}`} className="relative flex gap-3 pb-5 last:pb-0">
                  {i < (data?.items.length ?? 0) - 1 && (
                    <span className="absolute left-[15px] top-8 h-full w-px bg-border" aria-hidden />
                  )}
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-leaf-100 text-leaf-600">
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">{e.date} · {meta.label}</p>
                    <p className="text-sm font-medium">{e.title}</p>
                    <p className="text-xs text-muted-foreground">{e.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </TabsContent>
  );
}
