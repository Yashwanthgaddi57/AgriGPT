import Link from "next/link";
import { Sprout } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-leaf-600 text-white">
        <Sprout className="h-8 w-8" />
      </span>
      <div>
        <h1 className="font-display text-[28px] font-medium tracking-[0.36px]">Page not found</h1>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">
          The field you're looking for doesn't exist or has been harvested. Let's get you back to
          familiar ground.
        </p>
      </div>
      <div className="flex gap-3">
        <Button asChild>
          <Link href="/dashboard">Go to dashboard</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/">Home</Link>
        </Button>
      </div>
    </div>
  );
}
