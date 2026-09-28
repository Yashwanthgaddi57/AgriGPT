"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, API_URL } from "@/lib/api";
import type {
  Activity,
  AnalyticsKpis,
  ChatMessage,
  ChatSession,
  CropRecommendationItem,
  DashboardData,
  DiseaseReport,
  EstimatedVsActual,
  ExpenseItem,
  Farm,
  HarvestItem,
  MarketPrediction,
  Notification,
  ProfitPrediction,
  Profile,
  Recommendation,
  TimelineEvent,
  TodayPlan,
  WeatherIntelligence,
} from "@/types";

// ---------------- Profile ----------------
export function useProfile() {
  return useQuery<Profile>({
    queryKey: ["profile"],
    queryFn: async () => (await api.get("/profile")).data,
    retry: false,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Profile>) => (await api.patch("/profile", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile"] }),
  });
}

// ---------------- Location & Geo ----------------
export interface VendorItem {
  id: string;
  name: string;
  category: string;
  description: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  district: string | null;
  state: string | null;
  latitude: number;
  longitude: number;
  crops: string[];
  distance_km: number;
  raw_distance_km?: number;
  matches_crop: boolean;
  source?: "directory" | "osm";
  beyond_radius?: boolean;
}

export interface FarmerLocation {
  latitude: number;
  longitude: number;
  precision: string;
  label: string;
  village: string | null;
  district: string | null;
  state: string | null;
}

export function useMyLocation() {
  return useQuery<FarmerLocation>({
    queryKey: ["geo", "location"],
    queryFn: async () => (await api.get("/geo/location")).data,
  });
}

export function useSaveLocation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      latitude: number;
      longitude: number;
      source: "gps" | "map_pin";
      village?: string | null;
      district?: string | null;
      state?: string | null;
    }) => (await api.post("/geo/location", payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["geo"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["weather"] });
      qc.invalidateQueries({ queryKey: ["market"] });
      qc.invalidateQueries({ queryKey: ["vendors"] });
    },
  });
}

export function useNearbyVendors(params: { category?: string; crop?: string; radius_km?: number }) {
  return useQuery<{ location: FarmerLocation; radius_km: number; total: number; items: VendorItem[] }>({
    queryKey: ["vendors", params],
    queryFn: async () =>
      (
        await api.get("/geo/vendors", {
          params: {
            ...(params.category ? { category: params.category } : {}),
            ...(params.crop ? { crop: params.crop } : {}),
            ...(params.radius_km ? { radius_km: params.radius_km } : {}),
          },
        })
      ).data,
  });
}

export function useNearbyMandis(crop?: string) {
  return useQuery<{
    id: string;
    name: string;
    district: string | null;
    distance_km: number;
    major_crops: string[];
  }[]>({
    queryKey: ["geo", "mandis", crop],
    queryFn: async () =>
      (await api.get("/geo/mandis", { params: crop ? { crop } : {} })).data,
  });
}

// ---------------- Farms ----------------
export function useFarms() {
  return useQuery<Farm[]>({
    queryKey: ["farms"],
    queryFn: async () => (await api.get("/farms")).data,
  });
}

export function useCreateFarm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Farm>) => (await api.post("/farms", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["farms"] }),
  });
}

export function useUpdateFarm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: { id: string } & Partial<Farm>) =>
      (await api.patch(`/farms/${id}`, payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["farms"] }),
  });
}

export function useSavePlantingDate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      farm_id?: string | null;
      crop: string;
      planting_date: string; // ISO date
    }) => {
      if (payload.farm_id) {
        return (
          await api.patch(`/farms/${payload.farm_id}`, {
            current_crop: payload.crop,
            planting_date: payload.planting_date,
          })
        ).data as Farm;
      }
      // No farm record yet — create one with the planting info.
      const profile = (await api.get("/profile")).data as Profile;
      return (
        await api.post("/farms", {
          name: "My Farm",
          area_acres: profile.farm_size_acres || 1,
          soil_type: profile.soil_type || "unknown",
          water_source: profile.water_availability || "rainfed",
          current_crop: payload.crop,
          planting_date: payload.planting_date,
        })
      ).data as Farm;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["farms"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useDeleteFarm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/farms/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["farms"] }),
  });
}

// ---------------- Decision Engine / Farm Home ----------------
export function useTodayPlan() {
  return useQuery<TodayPlan>({
    queryKey: ["farm", "today"],
    queryFn: async () => (await api.get("/farm/today")).data,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useExpenses() {
  return useQuery<{ items: ExpenseItem[]; total: number; per_acre: number; by_category: Record<string, number> }>({
    queryKey: ["farm", "expenses"],
    queryFn: async () => (await api.get("/farm/expenses")).data,
  });
}

export function useCreateExpense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      category: string;
      amount_inr: number;
      description?: string | null;
      spent_on: string;
    }) => (await api.post("/farm/expenses", payload)).data as ExpenseItem,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["farm"] });
    },
  });
}

export function useDeleteExpense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/farm/expenses/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["farm"] }),
  });
}

export function useHarvests() {
  return useQuery<{ items: HarvestItem[] }>({
    queryKey: ["farm", "harvests"],
    queryFn: async () => (await api.get("/farm/harvests")).data,
  });
}

export function useCreateHarvest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      crop: string;
      harvest_date?: string | null;
      actual_yield_quintals?: number | null;
      selling_price_per_quintal?: number | null;
      market_name?: string | null;
      revenue_inr?: number | null;
    }) => (await api.post("/farm/harvests", payload)).data as HarvestItem,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["farm"] });
    },
  });
}

export function useEstimatedVsActual() {
  return useQuery<EstimatedVsActual>({
    queryKey: ["farm", "estimated-vs-actual"],
    queryFn: async () => (await api.get("/farm/estimated-vs-actual")).data,
  });
}

export function useFarmTimeline() {
  return useQuery<{ items: TimelineEvent[] }>({
    queryKey: ["farm", "timeline"],
    queryFn: async () => (await api.get("/farm/timeline")).data,
  });
}

// ---------------- Dashboard ----------------
export function useDashboard() {
  return useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard")).data,
    staleTime: 3 * 60 * 1000,
    gcTime: 30 * 60 * 1000, // instant paint from cache on revisit
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev, // keep previous data while refetching
    refetchInterval: 90 * 1000, // pick up bg-refreshed weather/alerts while open
  });
}

// ---------------- Crop Recommendations ----------------
export function useRecommendCrop() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      location: string;
      farm_size_acres: number;
      soil_type: string;
      water_source: string;
      budget_inr: number;
      season: string;
      farm_id?: string;
    }) => (await api.post("/crops/recommend", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recommendations"] }),
  });
}

export function useRecommendationHistory(page = 1) {
  return useQuery<{ items: Recommendation[]; total: number }>({
    queryKey: ["recommendations", page],
    queryFn: async () =>
      (await api.get(`/crops/history?page=${page}&page_size=10`)).data,
  });
}

// ---------------- Disease Detection ----------------
export function useAnalyzeDisease() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ image, crop, farm_id }: { image: File; crop: string; farm_id?: string }) => {
      const form = new FormData();
      form.append("image", image);
      form.append("crop", crop);
      if (farm_id) form.append("farm_id", farm_id);
      return (
        await api.post("/disease/analyze", form, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data as DiseaseReport;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["disease"] }),
  });
}

export function useDiseaseReports(page = 1) {
  return useQuery<{ items: DiseaseReport[]; total: number }>({
    queryKey: ["disease", "reports", page],
    queryFn: async () => (await api.get(`/disease/reports?page=${page}&page_size=10`)).data,
  });
}

export function useDiseaseAnalytics() {
  return useQuery({
    queryKey: ["disease", "analytics"],
    queryFn: async () => (await api.get("/disease/analytics")).data,
  });
}

export function useUpdateDiseaseFollowup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      reportId: string;
      followup_status: "open" | "monitoring" | "treated" | "resolved" | null;
      notes?: string | null;
    }) => {
      const { reportId, ...body } = payload;
      return (await api.patch(`/disease/reports/${reportId}`, body)).data as DiseaseReport;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["disease"] }),
  });
}

// ---------------- Profit Predictor ----------------
export function usePredictProfit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      crop: string;
      farm_size_acres: number;
      season?: string;
      seed_cost: number;
      labor_cost: number;
      fertilizer_cost: number;
      irrigation_cost: number;
      transportation_cost: number;
      other_cost?: number;
      farm_id?: string;
    }) => (await api.post("/profit/predict", payload)).data as ProfitPrediction,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profit"] }),
  });
}

export function useProfitPredictions(page = 1) {
  return useQuery<{ items: ProfitPrediction[]; total: number }>({
    queryKey: ["profit", "predictions", page],
    queryFn: async () => (await api.get(`/profit/predictions?page=${page}&page_size=10`)).data,
  });
}

// ---------------- Market Intelligence ----------------
export function useAnalyzeMarket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { crop: string; market?: string }) =>
      (await api.post("/market/analyze", payload)).data as MarketPrediction,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["market"] }),
  });
}

export function useMarketPredictions(page = 1) {
  return useQuery<{ items: MarketPrediction[]; total: number }>({
    queryKey: ["market", "predictions", page],
    queryFn: async () => (await api.get(`/market/predictions?page=${page}&page_size=10`)).data,
  });
}

export interface PriceTickerItem {
  crop: string;
  price: number;
  unit: string;
  trend_weekly_pct: number;
  history: { date: string; price: number }[];
  source: string;
  is_live: boolean;
  as_of: string;
}

export interface MandiPriceCompare {
  mandi: string;
  district: string | null;
  state: string | null;
  distance_km: number;
  price: number;
  unit: string;
  trend_weekly_pct: number;
  source: string;
  is_live: boolean;
  as_of: string;
}

export function useMarketCompare(crop?: string) {
  return useQuery<{
    crop: string;
    location: string;
    items: MandiPriceCompare[];
    note: string;
  }>({
    queryKey: ["market", "compare", crop],
    queryFn: async () =>
      (await api.get("/market/compare", { params: crop ? { crop } : {} })).data,
    enabled: !!crop,
    staleTime: 5 * 60 * 1000,
  });
}

export function usePriceTicker() {
  return useQuery<{ location: { label: string; state: string | null; district: string | null }; items: PriceTickerItem[] }>({
    queryKey: ["market", "ticker"],
    queryFn: async () => (await api.get("/market/ticker")).data,
    // Realtime feel without hammering the API — prices are cached 1h server-side.
    refetchInterval: 5 * 60 * 1000,
    staleTime: 60 * 1000,
  });
}

// ---------------- Weather ----------------
export function useWeather(location?: string) {
  return useQuery<WeatherIntelligence>({
    queryKey: ["weather", location],
    queryFn: async () =>
      (await api.get(`/weather${location ? `?location=${encodeURIComponent(location)}` : ""}`)).data,
    staleTime: 10 * 60 * 1000,
  });
}

// ---------------- Chat ----------------
export function useChatSessions() {
  return useQuery<ChatSession[]>({
    queryKey: ["chat", "sessions"],
    queryFn: async () => (await api.get("/chat/sessions")).data,
  });
}

export function useChatMessages(sessionId: string | null) {
  return useQuery<ChatMessage[]>({
    queryKey: ["chat", "messages", sessionId],
    queryFn: async () => (await api.get(`/chat/sessions/${sessionId}/messages`)).data,
    enabled: !!sessionId,
  });
}

export function useSendMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      content: string;
      agent?: string;
      session_id?: string | null;
      language?: string | null;
    }) => (await api.post("/chat/messages", payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat"] });
    },
  });
}

export function useDeleteChatSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/chat/sessions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat"] }),
  });
}

/**
 * Pull a human-readable message out of an axios-style error body.
 * The backend wraps errors as {"error": {"code", "detail", "path"}}.
 */
async function responseErrorMessage(res: Response): Promise<string> {
  let detail = "";
  try {
    const body = await res.json();
    detail = body?.error?.detail || body?.detail || body?.error?.message || body?.message || "";
  } catch {
    /* non-JSON body */
  }
  if (detail) return String(detail);
  if (res.status === 429) {
    return "You've reached your plan's daily copilot limit. Try again tomorrow or upgrade for unlimited chats.";
  }
  if (res.status === 401 || res.status === 403) {
    return "Your session expired. Please sign in again.";
  }
  return `The copilot request failed (${res.status}). Please try again.`;
}

/**
 * Streaming chat: POSTs to the SSE endpoint with fetch (axios can't stream),
 * parses `data: {...}` events, and invokes onEvent for each. Falls back to
 * the non-streaming endpoint automatically only if the stream is unreachable.
 */
export async function sendMessageStream(
  payload: { content: string; agent?: string; session_id?: string | null; language?: string | null },
  onEvent: (e: { type: string; text?: string; agent?: string; session_id?: string; message_id?: string; message?: string }) => void
): Promise<void> {
  const raw = localStorage.getItem("agrigpt-auth");
  let token = "";
  if (raw) {
    try {
      token = JSON.parse(raw)?.access_token ?? "";
    } catch {
      /* ignore */
    }
  }
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response | null = null;
  try {
    res = await fetch(`${API_URL}/api/v1/chat/messages/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
  } catch {
    res = null; // network failure -> try the classic endpoint below
  }

  // The server answered with a real HTTP error (401/403/429/5xx). Surface its
  // own message instead of retrying the non-streaming endpoint, which would
  // fail identically and hide the reason (e.g. the daily-quota 429).
  if (res && !res.ok) {
    throw new Error(await responseErrorMessage(res));
  }

  if (!res || !res.body) {
    // Endpoint unreachable / no stream support -> classic request-response fallback
    const data = (await api.post("/chat/messages", payload)).data as {
      session_id: string;
      message: ChatMessage;
      agent: string | null;
    };
    onEvent({ type: "meta", session_id: data.session_id });
    onEvent({ type: "agent", agent: data.agent ?? undefined });
    onEvent({ type: "delta", text: data.message.content });
    onEvent({ type: "done", session_id: data.session_id, message_id: data.message.id });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        try {
          onEvent(JSON.parse(line.slice(5).trim()));
        } catch {
          /* skip malformed chunk */
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ---------------- Notifications ----------------
export function useNotifications() {
  return useQuery<{ items: Notification[]; unread_count: number }>({
    queryKey: ["notifications"],
    queryFn: async () => (await api.get("/notifications")).data,
    refetchInterval: 60_000,
  });
}

export function useMarkNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (ids: string[]) => (await api.post("/notifications/mark-read", { ids })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

// ---------------- Analytics events moved to lib/events.ts ----------------

// ---------------- Subscription ----------------
export interface PlanInfo {
  id: string;
  name: string;
  // null for custom-priced plans (e.g. Cooperative / FPO — "Contact us")
  price_inr: number | null;
  period: string;
  description: string;
  features: string[];
  limits: Record<string, number>;
  cta?: string;
  highlight?: boolean;
}

export function useSubscriptionPlans() {
  return useQuery<{ plans: PlanInfo[]; payments_enabled: boolean }>({
    queryKey: ["subscription", "plans"],
    queryFn: async () => (await api.get("/subscription/plans")).data,
    staleTime: 10 * 60 * 1000,
  });
}

export function useMySubscription() {
  return useQuery<{
    plan: string;
    meta: { name: string; price_inr: number; features: string[] };
    limits: Record<string, number>;
    usage: Record<string, { used: number; limit: number }>;
  }>({
    queryKey: ["subscription", "me"],
    queryFn: async () => (await api.get("/subscription")).data,
  });
}

// ---------------- Analytics ----------------
export function useAnalyticsKpis() {
  return useQuery<AnalyticsKpis>({
    queryKey: ["analytics", "kpis"],
    queryFn: async () => (await api.get("/analytics/kpis")).data,
  });
}

export function useActivities(page = 1) {
  return useQuery<{ items: Activity[]; total: number }>({
    queryKey: ["activities", page],
    queryFn: async () => (await api.get(`/analytics/activities?page=${page}&page_size=20`)).data,
  });
}

export type { CropRecommendationItem };
