"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  BadgeCheck,
  Check,
  CloudSun,
  Info,
  LineChart,
  MessageSquareHeart,
  ScanSearch,
  Sprout,
  TrendingUp,
  Wallet,
} from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const reveal = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55 } },
};

function SectionHeading({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: React.ReactNode;
  subtitle?: string;
}) {
  return (
    <motion.div
      variants={reveal}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
      className="relative mx-auto mb-14 max-w-3xl text-center"
    >
      <Badge variant="secondary" className="mb-4">
        {eyebrow}
      </Badge>
      <h2 className="font-display text-[32px] font-semibold leading-[1.15] tracking-[-0.008em] sm:text-[40px]">{title}</h2>
      {subtitle && <p className="mt-4 text-[17px] text-muted-foreground">{subtitle}</p>}
    </motion.div>
  );
}

// ---------------- Trust / Value ----------------
const benefits = [
  {
    icon: Sprout,
    title: "Compare crops before planting",
    text: "See estimated costs, returns, duration and risks side by side for your soil, water and budget — before you spend.",
  },
  {
    icon: Wallet,
    title: "Estimate profit transparently",
    text: "A clear calculator shows total cost, expected revenue and break-even price. Change any assumption and see it update.",
  },
  {
    icon: ScanSearch,
    title: "Check crop symptoms early",
    text: "Upload a leaf photo for an AI-assisted analysis of possible issues, with confidence levels and alternative explanations.",
  },
  {
    icon: LineChart,
    title: "Understand market conditions",
    text: "Mandi prices with source and timestamp, price trends, and sell/wait guidance when data is available.",
  },
  {
    icon: CloudSun,
    title: "Farm-aware weather",
    text: "7-day forecasts translated into irrigation, spraying and harvest timing suggestions for your location.",
  },
  {
    icon: MessageSquareHeart,
    title: "Copilot in your language",
    text: "Ask in English, Hindi, Telugu, Tamil, Kannada or Marathi — by text or voice. Answers use your saved farm context.",
  },
];

export function Benefits() {
  return (
    <section className="border-b py-24">
      <div className="container">
        <SectionHeading
          eyebrow="Why AgriGPT"
          title={<>Decision support for <span className="text-gradient">every farm decision</span></>}
          subtitle="AI-powered estimates to help you plan — always verify high-stakes decisions with local experts."
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {benefits.map((b, i) => (
            <motion.div
              key={b.title}
              variants={reveal}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
            >
              <Card className="h-full">
                <CardContent className="pt-6">
                  <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-leaf-100 text-leaf-600">
                    <b.icon className="h-6 w-6" />
                  </span>
                  <h3 className="font-display mb-2 text-[20px] font-semibold tracking-[-0.24px]">{b.title}</h3>
                  <p className="text-sm text-muted-foreground">{b.text}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------- Features ----------------
const features = [
  { icon: Sprout, title: "Plan My Farm", text: "A guided workflow: describe your farm, get ranked crop options with estimated cost, revenue, profit, duration and water needs — clearly labeled as estimates." },
  { icon: ScanSearch, title: "Crop Health", text: "Upload a photo; get possible issues with confidence levels, alternative explanations, immediate actions and prevention steps. Track follow-ups in My Crop Health." },
  { icon: Wallet, title: "Profit Calculator", text: "Transparent math — not a black box. Total cost, expected production, revenue, gross profit per acre and break-even price." },
  { icon: TrendingUp, title: "Market Intelligence", text: "Mandi prices with source, unit and last-updated date. Compare nearby markets where data supports it; clearly flagged when data is unavailable." },
  { icon: CloudSun, title: "Weather Intelligence", text: "Real forecast data (Open-Meteo) with agro-context: when to irrigate, spray or harvest — clearly separated from AI recommendations." },
  { icon: MessageSquareHeart, title: "AI Farm Copilot", text: "Chat or speak in your language. The copilot knows your farm profile, recent scans and market views — no need to repeat yourself." },
];

export function Features() {
  return (
    <section id="features" className="py-24">
      <div className="container">
        <SectionHeading
          eyebrow="Features"
          title={<>One platform, <span className="text-gradient">every decision</span></>}
          subtitle="Farm data + weather + market prices + crop knowledge + AI reasoning — combined into actionable guidance."
        />
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              variants={reveal}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true }}
              transition={{ delay: i * 0.06 }}
            >
              <Card className="group h-full transition-all hover:-translate-y-1">
                <CardContent className="pt-6">
                  <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-leaf-100 text-leaf-600">
                    <f.icon className="h-6 w-6" />
                  </span>
                  <h3 className="font-display mb-2 text-[20px] font-semibold tracking-[-0.24px]">{f.title}</h3>
                  <p className="text-sm text-muted-foreground">{f.text}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------- How It Works ----------------
const steps = [
  { n: "01", title: "Tell us about your farm", text: "Location, soil, water, size and budget. Takes two minutes." },
  { n: "02", title: "AgriGPT analyzes it", text: "Ranked crop options with estimated costs, returns and risks for your conditions." },
  { n: "03", title: "Act on recommendations", text: "Plan planting, track crop health, watch the weather and check market prices." },
  { n: "04", title: "Track your farm", text: "Crop health history, profit estimates and daily suggestions — all season long." },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-b bg-secondary/30 py-24">
      <div className="container">
        <SectionHeading
          eyebrow="How it works"
          title={<>From farm data to <span className="text-gradient">better decisions</span></>}
        />
        <div className="relative grid gap-8 md:grid-cols-4">
          <div className="absolute left-0 right-0 top-6 hidden h-px bg-gradient-to-r from-transparent via-leaf-400 to-transparent md:block" />
          {steps.map((s, i) => (
            <motion.div
              key={s.n}
              variants={reveal}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="relative text-center md:text-left"
            >
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border-2 border-leaf-500 bg-background font-display font-medium text-leaf-600 md:mx-0">
                {s.n}
              </div>
              <h3 className="font-display mb-2 text-[20px] font-semibold tracking-[-0.24px]">{s.title}</h3>
              <p className="text-sm text-muted-foreground">{s.text}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------- Pricing ----------------
// Single source of truth is GET /api/v1/subscription/plans (backend/app/core/plans.py).
// This landing-page mirror lists only features that exist today; keep in sync.
const plans = [
  {
    name: "Kisan Free",
    price: "₹0",
    period: "forever",
    description: "Core AI tools for smallholders.",
    features: ["5 crop plans / month", "10 disease scans / month", "Weather intelligence", "AI Copilot (20 messages/day)", "Profit calculator"],
    cta: "Start free",
    highlight: false,
  },
  {
    name: "Pro Farmer",
    price: "₹299",
    period: "per month",
    description: "For serious growers who want every edge.",
    features: ["Unlimited crop plans", "Unlimited disease scans + health history", "Market intelligence & sell/wait guidance", "AI Copilot (unlimited)", "Priority support queue"],
    cta: "Go Pro",
    highlight: true,
  },
  {
    name: "Cooperative / FPO",
    price: "Early access",
    period: "",
    description: "For FPOs, NGOs and agri-program teams.",
    features: ["Organization dashboard (in development)", "Multi-farmer management*", "Aggregated analytics & reports*", "Admin controls*"],
    cta: "Contact us",
    highlight: false,
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="py-24">
      <div className="container">
        <SectionHeading
          eyebrow="Pricing"
          title={<>Tools designed to help you make <span className="text-gradient">better farming decisions</span></>}
          subtitle="Start free. Upgrade when you need more. Prices in INR."
        />
        <div className="grid gap-6 lg:grid-cols-3">
          {plans.map((p, i) => (
            <motion.div
              key={p.name}
              variants={reveal}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
            >
              <Card
                className={cn(
                  "relative h-full",
                  p.highlight && "ring-1 ring-leaf-500"
                )}
              >
                {p.highlight && (
                  <Badge className="absolute -top-3 left-1/2 -translate-x-1/2">Most popular</Badge>
                )}
                <CardContent className="flex h-full flex-col p-6">
                  <h3 className="font-display text-[20px] font-semibold tracking-[-0.24px]">{p.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{p.description}</p>
                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="font-display text-[28px] font-medium tracking-[0.36px]">{p.price}</span>
                    <span className="text-sm text-muted-foreground">/ {p.period}</span>
                  </div>
                  <ul className="mt-6 flex-1 space-y-3 text-sm">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-leaf-600" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    className="mt-6 w-full"
                    variant={p.highlight ? "default" : "outline"}
                    asChild
                  >
                    <Link href={p.highlight ? "/auth/register?plan=pro" : "/auth/register"}>{p.cta}</Link>
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
        <p className="mx-auto mt-8 flex max-w-2xl items-start gap-2 text-center text-xs text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            * Organization (FPO) features are in early access — the dashboard is not
            fully available yet. Online payments are being integrated; upgrades are
            currently handled by our team.
          </span>
        </p>
      </div>
    </section>
  );
}

// ---------------- Product demo ----------------
export function ProductDemo() {
  const shots = [
    { title: "Plan My Farm", body: "Guided farm profile → ranked crop options → your farm plan with estimated cost, revenue and profit.", icon: Sprout },
    { title: "Crop Health", body: "Photo scan → possible issue with confidence → actions, prevention and follow-up tracking.", icon: ScanSearch },
    { title: "Profit Calculator", body: "Transparent cost breakdown → break-even price → best/average/worst scenarios.", icon: Wallet },
    { title: "Market Intelligence", body: "Live mandi prices with source and timestamp → trends → sell/wait guidance.", icon: LineChart },
  ];
  return (
    <section id="demo" className="border-b py-24">
      <div className="container">
        <SectionHeading
          eyebrow="Inside the product"
          title={<>See how a <span className="text-gradient">farm decision</span> comes together</>}
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {shots.map((s) => (
            <Card key={s.title} className="h-full">
              <CardContent className="pt-6">
                <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-leaf-100 text-leaf-600">
                  <s.icon className="h-6 w-6" />
                </span>
                <h3 className="font-display mb-2 text-[20px] font-semibold tracking-[-0.24px]">{s.title}</h3>
                <p className="text-sm text-muted-foreground">{s.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------- Safety / Disclaimer ----------------
export function Safety() {
  return (
    <section className="py-16">
      <div className="container max-w-3xl">
        <Card className="border border-amber-500/25 bg-amber-50">
          <CardContent className="flex items-start gap-3 py-5">
            <Info className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
            <div className="text-sm leading-relaxed text-muted-foreground">
              <p className="mb-1 font-medium text-foreground">Important</p>
              AgriGPT provides AI-generated estimates and decision-support
              suggestions. Crop plans, profit projections and disease
              analyses are <strong>not guarantees</strong> — actual results
              depend on weather, soil, pests, market conditions and farming
              practices. For pesticides and chemical treatments, always follow
              the product label and confirm with your local agriculture
              officer or a licensed agronomist before high-stakes decisions.
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

// ---------------- FAQ ----------------
const faqs = [
  { q: "Is AgriGPT free to use?", a: "Yes — the Kisan Free plan includes monthly crop plans, disease scans, weather intelligence, the profit calculator and limited copilot chats, free forever. Pro removes the usage limits and adds market intelligence features." },
  { q: "Are the profit numbers guaranteed?", a: "No. All cost, revenue and profit figures are AI-generated estimates based on the inputs you provide and typical conditions for your area. Actual results depend on weather, pests, soil, market prices and farming practices. Treat them as decision support, not promises." },
  { q: "How reliable is disease detection?", a: "The AI reports a confidence level with every analysis and lists alternative explanations for the same symptoms. Low-confidence scans are flagged as inconclusive. Always confirm important diagnoses with your local agriculture officer before buying treatments." },
  { q: "Where do market prices come from?", a: "Live prices come from India's Agmarknet APMC feed (via data.gov.in) and always show the source, unit and last-updated date. When live data is unavailable, AgriGPT says so rather than making up numbers." },
  { q: "Does it work in my language?", a: "The copilot answers in English, Hindi, Telugu, Tamil, Kannada and Marathi — and you can ask questions by voice. The interface is English today with more coming." },
  { q: "What do I need to get started?", a: "Just a phone. Register, describe your farm, and the AI starts working. No sensors, no hardware, no setup cost." },
  { q: "Do you sell my farm data?", a: "No. Your farm data is stored in your own account, protected by row-level security, and used only to improve your own recommendations." },
];

export function FAQ() {
  const [openIdx, setOpenIdx] = React.useState<number | null>(0);
  return (
    <section id="faq" className="pb-24">
      <div className="container max-w-3xl">
        <SectionHeading eyebrow="FAQ" title={<>Questions, <span className="text-gradient">answered</span></>} />
        <div className="space-y-3">
          {faqs.map((f, i) => (
            <motion.div key={f.q} variants={reveal} initial="hidden" whileInView="show" viewport={{ once: true }}>
              <Card>
                <button
                  className="flex w-full items-center justify-between p-5 text-left font-medium"
                  onClick={() => setOpenIdx(openIdx === i ? null : i)}
                  aria-expanded={openIdx === i}
                >
                  {f.q}
                  <span className={cn("ml-4 transition-transform", openIdx === i && "rotate-45")}>+</span>
                </button>
                {openIdx === i && (
                  <div className="px-5 pb-5 text-sm text-muted-foreground">{f.a}</div>
                )}
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------- Footer ----------------
export function Footer() {
  return (
    <footer className="border-t py-14 text-ash">
      <div className="container grid gap-10 md:grid-cols-4">
        <div>
          <div className="mb-3 flex items-center gap-2 font-bold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-leaf-500 text-onyx">
              <Sprout className="h-5 w-5" />
            </span>
            AgriGPT
          </div>
          <p className="text-sm text-ash">
            AI-powered decision support for every farmer.
          </p>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-medium">Product</h4>
          <ul className="space-y-2 text-sm text-ash">
            <li><a href="#features" className="hover:text-ivory">Features</a></li>
            <li><a href="#pricing" className="hover:text-ivory">Pricing</a></li>
            <li><Link href="/auth/register" className="hover:text-ivory">Get started</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-medium">Resources</h4>
          <ul className="space-y-2 text-sm text-ash">
            <li><a href="#how-it-works" className="hover:text-ivory">How it works</a></li>
            <li><a href="#faq" className="hover:text-ivory">FAQ</a></li>
            <li>
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/docs`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 hover:text-ivory"
              >
                API docs <BadgeCheck className="h-3 w-3" />
              </a>
            </li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-medium">Legal</h4>
          <ul className="space-y-2 text-sm text-ash">
            <li><Link href="/help" className="hover:text-ivory">Help &amp; support</Link></li>
            <li><Link href="/privacy" className="hover:text-ivory">Privacy policy</Link></li>
            <li><Link href="/terms" className="hover:text-ivory">Terms of service</Link></li>
          </ul>
        </div>
      </div>
      <div className="container mt-10 border-t border-border/60 pt-6 text-center text-xs tracking-[0.01em] text-ash/70">
        © {new Date().getFullYear()} AgriGPT. AI-generated estimates are decision support, not guarantees.
      </div>
    </footer>
  );
}
