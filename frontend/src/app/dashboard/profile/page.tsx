"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useSaveLocation } from "@/hooks/use-api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useFarms,
  useProfile,
  useSavePlantingDate,
  useUpdateProfile,
} from "@/hooks/use-api";
import { apiErrorMessage } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const SOILS = ["black", "alluvial", "loamy", "clay", "sandy", "silt", "laterite", "red", "peaty", "unknown"];
const WATER = ["rainfed", "canal", "borewell", "well", "river", "pond", "none"];

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  phone: z.string().optional(),
  state: z.string().optional(),
  district: z.string().optional(),
  village: z.string().optional(),
  farm_size_acres: z.coerce.number().min(0),
  soil_type: z.string(),
  water_availability: z.string(),
  language: z.string(),
});
type FormData = z.infer<typeof schema>;

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "te", label: "తెలుగు (Telugu)" },
  { value: "hi", label: "हिंदी (Hindi)" },
  { value: "ta", label: "தமிழ் (Tamil)" },
  { value: "kn", label: "ಕನ್ನಡ (Kannada)" },
  { value: "mr", label: "मराठी (Marathi)" },
];

// Leaflet touches `window` on import — load browser-side only.
const LocationPicker = dynamic(
  () => import("@/components/location/LocationPicker").then((m) => m.LocationPicker),
  { ssr: false, loading: () => <div className="h-64 w-full animate-pulse rounded-lg border bg-muted" /> }
);

export default function ProfilePage() {
  const { data: profile } = useProfile();
  const update = useUpdateProfile();
  const saveLocation = useSaveLocation();
  const savePlanting = useSavePlantingDate();
  const { data: farms } = useFarms();
  const { toast } = useToast();
  const [soil, setSoil] = React.useState("unknown");
  const [water, setWater] = React.useState("rainfed");
  const [language, setLanguage] = React.useState("en");
  const [plantingCrop, setPlantingCrop] = React.useState("");
  const [plantingDate, setPlantingDate] = React.useState("");

  // Pre-fill the planting card from the farm that has a current crop.
  React.useEffect(() => {
    const withCrop = (farms ?? []).find((f) => f.current_crop);
    if (withCrop) {
      setPlantingCrop(withCrop.current_crop ?? "");
      setPlantingDate(withCrop.planting_date ?? "");
    }
  }, [farms]);

  React.useEffect(() => {
    if (profile) {
      setSoil(profile.soil_type);
      setWater(profile.water_availability);
      setLanguage(profile.language ?? "en");
      reset({
        name: profile.name,
        phone: profile.phone ?? "",
        state: profile.state ?? "",
        district: profile.district ?? "",
        village: profile.village ?? "",
        farm_size_acres: profile.farm_size_acres,
        language: profile.language ?? "en",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile]);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      await update.mutateAsync({ ...data, soil_type: soil, water_availability: water, language });
      toast({ title: "Profile updated", variant: "success" });
    } catch (e) {
      toast({ title: "Update failed", description: apiErrorMessage(e), variant: "destructive" });
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Profile</h1>
        <p className="text-sm text-muted-foreground">
          Keep farm details current — the AI uses them for every recommendation.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Exact farm location</CardTitle>
          <CardDescription>
            {profile?.latitude != null ? (
              <span>
                Saved pin: {Number(profile.latitude).toFixed(4)}, {Number(profile.longitude).toFixed(4)} — weather,
                mandi prices and vendors use this exact spot.
              </span>
            ) : (
              <span>
                Drop a pin or use GPS. Weather, market prices and nearby vendors become exact for
                your farm.
              </span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <LocationPicker
            initial={
              profile?.latitude != null
                ? { latitude: Number(profile.latitude), longitude: Number(profile.longitude) }
                : null
            }
            saving={saveLocation.isPending}
            onSave={async (payload) => {
              await saveLocation.mutateAsync(payload);
              toast({ title: "Location saved", description: "Weather, prices and vendors now use your exact spot.", variant: "success" });
            }}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Farm & contact details</CardTitle>
          <CardDescription>{profile?.email}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Full name</Label>
              <Input {...register("name")} />
              {errors.name && <p className="text-xs text-red-600">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label>Phone</Label>
              <Input {...register("phone")} />
            </div>
            <div className="space-y-2">
              <Label>State</Label>
              <Input {...register("state")} />
            </div>
            <div className="space-y-2">
              <Label>District</Label>
              <Input {...register("district")} />
            </div>
            <div className="space-y-2">
              <Label>Village</Label>
              <Input {...register("village")} />
            </div>
            <div className="space-y-2">
              <Label>Farm size (acres)</Label>
              <Input type="number" step="0.1" {...register("farm_size_acres")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="soil-type">Soil type</Label>
              <Select value={soil} onValueChange={setSoil}>
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
              <Select value={water} onValueChange={setWater}>
                <SelectTrigger id="water-availability"><SelectValue placeholder="Select water availability" /></SelectTrigger>
                <SelectContent>
                  {WATER.map((w) => (
                    <SelectItem key={w} value={w} className="capitalize">{w}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="preferred-language">Preferred language (AI answers)</Label>
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger id="preferred-language"><SelectValue placeholder="Select language" /></SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map((l) => (
                    <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="sm:col-span-2 space-y-3 rounded-xl border p-4">
              <div>
                <Label className="text-sm font-medium">Current crop & planting date</Label>
                <p className="text-xs text-muted-foreground">
                  When recorded, the copilot tailors advice to your crop&apos;s age
                  (e.g. &quot;your chilli is ~42 days old&quot;).
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Crop</Label>
                  <Input
                    placeholder="e.g. chilli"
                    value={plantingCrop}
                    onChange={(e) => setPlantingCrop(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Planting date</Label>
                  <Input
                    type="date"
                    max={new Date().toISOString().slice(0, 10)}
                    value={plantingDate}
                    onChange={(e) => setPlantingDate(e.target.value)}
                  />
                </div>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!plantingCrop || !plantingDate || savePlanting.isPending}
                onClick={async () => {
                  try {
                    const withCrop = (farms ?? []).find((f) => f.current_crop);
                    await savePlanting.mutateAsync({
                      farm_id: withCrop?.id ?? null,
                      crop: plantingCrop,
                      planting_date: plantingDate,
                    });
                    toast({ title: "Planting details saved", variant: "success" });
                  } catch (e) {
                    toast({ title: "Save failed", description: apiErrorMessage(e), variant: "destructive" });
                  }
                }}
              >
                {savePlanting.isPending && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
                Save planting details
              </Button>
            </div>
            <div className="sm:col-span-2">
              <Button type="submit" disabled={isSubmitting || update.isPending} className="gap-2">
                {isSubmitting || update.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Save changes
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
