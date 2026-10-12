export default function DashboardLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Title & subtitle skeleton */}
      <div className="space-y-2">
        <div className="h-7 w-48 rounded-lg bg-muted" />
        <div className="h-4 w-96 max-w-full rounded bg-muted/60" />
      </div>

      {/* Grid of skeleton cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="rounded-xl border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="h-4 w-20 rounded bg-muted" />
              <div className="h-6 w-6 rounded-full bg-muted/60" />
            </div>
            <div className="mt-4 h-8 w-28 rounded bg-muted" />
          </div>
        ))}
      </div>

      {/* Main card skeleton */}
      <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
        <div className="h-5 w-36 rounded bg-muted" />
        <div className="h-4 w-full rounded bg-muted/50" />
        <div className="h-4 w-5/6 rounded bg-muted/50" />
        <div className="h-32 w-full rounded-lg bg-muted/30" />
      </div>
    </div>
  );
}
