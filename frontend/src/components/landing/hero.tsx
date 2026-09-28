"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Camera,
  LineChart,
  ScanSearch,
  Sprout,
  Wallet,
  CloudSun,
  MessageCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, delay: i * 0.1 },
  }),
};

// Mock farm-plan summary shown in the hero — illustrative example data,
// labeled as such so no visitor mistakes it for a performance claim.
const PLAN_PREVIEW = {
  crop: "Groundnut",
  cost: "₹31,200",
  revenue: "₹58,900",
  profit: "₹27,700",
  duration: "110 days",
  risk: "Medium",
};

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-28 pb-16 sm:pt-36 sm:pb-24">
      <div className="grid-pattern absolute inset-0 [mask-image:radial-gradient(ellipse_60%_50%_at_50%_40%,#000,transparent)]" />
      <div className="absolute -top-40 left-1/2 h-[480px] w-[820px] -translate-x-1/2 rounded-full bg-leaf-50 blur-3xl" />

      <div className="container relative grid items-center gap-12 lg:grid-cols-2">
        <div className="flex flex-col items-center text-center lg:items-start lg:text-left">
          <motion.div variants={fadeUp} initial="hidden" animate="show" custom={0}>
            <Badge variant="success" className="mb-6 gap-1.5 px-3 py-1 text-sm">
              <Sprout className="h-3.5 w-3.5" />
              AI copilot for farmers
            </Badge>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={1}
            className="max-w-2xl font-display text-[36px] font-semibold leading-[1.1] tracking-[-0.01em] sm:text-[48px] xl:text-[56px]"
          >
            Your AI Copilot for{" "}
            <span className="text-gradient">Smarter Farming</span>
          </motion.h1>

          <motion.p
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={2}
            className="mt-6 max-w-xl text-[20px] font-normal tracking-[-0.24px] text-muted-foreground"
          >
            Know what to grow. Know what it may cost. Know what you could earn.
            Know what to do next.
          </motion.p>

          <motion.div
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={3}
            className="mt-8 flex w-full flex-col gap-3 sm:w-auto sm:flex-row"
          >
            <Button size="lg" className="gap-2" asChild>
              <Link href="/auth/register">
                Plan My Farm <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" className="gap-2" asChild>
              <Link href="/auth/register">
                <Camera className="h-4 w-4" /> Analyze My Crop
              </Link>
            </Button>
          </motion.div>

          <motion.p
            variants={fadeUp}
            initial="hidden"
            animate="show"
            custom={4}
            className="mt-6 max-w-lg text-xs leading-relaxed text-muted-foreground"
          >
            AgriGPT provides AI-generated estimates and decision support — not
            guarantees. Verify high-stakes decisions with your local
            agriculture officer.
          </motion.p>
        </div>

        {/* Mock farm-plan summary card */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.35 }}
          className="relative mx-auto w-full max-w-md"
        >
          <div className="rounded-2xl bg-card p-5 sm:p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground">
                  Example farm plan
                </p>
                <p className="font-display text-[20px] font-semibold tracking-[-0.24px]">2.5 acres · Kharif</p>
              </div>
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-leaf-500 text-onyx">
                <Sprout className="h-5 w-5" />
              </span>
            </div>

            <div className="mb-4 rounded-xl border border-leaf-200 bg-leaf-50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium capitalize">{PLAN_PREVIEW.crop}</span>
                <Badge variant="warning" className="text-[10px]">
                  Risk: {PLAN_PREVIEW.risk}
                </Badge>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Est. cost</p>
                  <p className="text-sm font-medium">{PLAN_PREVIEW.cost}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Est. revenue</p>
                  <p className="text-sm font-medium">{PLAN_PREVIEW.revenue}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Est. profit</p>
                  <p className="text-sm font-medium text-leaf-600">{PLAN_PREVIEW.profit}</p>
                </div>
              </div>
              <p className="mt-2 text-[10px] text-muted-foreground">
                AI-generated estimate · {PLAN_PREVIEW.duration} duration · based on provided inputs
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <ScanSearch className="h-3.5 w-3.5 text-amber-600" /> Crop health scans
              </span>
              <span className="flex items-center gap-1.5">
                <LineChart className="h-3.5 w-3.5 text-leaf-600" /> Market prices
              </span>
              <span className="flex items-center gap-1.5">
                <CloudSun className="h-3.5 w-3.5 text-sky-600" /> Weather alerts
              </span>
              <span className="flex items-center gap-1.5">
                <MessageCircle className="h-3.5 w-3.5 text-leaf-600" /> Copilot in your language
              </span>
            </div>
          </div>

          {/* floating accent card */}
          <motion.div
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.7 }}
            className="absolute -bottom-5 -left-4 hidden rounded-xl bg-card p-3 sm:flex sm:items-center sm:gap-2"
          >
            <Wallet className="h-4 w-4 text-leaf-600" />
            <span className="text-xs font-medium">Profit calculator, built in</span>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
