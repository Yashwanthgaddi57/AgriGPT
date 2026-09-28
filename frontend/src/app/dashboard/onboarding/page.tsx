"use client";

/**
 * Farm-first onboarding (Phase 5): after signup the farmer lands here instead
 * of a generic chat. Short steps, skippable optional fields, one save at the
 * end (profile PATCH + optional farm record + planting date + language).
 */
import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle2, Loader2 } from "lucide-react";

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
import { GeoAutocomplete } from "@/components/location/GeoAutocomplete";
import { useSavePlantingDate, useUpdateProfile } from "@/hooks/use-api";
import { suggestDistricts, suggestStates } from "@/lib/india-geo";
import { apiErrorMessage } from "@/lib/api";
import { trackEvent, EVENTS } from "@/lib/events";
import { useLang, type Lang } from "@/lib/i18n";
import { useToast } from "@/hooks/use-toast";

const SOILS = ["black", "alluvial", "loamy", "clay", "sandy", "silt", "laterite", "red", "peaty", "unknown"];
const WATER = ["rainfed", "canal", "borewell", "well", "river", "pond", "none"];

const LANGUAGES: { value: Lang; label: string }[] = [
  { value: "en", label: "English" },
  { value: "te", label: "తెలుగు (Telugu)" },
  { value: "hi", label: "हिंदी (Hindi)" },
  { value: "ta", label: "தமிழ் (Tamil)" },
  { value: "kn", label: "ಕನ್ನಡ (Kannada)" },
  { value: "mr", label: "मराठी (Marathi)" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { toast } = useToast();
  const { setLang } = useLang();
  const updateProfile = useUpdateProfile();
  const savePlanting = useSavePlantingDate();

  const [step, setStep] = React.useState(1);
  const [saving, setSaving] = React.useState(false);
  const [form, setForm] = React.useState({
    state: "",
    district: "",
    farm_size_acres: "",
    soil_type: "unknown",
    water_availability: "rainfed",
    crop: "",
    planting_date: "",
    budget_inr: "",
    language: "en" as Lang,
  });

  const total = 4;
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));

  const finish = async () => {
    setSaving(true);
    try {
      await updateProfile.mutateAsync({
        state: form.state || undefined,
        district: form.district || undefined,
        farm_size_acres: form.farm_size_acres ? Number(form.farm_size_acres) : undefined,
        soil_type: form.soil_type,
        water_availability: form.water_availability,
        language: form.language,
      });
      setLang(form.language);
      trackEvent(EVENTS.farmProfileCompleted, { language: form.language });
      if (form.crop && form.planting_date) {
        await savePlanting.mutateAsync({
          farm_id: null,
          crop: form.crop,
          planting_date: form.planting_date,
        });
      }
      toast({ title: "Your farm profile is ready", variant: "success" });
      router.push("/dashboard");
    } catch (e) {
      toast({ title: "Could not save", description: apiErrorMessage(e), variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="text-center">
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Welcome to AgriGPT</h1>
        <p className="mt-1 text-sm text-muted-foreground">Let&apos;s understand your farm.</p>
      </div>

      {/* Progress */}
      <div className="flex items-center gap-2">
        {Array.from({ length: total }).map((_, i) => (
          <span
            key={i}
            className={`h-1.5 flex-1 rounded-full ${step > i ? "bg-leaf-500" : "bg-muted"}`}
            aria-hidden
          />
        ))}
        <span className="text-xs text-muted-foreground">{step}/{total}</span>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {step === 1 && "Where is your farm?"}
            {step === 2 && "How big is it, and what's the soil like?"}
            {step === 3 && "What about water and crop?"}
            {step === 4 && "Language"}
          </CardTitle>
          <CardDescription>Optional fields can be skipped.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 1 && (
            <>
              <div className="space-y-2">
                <Label>State</Label>
                <GeoAutocomplete
                  ariaLabel="State"
                  placeholder="e.g. Andhra Pradesh"
                  value={form.state}
                  onChange={(v) => set({ state: v })}
                  suggestions={(q) => suggestStates(q)}
                />
              </div>
              <div className="space-y-2">
                <Label>District</Label>
                <GeoAutocomplete
                  ariaLabel="District"
                  placeholder="e.g. Guntur"
                  value={form.district}
                  onChange={(v) => set({ district: v })}
                  suggestions={(q) => suggestDistricts(q, form.state || undefined)}
                />
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <div className="space-y-2">
                <Label>Farm size (acres)</Label>
                <Input type="number" step="0.1" min="0" placeholder="e.g. 3.2" value={form.farm_size_acres} onChange={(e) => set({ farm_size_acres: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="soil-type">Soil type</Label>
                <Select value={form.soil_type} onValueChange={(v) => set({ soil_type: v })}>
                  <SelectTrigger id="soil-type"><SelectValue placeholder="Select soil type" /></SelectTrigger>
                  <SelectContent>
                    {SOILS.map((s) => (
                      <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <div className="space-y-2">
                <Label htmlFor="water-availability">Water / irrigation</Label>
                <Select value={form.water_availability} onValueChange={(v) => set({ water_availability: v })}>
                  <SelectTrigger id="water-availability"><SelectValue placeholder="Select water availability" /></SelectTrigger>
                  <SelectContent>
                    {WATER.map((w) => (
                      <SelectItem key={w} value={w} className="capitalize">{w}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Current crop (optional)</Label>
                  <Input placeholder="e.g. chilli" value={form.crop} onChange={(e) => set({ crop: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>Planting date (optional)</Label>
                  <Input
                    type="date"
                    max={new Date().toISOString().slice(0, 10)}
                    value={form.planting_date}
                    onChange={(e) => set({ planting_date: e.target.value })}
                  />
                </div>
              </div>
            </>
          )}

          {step === 4 && (
            <div className="space-y-2">
              <Label htmlFor="preferred-language">Preferred language (AI will answer in it)</Label>
              <Select value={form.language} onValueChange={(v) => set({ language: v as Lang })}>
                <SelectTrigger id="preferred-language"><SelectValue placeholder="Select language" /></SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map((l) => (
                    <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex items-center justify-between gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => (step === 1 ? router.push("/dashboard") : setStep(step - 1))}
              disabled={saving}
            >
              <ArrowLeft className="mr-1 h-4 w-4" /> {step === 1 ? "Skip" : "Back"}
            </Button>
            {step < total ? (
              <Button onClick={() => setStep(step + 1)} className="gap-2">
                Next <ArrowRight className="h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={finish} disabled={saving} className="gap-2">
                {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                <CheckCircle2 className="h-4 w-4" /> Finish
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
