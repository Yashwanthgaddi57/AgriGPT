"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { Crosshair, Loader2, MapPin, Search } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

interface Props {
  initial?: { latitude: number; longitude: number } | null;
  onSave: (payload: {
    latitude: number;
    longitude: number;
    source: "gps" | "map_pin";
    village?: string | null;
    district?: string | null;
    state?: string | null;
  }) => Promise<void> | void;
  saving?: boolean;
}

/** Map picker: click to drop a pin, use GPS, or search a place. */
export function LocationPicker({ initial, onSave, saving }: Props) {
  const mapRef = React.useRef<HTMLDivElement>(null);
  const map = React.useRef<L.Map | null>(null);
  const marker = React.useRef<L.Marker | null>(null);
  const [pos, setPos] = React.useState<{ lat: number; lng: number } | null>(
    initial ? { lat: initial.latitude, lng: initial.longitude } : null
  );
  const [label, setLabel] = React.useState<string>("");
  const [address, setAddress] = React.useState<{
    village?: string | null;
    district?: string | null;
    state?: string | null;
  }>({});
  const [search, setSearch] = React.useState("");
  const [busy, setBusy] = React.useState<"map" | "gps" | "search" | null>(null);
  const [error, setError] = React.useState("");

  // Init map once
  React.useEffect(() => {
    if (!mapRef.current || map.current) return;
    const start = pos ?? { lat: 20.5937, lng: 78.9629 }; // India center
    const m = L.map(mapRef.current).setView([start.lat, start.lng], pos ? 13 : 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
    }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => dropPin(e.latlng.lat, e.latlng.lng));
    map.current = m;
    if (pos) dropPin(pos.lat, pos.lng);
    return () => {
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const icon = L.divIcon({
    className: "",
    html: `<div style="font-size:32px;line-height:1;filter:drop-shadow(0 2px 2px rgba(0,0,0,.3))">📍</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 30],
  });

  async function describe(lat: number, lng: number) {
    try {
      const res = await api.get(`/geo/reverse?lat=${lat}&lon=${lng}`);
      const d = res.data || {};
      setAddress({ village: d.village ?? null, district: d.district ?? null, state: d.state ?? null });
      setLabel(d.display_name ? String(d.display_name).split(",").slice(0, 3).join(", ") : `${lat.toFixed(4)}, ${lng.toFixed(4)}`);
    } catch {
      setAddress({});
      setLabel(`${lat.toFixed(4)}, ${lng.toFixed(4)}`);
    }
  }

  function dropPin(lat: number, lng: number) {
    setPos({ lat, lng });
    const m = map.current;
    if (!m) return;
    if (marker.current) marker.current.setLatLng([lat, lng]);
    else marker.current = L.marker([lat, lng], { icon }).addTo(m);
    describe(lat, lng);
  }

  const useGps = () => {
    setError("");
    if (!navigator.geolocation) {
      setError("Geolocation is not supported on this device.");
      return;
    }
    setBusy("gps");
    navigator.geolocation.getCurrentPosition(
      (p) => {
        const { latitude, longitude } = p.coords;
        map.current?.setView([latitude, longitude], 15);
        dropPin(latitude, longitude);
        setBusy(null);
        save(latitude, longitude, "gps");
      },
      () => {
        setError("Could not get GPS fix. Drop a pin on the map instead.");
        setBusy(null);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const doSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!search.trim()) return;
    setBusy("search");
    setError("");
    try {
      const res = await api.get(`/geo/search?q=${encodeURIComponent(search)}`);
      const d = res.data;
      if (d?.latitude != null) {
        map.current?.setView([d.latitude, d.longitude], 13);
        dropPin(d.latitude, d.longitude);
      } else {
        setError("Place not found. Try a nearby town.");
      }
    } catch {
      setError("Search failed. Try again.");
    } finally {
      setBusy(null);
    }
  };

  const save = async (
    lat: number,
    lng: number,
    source: "gps" | "map_pin",
    addr = address
  ) => {
    setBusy("map");
    try {
      await onSave({
        latitude: lat,
        longitude: lng,
        source,
        village: addr.village ?? null,
        district: addr.district ?? null,
        state: addr.state ?? null,
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" onClick={useGps} disabled={busy !== null} className="gap-1.5">
          {busy === "gps" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Crosshair className="h-4 w-4" />}
          Use my GPS
        </Button>
        <form onSubmit={doSearch} className="flex flex-1 gap-2">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search village / town / district…"
            className="h-8"
          />
          <Button type="submit" size="sm" variant="outline" disabled={busy !== null}>
            {busy === "search" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          </Button>
        </form>
      </div>

      <div
        ref={mapRef}
        className="h-64 w-full rounded-lg border"
        style={{ zIndex: 0 }}
      />

      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <MapPin className="h-4 w-4 text-leaf-600" />
          {pos ? label || `${pos.lat.toFixed(4)}, ${pos.lng.toFixed(4)}` : "Tap the map to drop your farm pin"}
        </span>
        <Button
          type="button"
          size="sm"
          disabled={!pos || busy !== null}
          onClick={() => pos && save(pos.lat, pos.lng, "map_pin")}
        >
          {busy === "map" ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save this location"}
        </Button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
