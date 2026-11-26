/**
 * Saved flats, kept in this browser only (no account). Listing ids aren't personal data.
 * A versioned record; broken or foreign data reads as empty. Other tabs follow via the
 * `storage` event, this tab via a custom event.
 */

const KEY = "wohniq_saved_v1";
export const SAVED_EVENT = "wohniq:saved";
export const MAX_SAVED = 100;

type Stored = { v: 1; ids: string[] };

export function readSaved(storage: Storage | undefined = globalThis.localStorage): string[] {
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return [];
    const data = JSON.parse(raw) as Stored;
    if (data?.v !== 1 || !Array.isArray(data.ids)) return [];
    return data.ids.filter((x) => typeof x === "string").slice(0, MAX_SAVED);
  } catch {
    return [];
  }
}

export function writeSaved(ids: string[], storage: Storage | undefined = globalThis.localStorage): void {
  try {
    const unique = [...new Set(ids)].slice(0, MAX_SAVED);
    storage?.setItem(KEY, JSON.stringify({ v: 1, ids: unique } satisfies Stored));
    globalThis.dispatchEvent?.(new Event(SAVED_EVENT));
  } catch {
    /* storage unavailable (private mode): saving just doesn't persist */
  }
}

export function toggleSaved(id: string, storage?: Storage): boolean {
  const ids = readSaved(storage);
  const on = !ids.includes(id);
  writeSaved(on ? [id, ...ids] : ids.filter((x) => x !== id), storage);
  return on;
}

export const SAVED_STORAGE_KEY = KEY;
