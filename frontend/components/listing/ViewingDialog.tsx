"use client";

/**
 * "Request a viewing": the listings are synthetic, so there's no landlord to contact. The
 * button opens a short safety checklist instead, which is what anyone should read before
 * contacting a landlord in Berlin.
 */

import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/primitives";

const CHECKS = [
  "Never pay a deposit or rent before you have seen the flat in person.",
  "Keys are never sent by post or courier. A real landlord or agent meets you at the flat.",
  "Pay only by bank transfer to an account in the landlord's name, never via Western Union, crypto or gift cards.",
  "The Kaution is at most three months' cold rent, and you can pay it in three instalments.",
  "Ask whether Anmeldung (registration) is possible. You need it for almost everything in Germany.",
  "Check the rent against the Mietspiegel before you sign.",
];

export function ViewingDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    opener.current = document.activeElement;
    ref.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      (opener.current as HTMLElement | null)?.focus?.();
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[1300] flex items-end justify-center bg-[rgba(13,19,33,0.6)] p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="viewing-title"
        className="flex max-h-[90vh] w-full max-w-lg flex-col gap-4 overflow-auto rounded-t-xl bg-surface p-6 sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 id="viewing-title" className="text-[22px] font-semibold tracking-tight text-text">
            Before you request a viewing
          </h2>
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        </div>
        <p className="text-[15px] text-text-body">
          This is a sample listing, so there&apos;s no landlord to contact. For a real flat, these
          checks protect you:
        </p>
        <ul className="flex flex-col gap-2.5">
          {CHECKS.map((c) => (
            <li key={c} className="flex gap-2.5 text-[15px] leading-snug text-text-body">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-ok-text)" strokeWidth="2.4" className="mt-0.5 shrink-0">
                <path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {c}
            </li>
          ))}
        </ul>
        <Button onClick={onClose}>Got it</Button>
      </div>
    </div>
  );
}
