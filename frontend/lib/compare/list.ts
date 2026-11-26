/**
 * The compare list: up to four flats, kept in this browser (T9.7). Fed from result cards,
 * the listing page, similar flats and /saved; read by the compare bar and /compare.
 * Listing ids aren't personal data, so /compare?ids=… can be reloaded and shared.
 */

const KEY = "wohniq_compare_v1";
export const COMPARE_EVENT = "wohniq:compare";
export const MAX_COMPARE = 4;
const ID = /^[\w-]{1,64}$/;

type Stored = { v: 1; ids: string[] };

export function cleanIds(ids: unknown[]): string[] {
  return [...new Set(ids.filter((x): x is string => typeof x === "string" && ID.test(x)))].slice(0, MAX_COMPARE);
}

export function readCompare(storage: Storage | undefined = globalThis.localStorage): string[] {
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return [];
    const data = JSON.parse(raw) as Stored;
    return data?.v === 1 && Array.isArray(data.ids) ? cleanIds(data.ids) : [];
  } catch {
    return [];
  }
}

export function writeCompare(ids: string[], storage: Storage | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(KEY, JSON.stringify({ v: 1, ids: cleanIds(ids) } satisfies Stored));
    globalThis.dispatchEvent?.(new Event(COMPARE_EVENT));
  } catch {
    /* storage unavailable */
  }
}

/** Add or remove one flat. Adding to a full list does nothing (returns false). */
export function toggleIn(ids: string[], id: string): { ids: string[]; ok: boolean } {
  if (ids.includes(id)) return { ids: ids.filter((x) => x !== id), ok: true };
  if (ids.length >= MAX_COMPARE) return { ids, ok: false };
  return { ids: [...ids, id], ok: true };
}

/** ?ids=a,b,c → ids (invalid and duplicate ids dropped, at most four). */
export function idsFromQuery(value: string | null): string[] {
  return value ? cleanIds(value.split(",")) : [];
}

export function compareHref(ids: string[]): string {
  return `/compare?ids=${cleanIds(ids).join(",")}`;
}

/** A pasted WohnIQ listing link (or a bare id) → the listing id, else null. */
export function idFromLink(text: string): string | null {
  const t = text.trim();
  const m = t.match(/\/listings\/([0-9a-f-]{36})(?:[/?#]|$)/i) ?? t.match(/^([0-9a-f-]{36})$/i);
  return m ? m[1].toLowerCase() : null;
}

export const COMPARE_STORAGE_KEY = KEY;
