import { Sprout } from "lucide-react";

export default function RootLoading() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
      <div className="relative mb-6 flex h-20 w-20 items-center justify-center">
        {/* Glowing breathing ring */}
        <div className="absolute inset-0 animate-ping rounded-3xl bg-leaf-400/20 duration-1000" />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-leaf-700 to-leaf-500 text-white shadow-lg shadow-leaf-600/25">
          <Sprout className="h-8 w-8 animate-pulse" />
        </div>
      </div>

      <h2 className="font-display text-xl font-semibold tracking-tight text-foreground">
        Loading AgriGPT
      </h2>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        Waking up intelligent crop services and real-time market data...
      </p>

      {/* Progress track */}
      <div className="mt-6 h-1.5 w-48 overflow-hidden rounded-full bg-muted">
        <div className="h-full w-full animate-pulse rounded-full bg-leaf-500" />
      </div>

      <p className="mt-4 text-xs text-muted-foreground/80">
        Free-tier cloud servers may take ~30s to spin up from standby
      </p>
    </div>
  );
}
