"use client";

/**
 * "Compare with…" (T9.7): pick another flat for this one from similar flats, saved flats,
 * the last search, or a pasted WohnIQ listing link. Both go into the shared compare list and
 * /compare opens.
 */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getListingDetail } from "@/lib/api";
import type { SimilarItem } from "@/lib/types";
import { euro } from "@/lib/format";
import { readSaved } from "@/lib/saved";
import { readLastSearch } from "@/lib/listing/lastSearch";
import { compareHref, idFromLink, MAX_COMPARE, readCompare, writeCompare } from "@/lib/compare/list";
import { Button } from "@/components/ui/primitives";

type Option = { id: string; title: string; line: string };

export function CompareWith({ listingId, similar, onClose }: { listingId: string; similar: SimilarItem[]; onClose: () => void }) {
  const router = useRouter();
  const [saved, setSaved] = useState<Option[] | null>(null);
  const [link, setLink] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  const [last] = useState(readLastSearch);

  useEffect(() => {
    dialog.current?.querySelector<HTMLElement>("button, input")?.focus();
    const ids = readSaved().filter((id) => id !== listingId).slice(0, 8);
    Promise.all(ids.map((id) => getListingDetail(id).then((d) => ({ id, title: d.listing.title, line: `${euro(d.listing.warmmiete_eur)} warm · ${d.listing.kiez}` })).catch(() => null))).then((xs) =>
      setSaved(xs.filter((x): x is Option => x !== null)),
    );
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close.current();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [listingId]);

  function pick(otherId: string) {
    // This flat and the chosen one first, then whatever was already in the list.
    const ids = [listingId, otherId, ...readCompare().filter((x) => x !== listingId && x !== otherId)].slice(0, MAX_COMPARE);
    writeCompare(ids);
    router.push(compareHref(ids));
  }

  const sections: { title: string; options: Option[] | null }[] = [
    { title: "Similar flats", options: similar.map((s) => ({ id: s.listing.id, title: s.listing.title, line: `${euro(s.listing.warmmiete_eur)} warm · ${s.reasons[0]}` })) },
    { title: "Your saved flats", options: saved },
    {
      title: last ? `Your last search: ${last.heading}` : "Your last search",
      options: (last?.items ?? []).filter((x) => x.id !== listingId).slice(0, 8).map((x) => ({ id: x.id, title: x.title, line: `${euro(x.warm)} warm · ${x.kiez}` })),
    },
  ];

  return (
    <div className="fixed inset-0 z-[1200] flex items-end justify-center bg-[rgba(13,19,33,0.5)] sm:items-center" onClick={onClose}>
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="compare-with-title"
        className="flex max-h-[88vh] w-full max-w-[640px] flex-col overflow-hidden rounded-t-xl bg-surface sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <h2 id="compare-with-title" className="text-[20px] font-semibold text-text">Compare with…</h2>
          <Button variant="ghost" onClick={onClose} aria-label="Close">Close</Button>
        </div>
        <div className="flex flex-col gap-5 overflow-y-auto px-5 py-4">
          {sections.map((sec) => (
            <section key={sec.title} aria-label={sec.title}>
              <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-text-muted">{sec.title}</h3>
              {sec.options === null ? (
                <div className="h-12 animate-pulse rounded-md bg-chip" />
              ) : sec.options.length === 0 ? (
                <p className="text-[14px] text-text-muted">None yet.</p>
              ) : (
                <ul className="flex flex-col divide-y divide-line rounded-md border border-line">
                  {sec.options.map((o) => (
                    <li key={o.id}>
                      <button type="button" onClick={() => pick(o.id)} className="flex min-h-tap w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-ground">
                        <span className="min-w-0">
                          <span className="block truncate text-[14.5px] font-medium text-text">{o.title}</span>
                          <span className="block truncate text-[13px] text-text-muted">{o.line}</span>
                        </span>
                        <span className="shrink-0 text-[13.5px] font-semibold text-accent">Compare</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
          <form
            className="flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const id = idFromLink(link);
              if (!id || id === listingId) return setLinkError("Paste the link of another WohnIQ listing.");
              pick(id);
            }}
          >
            <label htmlFor="compare-link" className="text-[12px] font-semibold uppercase tracking-[0.06em] text-text-muted">Or paste a WohnIQ listing link</label>
            <div className="flex gap-2">
              <input
                id="compare-link"
                value={link}
                onChange={(e) => (setLink(e.target.value), setLinkError(null))}
                placeholder="https://…/listings/…"
                className="min-h-tap min-w-0 flex-1 rounded-md border border-input px-3 text-[15px] outline-none focus:border-accent"
              />
              <Button type="submit">Compare</Button>
            </div>
            {linkError && <p role="alert" className="text-[13px] text-warn">{linkError}</p>}
          </form>
        </div>
      </div>
    </div>
  );
}
