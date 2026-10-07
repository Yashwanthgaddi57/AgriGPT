"use client";

/**
 * Nearby Agri Services map (Leaflet + OpenStreetMap tiles — no API key).
 *
 * Renders one marker per business, coloured/emoji-tagged by category, with
 * lightweight grid clustering so dense cities never paint hundreds of markers.
 * Clicking a marker selects the matching card in the results list.
 */
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import * as React from "react";

import type { AgriServiceItem, FarmerLocation, VendorItem } from "@/hooks/use-api";

/** Category -> marker emoji, colour and farmer-friendly label. */
export const CATEGORY_MARKERS: Record<string, { emoji: string; color: string; label: string }> = {
  seeds: { emoji: "🌱", color: "#16a34a", label: "Seeds" },
  pesticide: { emoji: "🧪", color: "#dc2626", label: "Pesticides" },
  fertilizer: { emoji: "🌾", color: "#d97706", label: "Fertilizers" },
  agri_store: { emoji: "🏪", color: "#0d9488", label: "Agri Stores" },
  hardware: { emoji: "🔧", color: "#64748b", label: "Hardware & Supplies" },
  equipment: { emoji: "🚜", color: "#0284c7", label: "Equipment" },
  market: { emoji: "🥬", color: "#7c3aed", label: "Markets" },
  feed: { emoji: "🐄", color: "#b45309", label: "Animal Feed" },
  fpo: { emoji: "👨‍🌾", color: "#15803d", label: "FPOs" },
  services: { emoji: "🚚", color: "#475569", label: "Agri Services" },
  produce_buyer: { emoji: "💰", color: "#9d174d", label: "Crop Buyers" },
};

export function categoryMeta(category: string) {
  return CATEGORY_MARKERS[category] ?? { emoji: "📍", color: "#16a34a", label: category.replace("_", " ") };
}

/** Minimal shape both the new agri-services items and legacy vendor items share. */
type Point = Pick<
  AgriServiceItem,
  "id" | "name" | "category" | "latitude" | "longitude" | "distance_km"
> & { phone?: string | null };

interface Props {
  center: { lat: number; lng: number };
  you: FarmerLocation;
  points: (AgriServiceItem | VendorItem)[];
  /** Search radius in km — drawn as a circle so "10 km means 10 km" is visible. */
  radiusKm?: number;
  /** Highlighted business (kept in sync with the results list). */
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  className?: string;
}

/** Escape untrusted text (crowd-sourced OSM data) before it reaches Leaflet
 *  popup/tooltip HTML, so a spoofed name cannot inject markup. */
function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

/** Degrees per clustering cell at a given zoom — grows as you zoom out. */
function cellSizeFor(zoom: number): number {
  return 180 / Math.pow(2, Math.max(2, zoom) + 2);
}

export default function VendorMap({ center, you, points, radiusKm, selectedId, onSelect, className }: Props) {
  const ref = React.useRef<HTMLDivElement>(null);
  const map = React.useRef<L.Map | null>(null);
  const layer = React.useRef<L.LayerGroup | null>(null);
  const circle = React.useRef<L.Circle | null>(null);
  const [zoom, setZoom] = React.useState(9);
  // Keep the latest click handler without re-binding every marker.
  const selectRef = React.useRef(onSelect);
  selectRef.current = onSelect;

  React.useEffect(() => {
    if (!ref.current || map.current) return;
    const m = L.map(ref.current, { scrollWheelZoom: false }).setView([center.lat, center.lng], 9);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
    }).addTo(m);
    m.on("zoomend", () => setZoom(m.getZoom()));
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    setZoom(m.getZoom());
    return () => {
      m.remove();
      map.current = null;
      layer.current = null;
      circle.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recentre when the searched/selected location changes.
  React.useEffect(() => {
    map.current?.setView([center.lat, center.lng], map.current.getZoom());
  }, [center.lat, center.lng]);

  React.useEffect(() => {
    const m = map.current;
    const lg = layer.current;
    if (!m || !lg) return;
    lg.clearLayers();
    circle.current = null;

    // "You are here"
    L.marker([you.latitude, you.longitude], {
      icon: L.divIcon({
        className: "",
        html: `<div style="font-size:28px;line-height:1;filter:drop-shadow(0 2px 2px rgba(0,0,0,.3))">📍</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 26],
      }),
      zIndexOffset: 1000,
    })
      .bindTooltip(`You: ${escapeHtml(you.label)}`, { direction: "top" })
      .addTo(lg);

    if (radiusKm && radiusKm > 0) {
      circle.current = L.circle([you.latitude, you.longitude], {
        radius: radiusKm * 1000,
        color: "#16a34a",
        weight: 1.5,
        opacity: 0.6,
        fillColor: "#16a34a",
        fillOpacity: 0.05,
        dashArray: "6 6",
      }).addTo(lg);
    }

    const cell = cellSizeFor(zoom);

    // Grid-cluster so a city with many shops stays readable.
    const cells = new Map<string, Point[]>();
    for (const p of points as Point[]) {
      const key = `${Math.floor(p.latitude / cell)}:${Math.floor(p.longitude / cell)}`;
      const bucket = cells.get(key);
      if (bucket) bucket.push(p);
      else cells.set(key, [p]);
    }

    const bounds: L.LatLngExpression[] = [[you.latitude, you.longitude]];

    for (const bucket of cells.values()) {
      if (bucket.length > 1) {
        const lat = bucket.reduce((s, p) => s + p.latitude, 0) / bucket.length;
        const lng = bucket.reduce((s, p) => s + p.longitude, 0) / bucket.length;
        L.marker([lat, lng], {
          icon: L.divIcon({
            className: "",
            html: `<div style="display:flex;align-items:center;justify-content:center;min-width:34px;height:34px;padding:0 6px;border-radius:9999px;background:#16a34a;color:#fff;font:600 13px/1 system-ui;box-shadow:0 2px 6px rgba(0,0,0,.3)">${bucket.length}</div>`,
            iconSize: [34, 34],
            iconAnchor: [17, 17],
          }),
        })
          .bindTooltip(`${bucket.length} services here — tap to zoom`, { direction: "top" })
          .on("click", () => m.setView([lat, lng], Math.min(m.getZoom() + 2, 17)))
          .addTo(lg);
        bounds.push([lat, lng]);
        continue;
      }

      const p = bucket[0];
      const meta = categoryMeta(p.category);
      const isSelected = p.id === selectedId;
      L.marker([p.latitude, p.longitude], {
        icon: L.divIcon({
          className: "",
          html: `<div style="display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:9999px;background:#fff;border:2px solid ${meta.color};font-size:15px;box-shadow:0 1px 4px rgba(0,0,0,.3)${
            isSelected ? ";outline:3px solid " + meta.color + ";outline-offset:1px" : ""
          }">${meta.emoji}</div>`,
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        }),
        zIndexOffset: isSelected ? 500 : 0,
      })
        .bindTooltip(`${escapeHtml(p.name)} · ${p.distance_km} km`, { direction: "top" })
        .bindPopup(
          `<b>${escapeHtml(p.name)}</b><br/>${escapeHtml(meta.label)}<br/>${p.distance_km} km away${
            p.phone ? `<br/>${escapeHtml(p.phone)}` : ""
          }`
        )
        .on("click", () => selectRef.current?.(p.id))
        .addTo(lg);
      bounds.push([p.latitude, p.longitude]);
    }

    if (radiusKm && radiusKm > 0 && circle.current) {
      m.fitBounds(circle.current.getBounds().pad(0.1));
    } else if (points.length) {
      m.fitBounds(L.latLngBounds(bounds).pad(0.15));
    }
  }, [you, points, radiusKm, selectedId, zoom]);

  return <div ref={ref} className={className ?? "h-80 w-full rounded-lg border"} style={{ zIndex: 0 }} />;
}
