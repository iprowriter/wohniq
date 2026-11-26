import type { Persona } from "@/lib/lifestyle/types";

export function PersonaCard({ persona }: { persona: Persona }) {
  return (
    <div className="relative overflow-hidden rounded-lg bg-ink p-6 text-white shadow-xl sm:p-8">
      <p className="relative text-xs font-medium uppercase tracking-[0.2em] text-text-on-ink-muted">Your Berlin lifestyle</p>
      <div className="relative mt-3">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{persona.title}</h2>
      </div>
      <p className="relative mt-4 text-base leading-relaxed text-text-on-ink-soft">{persona.tagline}</p>
      {persona.priorities.length > 0 && (
        <div className="relative mt-5">
          <p className="text-xs text-text-muted">What matters most to you</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {persona.priorities.map((p) => (
              <span key={p} className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-sm">
                {p}
              </span>
            ))}
          </div>
        </div>
      )}
      <p className="relative mt-5 text-xs text-text-muted">{persona.disclaimer}</p>
    </div>
  );
}
