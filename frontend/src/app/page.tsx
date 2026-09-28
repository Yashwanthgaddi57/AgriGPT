import { Navbar } from "@/components/landing/navbar";
import { Hero } from "@/components/landing/hero";
import {
  Benefits,
  FAQ,
  Features,
  Footer,
  HowItWorks,
  Pricing,
  ProductDemo,
  Safety,
} from "@/components/landing/sections";

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">
        <Hero />
        <Benefits />
        <Features />
        <HowItWorks />
        <ProductDemo />
        <Pricing />
        <Safety />
        <FAQ />
      </main>
      <Footer />
    </div>
  );
}
