"use client";

/**
 * Nearby Agri Services — maps seed/pesticide/fertilizer shops, input stores,
 * equipment dealers, markets, cattle-feed shops, FPOs and agri services near
 * the farmer, using the AgriGPT directory + OpenStreetMap (no API key).
 *
 * Mobile: search → filters → map → result list. Desktop: list left, map right.
 * Nothing is invented — a field the source lacks (rating, phone, hours) is
 * simply not shown.
 */
import * as React from "react";
import dynamic from "next/dynamic";
import {
  Crosshair,
  ExternalLink,
  Globe,
  Loader2,
  MapPin,
  Navigation,
  Phone,
  Search,
  SlidersHorizontal,
  Star,
  Store,
  WifiOff,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { categoryMeta } from "@/components/location/VendorMap";
import {
  useAgriNearby,
  useMyLocation,
  searchPlace,
  type AgriServiceItem,
  type AgriSort,
} from "@/hooks/use-api";
import { useDetectLocation } from "@/hooks/use-detect-location";
import { useToast } from "@/hooks/use-toast";
import { formatDistance, phoneHref, safeExternalUrl } from "@/lib/agri-services";
import { cn } from "@/lib/utils";

const AgriMap = dynamic(() => import("@/components/location/VendorMap"), {
  ssr: false,
  loading: () => <Skeleton className="h-[320px] w-full rounded-lg lg:h-[560px]" />,
});

// Farmer-friendly category chips (spec §4 / §16).
const FILTERS: { key: string; label: string; emoji: string }[] = [
  { key: "seeds", label: "Seeds", emoji: "🌱" },
  { key: "pesticide", label: "Pesticides", emoji: "🧪" },
  { key: "fertilizer", label: "Fertilizers", emoji: "🌾" },
  { key: "agri_store", label: "Agri Stores", emoji: "🏪" },
  { key: "hardware", label: "Hardware", emoji: "🔧" },
  { key: "market", label: "Markets", emoji: "🥬" },
  { key: "equipment", label: "Equipment", emoji: "🚜" },
  { key: "feed", label: "Animal Feed", emoji: "🐄" },
  { key: "fpo", label: "FPO", emoji: "👨‍🌾" },
  { key: "services", label: "Services", emoji: "🚚" },
  { key: "produce_buyer", label: "Crop Buyers", emoji: "💰" },
];

const RADII = [5, 10, 25, 50, 100];
const SORTS: { key: AgriSort; label: string }[] = [
  { key: "nearest", label: "Nearest" },
  { key: "rating", label: "Highest rated" },
  { key: "name", label: "Name" },
];

const CACHE_KEY = "agrigpt-agri-nearby-cache";

function useDebounced<T>(value: T, delay = 400): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function NearbyAgriServicesPage() {
  const { toast } = useToast();
  const { data: myLocation } = useMyLocation();
  const detect = useDetectLocation();

  const [place, setPlace] = React.useState<{ lat: number; lng: number; label: string } | null>(null);
  const [search, setSearch] = React.useState("");
  const [radius, setRadius] = React.useState(25);
  const [categories, setCategories] = React.useState<string[]>([]);
  const [sort, setSort] = React.useState<AgriSort>("nearest");
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<AgriServiceItem | null>(null);
  const [suggestions, setSuggestions] = React.useState<{ label: string; lat: number; lng: number }[]>([]);
  const [offline, setOffline] = React.useState(false);
  const [cached, setCached] = React.useState<{ results: AgriServiceItem[]; at: string; radius: number } | null>(null);

  const debouncedSearch = useDebounced(search, 450);

  // Coordinates: an explicitly searched place wins, else the saved farm location.
  const lat = place?.lat ?? myLocation?.latitude ?? null;
  const lng = place?.lng ?? myLocation?.longitude ?? null;

  const { data, isLoading, isFetching, error, refetch } = useAgriNearby({
    lat,
    lng,
    radius_km: radius,
    categories,
    search: search.trim() ? debouncedSearch || undefined : undefined,
    sort,
  });

  // ---- Offline / error handling (§19, §22) -------------------------------
  React.useEffect(() => {
    const sync = () => setOffline(typeof navigator !== "undefined" && !navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  React.useEffect(() => {
    if (!data) return;
    try {
      localStorage.setItem(
        CACHE_KEY,
        JSON.stringify({ results: data.results, at: new Date().toISOString(), radius: data.radius_km })
      );
    } catch {
      /* storage full / disabled — cache is a nicety, never required */
    }
  }, [data]);

  React.useEffect(() => {
    if (data || !error) {
      if (data) setCached(null);
      return;
    }
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (raw) setCached(JSON.parse(raw));
    } catch {
      /* ignore malformed cache */
    }
  }, [data, error]);

  // ---- Place search (village / town / district) -------------------------
  React.useEffect(() => {
    const q = debouncedSearch.trim();
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    let cancelled = false;
    searchPlace(q)
      .then((d) => {
        if (cancelled) return;
        if (d?.latitude != null && d?.longitude != null) {
          setSuggestions([{ label: d.name || q, lat: d.latitude, lng: d.longitude }]);
        } else {
          setSuggestions([]);
        }
      })
      .catch(() => !cancelled && setSuggestions([]));
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch]);

  const results = data?.results ?? [];
  const shown = data ? results : (cached?.results ?? []);
  const you = data?.location ?? null;
  const detailWebsite = detail ? safeExternalUrl(detail.website) : null;

  const toggleCategory = (key: string) =>
    setCategories((prev) => (prev.includes(key) ? prev.filter((c) => c !== key) : [...prev, key]));

  const usedCached = !data && !!cached;
  const empty = !!data && results.length === 0;

  const useGps = async () => {
    const fix = await detect.detect();
    if (fix) {
      setPlace(null); // fall back to the saved (freshly updated) location
      setSelectedId(null);
      toast({ title: "Using your current location 📍", description: "Re-sorted by distance from you.", variant: "success" });
    } else {
      toast({
        title: "Could not read your location",
        description: "Allow location access, or search your village, town or district.",
        variant: "destructive",
      });
    }
  };

  const clearSearch = () => {
    setSearch("");
    setPlace(null);
    setSuggestions([]);
  };

  return (
    <div className="space-y-4">
      {/* ---------- Header ---------- */}
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">
          Nearby Agri Services
        </h1>
        <p className="text-sm text-muted-foreground">
          {you ? (
            <>
              📍 Around <span className="font-medium">{you.label}</span> ·{" "}
              {you.precision === "gps"
                ? "your exact location"
                : you.precision === "map_pin"
                  ? "your saved pin"
                  : you.precision === "search"
                    ? "your search"
                    : "approximate (district)"}{" "}
              · nearest first
            </>
          ) : (
            "Find seed, pesticide and fertilizer shops, markets, equipment and more near you"
          )}
        </p>
      </div>

      {/* ---------- Offline / error banners ---------- */}
      {offline && (
        <Card className="border-amber-500/30 bg-amber-50">
          <CardContent className="flex items-start gap-2 py-3 text-sm">
            <WifiOff className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <span>
              You are offline. Showing your last available nearby data.
              {cached?.at && (
                <> Last updated: {new Date(cached.at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}.</>
              )}
            </span>
          </CardContent>
        </Card>
      )}
      {!offline && error && !usedCached && (
        <Card className="border-red-500/30 bg-red-50">
          <CardContent className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
            <span className="text-red-700">
              We couldn&apos;t load nearby services. The server may be busy.
            </span>
            <Button size="sm" variant="outline" onClick={() => refetch()} className="min-h-[40px]">
              Try again
            </Button>
          </CardContent>
        </Card>
      )}
      {!offline && usedCached && (
        <Card className="border-amber-500/30 bg-amber-50">
          <CardContent className="py-3 text-sm">
            Showing your last available nearby data
            {cached?.at &&
              ` (last updated ${new Date(cached.at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })})`}
            . Pull to refresh when you are back online.
          </CardContent>
        </Card>
      )}

      {/* ---------- Search + location ---------- */}
      <div className="space-y-2">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search village, town, district or service…"
              aria-label="Search village, town, district or agricultural service"
              className="h-11 pl-9 pr-9"
            />
            {search && (
              <button
                type="button"
                onClick={clearSearch}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-muted-foreground hover:bg-accent"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <Button
            variant="outline"
            onClick={useGps}
            disabled={detect.busy}
            className="min-h-[44px] gap-1.5 sm:w-auto"
          >
            {detect.busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Crosshair className="h-4 w-4" />}
            Use my location
          </Button>
        </div>

        {suggestions.length > 0 && (
          <ul className="overflow-hidden rounded-lg border bg-card">
            {suggestions.map((s) => (
              <li key={`${s.label}-${s.lat}`}>
                <button
                  type="button"
                  onClick={() => {
                    setPlace({ lat: s.lat, lng: s.lng, label: s.label });
                    setSearch("");
                    setSuggestions([]);
                    setSelectedId(null);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm hover:bg-accent"
                >
                  <MapPin className="h-4 w-4 shrink-0 text-leaf-600" />
                  <span className="truncate">Move map to {s.label}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {place && (
          <p className="text-xs text-muted-foreground">
            Searching around <span className="font-medium">{place.label}</span> —{" "}
            <button onClick={() => setPlace(null)} className="text-leaf-700 underline">
              back to my location
            </button>
          </p>
        )}
      </div>

      {/* ---------- Category chips (multi-select) ---------- */}
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <FilterChip active={categories.length === 0} onClick={() => setCategories([])}>
          All
        </FilterChip>
        {FILTERS.map((f) => (
          <FilterChip key={f.key} active={categories.includes(f.key)} onClick={() => toggleCategory(f.key)}>
            <span aria-hidden>{f.emoji}</span> {f.label}
          </FilterChip>
        ))}
      </div>

      {/* ---------- Radius + sort ---------- */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
          <SlidersHorizontal className="h-3.5 w-3.5" /> Within
        </span>
        <div className="flex flex-wrap gap-1.5">
          {RADII.map((r) => (
            <FilterChip key={r} active={radius === r} onClick={() => setRadius(r)}>
              {r} km
            </FilterChip>
          ))}
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as AgriSort)}
          aria-label="Sort nearby services"
          className="ml-auto h-9 rounded-md border border-input bg-background px-2 text-sm"
        >
          {SORTS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {/* ---------- Map + results (desktop: list left, map right) ---------- */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,380px)_1fr]">
        <div className="order-2 lg:order-1">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold">
              Nearby {data ? `(${results.length})` : usedCached ? "(cached)" : ""}
            </h2>
            {isFetching && !isLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          </div>

          {isLoading && (
            <div className="space-y-2">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          )}

          {empty && (
            <Card>
              <CardContent className="space-y-3 py-8 text-center text-sm text-muted-foreground">
                <p>
                  {data?.note ?? `No agricultural services found within ${radius} km.`}
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="min-h-[40px]"
                    onClick={() => setRadius(RADII[RADII.indexOf(radius) + 1] ?? 100)}
                  >
                    Search a larger area
                  </Button>
                  {categories.length > 0 && (
                    <Button size="sm" variant="ghost" className="min-h-[40px]" onClick={() => setCategories([])}>
                      Clear filters
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {!isLoading && shown.length > 0 && (
            <div className="space-y-2 lg:max-h-[560px] lg:overflow-y-auto lg:pr-1">
              {shown.map((v) => (
                <ServiceCard
                  key={v.id}
                  item={v}
                  selected={v.id === selectedId}
                  onSelect={() => setSelectedId(v.id)}
                  onDetails={() => setDetail(v)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="order-1 lg:order-2">
          {you || place ? (
            <AgriMap
              center={{ lat: (place?.lat ?? you?.latitude) as number, lng: (place?.lng ?? you?.longitude) as number }}
              you={
                you ?? {
                  latitude: place!.lat,
                  longitude: place!.lng,
                  precision: "search",
                  label: place!.label,
                  village: null,
                  district: null,
                  state: null,
                }
              }
              points={shown}
              radiusKm={radius}
              selectedId={selectedId}
              onSelect={setSelectedId}
              className="h-[320px] w-full rounded-lg border lg:h-[560px]"
            />
          ) : (
            <Skeleton className="h-[320px] w-full rounded-lg lg:h-[560px]" />
          )}
        </div>
      </div>

      {/* ---------- Details modal (§6) ---------- */}
      <Dialog open={!!detail} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-w-md">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-start gap-2 pr-6">
                  <span aria-hidden>{categoryMeta(detail.category).emoji}</span>
                  <span>{detail.name}</span>
                </DialogTitle>
                <DialogDescription>
                  {categoryMeta(detail.category).label}
                  {detail.subcategory ? ` · ${detail.subcategory.replace(/_/g, " ")}` : ""}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3 text-sm">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span className="inline-flex items-center gap-1 font-medium">
                    <MapPin className="h-4 w-4 text-leaf-600" /> {formatDistance(detail.distance_km)} away
                  </span>
                  {detail.rating != null ? (
                    <span className="inline-flex items-center gap-1">
                      <Star className="h-4 w-4 text-amber-500" /> {detail.rating.toFixed(1)}
                      {detail.review_count != null && (
                        <span className="text-muted-foreground">({detail.review_count} reviews)</span>
                      )}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">No rating available</span>
                  )}
                </div>

                {detail.description && <p className="text-muted-foreground">{detail.description}</p>}

                <dl className="space-y-1.5">
                  <DetailRow label="Address">
                    {[detail.address, detail.village, detail.city, detail.district, detail.state, detail.pincode]
                      .filter(Boolean)
                      .join(", ") || "—"}
                  </DetailRow>
                  {detail.phone && <DetailRow label="Phone">{detail.phone}</DetailRow>}
                  {detail.website && <DetailRow label="Website">{detail.website}</DetailRow>}
                  {detail.opening_hours && <DetailRow label="Opening hours">{detail.opening_hours}</DetailRow>}
                  <DetailRow label="Coordinates">
                    {detail.latitude.toFixed(5)}, {detail.longitude.toFixed(5)}
                  </DetailRow>
                  {detail.crops.length > 0 && <DetailRow label="Crops">{detail.crops.join(", ")}</DetailRow>}
                </dl>

                <p className="text-xs text-muted-foreground">
                  Data source: <span className="font-medium">{detail.source}</span>
                  {detail.last_updated && (
                    <>
                      {" · "}Last updated:{" "}
                      {new Date(detail.last_updated).toLocaleString("en-IN", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </>
                  )}
                  {detail.rating == null && " · ratings are not available for this source"}
                </p>

                <div className="flex flex-wrap gap-2 pt-1">
                  <Button asChild className="min-h-[44px] gap-1.5">
                    <a
                      href={`https://www.google.com/maps/dir/?api=1&destination=${detail.latitude},${detail.longitude}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Navigation className="h-4 w-4" /> Directions
                    </a>
                  </Button>
                  {detail.phone && (
                    <Button asChild variant="outline" className="min-h-[44px] gap-1.5">
                      <a href={`tel:${detail.phone.replace(/[^\d+]/g, "")}`}>
                        <Phone className="h-4 w-4" /> Call
                      </a>
                    </Button>
                  )}
                  {detailWebsite && (
                    <Button asChild variant="outline" className="min-h-[44px] gap-1.5">
                      {/* Only http(s) links are rendered — never javascript:/data: URLs. */}
                      <a href={detailWebsite} target="_blank" rel="noreferrer noopener">
                        <Globe className="h-4 w-4" /> Website
                      </a>
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "flex min-h-[36px] shrink-0 items-center gap-1 whitespace-nowrap rounded-full border px-3 text-xs font-medium transition-colors",
        active
          ? "border-leaf-600 bg-leaf-600 text-white"
          : "border-input bg-card text-muted-foreground hover:border-leaf-400 hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-28 shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 flex-1 break-words">{children}</dd>
    </div>
  );
}

function ServiceCard({
  item,
  selected,
  onSelect,
  onDetails,
}: {
  item: AgriServiceItem;
  selected: boolean;
  onSelect: () => void;
  onDetails: () => void;
}) {
  const meta = categoryMeta(item.category);
  const address = [item.address, item.city, item.district, item.state].filter(Boolean).join(", ");
  const websiteHref = safeExternalUrl(item.website);
  const callHref = phoneHref(item.phone);
  return (
    <Card
      className={cn("cursor-pointer transition-shadow hover:shadow-md", selected && "ring-1 ring-leaf-500")}
      onClick={onSelect}
    >
      <CardContent className="space-y-2 pt-4">
        <div className="flex items-start gap-2">
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-leaf-100 text-base"
            aria-hidden
          >
            {meta.emoji}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium leading-tight" title={item.name}>
              {item.name}
            </p>
            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{formatDistance(item.distance_km)}</span>
              <span aria-hidden>·</span>
              <span>{meta.label}</span>
              {item.rating != null && (
                <>
                  <span aria-hidden>·</span>
                  <span className="inline-flex items-center gap-0.5">
                    <Star className="h-3 w-3 text-amber-500" /> {item.rating.toFixed(1)}
                  </span>
                </>
              )}
            </p>
          </div>
          {item.matches_crop && (
            <Badge variant="success" className="shrink-0 text-[10px]">
              your crop
            </Badge>
          )}
        </div>

        {address && <p className="line-clamp-2 text-xs text-muted-foreground">{address}</p>}

        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" className="min-h-[38px] gap-1.5">
            <a
              href={`https://www.google.com/maps/dir/?api=1&destination=${item.latitude},${item.longitude}`}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
            >
              <Navigation className="h-3.5 w-3.5" /> Directions
            </a>
          </Button>
          {callHref && (
            <Button asChild size="sm" variant="outline" className="min-h-[38px] gap-1.5">
              <a href={callHref} onClick={(e) => e.stopPropagation()}>
                <Phone className="h-3.5 w-3.5" /> Call
              </a>
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="min-h-[38px] gap-1.5"
            onClick={(e) => {
              e.stopPropagation();
              onDetails();
            }}
          >
            <Store className="h-3.5 w-3.5" /> Details
          </Button>
          {websiteHref && (
            <Button asChild size="sm" variant="ghost" className="min-h-[38px] gap-1.5">
              <a
                href={websiteHref}
                target="_blank"
                rel="noreferrer noopener"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="h-3.5 w-3.5" /> Website
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
