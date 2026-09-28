"use client";

import * as React from "react";
import { Loader2, Leaf, Sparkles } from "lucide-react";

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
import { useProfile, useRecommendCrop, useRecommendationHistory } from "@/hooks/use-api";
import type { CropRecommendationItem } from "@/types";
import { formatCompactINR, formatINR, riskLabel, formatDate } from "@/lib/utils";

const SOILS = ["black", "alluvial", "loamy", "clay", "sandy", "silt", "laterite", "red", "peaty", "unknown"];
const WATER = ["rainfed", "canal", "borewell", "well", "river", "pond", "none"];
const SEASONS = ["kharif", "rabi", "zaid"];

export default function CropsPage() {
  const { data: profile } = useProfile();
  const recommend = useRecommendCrop();
  const [result, setResult] = React.useState<{ crops: CropRecommendationItem[]; location: string; season: string } | null>(null);
  const [page, setPage] = React.useState(1);
  const { data: history } = useRecommendationHistory(page);

  const [form, setForm] = React.useState({
    location: "",
    farm_size_acres: "5",
    soil_type: "unknown",
    water_source: "rainfed",
    budget_inr: "50000",
    season: "kharif",
  });

  React.useEffect(() => {
    if (profile) {
      setForm((f) => ({
        ...f,
        location: f.location || [profile.district, profile.state].filter(Boolean).join(", ") || "",
        farm_size_acres: String(profile.farm_size_acres ?? 5),
        soil_type: profile.soil_type ?? "unknown",
        water_source: profile.water_availability ?? "rainfed",
      }));
    }
  }, [profile]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await recommend.mutateAsync({
        location: form.location,
        farm_size_acres: Number(form.farm_size_acres),
        soil_type: form.soil_type,
        water_source: form.water_source,
        budget_inr: Number(form.budget_inr),
        season: form.season,
      });
      setResult(res);
    } catch {
      /* toast shown by mutation? show inline */
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Crop Advisor</h1>
        <p className="text-sm text-muted-foreground">
          AI-ranked crop options by expected profit for your exact conditions.
        </p>
      </div>

      <Tabs defaultValue="recommend">
        <TabsList>
          <TabsTrigger value="recommend">Recommendation</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="recommend" className="mt-4 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Leaf className="h-4 w-4 text-leaf-600" /> Farm details
              </CardTitle>
              <CardDescription>The more precise, the better the projection.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="space-y-2">
                  <Label>Location (district, state)</Label>
                  <Input
                    required
                    placeholder="Nashik, Maharashtra"
                    value={form.location}
                    onChange={(e) => setForm({ ...form, location: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Farm size (acres)</Label>
                  <Input
                    required
                    type="number"
                    step="0.1"
                    min="0.1"
                    value={form.farm_size_acres}
                    onChange={(e) => setForm({ ...form, farm_size_acres: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Budget (₹)</Label>
                  <Input
                    required
                    type="number"
                    min="0"
                    value={form.budget_inr}
                    onChange={(e) => setForm({ ...form, budget_inr: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                <Label htmlFor="soil-type">Soil type</Label>
                <Select value={form.soil_type} onValueChange={(v) => setForm({ ...form, soil_type: v })}>
                  <SelectTrigger id="soil-type"><SelectValue placeholder="Select soil type" /></SelectTrigger>
                    <SelectContent>
                      {SOILS.map((s) => (
                        <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                <Label htmlFor="water-source">Water source</Label>
                <Select value={form.water_source} onValueChange={(v) => setForm({ ...form, water_source: v })}>
                  <SelectTrigger id="water-source"><SelectValue placeholder="Select water source" /></SelectTrigger>
                    <SelectContent>
                      {WATER.map((w) => (
                        <SelectItem key={w} value={w} className="capitalize">{w}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="season">Season</Label>
                  <Select value={form.season} onValueChange={(v) => setForm({ ...form, season: v })}>
                    <SelectTrigger id="season"><SelectValue placeholder="Select season" /></SelectTrigger>
                    <SelectContent>
                      {SEASONS.map((s) => (
                        <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="sm:col-span-2 lg:col-span-3">
                  <Button type="submit" disabled={recommend.isPending} className="gap-2">
                    {recommend.isPending ? (
                      <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing your farm…</>
                    ) : (
                      <><Sparkles className="h-4 w-4" /> Get AI recommendation</>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {recommend.isPending && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Card key={i} className="animate-pulse"><CardContent className="h-48" /></Card>
              ))}
            </div>
          )}

          {result && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {result.crops.map((c, idx) => {
                const risk = riskLabel(c.risk_score);
                return (
                  <Card key={`${c.crop_name}-${idx}`} className={idx === 0 ? "ring-1 ring-leaf-500" : ""}>
                    <CardContent className="pt-6">
                      <div className="mb-3 flex items-center justify-between">
                        <h3 className="text-lg font-bold capitalize">{c.crop_name}</h3>
                        {idx === 0 && <Badge>Best pick</Badge>}
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <p className="text-muted-foreground">Investment</p>
                          <p className="font-medium">{formatINR(c.investment_inr)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Expected profit</p>
                          <p className="font-medium text-leaf-700">{formatINR(c.expected_profit_inr)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Revenue</p>
                          <p className="font-medium">{formatINR(c.expected_revenue_inr)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Duration</p>
                          <p className="font-medium">{c.duration_days ?? "—"} days</p>
                        </div>
                      </div>
                      <div className="mt-4 space-y-2">
                        <div>
                          <div className="mb-1 flex justify-between text-xs">
                            <span className="text-muted-foreground">Risk</span>
                            <span className={risk.color}>{risk.label} ({c.risk_score.toFixed(0)})</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-muted">
                            <div className={`h-1.5 rounded-full ${c.risk_score >= 70 ? "bg-red-500" : c.risk_score >= 40 ? "bg-amber-500" : "bg-leaf-500"}`} style={{ width: `${c.risk_score}%` }} />
                          </div>
                        </div>
                        <div>
                          <div className="mb-1 flex justify-between text-xs">
                            <span className="text-muted-foreground">Confidence</span>
                            <span>{c.confidence_score.toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-muted">
                            <div className="h-1.5 rounded-full bg-leaf-500" style={{ width: `${c.confidence_score}%` }} />
                          </div>
                        </div>
                      </div>
                      <p className="mt-4 text-sm text-muted-foreground">{c.why_recommended}</p>
                      {c.risks.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {c.risks.map((r) => (
                            <Badge key={r} variant="warning" className="text-[10px]">{r}</Badge>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-4 space-y-4">
          {(history?.items ?? []).length === 0 ? (
            <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No recommendations yet.</CardContent></Card>
          ) : (
            (history?.items ?? []).map((h) => (
              <Card key={h.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">
                      {h.location} · <span className="capitalize">{h.season}</span> · {h.farm_size_acres} acres
                    </CardTitle>
                    <span className="text-xs text-muted-foreground">{formatDate(h.created_at)}</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {h.crops.map((c, idx) => (
                      <Badge key={`${c.crop_name}-${idx}`} variant="secondary" className="capitalize">
                        {c.crop_name} · {formatCompactINR(c.expected_profit_inr)}
                      </Badge>
                    ))}
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
