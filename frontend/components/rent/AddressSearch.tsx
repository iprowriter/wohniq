"use client";

/**
 * Address search over all 400,505 residential addresses (works offline in demo mode).
 * An accessible combobox: type, arrow keys to move, Enter to pick, Escape to close.
 */

import { useEffect, useId, useRef, useState } from "react";
import { searchAddresses } from "@/lib/api";
import type { AddressOut } from "@/lib/types";

const CLASS = { simple: "simple", medium: "medium", good: "good" } as const;

export function AddressSearch({
  value,
  onPick,
}: {
  value: AddressOut | null;
  onPick: (a: AddressOut | null) => void;
}) {
  const [text, setText] = useState(value?.label ?? "");
  const [hits, setHits] = useState<AddressOut[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const listId = useId();
  const inputId = useId();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => setText(value?.label ?? ""), [value]);

  function onType(t: string) {
    setText(t);
    if (value) onPick(null);
    if (timer.current) clearTimeout(timer.current);
    if (t.trim().length < 3) {
      setHits([]);
      setOpen(false);
      return;
    }
    timer.current = setTimeout(() => {
      setLoading(true);
      searchAddresses(t, 8)
        .then((h) => {
          setHits(h);
          setActive(0);
          setOpen(true);
        })
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 180);
  }

  function pick(a: AddressOut) {
    onPick(a);
    setText(a.label);
    setOpen(false);
  }

  return (
    <div className="relative">
      <label htmlFor={inputId} className="mb-1.5 block text-[15px] font-semibold text-text">
        Address
      </label>
      <input
        id={inputId}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && hits[active] ? `${listId}-${active}` : undefined}
        autoComplete="off"
        value={text}
        onChange={(e) => onType(e.target.value)}
        onFocus={() => hits.length && !value && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (!open || !hits.length) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, hits.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            pick(hits[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        placeholder="Street and house number, e.g. Choriner Str. 41"
        className="min-h-tap w-full rounded-md border border-input bg-surface px-3.5 text-base text-text outline-none placeholder:text-text-faint focus:border-accent focus:ring-2 focus:ring-accent/20"
      />
      {value ? (
        <p className="mt-1.5 text-[13px] text-ok" data-testid="address-found">
          Found · location class: {CLASS[value.location_class]} · {value.district}
          {value.planning_area ? ` · ${value.planning_area}` : ""}
        </p>
      ) : (
        <p className="mt-1.5 text-[13px] text-text-muted">
          {loading ? "Searching…" : "Searches all 400,505 Berlin residential addresses, offline."}
        </p>
      )}
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-line bg-surface py-1 shadow-lg"
        >
          {hits.length === 0 && (
            <li className="px-3.5 py-2.5 text-sm text-text-muted">
              No residential address found. Try the street with a house number.
            </li>
          )}
          {hits.map((a, i) => (
            <li
              key={a.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(a);
              }}
              onMouseEnter={() => setActive(i)}
              className={`flex min-h-tap cursor-pointer flex-col justify-center px-3.5 py-1.5 ${
                i === active ? "bg-accent-tint" : ""
              }`}
            >
              <span className="text-[15px] text-text">{a.label}</span>
              <span className="text-[12.5px] text-text-muted">
                {a.district} · location class {a.location_class}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
