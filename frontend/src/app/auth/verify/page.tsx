"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, MailCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/auth-context";
import { useToast } from "@/hooks/use-toast";
import { apiErrorMessage } from "@/lib/api";

// The backend enforces a cooldown between code requests, so the resend button
// counts down instead of letting the user walk into a 429.
const RESEND_COOLDOWN_S = 60;
const CODE_LENGTH = 6;

export default function VerifyEmailPage() {
  const { verifyEmail, resendVerification } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const [email, setEmail] = React.useState("");
  const [code, setCode] = React.useState("");
  const [done, setDone] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [cooldown, setCooldown] = React.useState(0);
  const [devHint, setDevHint] = React.useState(false);

  // The register page forwards ?email= so the farmer only retypes the code.
  // ?devcode= appears only in development without a mail provider, so the
  // flow is testable end to end before Brevo is configured.
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    setEmail(params.get("email") || "");
    const dev = params.get("devcode");
    if (dev) {
      setCode(dev.replace(/\D/g, "").slice(0, CODE_LENGTH));
      setDevHint(true);
    }
  }, []);

  React.useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!email.trim() || code.trim().length < CODE_LENGTH) {
      setError(`Enter the ${CODE_LENGTH}-digit code we emailed you.`);
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await verifyEmail(email.trim(), code.trim());
      setDone(true);
      toast({ title: "Email verified!", description: "Sign in to continue.", variant: "success" });
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  const resend = async () => {
    if (!email.trim()) {
      setError("Enter your email address first.");
      return;
    }
    setError(null);
    try {
      await resendVerification(email.trim());
      setCooldown(RESEND_COOLDOWN_S);
      toast({ title: "New code sent", description: `Check ${email.trim()} — it may take a minute.` });
    } catch (e) {
      setError(apiErrorMessage(e));
    }
  };

  if (done) {
    return (
      <Card className="max-w-md">
        <CardHeader className="items-center text-center">
          <CheckCircle2 className="h-12 w-12 text-leaf-600" />
          <CardTitle>Email verified</CardTitle>
          <CardDescription>Your account is active. Sign in to get started.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            className="w-full"
            onClick={() =>
              router.push(`/auth/login?verified=1&email=${encodeURIComponent(email.trim())}`)
            }
          >
            Sign in
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="max-w-md">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MailCheck className="h-5 w-5 text-leaf-600" />
          Verify your email
        </CardTitle>
        <CardDescription>
          We emailed you a {CODE_LENGTH}-digit code. Enter it below to activate your account.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          {devHint && (
            <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-700">
              Dev mode: no email provider configured — the code was filled in for you.
            </p>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="space-y-2">
            <Label htmlFor="verify-email">Email</Label>
            <Input
              id="verify-email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="verify-code">Verification code</Label>
            <Input
              id="verify-code"
              className="text-center text-lg tracking-[0.5em]"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={CODE_LENGTH}
              placeholder={"0".repeat(CODE_LENGTH)}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, CODE_LENGTH))}
            />
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={submitting || code.length < CODE_LENGTH || !email.trim()}
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Verify email
          </Button>

          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={resend}
            disabled={cooldown > 0}
          >
            {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
          </Button>

          <p className="pt-1 text-center text-sm text-muted-foreground">
            Already verified?{" "}
            <Link href="/auth/login" className="text-leaf-600 hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
