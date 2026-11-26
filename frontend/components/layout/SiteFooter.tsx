import Link from "next/link";
import { NAV } from "@/lib/nav";

/** The Berlin Ink footer: sections, the sample-data and sources notice, offline promise. */
export function SiteFooter() {
  return (
    <footer className="mx-auto mt-16 w-full max-w-page px-[18px] pb-10 md:px-8">
      <div className="flex flex-col gap-4 border-t border-line-strong pt-6 text-[13px] leading-relaxed text-text-muted">
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-1">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="inline-flex min-h-tap items-center hover:text-text">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex flex-wrap justify-between gap-4">
          <p className="max-w-[760px]">
            Sample listings are synthetic. Data: Berliner Mietspiegel 2026, Senate open data
            (Geoportal Berlin), Polizei Berlin, Unfallatlas, VBB timetables, © OpenStreetMap
            contributors. Rent results are estimates, not legal advice.
          </p>
          <p>Works offline · No account needed</p>
        </div>
      </div>
    </footer>
  );
}
