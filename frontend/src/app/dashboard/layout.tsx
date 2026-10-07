"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";
import {
  Bell,
  BellRing,
  Crown,
  LayoutDashboard,
  Leaf,
  LineChart,
  LogOut,
  Menu,
  MessageSquareHeart,
  NotebookPen,
  ScanSearch,
  Sparkles,
  Sprout,
  Store,
  TrendingUp,
  User,
  Wallet,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MobileBottomNav } from "@/components/dashboard/mobile-nav";
import { PageAnimatePresence, PageTransition } from "@/components/page-transition";
import { useAuth } from "@/contexts/auth-context";
import {
  useMarkNotificationsRead,
  useMyLocation,
  useNotifications,
} from "@/hooks/use-api";
import { LangSwitch, useLang } from "@/lib/i18n";
import { formatLocationLabel } from "@/lib/location-label";
import { cn, formatDate } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "My Farm", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/plan", label: "Plan My Farm", icon: Sprout },
  { href: "/dashboard/disease", label: "Crop Health", icon: ScanSearch },
  { href: "/dashboard/market", label: "Market", icon: TrendingUp },
  { href: "/dashboard/weather", label: "Weather", icon: LineChart },
  { href: "/dashboard/copilot", label: "Ask AgriGPT", icon: MessageSquareHeart },
  { href: "/dashboard/farm-log", label: "Farm Log", icon: NotebookPen },
  { href: "/dashboard/crops", label: "Crop Advisor", icon: Leaf },
  { href: "/dashboard/profit", label: "AI Profit Predictor", icon: Wallet },
  { href: "/dashboard/vendors", label: "Nearby Agri Services", icon: Store },
  { href: "/dashboard/analytics", label: "Analytics", icon: Sparkles },
  { href: "/dashboard/subscription", label: "Subscription", icon: Crown },
];

function NotificationBell() {
  const { data } = useNotifications();
  const [open, setOpen] = React.useState(false);
  const markRead = useMarkNotificationsRead();
  const { t } = useLang();
  const unread = data?.unread_count ?? 0;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <button
        onClick={() => {
          setOpen(true);
          if (unread > 0) {
            const ids = (data?.items ?? []).filter((n) => !n.is_read).map((n) => n.id);
            if (ids.length) markRead.mutate(ids);
          }
        }}
        className="relative rounded-full p-2.5 hover:bg-accent"
        aria-label="Notifications"
      >
        {unread > 0 ? <BellRing className="h-5 w-5 text-leaf-600" /> : <Bell className="h-5 w-5" />}
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unread}
          </span>
        )}
      </button>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("Notifications")}</DialogTitle>
          <DialogDescription>{t("Weather, disease, market and profit alerts")}</DialogDescription>
        </DialogHeader>
        <div className="max-h-80 space-y-2 overflow-y-auto">
          {(data?.items ?? []).length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">{t("No notifications yet.")}</p>
          )}
          {(data?.items ?? []).map((n) => (
            <div key={n.id} className="rounded-lg border p-3">
              <div className="mb-1 flex items-center justify-between">
                <Badge
                  variant={
                    n.type === "disease" ? "danger" : n.type === "market" ? "warning" : "success"
                  }
                >
                  {n.type}
                </Badge>
                <span className="text-xs text-muted-foreground">{formatDate(n.created_at)}</span>
              </div>
              <p className="text-sm font-medium">{n.title}</p>
              <p className="text-sm text-muted-foreground">{n.body}</p>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, initialized, logout } = useAuth();
  const { t } = useLang();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  // Live farm location — the auth profile is fetched once, so read the
  // resolver instead to reflect a location the farmer just allowed/saved.
  const { data: myLocation } = useMyLocation();
  const locationLabel = formatLocationLabel(myLocation, user, null);

  React.useEffect(() => {
    if (initialized && !loading && !user) router.replace("/auth/login");
  }, [initialized, loading, user, router]);

  // Farm-first onboarding: new accounts (no farm size recorded yet) are sent
  // through the onboarding wizard once. Returning users pass straight through.
  const onboardingCheckDone = React.useRef(false);
  React.useEffect(() => {
    if (!initialized || loading || !user || onboardingCheckDone.current) return;
    onboardingCheckDone.current = true;
    const isOnboarding = pathname === "/dashboard/onboarding";
    const needsOnboarding = !user.farm_size_acres && !localStorage.getItem("agrigpt-onboarded");
    if (needsOnboarding && !isOnboarding) {
      router.replace("/dashboard/onboarding");
    } else if (!needsOnboarding) {
      localStorage.setItem("agrigpt-onboarded", "1");
    }
  }, [initialized, loading, user, pathname, router]);

  if (!initialized || (loading && !user)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-leaf-200 border-t-leaf-600" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card transition-transform lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center justify-between border-b px-5">
          <Link href="/dashboard" className="flex items-center gap-2 font-bold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-leaf-100 text-leaf-700">
              <Sprout />
            </span>
            AgriGPT
          </Link>
          <button className="lg:hidden" onClick={() => setSidebarOpen(false)} aria-label="Close menu">
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {nav.map((item) => (
            <NavLink key={item.href} {...item} label={t(item.label)} onNavigate={() => setSidebarOpen(false)} />
          ))}
        </nav>
        <div className="border-t p-3">
          <Link
            href="/dashboard/profile"
            className="mb-2 flex items-center gap-3 rounded-lg p-2 hover:bg-accent"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-leaf-100 text-leaf-700">
              <User className="h-4 w-4" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{user.name}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {locationLabel || "Set location"}
              </span>
            </span>
          </Link>
          <Button variant="ghost" className="w-full justify-start gap-2" onClick={() => logout()}>
            <LogOut className="h-4 w-4" /> {t("Sign out")}
          </Button>
        </div>
      </aside>

      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/80 px-4 backdrop-blur-xl sm:px-6">
          <button className="lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden items-center gap-2 text-sm text-muted-foreground lg:flex">
            {locationLabel ? (
              <span className="max-w-[280px] truncate" title={locationLabel}>📍 {locationLabel}</span>
            ) : (
              <span>📍 Set location</span>
            )}
            <span aria-hidden>·</span>
            <span>{user.farm_size_acres} acres</span>
          </div>
          <div className="flex items-center gap-2">
            <LangSwitch />
            <NotificationBell />
          </div>
        </header>
        <main className="flex-1 p-4 pb-24 sm:p-6 lg:pb-6">
          <PageAnimatePresence>
            <PageTransition key={pathname}>{children}</PageTransition>
          </PageAnimatePresence>
        </main>
      </div>

      {/* Mobile bottom navigation — primary actions 1 tap away (prompt §4) */}
      <MobileBottomNav pathname={pathname} />
    </div>
  );
}

function NavLink({
  href,
  label,
  icon: Icon,
  exact,
  onNavigate,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  onNavigate: () => void;
}) {
  const pathname = usePathname();
  const active = exact ? pathname === href : pathname.startsWith(href);
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active ? "bg-leaf-600 text-white shadow" : "text-muted-foreground hover:bg-accent hover:text-foreground"
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}
