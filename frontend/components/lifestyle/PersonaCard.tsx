import type { Persona } from "@/lib/lifestyle/types";

export function PersonaCard({ persona }: { persona: Persona }) {
  return (
    <div className="animate-pop-in relative overflow-hidden rounded-3xl bg-gray-950 p-6 text-white shadow-xl sm:p-8">
      <div
        className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 opacity-40 blur-3xl"
        aria-hidden="true"
      />
      <p className="relative text-xs font-medium uppercase tracking-[0.2em] text-indigo-300">Your Berlin lifestyle</p>
      <div className="relative mt-3 flex items-center gap-4">
        <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/10 text-4xl backdrop-blur" aria-hidden="true">
          {persona.emoji}
        </span>
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{persona.title}</h2>
      </div>
      <p className="relative mt-4 text-base leading-relaxed text-gray-200">{persona.tagline}</p>
      {persona.priorities.length > 0 && (
        <div className="relative mt-5">
          <p className="text-xs text-gray-400">What matters most to you</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {persona.priorities.map((p) => (
              <span key={p} className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-sm">
                {p}
              </span>
            ))}
          </div>
        </div>
      )}
      <p className="relative mt-5 text-xs text-gray-400">{persona.disclaimer}</p>
    </div>
  );
}
