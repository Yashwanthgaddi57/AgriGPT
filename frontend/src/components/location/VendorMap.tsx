"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import * as React from "react";

import type { FarmerLocation, VendorItem } from "@/hooks/use-api";

interface Props {
  center: { lat: number; lng: number };
  you: FarmerLocation;
  points: VendorItem[];
  /** Search radius in km — drawn as a circle so "10 km means 10 km" is visible. */
  radiusKm?: number;
}

/** Escape untrusted text (OSM crowd-sourced vendor data) before it goes
 *  into Leaflet popup/tooltip HTML. Strips any HTML-special characters so a
 *  spoofed vendor name like `<img src=x onerror=...>` renders as text. */
function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c] as string);
}

const COLORS: Record<string, string> = {
  seeds: "#16a34a",
  fertilizer: "#d97706",
  pesticide: "#dc2626",
  equipment: "#0284c7",
  produce_buyer: "#7c3aed",
};

export default function VendorMap({ you, points, radiusKm }: Props) {
  const ref = React.useRef<HTMLDivElement>(null);
  const map = React.useRef<L.Map | null>(null);
  const layer = React.useRef<L.LayerGroup | null>(null);
  const circle = React.useRef<L.Circle | null>(null);

  React.useEffect(() => {
    if (!ref.current || map.current) return;
    const m = L.map(ref.current, { scrollWheelZoom: false }).setView(
      [you.latitude, you.longitude],
      9
    );
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
    }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      circle.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    const m = map.current;
    const lg = layer.current;
    if (!m || !lg) return;
    lg.clearLayers();

    L.marker([you.latitude, you.longitude], {
      icon: L.divIcon({
        className: "",
        html: `<div style="font-size:30px;line-height:1;filter:drop-shadow(0 2px 2px rgba(0,0,0,.3))">📍</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 28],
      }),
    })
      .bindTooltip(`You: ${you.label}`, { direction: "top" })
      .addTo(lg);

    // Honest radius: draw the search circle so the farmer can see that "10 km"
    // really means 10 km. Points beyond the circle are tagged in the list UI.
    if (radiusKm && radiusKm > 0) {
      if (circle.current) {
        circle.current.setLatLng([you.latitude, you.longitude]).setRadius(radiusKm * 1000);
      } else {
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
    } else if (circle.current) {
      lg.removeLayer(circle.current);
      circle.current = null;
    }

    const bounds: L.LatLngExpression[] = [[you.latitude, you.longitude]];
    for (const v of points) {
      const color = COLORS[v.category] ?? "#16a34a";
      L.circleMarker([v.latitude, v.longitude], {
        radius: 8,
        color,
        fillColor: color,
        fillOpacity: 0.85,
        weight: 2,
      })
        .bindTooltip(`${escapeHtml(v.name)} · ${v.raw_distance_km} km`, { direction: "top" })
        .bindPopup(
          `<b>${escapeHtml(v.name)}</b><br/>${escapeHtml(v.category.replace("_", " "))}${
            v.phone ? `<br/>${escapeHtml(v.phone)}` : ""
          }`
        )
        .addTo(lg);
      bounds.push([v.latitude, v.longitude]);
    }
    // Fit to the radius circle when present so it is fully visible; otherwise
    // fit to the vendor points as before.
    if (radiusKm && radiusKm > 0 && circle.current) {
      m.fitBounds(circle.current.getBounds().pad(0.1));
    } else if (points.length) {
      m.fitBounds(L.latLngBounds(bounds).pad(0.15));
    }
  }, [you, points, radiusKm]);

  return <div ref={ref} className="h-80 w-full rounded-lg border" style={{ zIndex: 0 }} />;
}
