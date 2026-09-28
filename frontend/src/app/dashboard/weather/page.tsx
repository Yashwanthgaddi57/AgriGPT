"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CloudRain, CloudSun, Crosshair, Droplets, Loader2, MapPin, Snowflake, Sun, Wind } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyLocation, useProfile, useSaveLocation, useWeather } from "@/hooks/use-api";
import { apiErrorMessage } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const ACTION_VARIANT: Record<string, "success" | "warning" | "destructive" | "secondary"> = {
  plant_now: "success",
  irrigate: "warning",
  delay_planting: "secondary",
  harvest_now: "destructive",
  none: "secondary",
};

export default function WeatherPage() {
  const { data: profile } = useProfile();
  const [location, setLocation] = React.useState<string | undefined>(undefined);
  const [input, setInput] = React.useState("");
  const [locating, setLocating] = React.useState(false);
  const { data, isLoading, refetch, isRefetching } = useWeather(location);
  const { toast } = useToast();
  const saveLocation = useSaveLocation();
  const { data: myLoc } = useMyLocation();

  // Once the user picks a location themselves (typed or GPS), stop auto-filling
  // from the profile — otherwise the effect fights the GPS result.
  const manualPick = React.useRef(false);

  React.useEffect(() => {
    if (!manualPick.current && profile?.district && location === undefined) {
      setLocation(profile.district);
    }
  }, [profile, location]);

  // Human-readable reason for a failed GPS fix (browsers block re-prompting
  // after a denial, so we must teach the user how to re-enable it).
  const gpsError = (err: GeolocationPositionError) => {
    if (err.code === err.PERMISSION_DENIED) {
      return {
        title: "Location permission is blocked",
        description:
          "Tap the 🔒 icon (or ⋮ menu) next to the website address → Permissions → Location → Allow, then tap Use My Location again.",
      };
    }
    if (err.code === err.POSITION_UNAVAILABLE) {
      return {
        title: "Couldn't determine your position",
        description: "Move to an open area and try again, or type your town / district below.",
      };
    }
    return {
      title: "Getting your location took too long",
      description: "Try again outdoors, or type your town / district below.",
    };
  };

  // [Use My Location] — opt-in GPS (never mandatory): saves exact coordinates
  // to the profile; the backend then uses them for the forecast automatically.
  const useGps = () => {
    if (!navigator.geolocation) {
      toast({
        title: "Location not available",
        description: "This device or browser doesn't support location. Type your town or district instead.",
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
          // Switch the page to the saved-coordinates forecast (backend uses
          // exact coords automatically once they exist on the profile).
          manualPick.current = true;
          setLocation(undefined);
          setInput("");
          await refetch();
          toast({ title: "Using your current location 📍", description: "Forecast updated for your exact spot.", variant: "success" });
        } catch (e) {
          toast({ title: "Could not save location", description: apiErrorMessage(e), variant: "destructive" });
        } finally {
          setLocating(false);
        }
      },
      (err) => {
        setLocating(false);
        toast({ ...gpsError(err), variant: "destructive" });
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    );
  };

  const search = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      manualPick.current = true;
      setLocation(input.trim());
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div>
          <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Weather</h1>
          <p className="inline-block flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
            <MapPin className="h-4 w-4 shrink-0 text-leaf-600" aria-hidden />
            <span className="font-medium text-foreground">
              {myLoc?.label || data?.location || "…"}
            </span>
            {myLoc && (myLoc.precision === "gps" || myLoc.precision === "map_pin") ? (
              <Badge variant="success" className="text-[10px]">
                📍 Your exact location
              </Badge>
            ) : myLoc ? (
              <Badge variant="warning" className="text-[10px]">
                Approximate (district)
              </Badge>
            ) : null}
          </p>
        </div>
        <form onSubmit={search} className="flex flex-wrap gap-2">
          <Button
            type="button"
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
          <Input
            placeholder="Change location…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="min-w-0 flex-1 sm:w-48 sm:flex-none"
            aria-label="Location"
          />
          <Button type="submit" variant="outline" className="shrink-0">Update</Button>
        </form>
      </div>

      {data && (
        <>
          {/* AI action banner */}
          <Card className="border-sky-200 bg-gradient-to-r from-sky-50 to-leaf-50 dark:from-sky-950/30 dark:to-leaf-950/20">
            <CardContent className="flex flex-wrap items-start gap-4 py-5">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-sky-100 text-sky-600">
                <CloudSun className="h-6 w-6" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={ACTION_VARIANT[data.action ?? "none"] ?? "secondary"}>
                    {(data.action ?? "none").replace(/_/g, " ").toUpperCase()}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    AI agro-advisory · updated {new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => refetch()}
                    disabled={isRefetching}
                  >
                    {isRefetching ? "Refreshing…" : "Refresh"}
                  </Button>
                </div>
                <p className="mt-2 text-sm leading-relaxed">{data.ai_recommendation ?? "No advisory available."}</p>
              </div>
            </CardContent>
          </Card>

          {/* Alerts */}
          {data.alerts.length > 0 && (
            <div className="space-y-2">
              {data.alerts.map((a) => (
                <Card key={a} className="border-amber-500/25 bg-amber-50">
                  <CardContent className="flex items-center gap-3 py-3">
                    <Snowflake className="h-4 w-4 shrink-0 text-amber-600" />
                    <p className="text-sm">{a}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Day cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
            {data.days.map((d) => {
              const Icon = d.condition.toLowerCase().includes("rain") || d.condition.toLowerCase().includes("drizzle")
                ? CloudRain
                : d.condition.toLowerCase().includes("clear")
                ? Sun
                : CloudSun;
              return (
                <Card key={d.date}>
                  <CardContent className="flex flex-col items-center gap-1.5 pt-6 text-center">
                    <p className="text-xs font-medium text-muted-foreground">
                      {new Date(d.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric" })}
                    </p>
                    <Icon className="h-7 w-7 text-sky-500" />
                    <p className="text-lg font-bold">{d.temp_c ?? "—"}°C</p>
                    <p className="text-[11px] leading-tight text-muted-foreground">{d.condition}</p>
                    <div className="mt-1 flex w-full justify-between text-[11px] text-muted-foreground">
                      <span className="flex items-center gap-0.5"><Droplets className="h-3 w-3" />{d.humidity ?? "—"}%</span>
                      <span className="flex items-center gap-0.5"><Wind className="h-3 w-3" />{d.wind_kph ?? "—"} km/h</span>
                    </div>
                    <div className="w-full rounded bg-sky-50 py-0.5 text-[11px] text-sky-700 dark:bg-sky-900/40">
                      {d.precip_probability ?? 0}% rain · {d.precip_mm ?? 0} mm
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Charts */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Temperature & rain</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart
                    data={data.days.map((d) => ({
                      day: new Date(d.date).toLocaleDateString("en-IN", { weekday: "short" }),
                      temp: d.temp_c,
                      rain_mm: d.precip_mm,
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="day" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis yAxisId="t" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis yAxisId="r" orientation="right" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip />
                    <Line yAxisId="t" type="monotone" dataKey="temp" name="Temp °C" stroke="#f97316" strokeWidth={2} dot />
                    <Line yAxisId="r" type="monotone" dataKey="rain_mm" name="Rain mm" stroke="#0ea5e9" strokeWidth={2} dot />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Humidity & wind</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart
                    data={data.days.map((d) => ({
                      day: new Date(d.date).toLocaleDateString("en-IN", { weekday: "short" }),
                      humidity: d.humidity,
                      wind: d.wind_kph,
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="day" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip />
                    <Bar dataKey="humidity" name="Humidity %" fill="#0ea5e9" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="wind" name="Wind km/h" fill="#a37e5b" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {!data && !isLoading && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Enter a location above to load the forecast.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
