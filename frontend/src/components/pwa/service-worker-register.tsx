"use client";

import * as React from "react";

/**
 * Registers the service worker in production builds.
 *
 * In development it does the opposite: it unregisters any worker and clears its
 * caches. `start_local.bat` serves a production build on the same origin, so a
 * worker registered there stays active when you switch to `next dev` and keeps
 * serving its cached `/_next/static` chunks — and dev chunk paths are not
 * content-hashed, so the browser runs stale modules forever.
 */
export function ServiceWorkerRegister() {
  React.useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;

    if (process.env.NODE_ENV !== "production") {
      void (async () => {
        try {
          const regs = await navigator.serviceWorker.getRegistrations();
          await Promise.all(regs.map((reg) => reg.unregister()));
          if (typeof caches !== "undefined") {
            const keys = await caches.keys();
            await Promise.all(keys.map((key) => caches.delete(key)));
          }
        } catch {
          /* best effort — dev convenience only */
        }
      })();
      return;
    }

    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  }, []);
  return null;
}
