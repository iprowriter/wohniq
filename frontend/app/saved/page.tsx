"use client";

/**
 * Saved flats and saved searches, kept in this browser (no account, T9.7, ADR-0020).
 * Download / import moves them to another browser as one small file.
 */

import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { getListingDetail } from "@/lib/api";
import type { ListingOut } from "@/lib/types";
import { useSaved } from "@/lib/useSaved";
import { useCompare } from "@/lib/compare/useCompare";
import { readSaved, writeSaved, MAX_SAVED } from "@/lib/saved";
import { useSavedSearches } from "@/lib/useSavedSearches";
import { buildExport, mergeImport, readSearches, removeSearch, renameSearch, searchHref, writeSearches, type SavedSearch } from "@/lib/savedSearches";
import { SORT_LABELS } from "@/lib/results";
import { FeaturedCard } from "@/components/FeaturedCard";
import { Button, ButtonLink } from "@/components/ui/primitives";

type Tab = "flats" | "searches";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export default function SavedPage() {
  return (
    <Suspense fallback={null}>
      <SavedInner />
    </Suspense>
  );
}

function SavedInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: Tab = params.get("tab") === "searches" ? "searches" : "flats";
  const saved = useSaved();
  const { searches } = useSavedSearches();
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function setTab(t: Tab) {
    router.replace(t === "flats" ? pathname : `${pathname}?tab=searches`, { scroll: false });
  }

  function download() {
    const blob = new Blob([JSON.stringify(buildExport(readSaved(), readSearches()), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `wohniq-saved-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function importFile(file: File) {
    try {
      if (file.size > 512_000) throw new Error("This file is too large to be a WohnIQ saved-items file.");
      const out = mergeImport(await file.text(), readSaved(), readSearches(), MAX_SAVED);
      writeSaved(out.flats);
      writeSearches(out.searches);
      const parts = [`${out.addedFlats} flat${out.addedFlats === 1 ? "" : "s"}`, `${out.addedSearches} search${out.addedSearches === 1 ? "" : "es"}`];
      setMessage({ text: `Imported ${parts.join(" and ")}. Nothing you had was changed.`, ok: true });
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : "Import failed.", ok: false });
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const tabClass = (on: boolean) =>
    `min-h-tap rounded-md px-4 text-[15px] ${on ? "bg-ink font-semibold text-white" : "text-text-body hover:bg-chip"}`;

  return (
    <div className="mx-auto flex max-w-page flex-col gap-6 px-[18px] py-10 md:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[36px] font-bold tracking-tight text-text">Saved</h1>
          <p className="mt-1 text-[15px] text-text-muted">Kept in this browser only. No account needed.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={download} disabled={!saved.ids.length && !searches.length}>
            Download my saved items
          </Button>
          <Button variant="outline" onClick={() => fileRef.current?.click()}>Import</Button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="sr-only"
            aria-label="Import saved items file"
            data-testid="import-file"
            onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])}
          />
        </div>
      </div>
      {message && (
        <p role="status" data-testid="saved-message" className={`rounded-md px-4 py-3 text-[14px] ${message.ok ? "bg-ok-bg text-ok" : "bg-warn-bg text-warn"}`}>
          {message.text}
        </p>
      )}

      <div role="tablist" aria-label="Saved items" className="flex gap-1">
        <button type="button" role="tab" aria-selected={tab === "flats"} className={tabClass(tab === "flats")} onClick={() => setTab("flats")}>
          Flats ({saved.ids.length})
        </button>
        <button type="button" role="tab" aria-selected={tab === "searches"} className={tabClass(tab === "searches")} onClick={() => setTab("searches")}>
          Searches ({searches.length})
        </button>
      </div>

      {tab === "flats" ? <Flats ids={saved.ids} onRemove={saved.toggle} /> : <Searches searches={searches} />}
    </div>
  );
}

function Flats({ ids, onRemove }: { ids: string[]; onRemove: (id: string) => void }) {
  const compare = useCompare();
  const [listings, setListings] = useState<Record<string, ListingOut | null>>({});
  useEffect(() => {
    const missing = ids.filter((id) => !(id in listings));
    if (!missing.length) return;
    Promise.all(
      missing.map((id) =>
        getListingDetail(id)
          .then((d) => [id, { ...d.listing, rent: d.rent, location: d.location }] as const)
          .catch(() => [id, null] as const),
      ),
    ).then((pairs) => setListings((prev) => ({ ...prev, ...Object.fromEntries(pairs) })));
  }, [ids, listings]);

  if (!ids.length)
    return (
      <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-text-body">
        <p>No saved flats yet. Press <strong>Save</strong> on a search result or a listing to keep it here.</p>
        <ButtonLink href="/" className="mt-4">Search flats</ButtonLink>
      </div>
    );
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="saved-list">
      {ids.map((id) => {
        const l = listings[id];
        return (
          <li key={id} className="flex flex-col gap-2">
            {l ? (
              <FeaturedCard listing={l} />
            ) : l === null ? (
              <div className="rounded-lg border border-line bg-surface p-4 text-[14px] text-text-muted">This listing is no longer available.</div>
            ) : (
              <div className="h-64 animate-pulse rounded-lg bg-chip" />
            )}
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                aria-pressed={compare.has(id)}
                disabled={!compare.has(id) && compare.full}
                onClick={() => compare.toggle(id)}
              >
                {compare.has(id) ? "Comparing" : "Compare"}
              </Button>
              <Button variant="outline" onClick={() => onRemove(id)}>Remove</Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Searches({ searches }: { searches: SavedSearch[] }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirmAll, setConfirmAll] = useState(false);
  const change = (fn: (s: SavedSearch[]) => SavedSearch[]) => writeSearches(fn(readSearches()));

  if (!searches.length)
    return (
      <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-text-body">
        <p>No saved searches yet. Run a search and press <strong>Save search</strong> above the results.</p>
        <ButtonLink href="/" className="mt-4">Search flats</ButtonLink>
      </div>
    );
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col divide-y divide-line rounded-lg border border-line bg-surface" data-testid="saved-searches">
        {searches.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-4" data-testid="saved-search">
            <div className="min-w-0 flex-1">
              {editing === s.id ? (
                <form
                  className="flex flex-wrap gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    change((l) => renameSearch(l, s.id, draft));
                    setEditing(null);
                  }}
                >
                  <input
                    autoFocus
                    value={draft}
                    maxLength={80}
                    onChange={(e) => setDraft(e.target.value)}
                    aria-label="Name of this saved search"
                    className="min-h-tap min-w-0 flex-1 rounded-md border border-input px-3 text-[15px] outline-none focus:border-accent"
                  />
                  <Button type="submit">Save name</Button>
                  <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                </form>
              ) : (
                <>
                  <p className="truncate text-[16px] font-semibold text-text">{s.name}</p>
                  {s.name !== s.q && <p className="truncate text-[14px] text-text-body">&ldquo;{s.q}&rdquo;</p>}
                  <p className="text-[13px] text-text-muted">
                    {[s.fair && "only fair rents", s.sort !== "fit" && SORT_LABELS[s.sort].toLowerCase(), s.budget && `budget €${s.budget}`]
                      .filter(Boolean)
                      .join(" · ")}
                    {(s.fair || s.sort !== "fit" || s.budget) && " · "}
                    Saved {day(s.savedAt)} · last run {day(s.lastRunAt)} · {s.lastCount} result{s.lastCount === 1 ? "" : "s"}
                  </p>
                </>
              )}
            </div>
            {editing !== s.id && (
              <div className="flex flex-wrap gap-2">
                <ButtonLink href={searchHref(s)}>Run</ButtonLink>
                <Button variant="outline" onClick={() => (setEditing(s.id), setDraft(s.name))} aria-label={`Rename ${s.name}`}>
                  Rename
                </Button>
                <Button variant="ghost" onClick={() => change((l) => removeSearch(l, s.id))} aria-label={`Delete ${s.name}`}>
                  Delete
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-2">
        {confirmAll ? (
          <>
            <span className="text-[14px] text-text-body">Delete all {searches.length} saved searches?</span>
            <Button variant="dark" onClick={() => (writeSearches([]), setConfirmAll(false))}>Yes, delete all</Button>
            <Button variant="ghost" onClick={() => setConfirmAll(false)}>Keep them</Button>
          </>
        ) : (
          <Button variant="ghost" onClick={() => setConfirmAll(true)}>Delete all searches</Button>
        )}
      </div>
      <p className="text-[13px] text-text-muted">
        Running a saved search again shows which flats are new since last time. <Link href="/" className="underline">New search</Link>
      </p>
    </div>
  );
}
