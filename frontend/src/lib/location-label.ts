/**
 * One display string for the farmer's current location, shared by the dashboard
 * home and the dashboard shell header/sidebar.
 *
 * Precedence: a saved GPS / map-pin fix (`precision !== "district"`) wins, then
 * any place names the resolver returned, then the profile, then the farm record.
 * Empty strings are ignored: the API returns `""` (not null) for a missing
 * district, which is why the dashboard's Location card used to render blank.
 */
export interface LocationLike {
  precision?: string | null;
  label?: string | null;
  village?: string | null;
  district?: string | null;
  state?: string | null;
}

function joinParts(parts: (string | null | undefined)[]): string {
  return parts
    .map((p) => (p ?? "").trim())
    .filter((p) => p.length > 0)
    .join(", ");
}

export function formatLocationLabel(
  resolved?: LocationLike | null,
  profile?: LocationLike | null,
  farm?: LocationLike | null
): string {
  const fixedLabel =
    resolved && resolved.precision !== "district" ? (resolved.label ?? "").trim() : "";
  return (
    fixedLabel ||
    joinParts([resolved?.village, resolved?.district, resolved?.state]) ||
    joinParts([profile?.village, profile?.district, profile?.state]) ||
    joinParts([farm?.village, farm?.district, farm?.state])
  );
}
