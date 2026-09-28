"use client";

import * as React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Calculator, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePredictProfit, useProfitPredictions } from "@/hooks/use-api";
import { apiErrorMessage } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { formatCompactINR, formatINR, riskLabel } from "@/lib/utils";

const COST_FIELDS = [
  { key: "seed_cost", label: "Seed cost (₹)" },
  { key: "labor_cost", label: "Labor cost (₹)" },
  { key: "fertilizer_cost", label: "Fertilizer cost (₹)" },
  { key: "irrigation_cost", label: "Irrigation cost (₹)" },
  { key: "transportation_cost", label: "Transportation cost (₹)" },
  { key: "other_cost", label: "Other cost (₹)" },
] as const;

export default function ProfitPage() {
  const predict = usePredictProfit();
  const { toast } = useToast();
  const [page, setPage] = React.useState(1);
  const { data: history } = useProfitPredictions(page);

  const [form, setForm] = React.useState({
    crop: "",
    farm_size_acres: "5",
    season: "kharif",
    seed_cost: "5000",
    labor_cost: "15000",
    fertilizer_cost: "8000",
    irrigation_cost: "4000",
    transportation_cost: "3000",
    other_cost: "0",
  });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await predict.mutateAsync({
        crop: form.crop,
        farm_size_acres: Number(form.farm_size_acres),
        season: form.season,
        seed_cost: Number(form.seed_cost),
        labor_cost: Number(form.labor_cost),
        fertilizer_cost: Number(form.fertilizer_cost),
        irrigation_cost: Number(form.irrigation_cost),
        transportation_cost: Number(form.transportation_cost),
        other_cost: Number(form.other_cost),
      });
      toast({ title: "Prediction ready", variant: "success" });
    } catch (err) {
      toast({ title: "Prediction failed", description: apiErrorMessage(err), variant: "destructive" });
    }
  };

  const result = predict.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Profit Predictor</h1>
        <p className="text-sm text-muted-foreground">
          Know your ROI before you spend — best, average and worst-case scenarios.
        </p>
      </div>

      <Tabs defaultValue="predict">
        <TabsList>
          <TabsTrigger value="predict">Predict</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="predict" className="mt-4 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Calculator className="h-4 w-4 text-leaf-600" /> Cost breakdown
              </CardTitle>
              <CardDescription>Enter planned costs for the full farm.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="space-y-2">
                  <Label>Crop</Label>
                  <Input required placeholder="e.g. wheat" value={form.crop} onChange={(e) => setForm({ ...form, crop: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>Farm size (acres)</Label>
                  <Input required type="number" step="0.1" min="0.1" value={form.farm_size_acres} onChange={(e) => setForm({ ...form, farm_size_acres: e.target.value })} />
                </div>
                <div className="space-y-2">
                <Label htmlFor="season">Season</Label>
                <Select value={form.season} onValueChange={(v) => setForm({ ...form, season: v })}>
                  <SelectTrigger id="season"><SelectValue placeholder="Select season" /></SelectTrigger>
                    <SelectContent>
                      {["kharif", "rabi", "zaid"].map((s) => (
                        <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {COST_FIELDS.map((f) => (
                  <div key={f.key} className="space-y-2">
                    <Label>{f.label}</Label>
                    <Input required type="number" min="0" value={form[f.key]} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
                  </div>
                ))}
                <div className="sm:col-span-2 lg:col-span-3">
                  <Button type="submit" disabled={predict.isPending} className="gap-2">
                    {predict.isPending ? (
                      <><Loader2 className="h-4 w-4 animate-spin" /> Crunching numbers…</>
                    ) : (
                      <>Predict profit</>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {result && (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <KpiCard label="Expected Yield" value={`${result.expected_yield_quintals.toFixed(1)} q`} />
                <KpiCard label="Expected Revenue" value={formatCompactINR(result.expected_revenue)} />
                <KpiCard label="Expected Profit" value={formatCompactINR(result.expected_profit)} highlight />
                <KpiCard label="ROI" value={`${result.roi.toFixed(0)}%`} />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Scenario comparison</CardTitle>
                    <CardDescription>Profit under different outcomes</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart
                        data={["best", "average", "worst"]
                          .map((k) => ({ name: k, ...(result.scenarios[k as keyof typeof result.scenarios] ?? {}) }))
                          .filter((s) => s.revenue_inr != null)}
                      >
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => formatCompactINR(v)} />
                        <Tooltip formatter={(v: number) => formatINR(v)} />
                        <Bar dataKey="revenue_inr" name="Revenue" fill="#16a34a" radius={[6, 6, 0, 0]} />
                        <Bar dataKey="profit_inr" name="Profit" fill="#0ea5e9" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Details</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Total cost</span>
                      <span className="font-medium">{formatINR(result.total_cost)}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Price assumption</span>
                      <span className="font-medium">{formatINR(result.expected_price_per_quintal)}/q</span>
                    </div>
                    <div>
                      <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                        <span>Risk score</span><span>{result.risk_score.toFixed(0)}/100</span>
                      </div>
                      <Progress value={result.risk_score} />
                    </div>
                    <div>
                      <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                        <span>Confidence</span><span>{result.confidence_score.toFixed(0)}%</span>
                      </div>
                      <Progress value={result.confidence_score} />
                    </div>
                    <div className="space-y-2 pt-2">
                      {(["best", "average", "worst"] as const).map((k) => {
                        const s = result.scenarios[k];
                        if (!s) return null;
                        return (
                          <div key={k} className="rounded-lg border p-3 text-sm">
                            <div className="flex items-center justify-between">
                              <Badge variant={k === "best" ? "success" : k === "worst" ? "destructive" : "secondary"}>
                                {k}
                              </Badge>
                              <span className="font-medium">{formatINR(s.profit_inr)}</span>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {s.yield_quintals.toFixed(1)} q @ {formatINR(s.price_per_quintal)}/q · ROI {s.roi_percent.toFixed(0)}%
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-4 space-y-4">
          {(history?.items ?? []).length === 0 ? (
            <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No predictions yet.</CardContent></Card>
          ) : (
            (history?.items ?? []).map((p) => (
              <Card key={p.id}>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
                  <div>
                    <p className="font-medium capitalize">{p.crop} · {p.farm_size_acres} acres</p>
                    <p className="text-xs text-muted-foreground">
                      Cost {formatINR(p.total_cost)} · Revenue {formatINR(p.expected_revenue)}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-sm font-bold text-leaf-700">{formatCompactINR(p.expected_profit)}</p>
                      <p className="text-xs text-muted-foreground">profit · ROI {p.roi.toFixed(0)}%</p>
                    </div>
                    <Badge variant={p.risk_score >= 70 ? "destructive" : p.risk_score >= 40 ? "warning" : "success"}>
                      risk {p.risk_score.toFixed(0)}
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

function KpiCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <Card className={highlight ? "ring-1 ring-leaf-500" : ""}>
      <CardContent className="pt-6">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className={`font-display text-[22px] font-medium leading-tight tracking-[0.32px] ${highlight ? "text-leaf-700" : ""}`}>{value}</p>
      </CardContent>
    </Card>
  );
}
