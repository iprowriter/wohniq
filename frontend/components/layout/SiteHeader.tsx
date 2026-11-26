"use client";

/**
 * The Berlin Ink header: ink bar, logo, the four sections, and the data status badge.
 * On phones the sections move into a menu behind a button (44 px tap targets).
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { NAV, isActive } from "@/lib/nav";
import { StatusBadge } from "./StatusBadge";
import { useSaved } from "@/lib/useSaved";
import { useSavedSearches } from "@/lib/useSavedSearches";

export function Logo() {
  return (
    <svg aria-hidden="true" width="28" height="28" viewBox="0 0 28 28" fill="none">
      <rect x="1" y="1" width="26" height="26" rx="8" stroke="var(--color-accent-logo)" strokeWidth="2" />
      <path d="M8 18V11l6-4 6 4v7" stroke="#FFFFFF" strokeWidth="2" strokeLinejoin="round" />
      <path d="M12 18v-4h4v4" stroke="var(--color-accent-logo)" strokeWidth="2" />
    </svg>
  );
}

export function SiteHeader() {
  const pathname = usePathname() ?? "/";
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [pathname]); // close the phone menu on navigation
  const searches = useSavedSearches().searches.length;
  const saved = useSaved().ids.length + searches; // flats and searches

  return (
    <header className="sticky top-0 z-[1100] bg-ink text-text-on-ink">
      <div className="mx-auto flex max-w-page items-center gap-4 px-[18px] py-3 md:gap-6 md:px-8 md:py-[14px]">
        <Link
          href="/"
          className="flex min-h-tap items-center gap-2.5 text-xl font-bold tracking-tight text-white"
        >
          <Logo />
          WohnIQ
        </Link>
        <nav aria-label="Main" className="hidden flex-1 flex-wrap gap-1 md:flex">
          {NAV.map((item) => {
            const active = isActive(item.href, pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-tap items-center rounded-[10px] px-3.5 text-[15px] ${
                  active ? "bg-white/[0.08] text-white" : "text-text-on-ink-muted hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <StatusBadge />
          <Link
            href="/saved"
            data-testid="saved-link"
            aria-current={pathname.startsWith("/saved") ? "page" : undefined}
            className="hidden min-h-tap items-center rounded-md bg-white px-4 text-[15px] font-medium text-text hover:bg-text-on-ink-soft sm:inline-flex"
          >
            Saved ({saved})
          </Link>
          <button
            type="button"
            className="flex min-h-tap min-w-[44px] items-center justify-center rounded-[10px] text-white md:hidden"
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-menu" aria-label="Main" className="border-t border-white/10 px-[18px] pb-3 md:hidden">
          {NAV.map((item) => {
            const active = isActive(item.href, pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-tap items-center rounded-[10px] px-3 text-base ${
                  active ? "bg-white/[0.08] text-white" : "text-text-on-ink-muted"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          <Link
            href="/saved"
            className="flex min-h-tap items-center rounded-[10px] px-3 text-base text-text-on-ink-muted"
          >
            Saved ({saved})
          </Link>
        </nav>
      )}
    </header>
  );
}
