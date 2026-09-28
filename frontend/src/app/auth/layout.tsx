import Link from "next/link";
import { Sprout } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <div className="grid-pattern absolute inset-0 [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,#000,transparent)]" />
      <div className="absolute -top-32 left-1/2 h-[420px] w-[720px] -translate-x-1/2 rounded-full bg-leaf-200/40 blur-3xl" />
      <div className="relative w-full max-w-md">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2 font-bold">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-leaf-600 text-white">
            <Sprout className="h-5 w-5" />
          </span>
          <span className="text-xl">AgriGPT</span>
        </Link>
        {children}
      </div>
    </div>
  );
}
