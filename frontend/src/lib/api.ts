import axios from "axios";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  timeout: 120_000, // AI calls can be slow
  headers: { "Content-Type": "application/json" },
});

// Request: attach the best available access token.
//  - Password-login users: tokens stashed in localStorage by auth-context.
//  - Google OAuth users: no localStorage entry — read the live Supabase
//    session instead, and stash it so the refresh path can work with it.
api.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    let raw = localStorage.getItem("agrisphere-auth");
    if (!raw) {
      try {
        const { getSupabase } = await import("@/lib/supabase");
        const supabase = getSupabase();
        if (supabase) {
          const { data } = await supabase.auth.getSession();
          if (data.session?.access_token) {
            const session = {
              access_token: data.session.access_token,
              refresh_token: data.session.refresh_token,
              expires_at: data.session.expires_at
                ? data.session.expires_at * 1000
                : Date.now() + 3600_000,
            };
            localStorage.setItem("agrisphere-auth", JSON.stringify(session));
            raw = JSON.stringify(session);
          }
        }
      } catch {
        /* ignore */
      }
    }
    if (raw) {
      try {
        const session = JSON.parse(raw);
        if (session?.access_token) {
          config.headers.Authorization = `Bearer ${session.access_token}`;
        }
      } catch {
        /* ignore */
      }
    }
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const raw = localStorage.getItem("agrisphere-auth");
        if (!raw) return null;
        const session = JSON.parse(raw);
        if (!session?.refresh_token) return null;

        const res = await axios.post(
          `${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`,
          { refresh_token: session.refresh_token },
          { headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "" } }
        );
        const next = {
          access_token: res.data.access_token,
          refresh_token: res.data.refresh_token,
          expires_at: Date.now() + (res.data.expires_in || 3600) * 1000,
        };
        localStorage.setItem("agrisphere-auth", JSON.stringify(next));
        return next.access_token;
      } catch {
        localStorage.removeItem("agrisphere-auth");
        return null;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

// Response: single-flight refresh on 401, then retry once
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const token = await tryRefresh();
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/auth")) {
        window.location.href = "/auth/login";
      }
    }
    return Promise.reject(error);
  }
);

export function apiErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data;
    if (detail?.error?.detail) return detail.error.detail;
    if (detail?.detail) return typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail);
    if (typeof detail === "string") return detail;
    if (error.message) return error.message;
  }
  return "Something went wrong. Please try again.";
}
