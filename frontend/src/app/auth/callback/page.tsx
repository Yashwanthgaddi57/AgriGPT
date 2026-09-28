"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";

/**
 * OAuth return landing for Google sign-in.
 *  - Supabase detects the session in the URL (detectSessionInUrl: true).
 *  - We stash tokens for the api client, sync the backend profile,
 *    then send the farmer to the dashboard.
 */
export default function AuthCallbackPage() {
  const { refreshProfile } = useAuth();
  const router = useRouter();
  const [error, setError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState(false);

  React.useEffect(() => {
    if (done) return; // guard against Strict Mode double-run
    let cancelled = false;

    const finish = async () => {
      try {
        const { getSupabase } = await import("@/lib/supabase");
        const supabase = getSupabase();
        if (!supabase) {
          throw new Error("Supabase is not configured.");
        }

        // detectSessionInUrl is on, so the URL fragment (#access_token=...)
        // is consumed on client init. Give supabase-js a moment, then poll.
        const deadline = Date.now() + 10000;
        let session = null;
        let attempts = 0;
        while (Date.now() < deadline) {
          const { data, error: sessionError } = await supabase.auth.getSession();
          session = data.session;
          if (session) break;
          if (sessionError) break;
          attempts++;
          await new Promise((r) => setTimeout(r, attempts < 5 ? 250 : 1000));
          await supabase.auth.refreshSession().catch(() => undefined);
        }
        if (!session) {
          throw new Error(
            "No session found after Google sign-in. Please try again."
          );
        }

        // Persist tokens for the api client (same shape as password login).
        localStorage.setItem(
          "agrigpt-auth",
          JSON.stringify({
            access_token: session.access_token,
            refresh_token: session.refresh_token,
            expires_at: session.expires_at
              ? session.expires_at * 1000
              : Date.now() + 3600_000,
          })
        );

        if (cancelled) return;
        await refreshProfile(); // backend auto-provisions the profile row
        if (cancelled) return;
        setDone(true);
        router.replace("/dashboard");
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Google sign-in failed.");
        }
      }
    };

    finish();
    return () => {
      cancelled = true;
    };
  }, [done, refreshProfile, router]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">
          {error ? "Sign-in problem" : "Signing you in…"}
        </CardTitle>
        <CardDescription>
          {error
            ? "Google sign-in could not be completed."
            : "Finishing Google sign-in and loading your farm."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <>
            <div className="flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-50 p-3 text-sm text-amber-600">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => router.push("/auth/login")}>
                Back to sign in
              </Button>
              <Button className="flex-1" onClick={() => window.location.reload()}>
                Try again
              </Button>
            </div>
            <p className="text-center text-xs text-muted-foreground">
              If this keeps happening, ask the admin to enable the Google provider in Supabase Auth.
            </p>
          </>
        ) : (
          <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Finishing up…
          </div>
        )}
      </CardContent>
    </Card>
  );
}
