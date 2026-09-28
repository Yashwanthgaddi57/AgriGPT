"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import { AuthProvider } from "@/contexts/auth-context";
import { LangProvider } from "@/lib/i18n";
import { Toaster } from "@/components/ui/toaster";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Backend caches aggressively (1h ticker, 30min weather); the UI
            // can safely trust data for a couple of minutes per query.
            staleTime: 2 * 60 * 1000,
            gcTime: 30 * 60 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <LangProvider>
        <AuthProvider>
          {children}
          <Toaster />
        </AuthProvider>
      </LangProvider>
    </QueryClientProvider>
  );
}
