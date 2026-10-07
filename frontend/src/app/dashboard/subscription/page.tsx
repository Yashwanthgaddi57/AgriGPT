"use client";

import * as React from "react";
import { Check, Crown, Info, Loader2 } from "lucide-react";

import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/contexts/auth-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  useMySubscription,
  useSubscriptionPlans,
} from "@/hooks/use-api";
import { api } from "@/lib/api";
import { trackEvent, EVENTS } from "@/lib/events";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

export default function SubscriptionPage() {
  const { data: plans } = useSubscriptionPlans();
  const { data: sub } = useMySubscription();
  const { toast } = useToast();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [upgrading, setUpgrading] = React.useState<string | null>(null);

  React.useEffect(() => {
    trackEvent(EVENTS.subscriptionPageViewed);
  }, []);

  // One checkout flow, two outcomes:
  //  - 501 from the backend  -> payments not configured yet, show the old copy.
  //  - order payload          -> open Razorpay Checkout, then /verify on success.
  // Plan activation is server-side only (signature + capture check), so this
  // callback can never grant Pro by itself — it just forwards what Razorpay
  // returned to the backend for verification.
  const upgrade = async (planId: string) => {
    setUpgrading(planId);
    trackEvent(EVENTS.subscriptionStarted, { plan: planId });
    try {
      const { data: order } = await api.post("/subscription/checkout", { plan: planId });
      await openRazorpayCheckout(order);
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      const detail =
        (e as { response?: { data?: { error?: { detail?: string } } } })?.response?.data?.error
          ?.detail ?? "Could not start the payment. Please try again.";
      if (status === 501) {
        toast({ title: "Payments coming soon", description: detail });
      } else {
        toast({ title: "Upgrade failed", description: detail, variant: "destructive" });
      }
    } finally {
      setUpgrading(null);
    }
  };

  const openRazorpayCheckout = (order: {
    order_id: string;
    amount_inr: number;
    currency: string;
    key_id: string;
    plan: string;
  }) =>
    new Promise<void>((resolve, reject) => {
      if (typeof window === "undefined") return reject(new Error("no window"));
      const w = window as unknown as {
        Razorpay?: new (options: Record<string, unknown>) => { open: () => void; on: (event: string, cb: (r: unknown) => void) => void };
      };

      const start = () => {
        if (!w.Razorpay) return reject(new Error("Razorpay script did not load."));
        const rzp = new w.Razorpay({
          key: order.key_id,
          amount: order.amount_inr,
          currency: order.currency,
          name: "AgriGPT",
          description: `AgriGPT ${order.plan} plan`,
          order_id: order.order_id,
          prefill: sub ? { name: user?.name ?? "", email: user?.email ?? "" } : undefined,
          theme: { color: "#15803d" },
          handler: async (response: {
            razorpay_order_id: string;
            razorpay_payment_id: string;
            razorpay_signature: string;
          }) => {
            try {
              await api.post("/subscription/verify", response);
              await qc.invalidateQueries({ queryKey: ["subscription"] });
              toast({ title: "Pro activated!", description: "Unlimited access is now enabled on your account.", variant: "success" });
              trackEvent(EVENTS.subscriptionCompleted, { plan: order.plan });
              resolve();
            } catch (e) {
              const detail =
                (e as { response?: { data?: { error?: { detail?: string } } } })?.response?.data?.error
                  ?.detail ?? "Verification failed. If you were charged, contact support.";
              toast({ title: "Verification failed", description: detail, variant: "destructive" });
              reject(e);
            }
          },
          modal: {
            ondismiss: () => reject(new Error("Payment cancelled.")),
          },
        });
        rzp.on("payment.failed", () =>
          toast({ title: "Payment failed", description: "The bank declined the payment. No amount was deducted.", variant: "destructive" })
        );
        rzp.open();
      };

      // Load the Checkout script once; reuse it on subsequent upgrades.
      const existing = document.querySelector<HTMLScriptElement>("script[src='https://checkout.razorpay.com/v1/checkout.js']");
      if (existing) {
        start();
        return;
      }
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = start;
      script.onerror = () => reject(new Error("Could not load Razorpay. Check your connection."));
      document.body.appendChild(script);
    });

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Subscription</h1>
        <p className="text-sm text-muted-foreground">
          Your current plan and usage. Limits are enforced server-side.
        </p>
      </div>

      {/* Current plan + usage */}
      {sub && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Crown className="h-4 w-4 text-leaf-600" />
              {sub.meta.name} {sub.plan === "free" && <Badge variant="secondary">current</Badge>}
            </CardTitle>
            <CardDescription>Usage on your account</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(sub.usage).map(([feature, u]) => {
              const unlimited = u.limit === -1;
              const pct = unlimited ? 0 : Math.min(100, (u.used / Math.max(u.limit, 1)) * 100);
              return (
                <div key={feature} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="capitalize text-muted-foreground">
                      {feature.replace(/_/g, " ").replace(/messages$/, "copilot messages")}
                    </span>
                    <span className="font-medium">
                      {u.used} / {unlimited ? "∞" : u.limit}
                    </span>
                  </div>
                  {!unlimited && <Progress value={pct} className="mt-2 h-1.5" />}
                  {unlimited && <p className="mt-1 text-xs text-muted-foreground">Unlimited</p>}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Plans */}
      <div className="grid gap-6 lg:grid-cols-3">
        {(plans?.plans ?? []).map((p) => (
          <Card
            key={p.id}
            className={cn(
              "relative flex h-full flex-col",
              p.highlight && "ring-1 ring-leaf-500",
              sub?.plan === p.id && "ring-1 ring-leaf-500"
            )}
          >
            {p.highlight && (
              <Badge className="absolute -top-3 left-1/2 -translate-x-1/2">Most popular</Badge>
            )}
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{p.name}</CardTitle>
              <CardDescription>{p.description}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col">
              <div className="flex items-baseline gap-1">
                <span className="font-display text-[28px] font-medium tracking-[0.36px]">
                  {p.price_inr === null ? "Custom" : `₹${p.price_inr.toLocaleString("en-IN")}`}
                </span>
                <span className="text-sm text-muted-foreground">/ {p.period}</span>
              </div>
              <ul className="mt-4 flex-1 space-y-2 text-sm">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-leaf-600" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              {sub?.plan === p.id ? (
                <Button className="mt-5 w-full" disabled>
                  Current plan
                </Button>
              ) : (
                <Button
                  className="mt-5 w-full"
                  variant={p.highlight ? "default" : "outline"}
                  disabled={upgrading !== null}
                  onClick={() => upgrade(p.id)}
                >
                  {upgrading === p.id && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {p.cta ?? "Choose plan"}
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <p className="flex items-start gap-2 rounded-lg border bg-muted/40 p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        Payments are processed securely by Razorpay (UPI, cards, netbanking).
        Plan activation is verified server-side — your data and usage are
        never affected while you decide.
      </p>
    </div>
  );
}
