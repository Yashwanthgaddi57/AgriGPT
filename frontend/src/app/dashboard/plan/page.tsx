"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Coins,
  Droplets,
  Leaf,
  Loader2,
  MapPin,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Sprout,
  Wallet,
} from "lucide-react";

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
import { apiErrorMessage } from "@/lib/api";
import { trackEvent, EVENTS } from "@/lib/events";
import { useProfile, useRecommendCrop, useRecommendationHistory } from "@/hooks/use-api";
import { useToast } from "@/hooks/use-toast";
import type { CropRecommendationItem, Recommendation } from "@/types";
import { cn, formatINR, riskLabel } from "@/lib/utils";

const SOILS = ["black", "alluvial", "loamy", "clay", "sandy", "silt", "laterite", "red", "peaty", "unknown"];
const WATER = ["rainfed", "canal", "borewell", "well", "river", "pond", "none"];
const SEASONS = ["kharif", "rabi", "zaid"];

type Step = 1 | 2 | 3;

export default function PlanMyFarmPage() {
  const { data: profile } = useProfile();
  const recommend = useRecommendCrop();
  const { toast } = useToast();
  const router = useRouter();

  const [step, setStep] = React.useState<Step>(1);
  const [result, setResult] = React.useState<Recommendation | null>(null);
  const [selected, setSelected] = React.useState<number>(0);
  const [form, setForm] = React.useState({
    location: "",
    village: "",
    farm_size_acres: "2.5",
    soil_type: "unknown",
    water_source: "rainfed",
    season: "kharif",
    budget_inr: "50000",
    previous_crop: "",
    preferred_crops: "",
  });

  React.useEffect(() => {
    if (profile) {
      setForm((f) => ({
        ...f,
        location: f.location || [profile.district, profile.state].filter(Boolean).join(", ") || "",
        village: f.village || profile.village || "",
        farm_size_acres: f.farm_size_acres === "2.5" ? String(profile.farm_size_acres ?? 2.5) : f.farm_size_acres,
        soil_type: f.soil_type === "unknown" ? profile.soil_type ?? "unknown" : f.soil_type,
        water_source: f.water_source === "rainfed" ? profile.water_availability ?? "rainfed" : f.water_source,
      }));
    }
  }, [profile]);

  const profileValid = form.location.trim().length >= 2 && Number(form.farm_size_acres) > 0;

  React.useEffect(() => {
    trackEvent(EVENTS.planWizardStarted);
  }, []);

  const analyze = async () => {
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
      setSelected(0);
      setStep(3);
      trackEvent(EVENTS.planWizardCompleted, {
        top_crop: res.crops?.[0]?.crop_name ?? null,
      });
      trackEvent(EVENTS.cropPlanCompleted);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      toast({
        title: "Analysis failed",
        description: apiErrorMessage(err) || "Something went wrong while analyzing your farm. Please try again.",
        variant: "destructive",
      });
    }
  };

  const crops: CropRecommendationItem[] = (result?.crops ?? []) as CropRecommendationItem[];
  const chosen = crops[selected];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Plan My Farm</h1>
        <p className="text-sm text-muted-foreground">
          Tell us about your farm — get AI-generated crop options with estimated
          costs, returns and risks. Estimates only, not guarantees.
        </p>
      </div>

      {/* Stepper */}
      <ol className="flex items-center gap-2 text-xs sm:text-sm">
        {[
          { n: 1 as Step, label: "Farm profile" },
          { n: 2 as Step, label: "Analyze" },
          { n: 3 as Step, label: "Compare & plan" },
        ].map((s, i) => (
          <li key={s.n} className="flex flex-1 items-center gap-2">
            <span
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 font-bold",
                step === s.n
                  ? "border-leaf-600 bg-leaf-600 text-white"
                  : step > s.n
                  ? "border-leaf-600 bg-leaf-100 text-leaf-600"
                  : "border-muted text-muted-foreground"
              )}
            >
              {step > s.n ? <CheckCircle2 className="h-4 w-4" /> : s.n}
            </span>
            <span className={cn("hidden sm:inline", step >= s.n ? "font-medium" : "text-muted-foreground")}>
              {s.label}
            </span>
            {i < 2 && <span className="h-px flex-1 bg-border" />}
          </li>
        ))}
      </ol>

      {/* STEP 1 — Farm profile */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <MapPin className="h-4 w-4 text-leaf-600" /> Step 1 · Farm profile
            </CardTitle>
            <CardDescription>The more precise, the better the estimates.</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (profileValid) {
                  setStep(2);
                  analyze();
                }
              }}
              className="grid gap-4 sm:grid-cols-2"
            >
              <div className="space-y-2">
                <Label>District & state *</Label>
                <Input
                  required
                  placeholder="Nashik, Maharashtra"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Village / location (optional)</Label>
                <Input
                  placeholder="Ozar"
                  value={form.village}
                  onChange={(e) => setForm({ ...form, village: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Farm size (acres) *</Label>
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
                <Label htmlFor="season">Current season *</Label>
                <Select value={form.season} onValueChange={(v) => setForm({ ...form, season: v })}>
                  <SelectTrigger id="season"><SelectValue placeholder="Select season" /></SelectTrigger>
                  <SelectContent>
                    {SEASONS.map((s) => (
                      <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
                <Label htmlFor="water-availability">Water availability</Label>
                <Select value={form.water_source} onValueChange={(v) => setForm({ ...form, water_source: v })}>
                  <SelectTrigger id="water-availability"><SelectValue placeholder="Select water availability" /></SelectTrigger>
                  <SelectContent>
                    {WATER.map((w) => (
                      <SelectItem key={w} value={w} className="capitalize">{w}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Available budget (₹) *</Label>
                <Input
                  required
                  type="number"
                  min="0"
                  value={form.budget_inr}
                  onChange={(e) => setForm({ ...form, budget_inr: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Previous crop (optional)</Label>
                <Input
                  placeholder="e.g. soybean"
                  value={form.previous_crop}
                  onChange={(e) => setForm({ ...form, previous_crop: e.target.value })}
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label>Preferred crops (optional)</Label>
                <Input
                  placeholder="e.g. groundnut, cotton"
                  value={form.preferred_crops}
                  onChange={(e) => setForm({ ...form, preferred_crops: e.target.value })}
                />
              </div>
              <div className="sm:col-span-2">
                <Button type="submit" disabled={!profileValid || recommend.isPending} className="gap-2">
                  {recommend.isPending ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing…</>
                  ) : (
                    <>Analyze my farm <ArrowRight className="h-4 w-4" /></>
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* STEP 2 — Analyzing */}
      {step === 2 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
            <Loader2 className="h-10 w-10 animate-spin text-leaf-600" />
            <div>
              <p className="font-medium">Analyzing your farm…</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Comparing crops for {form.location || "your area"} — this usually takes 10–30 seconds.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STEP 3 — Compare & plan */}
      {step === 3 && result && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-[17px] font-medium tracking-[-0.24px]">Step 3 · Compare crops</h2>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => {
                setStep(1);
                setResult(null);
              }}
            >
              <RefreshCw className="h-3.5 w-3.5" /> Edit farm profile
            </Button>
          </div>

          <p className="rounded-lg bg-muted p-3 text-xs text-muted-foreground">
            All figures below are <strong>AI-generated estimates</strong> based on
            the farm profile you provided — not guarantees. Verify with local
            experts before committing money.
          </p>

          {/* Comparison cards */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {crops.map((c, idx) => {
              const risk = riskLabel(c.risk_score);
              return (
                <Card
                  key={`${c.crop_name}-${idx}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelected(idx)}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setSelected(idx)}
                  className={cn(
                    "cursor-pointer transition-all hover:shadow-md",
                    selected === idx ? "ring-1 ring-leaf-500" : ""
                  )}
                >
                  <CardContent className="pt-6">
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="text-lg font-bold capitalize">{c.crop_name}</h3>
                      {selected === idx ? (
                        <Badge>Selected</Badge>
                      ) : (
                        <Badge variant="secondary">Compare</Badge>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-muted-foreground">Est. cost</p>
                        <p className="font-medium">{formatINR(c.investment_inr)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Est. revenue</p>
                        <p className="font-medium">{formatINR(c.expected_revenue_inr)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Est. profit</p>
                        <p className="font-medium text-leaf-700">{formatINR(c.expected_profit_inr)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Duration</p>
                        <p className="font-medium">{c.duration_days ?? "—"} days</p>
                      </div>
                    </div>
                    <div className="mt-3">
                      <div className="mb-1 flex justify-between text-xs">
                        <span className="text-muted-foreground">Risk</span>
                        <span className={risk.color}>{risk.label} ({c.risk_score.toFixed(0)})</span>
                      </div>
                      <Progress value={c.risk_score} className="h-1.5" />
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Farm plan for selected crop */}
          {chosen && (
            <Card className="ring-1 ring-leaf-500">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sprout className="h-4 w-4 text-leaf-600" /> Your farm plan ·{" "}
                  <span className="capitalize">{chosen.crop_name}</span>
                </CardTitle>
                <CardDescription>AI-generated estimate — based on provided inputs</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <PlanStat icon={Wallet} label="Est. cost" value={formatINR(chosen.investment_inr)} />
                  <PlanStat icon={Coins} label="Est. revenue" value={formatINR(chosen.expected_revenue_inr)} />
                  <PlanStat icon={Leaf} label="Est. profit" value={formatINR(chosen.expected_profit_inr)} highlight />
                  <PlanStat icon={Droplets} label="Duration" value={`${chosen.duration_days ?? "—"} days`} />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl border p-4">
                    <p className="mb-2 flex items-center gap-2 text-sm font-medium">
                      <Sparkles className="h-4 w-4 text-leaf-600" /> Why this crop?
                    </p>
                    <p className="text-sm text-muted-foreground">{chosen.why_recommended}</p>
                  </div>
                  <div className="rounded-xl border p-4">
                    <p className="mb-2 flex items-center gap-2 text-sm font-medium">
                      <ShieldAlert className="h-4 w-4 text-amber-500" /> Key risks
                    </p>
                    {chosen.risks.length > 0 ? (
                      <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                        {chosen.risks.map((r) => <li key={r}>{r}</li>)}
                      </ul>
                    ) : (
                      <p className="text-sm text-muted-foreground">No specific risks flagged.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border p-4">
                  <p className="mb-2 text-sm font-medium">What to do next</p>
                  <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                    <li>Confirm the crop suits your soil and water — consult your local agriculture officer if unsure.</li>
                    <li>Use the <Link className="text-leaf-600 underline" href="/dashboard/profit">profit calculator</Link> with your real input costs.</li>
                    <li>Check <Link className="text-leaf-600 underline" href="/dashboard/market">market prices</Link> for this crop before planting.</li>
                    <li>Plan planting within the {form.season} season window for {form.location || "your area"}.</li>
                  </ul>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button asChild>
                    <Link href="/dashboard/profit">Calculate profit</Link>
                  </Button>
                  <Button variant="outline" asChild>
                    <Link href="/dashboard/market">Check market</Link>
                  </Button>
                  <Button variant="outline" asChild>
                    <Link href="/dashboard/disease">Analyze crop</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function PlanStat({
  icon: Icon,
  label,
  value,
  highlight,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className={cn("rounded-xl border p-3 text-center", highlight && "border-leaf-200 bg-leaf-50")}>
      <Icon className={cn("mx-auto mb-1 h-4 w-4", highlight ? "text-leaf-700" : "text-muted-foreground")} />
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("text-sm font-bold", highlight && "text-leaf-700")}>{value}</p>
    </div>
  );
}
