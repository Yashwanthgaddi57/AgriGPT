import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/* Mercury badges: pill-shaped tags. Status colors stay muted tints of the
   semantic hue — never competing with the leaf accent. */
const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-[0.01em] transition-colors focus:outline-none",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/20 text-leaf-700",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive/15 text-red-700",
        outline: "border-border text-foreground",
        success: "border-transparent bg-leaf-100 text-leaf-800",
        warning: "border-transparent bg-amber-100 text-amber-700",
        danger: "border-transparent bg-red-100 text-red-700",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  // <span> (not <div>) so Badge is valid inside <p> without hydration errors
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
