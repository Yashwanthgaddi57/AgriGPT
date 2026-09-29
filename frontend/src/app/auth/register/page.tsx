"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/contexts/auth-context";
import { GoogleButton } from "@/components/auth/google-button";
import { apiErrorMessage } from "@/lib/api";
import { trackEvent, EVENTS } from "@/lib/events";
import { useToast } from "@/hooks/use-toast";

const SOILS = ["black", "alluvial", "loamy", "clay", "sandy", "silt", "laterite", "red", "peaty", "unknown"];
const WATER = ["rainfed", "canal", "borewell", "well", "river", "pond", "none"];

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "At least 8 characters"),
  phone: z.string().optional(),
  state: z.string().optional(),
  district: z.string().optional(),
  village: z.string().optional(),
  farm_size_acres: z.coerce.number().min(0.1, "At least 0.1 acres"),
  soil_type: z.string(),
  water_availability: z.string(),
});
type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { soil_type: "unknown", water_availability: "rainfed" },
  });

  const soil = watch("soil_type");
  const water = watch("water_availability");

  // Landing-page pricing CTAs link here with ?plan=pro|cooperative —
  // remember it so we can route the farmer to the subscription page after
  // signup (fixes the dangling ?plan=pro wire).
  const planParam = new URLSearchParams(
    typeof window !== "undefined" ? window.location.search : ""
  ).get("plan");

  React.useEffect(() => {
    trackEvent(EVENTS.signupStarted, { plan: planParam ?? "free" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = async (data: FormData) => {
    try {
      const { status, verificationSent, devCode } = await registerUser(data);
      if (status === "authenticated") {
        trackEvent(EVENTS.signupCompleted, { plan: planParam ?? "free" });
        toast({ title: "Welcome to AgriGPT!", variant: "success" });
        // Farm-first onboarding; ?plan=pro still lands on subscription after.
        router.push(planParam === "pro" ? "/dashboard/subscription" : "/dashboard/onboarding");
      } else {
        // Never promise an email that the provider refused to take.
        toast(
          verificationSent
            ? {
                title: "Registration successful",
                description: "We emailed you a 6-digit code — enter it to activate your account.",
                variant: "success",
              }
            : {
                title: "Account created",
                description: "We couldn't send the verification email. Tap “Resend code” on the next screen.",
                variant: "destructive",
              }
        );
        // Dev-only: when no mail provider is configured the backend returns
        // the code so the flow is fully testable before Brevo is wired up.
        const devSuffix = devCode ? `&devcode=${devCode}` : "";
        // Carry the email through so they only type the code, not both fields.
        router.push(`/auth/verify?email=${encodeURIComponent(data.email)}${devSuffix}`);
      }
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = (e?.response?.data?.error?.detail || apiErrorMessage(e)) as string;
      if (status === 409 || detail.toLowerCase().includes("already exist")) {
        toast({
          title: "Account already exists",
          description: "That email is already registered — sign in instead.",
          variant: "default",
        });
        router.push("/auth/login");
        return;
      }
      toast({ title: "Registration failed", description: detail, variant: "destructive" });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Create your account</CardTitle>
        <CardDescription>Tell us about your farm for better AI advice</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Full name</Label>
              <Input placeholder="Ramesh Patil" {...register("name")} />
              {errors.name && <p className="text-xs text-red-600">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label>Phone</Label>
              <Input placeholder="+91 98765 43210" {...register("phone")} />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input type="email" placeholder="you@example.com" {...register("email")} />
            {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <Label>Password</Label>
            <Input type="password" {...register("password")} />
            {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-2">
              <Label>State</Label>
              <Input placeholder="Maharashtra" {...register("state")} />
            </div>
            <div className="space-y-2">
              <Label>District</Label>
              <Input placeholder="Nashik" {...register("district")} />
            </div>
            <div className="space-y-2">
              <Label>Village</Label>
              <Input placeholder="Ozar" {...register("village")} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-2">
              <Label>Farm size (acres)</Label>
              <Input type="number" step="0.1" min="0.1" {...register("farm_size_acres")} />
              {errors.farm_size_acres && (
                <p className="text-xs text-red-600">{errors.farm_size_acres.message}</p>
              )}
            </div>
<div className="space-y-2">
              <Label htmlFor="soil-type">Soil type</Label>
              <Select value={soil} onValueChange={(v) => setValue("soil_type", v)}>
                <SelectTrigger id="soil-type"><SelectValue placeholder="Select soil type" /></SelectTrigger>
                <SelectContent>
                  {SOILS.map((s) => (
                    <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
<div className="space-y-2">
              <Label htmlFor="water-source">Water source</Label>
              <Select value={water} onValueChange={(v) => setValue("water_availability", v)}>
                <SelectTrigger id="water-source"><SelectValue placeholder="Select water source" /></SelectTrigger>
                <SelectContent>
                  {WATER.map((w) => (
                    <SelectItem key={w} value={w} className="capitalize">{w}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Create account
          </Button>
          <div className="flex items-center gap-3 py-1">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs text-muted-foreground">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>
          <GoogleButton label="Continue with Google" />
          <p className="text-center text-sm text-muted-foreground">
            Already registered?{" "}
            <Link href="/auth/login" className="text-leaf-600 hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
