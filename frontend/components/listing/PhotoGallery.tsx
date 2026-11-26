"use client";

/**
 * Listing photos. Desktop: one large photo and up to four small ones. Phone: a swipeable
 * strip with a counter and back/share buttons on top. Any photo opens the viewer (arrow
 * keys, Escape; focus returns to the photo that opened it).
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { PhotoOut } from "@/lib/types";
import { ListingPhoto } from "@/components/ListingPhoto";

const ROOM = (t: string) => t.replace(/_/g, " ");

export function PhotoGallery({
  photos,
  title,
  backHref,
  onShare,
}: {
  photos: PhotoOut[];
  title: string;
  backHref: string;
  onShare: () => void;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const [slide, setSlide] = useState(0);
  const opener = useRef<HTMLElement | null>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => {
    setOpen(null);
    opener.current?.focus();
  }, []);

  useEffect(() => {
    if (open === null) return;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "ArrowLeft") setOpen((i) => (i !== null && i > 0 ? i - 1 : i));
      if (e.key === "ArrowRight") setOpen((i) => (i !== null && i < photos.length - 1 ? i + 1 : i));
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, photos.length, close]);

  function openAt(i: number, el: HTMLElement) {
    opener.current = el;
    setOpen(i);
  }

  const tile = (i: number, cls: string) => (
    <button
      key={i}
      type="button"
      onClick={(e) => openAt(i, e.currentTarget)}
      className={`relative overflow-hidden bg-placeholder ${cls}`}
      aria-label={`Open photo ${i + 1} of ${photos.length}: ${ROOM(photos[i].room_type)}`}
    >
      <ListingPhoto
        url={photos[i].url}
        alt=""
        className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 hover:scale-[1.02]"
        placeholderClassName="absolute inset-0 h-full w-full bg-placeholder"
      />
    </button>
  );

  return (
    <>
      {/* Desktop grid */}
      <div className="hidden h-[440px] grid-cols-4 grid-rows-2 gap-2 overflow-hidden rounded-xl md:grid" data-testid="photo-grid">
        {photos.length === 0 && <div className="col-span-4 row-span-2 bg-placeholder" />}
        {photos[0] && tile(0, "col-span-2 row-span-2")}
        {photos.slice(1, 5).map((_, k) => tile(k + 1, ""))}
      </div>

      {/* Phone strip */}
      <div className="relative -mx-[18px] md:hidden">
        <div
          className="flex h-[300px] snap-x snap-mandatory overflow-x-auto"
          onScroll={(e) => {
            const el = e.currentTarget;
            setSlide(Math.round(el.scrollLeft / el.clientWidth));
          }}
          aria-label={`Photos of ${title}`}
        >
          {(photos.length ? photos : [null]).map((p, i) =>
            p ? (
              <button
                key={i}
                type="button"
                onClick={(e) => openAt(i, e.currentTarget)}
                className="relative h-full w-full shrink-0 snap-center bg-placeholder"
                aria-label={`Open photo ${i + 1} of ${photos.length}: ${ROOM(p.room_type)}`}
              >
                <ListingPhoto url={p.url} alt="" className="absolute inset-0 h-full w-full object-cover" placeholderClassName="absolute inset-0 h-full w-full bg-placeholder" />
              </button>
            ) : (
              <div key={i} className="h-full w-full shrink-0 bg-placeholder" />
            ),
          )}
        </div>
        <Link
          href={backHref}
          aria-label="Back"
          className="absolute left-4 top-4 flex h-11 w-11 items-center justify-center rounded-full bg-surface text-text shadow"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
        </Link>
        <button
          type="button"
          onClick={onShare}
          aria-label="Share"
          className="absolute right-4 top-4 flex h-11 w-11 items-center justify-center rounded-full bg-surface text-text shadow"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
        </button>
        {photos.length > 1 && (
          <span className="absolute bottom-3 right-4 rounded-full bg-ink px-2.5 py-0.5 text-[13px] text-white">
            {slide + 1} / {photos.length}
          </span>
        )}
      </div>

      {open !== null && photos[open] && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Photo ${open + 1} of ${photos.length}`}
          className="fixed inset-0 z-[1300] flex items-center justify-center bg-[rgba(13,19,33,0.92)] p-4"
          onClick={close}
        >
          <div className="relative flex max-h-full max-w-5xl flex-col items-center" onClick={(e) => e.stopPropagation()}>
            <ListingPhoto
              url={photos[open].url}
              alt={`${title}: ${ROOM(photos[open].room_type)}`}
              className="max-h-[80vh] max-w-full rounded-lg object-contain"
              placeholderClassName="h-[60vh] w-[80vw] max-w-full rounded-lg bg-placeholder"
            />
            <p className="mt-3 text-[14px] capitalize text-text-on-ink-muted">
              {ROOM(photos[open].room_type)} · {open + 1} / {photos.length}
              {photos[open].attribution ? ` · ${photos[open].attribution}` : ""}
            </p>
          </div>
          <button ref={closeBtn} type="button" onClick={close} aria-label="Close" className="absolute right-4 top-4 flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
          {open > 0 && (
            <button type="button" aria-label="Previous photo" onClick={(e) => { e.stopPropagation(); setOpen(open - 1); }} className="absolute left-4 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
            </button>
          )}
          {open < photos.length - 1 && (
            <button type="button" aria-label="Next photo" onClick={(e) => { e.stopPropagation(); setOpen(open + 1); }} className="absolute right-4 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
            </button>
          )}
        </div>
      )}
    </>
  );
}
