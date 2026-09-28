"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/auth-context";
import { GoogleButton } from "@/components/auth/google-button";
import { apiErrorMessage } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "At least 8 characters"),
});
type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const { login, resendVerification } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [emailNotConfirmed, setEmailNotConfirmed] = React.useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      await login(data.email, data.password);
      router.push("/dashboard");
    } catch (e: any) {
      const msg = (e?.response?.data?.detail || apiErrorMessage(e)).toLowerCase();
      if (msg.includes("confirm") || msg.includes("verify")) {
        setEmailNotConfirmed(data.email);
      }
      toast({ title: "Sign in failed", description: apiErrorMessage(e), variant: "destructive" });
    }
  };

  const handleResend = async () => {
    if (!emailNotConfirmed) return;
    try {
      await resendVerification(emailNotConfirmed);
      toast({ title: "Verification email sent", variant: "success" });
    } catch (e) {
      toast({ title: "Could not resend", description: apiErrorMessage(e), variant: "destructive" });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Welcome back</CardTitle>
        <CardDescription>Sign in to your farm dashboard</CardDescription>
      </CardHeader>
      <CardContent>
        {emailNotConfirmed && (
          <div className="mb-4 flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm">
            <Mail className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <div className="flex-1">
              <p className="font-medium text-amber-900">Email not verified</p>
              <p className="text-amber-800">
                Check your inbox for the verification link sent to{" "}
                <span className="font-medium">{emailNotConfirmed}</span>. Once you
                click it, come back and sign in.
              </p>
              <button
                onClick={handleResend}
                className="mt-1 text-xs font-medium text-leaf-700 hover:underline"
              >
                Resend verification email
              </button>
            </div>
          </div>
        )}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" placeholder="you@example.com" {...register("email")} />
            {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password">Password</Label>
              <Link href="/auth/forgot-password" className="text-xs text-leaf-600 hover:underline">
                Forgot password?
              </Link>
            </div>
            <Input id="password" type="password" {...register("password")} />
            {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Sign in
          </Button>
          <div className="flex items-center gap-3 py-1">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs text-muted-foreground">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>
          <GoogleButton />
          <p className="text-center text-sm text-muted-foreground">
            New here?{" "}
            <Link href="/auth/register" className="text-leaf-600 hover:underline">
              Create an account
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
