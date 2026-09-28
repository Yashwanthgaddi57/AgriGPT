"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { CheckCircle2, Loader2 } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getSupabase } from "@/lib/supabase";

const schema = z
  .object({
    password: z.string().min(8, "At least 8 characters"),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });
type FormData = z.infer<typeof schema>;

/**
 * Password reset landing — target of the "Forgot password" email link.
 *
 * Supabase delivers the recovery link as either
 *   - an implicit-flow URL fragment  (#access_token=...&type=recovery) or
 *   - a one-time code query param    (?code=...)
 * detectSessionInUrl + the exchange below cover both shapes.
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  const [ready, setReady] = React.useState(false); // recovery session established
  const [error, setError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const supabase = getSupabase();
        if (!supabase) throw new Error("Supabase is not configured.");

        const hash = window.location.hash.startsWith("#")
          ? window.location.hash.slice(1)
          : window.location.hash;
        const params = new URLSearchParams(hash || window.location.search);
        const code = params.get("code");

        // Wait briefly for detectSessionInUrl to consume an implicit-flow fragment.
        const deadline = Date.now() + 5000;
        let session = null;
        while (Date.now() < deadline) {
          const { data } = await supabase.auth.getSession();
          session = data.session;
          if (session) break;
          await new Promise((r) => setTimeout(r, 250));
        }

        // PKCE/otp flow: exchange the one-time code explicitly.
        if (!session && code) {
          const { data, error: exErr } = await supabase.auth.exchangeCodeForSession(code);
          if (exErr) throw exErr;
          session = data.session;
        }

        if (!session) {
          throw new Error(
            "This reset link is invalid or has expired. Request a new one from the sign-in page."
          );
        }
        if (!cancelled) setReady(true);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not validate the reset link.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = async (data: FormData) => {
    setError(null);
    try {
      const supabase = getSupabase();
      if (!supabase) throw new Error("Supabase is not configured.");
      const { error: upErr } = await supabase.auth.updateUser({ password: data.password });
      if (upErr) throw upErr;

      setDone(true);
      // Clear any stale app token cache; user signs in fresh.
      localStorage.removeItem("agrisphere-auth");
      setTimeout(() => router.push("/auth/login"), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update the password.");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">
          {done ? "Password updated" : "Choose a new password"}
        </CardTitle>
        <CardDescription>
          {done
            ? "You can now sign in with your new password."
            : ready
              ? "Pick something strong — at least 8 characters."
              : "Validating your reset link…"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {done ? (
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <CheckCircle2 className="h-10 w-10 text-leaf-600" />
            <p className="font-medium">All set — redirecting to sign in…</p>
            <Button variant="outline" asChild>
              <Link href="/auth/login">Go to sign in</Link>
            </Button>
          </div>
        ) : error ? (
          <>
            <p className="rounded-lg border border-amber-500/25 bg-amber-50 p-3 text-sm text-amber-600">
              {error}
            </p>
            <Button variant="outline" asChild className="w-full">
              <Link href="/auth/forgot-password">Request a new reset link</Link>
            </Button>
          </>
        ) : ready ? (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password">New password</Label>
              <Input id="password" type="password" {...register("password")} />
              {errors.password && (
                <p className="text-xs text-red-600">{errors.password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm password</Label>
              <Input id="confirm" type="password" {...register("confirm")} />
              {errors.confirm && (
                <p className="text-xs text-red-600">{errors.confirm.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              Update password
            </Button>
          </form>
        ) : (
          <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Checking link…
          </div>
        )}
      </CardContent>
    </Card>
  );
}
