import type { Metadata } from "next";
import { ButtonLink } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Rent check — WohnIQ" };

/** Placeholder until the rent check page is built (T9.4). The backend is ready. */
export default function RentCheckPage() {
  return (
    <div>
      <section className="bg-ink text-text-on-ink">
        <div className="mx-auto max-w-page px-[18px] pb-14 pt-10 md:px-8">
          <p className="text-sm font-semibold uppercase tracking-[0.08em] text-accent-on-ink">
            Rent check · Berliner Mietspiegel 2026
          </p>
          <h1 className="mt-3 text-[44px] font-bold leading-tight tracking-[-0.03em]">
            Is this rent fair?
          </h1>
          <p className="mt-3 max-w-xl text-text-on-ink-muted">
            Check any of Berlin&apos;s 400,505 residential addresses against the official
            Mietspiegel 2026 and the rent brake. This page is being built; until then every
            listing already shows its rent check.
          </p>
        </div>
      </section>
      <div className="mx-auto max-w-page px-[18px] py-10 md:px-8">
        <ButtonLink href="/">Search flats</ButtonLink>
      </div>
    </div>
  );
}
