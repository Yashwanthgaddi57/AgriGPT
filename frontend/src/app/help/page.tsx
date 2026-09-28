import type { Metadata } from "next";
import Link from "next/link";
import { LifeBuoy, MessageSquareHeart, Sprout } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Help & Support",
  description: "How to use AgriGPT, answers to common questions, and how to reach support.",
};

const FAQS = [
  {
    q: "How does AgriGPT decide what to recommend?",
    a: "AgriGPT combines your saved farm profile (size, soil, water, crop, planting date) with live weather data, your crop-health scans, market prices with their sources, and your recorded expenses. Recommendations are generated from this data with the reason shown alongside each one.",
  },
  {
    q: "Are the profit numbers guaranteed?",
    a: "No. Cost, revenue and profit figures are estimates based on your inputs and typical conditions. Record your actual harvest in Farm Log and AgriGPT will show estimated vs actual — real outcomes from your own farm.",
  },
  {
    q: "Where do market prices come from?",
    a: "Live prices come from India's Agmarknet APMC feed (via data.gov.in) and always show source, unit and last-updated date. When the live feed is unavailable, AgriGPT clearly shows modeled estimates instead of inventing numbers.",
  },
  {
    q: "How do I track what I spend?",
    a: "Open Farm Log → Expenses. Add each expense with a category (seed, fertilizer, labor…) and AgriGPT shows your total, per-acre cost and category breakdown, and compares recorded spending against your estimates.",
  },
  {
    q: "How do I record a harvest?",
    a: "Farm Log → Harvest. Enter actual yield and selling price; revenue is calculated automatically and compared with your estimate on the 'Estimate vs Actual' tab.",
  },
  {
    q: "Can AgriGPT answer in my language?",
    a: "Yes — the copilot answers in English, Telugu, Hindi, Tamil, Kannada and Marathi. Set your preferred language in onboarding, your profile, or with the language switcher in the dashboard header.",
  },
  {
    q: "Is my farm data private?",
    a: "Yes. Your farms, scans, expenses and chats are stored in your own account and protected by row-level security. Only you can access them.",
  },
];

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 px-4 py-12">
      <div className="text-center">
        <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-leaf-600 text-white">
          <LifeBuoy className="h-6 w-6" />
        </span>
        <h1 className="font-display text-[28px] font-medium leading-[1.2] tracking-[0.36px]">Help &amp; Support</h1>
        <p className="mt-2 text-muted-foreground">
          How AgriGPT works, and how to reach us when something doesn&apos;t.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Sprout className="h-4 w-4 text-leaf-600" /> Getting started
          </CardTitle>
          <CardDescription>The recommended first week</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="list-inside list-decimal space-y-1.5 text-sm text-muted-foreground">
            <li>Create your account and complete the farm profile (location, size, soil, water).</li>
            <li>Run <Link className="text-leaf-600 underline" href="/dashboard/plan">Plan My Farm</Link> to compare crop options with estimated costs and returns.</li>
            <li>Record your expenses in <Link className="text-leaf-600 underline" href="/dashboard/farm-log">Farm Log</Link> so economics reflect reality.</li>
            <li>Use <Link className="text-leaf-600 underline" href="/dashboard/disease">Crop Health</Link> to scan leaves whenever something looks off.</li>
            <li>Check <Link className="text-leaf-600 underline" href="/dashboard">My Farm</Link> each morning — Today&apos;s Farm Plan suggests what to do next, with reasons.</li>
            <li>At harvest, record actual yield and price to see estimated vs actual.</li>
          </ol>
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h2 className="text-xl font-medium">Common questions</h2>
        {FAQS.map((f) => (
          <Card key={f.q}>
            <CardContent className="py-4">
              <p className="font-medium">{f.q}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <Card className="border-leaf-200 bg-leaf-50">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquareHeart className="h-4 w-4 text-leaf-600" /> Contact support
          </CardTitle>
          <CardDescription>We read and answer every message</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            Email:{" "}
            <a className="text-leaf-600 underline" href="mailto:support@agrigpt.app">
              support@agrigpt.app
            </a>{" "}
            — include your registered email and what you were doing when the issue happened.
          </p>
          <p>
            Found a wrong price or a bad recommendation? Report it — correcting real-world
            feedback is how the decision engine improves.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
