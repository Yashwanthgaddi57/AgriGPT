# Vendor Range Selection & Location-True Vendor Discovery — Spec

**Short name:** vendor-range
**Status:** Draft — decisions confirmed via product interview, 2026-09-22
**Feature area:** Vendors & Buyers Near Me (`/dashboard/vendors`)
**Related code:**
- `backend/app/services/vendor_service.py` (merge/rank logic)
- `backend/app/services/osm_vendors.py` (live OSM discovery)
- `backend/app/services/seed_geo_data.py` (mandi/vendor directory)
- `backend/app/routers/geo.py` (`/geo/vendors`, `/geo/mandis`, `/geo/location`)
- `frontend/src/app/dashboard/vendors/page.tsx`
- `frontend/src/components/location/VendorMap.tsx`
- `frontend/src/hooks/use-api.ts` (`useNearbyVendors`, `useSaveLocation`)

---

## 1. Problem Statement

The Vendors page promises "agri-input shops and produce buyers near you," but coverage is inconsistent across India. Verified live during this interview:

| Location | Current behavior |
|---|---|
| Nashik | Good — 5 directory vendors within 8 km + OSM shops |
| Lucknow | 2 live OSM shops found; directory contributed nothing under 150 km |
| Warangal | Directory only (0.3–11 km); OSM had no agri-tagged shops within 45 km |
| **Chennai** | **Zero local results.** Nearest is Kaveri Delta Paddy Buyers at 283 km; everything else 284–911 km away. No mandi seeded either (Koyambedu missing) |

Root causes:
1. The curated vendor directory is sparse (20 vendors nationwide) with no Chennai/Tamil Nadu coverage.
2. Live OSM discovery is the only location-true source, but it is unreliable under load (watched it fail on all 3 mirrors with 504s/timeouts for 30+ seconds) and Indian OSM agri-tagging is thin in rural/peri-urban areas.
3. There is no farmer-controlled search radius — results silently include vendors hundreds of km away, which is not actionable.

**Goal:** a farmer in ANY location — including Chennai — gets a predictable, honest, range-controlled vendor experience.

---

## 2. Product Decisions (from interview)

| # | Decision | Choice |
|---|---|---|
| D1 | Coverage guarantee | Farmer picks a search range; results must respect it |
| D2 | Applies to | All users, all locations — not a Chennai-specific fix |
| D3 | Range control lives | On the Vendors page (per-visit override, NOT saved to profile) |
| D4 | Default radius | 50 km |
| D5 | Range scope | **Vendors page only.** Mandis/weather keep current behavior |
| D6 | Data source for vendors | **Live OSM discovery is the primary source** (curated directory stays as baseline/fallback) |
| D7 | OSM outage handling | Show directory/mandi results instantly; fetch OSM in background and **inject into the page without reload** when ready |
| D8 | Zero-results experience | Guided alternatives: honest empty state + "nearest wholesale market is X (N km)" suggestion + "Ask the Copilot" action |
| D9 | Data quality | Show OSM data as-is; missing phone = no Call button; occasional category mislabeling accepted |
| D10 | Freshness | 24h cache **+ visible Refresh button** that forces a live re-query |
| D11 | Wholesale market data for guided alternatives | **Both**: seed major hub mandis nationwide (incl. Koyambedu) AND layer OSM marketplaces on top |
| D12 | Language | English only for now (profile language field exists for future work) |
| D13 | Mobile UX | Standard responsive — cards stack, map full-width. No special mobile mode |
| D14 | Category trust | Trust the OSM category as-is (no AI re-categorization) |

---

## 3. Detailed Requirements

### 3.1 Range Selection (Vendors page)

- **UI:** radius chips or slider on the Vendors page: 10 / 25 / 50 / 100 / 200 km, default **50 km** (D3, D4).
- Range is a **query parameter to the API**, not a persisted profile field (D3).
- Changing the range:
  - Refetches `/geo/vendors` with the new radius.
  - Adjusts the map: draw a **radius circle** centered on the farmer's pin; fit bounds to results ∪ circle.
  - Updates the transparency line: *"Showing vendors within 50 km of {location} — found N."* (search-stats requirement).
- Range selection resets to 50 km on page reload (it is a session control, not a preference).

### 3.2 API Changes

`GET /api/v1/geo/vendors` gains parameters:

```
category?: seeds|fertilizer|pesticide|equipment|produce_buyer   (existing)
crop?: string                                                    (existing)
radius_km?: int = 50                                             (NEW, clamp 5–300)
refresh?: bool = false                                           (NEW, forces OSM re-query)
```

Response additions:

```jsonc
{
  "location": { ... },            // existing
  "radius_km": 50,                // NEW — echo the applied radius
  "osm_status": "live" | "cached" | "unavailable" | "timeout",  // NEW
  "total": 7,
  "items": [ ... ]                // existing VendorOut shape (source field already present)
}
```

Behavior:
- `radius_km` filters **directory** results (`raw_distance_km <= radius_km`) and sets the OSM discovery radius (`min(radius_km, 45) * 1000` meters — Overpass reliability ceiling).
- **Progressive widening (internal, when range yields zero results):** if nothing is found within the requested radius, the backend widens once to the next step (max 2 widening attempts) and reports the effective radius actually used via `radius_km` echo — the UI then says "nothing within 50 km; showing results within 150 km."
- `refresh=true` bypasses the OSM cache read (still writes to cache on success).
- All existing response fields (id, name, category, phone, distance, matches_crop, source) unchanged.

### 3.3 OSM Discovery Reliability (background inject, D6/D7)

Backend:
- Keep current two-tier OSM strategy (strict agri tags → agri-named hardware/trade shops) + radius escalation (25→45 km), 24h cache, mirror failover.
- The synchronous request path keeps a **short deadline (≤3s)** for cached OSM results only. A live Overpass query is kicked off **in the background** (fire-and-forget `asyncio.create_task`) when no fresh cache exists:
  - The response returns immediately with directory + mandi data, `osm_status: "timeout"` or `"unavailable"`.
  - When the background task completes, results are written to the cache (24h).
- Frontend detects `osm_status != "live"` and **polls `/geo/vendors` every ~5s (max 3 attempts)**; when `osm_status` becomes `"live"`/`"cached"`, it injects the OSM rows into the list **without a full reload** (TanStack Query cache update / partial refetch).
- Visible **Refresh button** (D10): calls `/geo/vendors?refresh=true` — forces a live re-query; show a spinner while waiting; disable while in-flight.
- Overpass failure modes to keep fail-soft: all-mirrors-down, read-timeout, 504, empty result set (each → `osm_status` value, never a thrown error to the client).

### 3.4 Zero-Results Experience (Guided Alternatives, D8)

When the merged result set is empty after all widening attempts:

1. **Empty state card**: "No agri vendors found within {effective_radius} km of {location}."
2. **Guided alternative 1 — nearest wholesale market(s):** show up to 3 nearest entries from the mandi directory (or OSM marketplaces) regardless of distance, e.g. *"Nearest wholesale market: Koyambedu Market, Chennai — 12 km."* Includes distance + a Directions link. (Requires 3.5 mandi seeding.)
3. **Guided alternative 2 — Ask the Copilot:** button deep-links to `/dashboard/copilot` with a prefilled prompt: *"Where can I buy seeds/fertilizer for {crop} near {location}?"* (uses existing chat; the coordinator routes to the advisor).
4. Map still renders the farmer's pin + radius circle so the farmer sees *what was searched*.

### 3.5 Mandi Directory Expansion (D11 — "Both")

- Extend the seed file (`seed_geo_data.py`) with **~100 real APMC/wholesale markets** covering every major state, including Chennai region at minimum:
  - Koyambedu Wholesale Market Complex (Chennai), Chengalpattu APMC, Tiruvallur APMC, Kanchipuram APMC, Vellore APMC, Coimbatore APMC, Madurai APMC, Salem APMC, Erode APMC, Trichy APMC, Tirunelveli APMC, Thanjavur APMC.
- Priority order for the seed expansion: Tamil Nadu first (fixes the reported case), then the remaining states not yet covered (verify against current 50-mandi list: complete coverage gaps in Odisha, Jharkhand, Assam/NE, Uttarakhand, Himachal, Goa, Kerala, J&K, Chhattisgarh, Andhra north coast).
- Seed remains idempotent by name (existing `seed_geo_data()` mechanism, runs at startup).
- Additionally, OSM discovery adds `amenity=marketplace` / `shop=wholesale` results to the guided-alternatives pool (category `produce_buyer`-like, source `osm`).
- Mandi endpoints (`/geo/mandis`) are **not** range-filtered (D5) — they keep current nearest-N behavior.

### 3.6 Frontend (Vendors page)

- Add radius chips row (10/25/50/100/200 km) + Refresh button to the filter bar.
- Map: draw `L.circle` at farmer's pin with `radius_km * 1000` meters; fit bounds to circle ∪ results.
- Search-stats line under the page title: *"Showing vendors within 50 km of Kakatiya Colony — found 7 (2 live, 5 directory)."*
- Background inject: subtle inline notice while OSM is pending — *"Checking live OSM shops nearby…"* — replaced by injected rows when ready (D7). No full-page spinner; directory/mandi content shows instantly.
- Zero-results: guided alternatives block per 3.4.
- Cards unchanged (call/directions buttons appear only when phone exists — already correct). LIVE badge stays.
- Standard responsive layout (D13). English labels (D12).

### 3.7 Testing & Acceptance Criteria

- **AC1 (Chennai):** pin at T. Nagar, Chennai → within 50 km the farmer sees either live OSM shops, seeded local mandis as guided alternatives, or both — never a bare empty state; NEVER a >50 km vendor unless the empty-state alternative explicitly labels it as the nearest market.
- **AC2 (range respected):** setting 25 km excludes results beyond 25 km on the vendors list.
- **AC3 (outage-safe):** with Overpass fully down (simulate by blocking overpass hosts), the page still renders directory/mandi results in <2s, shows the pending notice, and offers Refresh.
- **AC4 (refresh):** clicking Refresh triggers `refresh=true` and eventually flips `osm_status` from `unavailable` to `live`/`cached` (or shows a friendly failure note after 3 polls).
- **AC5 (stats line):** transparency text always matches applied radius and result counts.
- **AC6 (no regressions):** existing behavior in Nashik/Lucknow/Warangal preserved (local-first results, distance sort, crop-match ranking, 150 km directory cap logic replaced by the new radius parameter — see §4).
- Backend: unit tests for radius filtering, widening fallback, osm_status mapping, and empty-state payload; pytest suite stays green (currently 18/18).
- Frontend: `tsc --noEmit` clean; production build succeeds.

---

## 4. Refactors / Cleanups in Scope

- Replace the implicit 150 km directory cap in `nearby_vendors()` with explicit `radius_km` filtering (the cap logic becomes redundant once the farmer controls range).
- Extract `osm_status` as a first-class concept in `vendor_service` (track per-request: cached hit / live fetch / timeout / unavailable).
- Background OSM task must be safe under uvicorn's single worker (guard against task pile-up: skip scheduling if an in-flight task for the same cache key exists — track via a module-level dict).
- Keep `discover_vendors_osm` signature; add optional `force_refresh: bool = False`.

## 5. Out of Scope (explicitly)

- Saving range to the farmer profile (D3).
- Range filtering for mandis, weather, or market intelligence (D5).
- i18n/localization of vendor labels (D12).
- Farmer-contributed vendor edits or "report wrong info" flows (D9).
- AI re-categorization of OSM shops (D14).
- Real Agmarknet/eNAM price feeds, vendor onboarding/claims, admin vendor-approval UI.
- Mobile-specific UX modes (D13).

## 6. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Overpass mirrors frequently down/slow | Background inject keeps page useful; 24h cache; 3 mirrors; `osm_status` transparency; Refresh retry |
| Indian OSM agri-tag sparsity → few/no live shops in rural areas | Mandi directory expansion (3.5) guarantees a wholesale-market alternative; progressive radius widening |
| Radius widening could surface far vendors without user intent | Widening only happens on zero results and the effective radius is always echoed + displayed |
| Background task pile-up under load | In-flight dedupe per cache key; single worker assumption documented |
| Category mislabeling from OSM | Accepted by product (D14); LIVE badge already signals provenance |
