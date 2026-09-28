"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import type { Profile } from "@/types";

interface AuthState {
  user: Profile | null;
  loading: boolean;
  initialized: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<"authenticated" | "confirm_email">;
  resendVerification: (email: string) => Promise<void>;
  verifyEmail: (token: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  refreshProfile: () => Promise<void>;
}

export interface RegisterData {
  email: string;
  password: string;
  name: string;
  phone?: string;
  district?: string;
  state?: string;
  village?: string;
  farm_size_acres?: number;
  soil_type?: string;
  water_availability?: string;
}

const AuthContext = React.createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<Profile | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [initialized, setInitialized] = React.useState(false);
  const router = useRouter();

  const fetchProfile = React.useCallback(async (): Promise<Profile | null> => {
    try {
      const res = await api.get<Profile>("/profile");
      setUser(res.data);
      return res.data;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  React.useEffect(() => {
    let mounted = true;
    let cleanup: (() => void) | undefined;
    const supabase = getSupabase();

    const init = async () => {
      // Google OAuth users have no localStorage entry — the live Supabase
      // session is the source of truth for them. Check it FIRST so an OAuth
      // session is picked up before any redirect-based stale state.
      if (supabase) {
        try {
          const { data } = await supabase.auth.getSession();
          if (data.session && mounted) {
            await fetchProfile();
            if (mounted) {
              setLoading(false);
              setInitialized(true);
            }
            return;
          }
        } catch {
          /* fall through to localStorage path */
        }
      }
      const raw = localStorage.getItem("agrigpt-auth");
      if (raw) {
        await fetchProfile();
      }
      if (mounted) {
        setLoading(false);
        setInitialized(true);
      }
    };
    init();

    if (supabase) {
      const { data: sub } = supabase.auth.onAuthStateChange((event) => {
        if (event === "SIGNED_OUT") {
          localStorage.removeItem("agrigpt-auth");
          setUser(null);
        }
      });
      cleanup = () => sub.subscription.unsubscribe();
    }
    return () => {
      mounted = false;
      cleanup?.();
    };
  }, [fetchProfile]);

  const login = React.useCallback(
    async (email: string, password: string) => {
      setLoading(true);
      try {
        const res = await api.post("/auth/login", { email, password });
        localStorage.setItem(
          "agrigpt-auth",
          JSON.stringify({
            access_token: res.data.access_token,
            refresh_token: res.data.refresh_token,
          })
        );
        await fetchProfile();
      } finally {
        setLoading(false);
      }
    },
    [fetchProfile]
  );

  const register = React.useCallback(async (data: RegisterData) => {
    setLoading(true);
    try {
      const res = await api.post("/auth/register", data);
      // Local mode returns tokens immediately -> signed in on the spot.
      if (res.data?.access_token) {
        localStorage.setItem(
          "agrigpt-auth",
          JSON.stringify({
            access_token: res.data.access_token,
            refresh_token: res.data.refresh_token,
          })
        );
        await fetchProfile();
        return "authenticated" as const;
      }
      return "confirm_email" as const;
    } finally {
      setLoading(false);
    }
  }, [fetchProfile]);

  const resendVerification = React.useCallback(async (email: string) => {
    await api.post("/auth/resend-verification", { email });
  }, []);

  const verifyEmail = React.useCallback(async (token: string) => {
    await api.post("/auth/verify-email", { token });
  }, []);

  const signInWithGoogle = React.useCallback(async () => {
    const supabase = getSupabase();
    if (!supabase) {
      throw new Error(
        "Google sign-in needs Supabase configuration (NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY)."
      );
    }
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      if (error) throw error;
      // Browser navigates to Google from here; nothing else to do.
    } catch (e) {
      setLoading(false);
      throw e instanceof Error ? e : new Error("Could not start Google sign-in.");
    }
  }, []);

  const logout = React.useCallback(async () => {
    const supabase = getSupabase();
    if (supabase) await supabase.auth.signOut().catch(() => undefined);
    localStorage.removeItem("agrigpt-auth");
    setUser(null);
    router.push("/");
  }, [router]);

  const resetPassword = React.useCallback(async (email: string) => {
    await api.post("/auth/forgot-password", { email });
  }, []);

  const refreshProfile = React.useCallback(async () => {
    await fetchProfile();
  }, [fetchProfile]);

  const value = React.useMemo(
    () => ({
      user,
      loading,
      initialized,
      login,
      register,
      resendVerification,
      verifyEmail,
      signInWithGoogle,
      logout,
      resetPassword,
      refreshProfile,
    }),
    [user, loading, initialized, login, register, resendVerification, verifyEmail, signInWithGoogle, logout, resetPassword, refreshProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
