import Link from "next/link";
import { LIFESTYLE_FACTS, LIFESTYLE_PATH } from "@/lib/lifestyle/marketing";

// Decorative "heat map" motif: a grid of Kiez tiles, darker = weaker match.
// Purely illustrative — no real scores, so it never goes stale and costs no API call.
const TILE_SHADES = ["#1e1b4b", "#312e81", "#4338ca", "#6366f1", "#c084fc"];
const TILES = [
  0, 1, 1, 2, 1, 0, 0, 1, 2, 3, 2, 1, 1, 2, 3, 4, 3, 2, 0, 2, 4, 4, 3, 1, 1, 2, 3, 3, 2, 1, 0, 1, 2, 1, 1, 0,
];

const FACTS = [
  { value: LIFESTYLE_FACTS.areas, label: "Berlin areas scored" },
  { value: LIFESTYLE_FACTS.factors, label: "lifestyle factors" },
  { value: LIFESTYLE_FACTS.sources, label: "official & open data sources" },
];

/** Homepage marketing card for Lifestyle Match (spans the full width of the feature grid). */
export function LifestyleFeatureCard() {
  return (
    <section
      aria-labelledby="lifestyle-card-title"
      className="relative overflow-hidden rounded-3xl bg-gray-950 text-white shadow-xl shadow-indigo-950/20 sm:col-span-2"
    >
      <div className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-indigo-600/30 blur-3xl" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 right-10 h-72 w-72 rounded-full bg-fuchsia-600/25 blur-3xl" aria-hidden="true" />

      <div className="relative grid gap-8 p-7 sm:p-10 md:grid-cols-[1.25fr_1fr] md:items-center">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-indigo-200">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" aria-hidden="true" />
            New · Lifestyle Match
          </span>
          <h2 id="lifestyle-card-title" className="mt-4 text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
            Tell us how you live.{" "}
            <span className="bg-gradient-to-r from-indigo-300 via-fuchsia-300 to-indigo-300 bg-clip-text text-transparent">
              We&apos;ll find your Kiez.
            </span>
          </h2>
          <p className="mt-4 max-w-lg text-base leading-relaxed text-gray-300">
            Quiet streets or buzzing nights, a short ride to campus, parks for the kids — answer a few playful
            questions and we rank every Berlin neighbourhood for you, with the data behind each suggestion.
          </p>

          <dl className="mt-6 grid max-w-lg grid-cols-3 gap-3">
            {FACTS.map((f) => (
              // dt before dd in the DOM (label, then value); shown value-first.
              <div key={f.label} className="flex flex-col-reverse rounded-2xl border border-white/10 bg-white/5 px-3 py-3">
                <dt className="text-xs leading-snug text-gray-400">{f.label}</dt>
                <dd className="text-2xl font-bold tabular-nums">{f.value}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-7 flex flex-wrap items-center gap-4">
            <Link
              href={LIFESTYLE_PATH}
              className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-fuchsia-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-fuchsia-900/40 transition hover:shadow-xl hover:shadow-fuchsia-900/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-fuchsia-300 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950"
            >
              Find my neighbourhood
              <span className="transition-transform group-hover:translate-x-1" aria-hidden="true">
                →
              </span>
            </Link>
            <p className="flex items-center gap-1.5 text-xs text-gray-400">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <rect x="4" y="11" width="16" height="10" rx="2" />
                <path d="M8 11V7a4 4 0 018 0v4" />
              </svg>
              No sign-up · answers never stored
            </p>
          </div>
        </div>

        {/* ── Decorative preview ── */}
        <div className="relative hidden md:block" aria-hidden="true">
          <div className="grid grid-cols-6 gap-1.5 rounded-3xl border border-white/10 bg-white/5 p-4">
            {TILES.map((shade, i) => (
              <span
                key={i}
                className="aspect-square rounded-md transition-transform duration-300 hover:scale-110"
                style={{
                  background: TILE_SHADES[shade],
                  boxShadow: shade === 4 ? "0 0 18px rgba(192,132,252,.55)" : undefined,
                }}
              />
            ))}
          </div>
          <div className="absolute -bottom-5 -left-6 w-56 rotate-[-3deg] rounded-2xl border border-white/10 bg-gray-900/95 p-4 shadow-2xl backdrop-blur">
            <p className="text-[10px] uppercase tracking-[0.2em] text-indigo-300">Your Berlin lifestyle</p>
            <p className="mt-1.5 flex items-center gap-2 font-semibold">
              <span className="text-2xl">🌳</span> The Green Retreater
            </p>
            <div className="mt-2 flex flex-wrap gap-1">
              {["Quiet", "Green space", "Water & nature"].map((p) => (
                <span key={p} className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-gray-200">
                  {p}
                </span>
              ))}
            </div>
          </div>
          <div className="absolute -right-3 -top-4 flex gap-1.5 rotate-[4deg]">
            {["🎓", "💼", "👨‍👩‍👧", "🎨"].map((e) => (
              <span key={e} className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-gray-900 text-lg shadow-lg">
                {e}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
