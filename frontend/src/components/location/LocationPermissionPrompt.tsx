"use client";

/**
 * Location gate for the dashboard (prompt §3: weather, mandi prices, vendors
 * and crop advice all follow the farm's location).
 *
 * On every dashboard open it refreshes to the device's *present* position and
 * saves it, so the displayed location tracks where the farmer actually is
 * rather than a stale fix from an earlier session. It renders a small card
 * while looking (only when no location is known yet), and an actionable card
 * when the browser blocks or can't provide a fix.
 */
import * as React from "react";
import Link from "next/link";
import { Crosshair, Loader2, MapPin, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useProfile } from "@/hooks/use-api";
import { useDetectLocation } from "@/hooks/use-detect-location";
import { useToast } from "@/hooks/use-toast";

/** Dismissal lasts the browser session, so a fresh open asks again. */
const DISMISS_KEY = "agrigpt-location-prompt-dismissed";

type Status = "checking" | "hidden" | "locating" | "saved" | "warn";

export function LocationPermissionPrompt() {
  const { data: profile, isLoading: profileLoading } = useProfile();
  const { detect, busy, error, denied } = useDetectLocation();
  const { toast } = useToast();
  const [status, setStatus] = React.useState<Status>("checking");

  // A location is known once the profile has coordinates or a place name.
  const hasSavedLocation = Boolean(
    profile?.latitude != null ||
      profile?.longitude != null ||
      profile?.village ||
      profile?.district ||
      profile?.state
  );

  const detectRef = React.useRef(detect);
  detectRef.current = detect;

  const askedRef = React.useRef(false);
  React.useEffect(() => {
    if (askedRef.current || profileLoading) return;
    askedRef.current = true;

    if (typeof sessionStorage !== "undefined" && sessionStorage.getItem(DISMISS_KEY) === "1") {
      setStatus("hidden");
      return;
    }

    // Refresh to the present position once per session. When a location is
    // already known this is silent, so reopening the app isn't noisy.
    const silent = hasSavedLocation;
    void (async () => {
      if (!silent) setStatus("locating");
      const fix = await detectRef.current();
      if (fix) {
        setStatus("saved");
        if (!silent) {
          toast({
            title: "Location saved 📍",
            description: "Weather, prices and nearby vendors now follow your farm.",
            variant: "success",
          });
        }
      } else {
        setStatus("warn");
      }
    })();
  }, [profileLoading, hasSavedLocation, toast]);

  const dismiss = () => {
    if (typeof sessionStorage !== "undefined") sessionStorage.setItem(DISMISS_KEY, "1");
    setStatus("hidden");
  };

  const retry = async () => {
    const fix = await detectRef.current();
    setStatus(fix ? "saved" : "warn");
  };

  if (status === "checking" || status === "hidden" || status === "saved") return null;

  const looking = status === "locating";

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-start gap-3 rounded-xl border border-leaf-300 bg-leaf-50 p-3"
    >
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-leaf-100 text-leaf-700">
        {looking ? <Loader2 className="h-5 w-5 animate-spin" /> : <MapPin className="h-5 w-5" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">
          {looking ? "Finding your current location…" : denied ? "Location is blocked" : "We couldn’t read your location"}
        </p>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {looking
            ? "Weather, mandi prices and crop advice follow your farm location."
            : denied
            ? "Allow location in your browser so weather, prices and nearby vendors match where you are."
            : error || "Allow location, or set your district and state manually."}
        </p>
        {!looking && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" onClick={retry} disabled={busy} className="gap-1.5">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Crosshair className="h-4 w-4" />}
              {denied ? "Try again" : "Use my location"}
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/dashboard/plan">Set manually</Link>
            </Button>
          </div>
        )}
      </div>
      {!looking && (
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss location prompt"
          className="shrink-0 rounded-full p-1.5 text-muted-foreground hover:bg-leaf-100"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
