"use client";

/**
 * Mobile bottom navigation (farmer-first): 5 primary destinations + a "More"
 * sheet for everything else. Only rendered below lg (the sidebar takes over
 * from lg up). Active state = filled pill + label, not color alone. Respects
 * safe-area insets on notched phones and never covers page content (main gets
 * matching bottom padding in the dashboard layout).
 */
import * as React from "react";
import Link from "next/link";
import {
  Camera,
  CloudRain,
  Crown,
  LayoutDashboard,
  Leaf,
  Menu,
  MessageSquareHeart,
  MoreHorizontal,
  NotebookPen,
  Sparkles,
  Sprout,
  Store,
  TrendingUp,
  Wallet,
  X,
} from "lucide-react";

import { AnimatePresence, motion } from "framer-motion";
import { useLang } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const PRIMARY = [
  { href: "/dashboard", label: "Home", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/plan", label: "Farm", icon: Sprout, exact: false },
  { href: "/dashboard/disease", label: "Health", icon: Camera, exact: false },
  { href: "/dashboard/market", label: "Market", icon: TrendingUp, exact: false },
  { href: "/dashboard/copilot", label: "Copilot", icon: MessageSquareHeart, exact: false },
];

const MORE = [
  { href: "/dashboard/weather", label: "Weather", icon: CloudRain },
  { href: "/dashboard/farm-log", label: "Farm Log", icon: NotebookPen },
  { href: "/dashboard/crops", label: "Crop Advisor", icon: Leaf },
  { href: "/dashboard/profit", label: "AI Profit Predictor", icon: Wallet },
  { href: "/dashboard/vendors", label: "Vendors Near Me", icon: Store },
  { href: "/dashboard/analytics", label: "Analytics", icon: Sparkles },
  { href: "/dashboard/subscription", label: "Subscription", icon: Crown },
];

/** True when this dashboard path should highlight the given nav item. */
function isActive(pathname: string, href: string, exact?: boolean) {
  return exact ? pathname === href : pathname.startsWith(href);
}

export function MobileBottomNav({ pathname }: { pathname: string }) {
  const { t } = useLang();
  const [moreOpen, setMoreOpen] = React.useState(false);

  // Close the More sheet whenever the route changes.
  React.useEffect(() => {
    setMoreOpen(false);
  }, [pathname]);

  const moreActive = MORE.some((m) => isActive(pathname, m.href, m.href === "/dashboard"));

  return (
    <>
      <nav
        aria-label="Main navigation"
        className="fixed inset-x-0 bottom-0 z-40 border-t bg-card/95 backdrop-blur lg:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <ul className="mx-auto flex max-w-lg items-stretch">
          {PRIMARY.map((item) => {
            const active = isActive(pathname, item.href, item.exact);
            const Icon = item.icon;
            return (
              <li key={item.href} className="flex-1">
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-[56px] flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-[10px] font-medium leading-tight transition-colors",
                    active ? "text-leaf-700" : "text-muted-foreground"
                  )}
                >
                  <motion.span
                    aria-hidden
                    layout
                    transition={{ duration: 0.18, ease: "easeOut" }}
                    className={cn(
                      "flex h-8 w-12 items-center justify-center rounded-full",
                      active ? "bg-leaf-600 text-white" : ""
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </motion.span>
                  <span className="max-w-full truncate px-0.5">{t(item.label)}</span>
                </Link>
              </li>
            );
          })}
          <li className="flex-1">
            <button
              type="button"
              onClick={() => setMoreOpen(true)}
              aria-haspopup="dialog"
              aria-expanded={moreOpen}
              className={cn(
                "flex min-h-[56px] w-full flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-[10px] font-medium leading-tight transition-colors",
                moreActive ? "text-leaf-700" : "text-muted-foreground"
              )}
            >
              <motion.span
                aria-hidden
                layout
                transition={{ duration: 0.18, ease: "easeOut" }}
                className={cn(
                  "flex h-8 w-12 items-center justify-center rounded-full",
                  moreActive ? "bg-leaf-100 text-leaf-700" : ""
                )}
              >
                <MoreHorizontal className="h-5 w-5" />
              </motion.span>
              {t("More")}
            </button>
          </li>
        </ul>
      </nav>

      {/* More — bottom sheet on mobile (section 22), large touch targets (section 10) */}
      <AnimatePresence>
        {moreOpen && (
          <motion.div
            key="more-sheet"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed inset-0 z-50 lg:hidden"
            role="dialog"
            aria-modal="true"
            aria-label="More pages"
          >
            <div
              className="absolute inset-0 bg-black/50"
              onClick={() => setMoreOpen(false)}
              aria-hidden
            />
            <motion.div
              initial={{ translateY: "100%" }}
              animate={{ translateY: 0 }}
              exit={{ translateY: "100%" }}
              transition={{ duration: 0.26, ease: "easeOut" }}
              className="absolute inset-x-0 bottom-0 mx-auto max-w-lg rounded-t-2xl border bg-card"
              style={{ paddingBottom: "calc(env(safe-area-inset-bottom) + 0.5rem)" }}
            >
              <div className="flex items-center justify-between border-b px-4 py-3">
                <p className="text-sm font-medium">{t("All pages")}</p>
                <button
                  type="button"
                  onClick={() => setMoreOpen(false)}
                  aria-label="Close menu"
                  className="flex h-11 w-11 items-center justify-center rounded-full text-muted-foreground hover:bg-accent"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <ul className="max-h-[60vh] overflow-y-auto p-2">
                {MORE.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(pathname, item.href, false);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "flex min-h-[48px] items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                          active ? "bg-leaf-600 text-white" : "text-foreground hover:bg-accent"
                        )}
                      >
                        <Icon className="h-5 w-5 shrink-0" />
                        {t(item.label)}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
