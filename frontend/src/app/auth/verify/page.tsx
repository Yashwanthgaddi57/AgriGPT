"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";
import { useToast } from "@/hooks/use-toast";

export default function VerifyEmailPage() {
  const { verifyEmail } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [token, setToken] = React.useState("");
  const [done, setDone] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    setToken(params.get("token") || "");
  }, []);

  const submit = async () => {
    if (!token) return;
    try {
      await verifyEmail(token);
      setDone(true);
      toast({ title: "Email verified!", variant: "success" });
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Invalid or expired verification link.");
    }
  };

  if (done) {
    return (
      <Card className="max-w-md">
        <CardHeader className="items-center text-center">
          <CheckCircle2 className="h-12 w-12 text-leaf-600" />
          <CardTitle>Email verified</CardTitle>
          <CardDescription>Your account is now active.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button className="w-full" asChild>
            <Link href="/auth/login">Sign in</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="max-w-md">
      <CardHeader>
        <CardTitle>Verify your email</CardTitle>
        <CardDescription>
          Open the verification link we sent to your inbox, then confirm here.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && <p className="text-sm text-red-600">{error}</p>}
        <Button className="w-full" onClick={submit} disabled={!token}>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" style={{ display: "none" }} />
          Verify email
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Didn&apos;t get the email?{" "}
          <Link href="/auth/login" className="text-leaf-600 hover:underline">
            Sign in to request a new one
          </Link>.
        </p>
      </CardContent>
    </Card>
  );
}