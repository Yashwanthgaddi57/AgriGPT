"use client";

/**
 * Privacy-conscious product analytics (first-party only).
 * Events go to POST /analytics/events (backend allowlist) and are stored
 * against the authenticated user's activity log. No PII beyond the session.
 */
import { api } from "@/lib/api";

export const EVENTS = {
  signupStarted: "signup_started",
  signupCompleted: "signup_completed",
  farmProfileCompleted: "farm_profile_completed",
  cropPlanStarted: "crop_plan_started",
  cropPlanCompleted: "crop_plan_completed",
  diseaseScanStarted: "disease_scan_started",
  diseaseScanCompleted: "disease_scan_completed",
  profitCalculatorUsed: "profit_calculator_used",
  marketPageViewed: "market_page_viewed",
  subscriptionPageViewed: "subscription_page_viewed",
  subscriptionStarted: "subscription_started",
  subscriptionCompleted: "subscription_completed",
  voiceInputUsed: "voice_input_used",
  ttsUsed: "tts_used",
  planWizardStarted: "plan_wizard_started",
  planWizardCompleted: "plan_wizard_completed",
} as const;

type EventName = (typeof EVENTS)[keyof typeof EVENTS];

export function trackEvent(event: EventName, metadata?: Record<string, unknown>) {
  if (process.env.NODE_ENV !== "production") {
    console.debug(`[analytics] ${event}`, metadata ?? "");
  }
  // Fire-and-forget: never block or break the UI on analytics.
  api.post("/analytics/events", { event, metadata }).catch(() => undefined);
}
