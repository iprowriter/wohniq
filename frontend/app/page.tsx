"use client";

import { useState } from "react";
import { search } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import { CriteriaChips } from "@/components/CriteriaChips";
import { ResultCard } from "@/components/ResultCard";

const EXAMPLE =
  "I work near Alexanderplatz, budget €1,500, quiet neighborhood, good transport, cafes nearby";

export default function Home() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSearch(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      setData(await search(trimmed));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <header className="mb-6">
        <h1 className="text-2xl font-medium">WohnIQ</h1>
        <p className="text-sm text-gray-500">AI-assisted apartment search for Berlin.</p>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void runSearch(query);
        }}
        className="flex gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Describe the flat you want…"
          className="flex-1 rounded-full border border-gray-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-gray-400"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-full bg-gray-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      <button
        type="button"
        onClick={() => {
          setQuery(EXAMPLE);
          void runSearch(EXAMPLE);
        }}
        className="mt-2 text-xs text-gray-400 hover:text-gray-600"
      >
        Try an example →
      </button>

      {error && (
        <p className="mt-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      )}

      {data && (
        <section className="mt-6">
          <div className="mb-3">
            <CriteriaChips criteria={data.criteria} />
          </div>
          <p className="mb-3 text-sm text-gray-500">
            {data.results.length} result{data.results.length === 1 ? "" : "s"} · ranked by fit
          </p>
          <div className="space-y-4">
            {data.results.map((item) => (
              <ResultCard key={item.listing.id} item={item} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
