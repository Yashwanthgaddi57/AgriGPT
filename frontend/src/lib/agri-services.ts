/**
 * Small pure helpers for the Nearby Agri Services map.
 * Kept separate from the page so they can be unit-tested directly.
 */

/** `500 m` · `1.2 km` · `8.4 km` — farmers read distances, not coordinates. */
export function formatDistance(km: number | null | undefined): string {
  if (km == null || !Number.isFinite(km)) return "";
  if (km < 1) return `${Math.round((km * 1000) / 100) * 100} m`;
  return `${km.toFixed(1)} km`;
}

/**
 * Absolute http(s) URL or null.
 *
 * Business data is crowd-sourced (OpenStreetMap), so a `website` tag can be
 * anything. This blocks `javascript:`, `data:` and other non-web schemes from
 * ever reaching an anchor href.
 */
export function safeExternalUrl(raw: string | null | undefined): string | null {
  const value = (raw ?? "").trim();
  if (!value) return null;
  try {
    const url = new URL(/^[a-z][a-z0-9+.-]*:/i.test(value) ? value : `https://${value}`);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

/** Digits plus a leading `+` — safe to interpolate into a `tel:` link. */
export function phoneHref(phone: string | null | undefined): string | null {
  const digits = (phone ?? "").replace(/[^\d+]/g, "");
  return digits.length >= 6 ? `tel:${digits}` : null;
}
