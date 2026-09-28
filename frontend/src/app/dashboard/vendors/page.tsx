"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { Crosshair, Loader2, MapPin, Navigation, Phone, Store } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useNearbyVendors, useSaveLocation } from "@/hooks/use-api";
import { apiErrorMessage } from "@/lib/api";
import type { FarmerLocation, VendorItem } from "@/hooks/use-api";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

const LeafletMap = dynamic(() => import("@/components/location/VendorMap"), {
  ssr: false,
  loading: () => <Skeleton className="h-80 w-full" />,
});

const CATEGORIES = [
  { key: "", label: "All" },
  { key: "seeds", label: "Seeds" },
  { key: "fertilizer", label: "Fertilizer" },
  { key: "pesticide", label: "Crop Protection" },
  { key: "equipment", label: "Equipment" },
  { key: "produce_buyer", label: "Crop Buyers" },
];

const CATEGORY_VARIANT: Record<
  string,
  "success" | "warning" | "danger" | "secondary" | "default"
> = {
  seeds: "success",
  fertilizer: "warning",
  pesticide: "danger",
  equipment: "secondary",
  produce_buyer: "default",
};

const RADII = [10, 25, 50, 100, 200];

export default function VendorsPage() {
  const [category, setCategory] = React.useState("");
  const [crop, setCrop] = React.useState("");
  const [radius, setRadius] = React.useState(50); // spec D4: default 50 km
  const [locating, setLocating] = React.useState(false);
  const { toast } = useToast();
  const { data, isLoading } = useNearbyVendors({
    category: category || undefined,
    crop: crop || undefined,
    radius_km: radius,
  });

  const you: FarmerLocation | null = data?.location ?? null;
  // Items are strictly within the chosen radius, except up to 3 tagged
  // `beyond_radius` (nearest fallbacks when the radius had nothing).
  const allItems: VendorItem[] = data?.items ?? [];
  const items: VendorItem[] = allItems.filter((v) => !v.beyond_radius);
  const beyond: VendorItem[] = allItems.filter((v) => v.beyond_radius);
  const nothingWithin = items.length === 0 && allItems.length === 0;

  // [📍 Use My Location] — explicit opt-in (permission UX per prompt §12).
  // Saves exact coordinates to the profile so vendors, weather and market all
  // switch to GPS precision. Manual map pin remains available on the profile.
  const saveLocation = useSaveLocation();
  const useGps = () => {
    if (!navigator.geolocation) {
      toast({
        title: "Location not available",
        description: "This device doesn't support location. Save a map pin on the profile page instead.",
        variant: "destructive",
      });
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (p) => {
        try {
          await saveLocation.mutateAsync({
            latitude: p.coords.latitude,
            longitude: p.coords.longitude,
            source: "gps",
          });
          toast({ title: "Using your current location 📍", description: "Vendors re-sorted by true distance from your farm.", variant: "success" });
        } catch (e) {
          toast({ title: "Could not save location", description: apiErrorMessage(e), variant: "destructive" });
        } finally {
          setLocating(false);
        }
      },
      (err) => {
        setLocating(false);
        if (err.code === err.PERMISSION_DENIED) {
          toast({
            title: "Location permission is blocked",
            description:
              "Tap the 🔒 icon (or ⋮ menu) next to the website address → Permissions → Location → Allow, then tap Use My Location again.",
            variant: "destructive",
          });
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          toast({
            title: "Couldn't determine your position",
            description: "Move to an open area and try again, or save a map pin on the profile page.",
            variant: "destructive",
          });
        } else {
          toast({
            title: "Getting your location took too long",
            description: "Try again outdoors, or save a map pin on the profile page.",
            variant: "destructive",
          });
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Vendors &amp; Buyers Near You</h1>
        <p className="text-sm text-muted-foreground">
          {you ? (
            <>
              📍 Around <span className="font-medium">{you.label}</span> ·{" "}
              {you.precision === "gps"
                ? "your exact location"
                : you.precision === "map_pin"
                  ? "your saved pin"
                  : "approximate (district)"}{" "}
              · sorted by distance
            </>
          ) : (
            "Agri-input shops and produce buyers sorted by distance from your farm"
          )}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="outline"
          onClick={useGps}
          disabled={locating || saveLocation.isPending}
          className="min-h-[44px] shrink-0 gap-1.5"
        >
          {locating || saveLocation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Crosshair className="h-4 w-4" />
          )}
          📍 Use My Location
        </Button>
        <Tabs value={category} onValueChange={setCategory}>
          <TabsList>
            {CATEGORIES.map((c) => (
              <TabsTrigger key={c.key} value={c.key}>
                {c.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <input
          value={crop}
          onChange={(e) => setCrop(e.target.value)}
          placeholder="your crop (e.g. cotton)"
          className="h-9 w-44 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
        <div className="flex items-center gap-1.5">
          {RADII.map((r) => (
            <button
              key={r}
              onClick={() => setRadius(r)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                radius === r
                  ? "border-leaf-600 bg-leaf-600 text-white"
                  : "border-input text-muted-foreground hover:border-leaf-400 hover:text-foreground"
              )}
            >
              {r} km
            </button>
          ))}
        </div>
      </div>

      {you && items.length > 0 && (
        <p className="-mt-3 text-xs text-muted-foreground">
          Showing <span className="font-medium">{items.length} vendors</span> within{" "}
          <span className="font-medium">{radius} km</span> of {you.label}.
        </p>
      )}

      {isLoading && <Skeleton className="h-80 w-full" />}

      {data && nothingWithin && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No vendors found within <span className="font-medium text-foreground">{radius} km</span> of{" "}
            {you?.label ?? "your location"} for this filter. Try the{' '}
            <button onClick={() => setCategory("")} className="text-leaf-600 underline">All</button>{' '}
            tab or a bigger radius.
          </CardContent>
        </Card>
      )}

      {data && items.length === 0 && beyond.length > 0 && (
        <Card className="border-amber-500/25 bg-amber-50">
          <CardContent className="py-4 text-sm">
            Nothing within <span className="font-medium">{radius} km</span> for this filter. Nearest matches:
          </CardContent>
        </Card>
      )}

      {data && allItems.length > 0 && (
        <>
          {you && (
            <LeafletMap
              center={{ lat: you.latitude, lng: you.longitude }}
              you={you}
              points={allItems}
              radiusKm={radius}
            />
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {allItems.map((v) => (
              <Card key={v.id} className={v.matches_crop ? "ring-1 ring-leaf-500" : ""}>
                <CardContent className="pt-6">
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-leaf-100 text-leaf-700">
                        <Store className="h-4 w-4" />
                      </span>
                      <div>
                        <p className="font-medium leading-tight">{v.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {v.city ?? v.district} · {v.raw_distance_km} km away
                        </p>
                      </div>
                    </div>
                    <Badge variant={CATEGORY_VARIANT[v.category] ?? "secondary"}>
                      {v.category.replace("_", " ")}
                    </Badge>
                  </div>
                  {v.source === "osm" && (
                    <Badge variant="secondary" className="mb-2 text-[10px]">
                      LIVE nearby listing
                    </Badge>
                  )}
                  {v.beyond_radius && (
                    <Badge variant="warning" className="mb-2 text-[10px]">
                      beyond {radius} km — nearest match
                    </Badge>
                  )}
                  {v.description && (
                    <p className="text-sm text-muted-foreground">{v.description}</p>
                  )}
                  {v.matches_crop && (
                    <Badge variant="success" className="mt-2 text-[10px]">
                      works with your crop
                    </Badge>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {v.phone && (
                      <Button size="sm" variant="outline" className="gap-1.5" asChild>
                        <a href={`tel:${v.phone.replace(/\s/g, "")}`}>
                          <Phone className="h-3.5 w-3.5" /> Call
                        </a>
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" className="gap-1.5" asChild>
                      <a
                        href={`https://www.google.com/maps/dir/?api=1&destination=${v.latitude},${v.longitude}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Navigation className="h-3.5 w-3.5" /> Directions
                      </a>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}

      {data && data.location.precision === "district" && (
        <Card className="border-amber-500/25 bg-amber-50">
          <CardContent className="py-4 text-sm">
            Currently using district-level location — distances are approximate. Tap{" "}
            <span className="font-medium">📍 Use My Location</span> above for GPS-accurate results, or save a
            map pin on the{" "}
            <a href="/dashboard/profile" className="font-medium text-leaf-700 underline">
              profile page
            </a>
            . <MapPin className="ml-1 inline h-4 w-4" />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
