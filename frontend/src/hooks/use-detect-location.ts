"use client";

/**
 * Read the device's *present* position, reverse-geocode it and save it.
 *
 * The fix is always fresh (`maximumAge: 0`) — a cached position can report a
 * place the farmer has already left. The coordinates are authoritative: the
 * reverse-geocoded village/district/state are sent together (null when the
 * geocoder can't tell), so a previously stored but stale place name is replaced
 * instead of silently kept. That mismatch was why the dashboard showed a state
 * that did not match the saved coordinates.
 */
import * as React from "react";

import { api, apiErrorMessage } from "@/lib/api";
import { useSaveLocation } from "@/hooks/use-api";

export interface DetectedLocation {
  latitude: number;
  longitude: number;
  village: string | null;
  district: string | null;
  state: string | null;
}

function positionErrorReason(err: GeolocationPositionError): { denied: boolean; message: string } {
  switch (err?.code) {
    case 1: // PERMISSION_DENIED
      return { denied: true, message: "Location permission is blocked in your browser." };
    case 2: // POSITION_UNAVAILABLE
      return { denied: false, message: "Your device couldn't get a location fix." };
    case 3: // TIMEOUT
      return { denied: false, message: "Getting your location timed out." };
    default:
      return { denied: false, message: "Could not read your location." };
  }
}

export function useDetectLocation() {
  const saveLocation = useSaveLocation();
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [denied, setDenied] = React.useState(false);

  const detect = React.useCallback(async (): Promise<DetectedLocation | null> => {
    setError(null);
    setDenied(false);

    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setError("This device doesn't support location.");
      return null;
    }

    setBusy(true);
    try {
      let pos: GeolocationPosition;
      try {
        pos = await new Promise<GeolocationPosition>((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0,
          })
        );
      } catch (e) {
        const reason = positionErrorReason(e as GeolocationPositionError);
        setDenied(reason.denied);
        setError(reason.message);
        return null;
      }

      const { latitude, longitude } = pos.coords;

      // Resolve the coordinates to a place name; coordinates alone still work.
      let village: string | null = null;
      let district: string | null = null;
      let state: string | null = null;
      try {
        const rev = (await api.get(`/geo/reverse?lat=${latitude}&lon=${longitude}`)).data as {
          village?: string | null;
          district?: string | null;
          state?: string | null;
        };
        village = rev?.village ?? null;
        district = rev?.district ?? null;
        state = rev?.state ?? null;
      } catch {
        /* best-effort */
      }

      try {
        await saveLocation.mutateAsync({
          latitude,
          longitude,
          source: "gps",
          village,
          district,
          state,
        });
      } catch (e) {
        setError(apiErrorMessage(e));
        return null;
      }

      return { latitude, longitude, village, district, state };
    } finally {
      setBusy(false);
    }
  }, [saveLocation]);

  return { detect, busy: busy || saveLocation.isPending, error, denied };
}
