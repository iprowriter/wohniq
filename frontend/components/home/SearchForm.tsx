"use client";

import { useEffect, useState } from "react";

export const SEARCH_PLACEHOLDER = "e.g. 2 rooms near Alexanderplatz, quiet, under €1,400 warm";

/**
 * The white hero search box from the design (input + accent button). Focus shows as a soft
 * light halo around the whole box (on the dark hero), not the global blue outline.
 */
export function SearchForm({
  initial = "",
  busy = false,
  onSearch,
}: {
  initial?: string;
  busy?: boolean;
  onSearch: (q: string) => void;
}) {
  const [q, setQ] = useState(initial);
  useEffect(() => setQ(initial), [initial]);
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        if (q.trim()) onSearch(q.trim());
      }}
      className="flex flex-wrap gap-2.5 rounded-[18px] bg-surface p-2.5 shadow-[0_20px_60px_rgba(0,0,0,0.35)] transition-shadow duration-200 focus-within:shadow-[0_20px_60px_rgba(0,0,0,0.35),0_0_0_5px_rgba(255,255,255,0.16)]"
    >
      <label htmlFor="hero-search" className="sr-only">
        Describe your flat
      </label>
      <input
        id="hero-search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={SEARCH_PLACEHOLDER}
        className="min-h-[52px] min-w-0 flex-[1_1_300px] bg-transparent px-4 text-[17px] text-text outline-none placeholder:text-text-faint focus-visible:outline-none"
      />
      <button
        type="submit"
        disabled={busy}
        className="inline-flex min-h-[52px] flex-[0_0_auto] items-center justify-center gap-2 rounded-md bg-accent px-6 text-base font-semibold text-white hover:bg-accent-hover disabled:opacity-60 max-sm:flex-1"
      >
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        {busy ? "Searching…" : "Search"}
      </button>
    </form>
  );
}
