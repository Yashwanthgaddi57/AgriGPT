import Link from "next/link";
import { Sprout } from "lucide-react";

export const metadata = { title: "Terms of Service" };

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <Link href="/" className="mb-8 flex items-center gap-2 font-bold">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-leaf-600 text-white">
          <Sprout className="h-4 w-4" />
        </span>
        AgriGPT
      </Link>
      <h1 className="font-display text-[28px] font-medium leading-[1.2] tracking-[0.36px]">Terms of Service</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: September 23, 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed">
        <section>
          <h2 className="text-[17px] font-medium tracking-[-0.24px]">1. The service</h2>
          <p className="mt-2 text-muted-foreground">
            AgriGPT provides AI-assisted agricultural guidance: crop recommendations, disease
            screening, profit projections, market intelligence, and weather advisories.
          </p>
        </section>

        <section>
          <h2 className="text-[17px] font-medium tracking-[-0.24px]">2. Not professional advice</h2>
          <p className="mt-2 text-muted-foreground">
            AI outputs are <strong>decision-support estimates</strong>, not guarantees. Market
            prices are official Agmarknet observations and forecasts are model-based; actual
            yields, prices, and outcomes depend on factors beyond our control. Verify important
            actions (planting, selling, treatment) with your local agriculture officer or agronomist.
          </p>
        </section>

        <section>
          <h2 className="text-[17px] font-medium tracking-[-0.24px]">3. Your account</h2>
          <p className="mt-2 text-muted-foreground">
            Keep your credentials secure. You are responsible for activity under your account. You
            must provide accurate farm information for quality advice.
          </p>
        </section>

        <section>
          <h2 className="text-[17px] font-medium tracking-[-0.24px]">4. Acceptable use</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
            <li>Don't upload images or content you don't have rights to.</li>
            <li>Don't attempt to abuse, scrape, or overload the service.</li>
            <li>Don't use the service for unlawful activity.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-[17px] font-medium tracking-[-0.24px]">5. Availability &amp; changes</h2>
          <p className="mt-2 text-muted-foreground">
            We aim for high availability but the service is provided &quot;as is&quot; without
            warranties. Features, data sources, and pricing may change; material changes to these
            terms will be communicated in-app.
          </p>
        </section>

        <section>
          <h2 className="text-[17px] font-medium tracking-[-0.24px]">6. Limitation of liability</h2>
          <p className="mt-2 text-muted-foreground">
            To the maximum extent permitted by law, AgriGPT is not liable for indirect or
            consequential losses (including crop or income losses) arising from use of the service.
          </p>
        </section>

        <section>
          <h2 className="text-[17px] font-medium tracking-[-0.24px]">7. Contact</h2>
          <p className="mt-2 text-muted-foreground">
            Questions: <span className="font-medium">support@agrigpt.app</span>
          </p>
        </section>
      </div>
    </div>
  );
}
