import type { Metadata } from "next";
import { RentCheck } from "@/components/rent/RentCheck";

export const metadata: Metadata = {
  title: "Rent check — WohnIQ",
  description:
    "Check any Berlin address against the Mietspiegel 2026 and the rent brake. Works offline; your flat's details stay in your browser.",
};

export default function RentCheckPage({ searchParams }: { searchParams?: { listing?: string } }) {
  const listing = searchParams?.listing && /^[0-9a-f-]{36}$/i.test(searchParams.listing) ? searchParams.listing : undefined;
  return (
    <div>
      <section className="no-print bg-ink text-text-on-ink">
        <div className="mx-auto max-w-page px-[18px] pb-12 pt-10 md:px-8">
          <p className="text-sm font-semibold uppercase tracking-[0.08em] text-accent-on-ink">
            Rent check · Berliner Mietspiegel 2026
          </p>
          <h1 className="mt-3 text-[36px] font-bold leading-tight tracking-[-0.03em] sm:text-[44px]">
            Is this rent fair?
          </h1>
          <p className="mt-3 max-w-xl text-[16px] leading-relaxed text-text-on-ink-muted">
            Check any of Berlin&apos;s 400,505 residential addresses against the official
            Mietspiegel 2026 and the rent brake. Works offline; your flat&apos;s details stay in
            your browser.
          </p>
        </div>
      </section>
      <RentCheck listingId={listing} />
    </div>
  );
}
