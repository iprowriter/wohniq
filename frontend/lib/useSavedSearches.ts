"use client";

import { useCallback, useEffect, useState } from "react";
import { readSearches, SEARCHES_EVENT, SEARCHES_STORAGE_KEY, writeSearches, type SavedSearch } from "./savedSearches";

/** Saved searches, kept in sync with other components and tabs. */
export function useSavedSearches() {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const sync = () => setSearches(readSearches());
    sync();
    setReady(true);
    const onStorage = (e: StorageEvent) => e.key === SEARCHES_STORAGE_KEY && sync();
    window.addEventListener(SEARCHES_EVENT, sync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(SEARCHES_EVENT, sync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);
  const update = useCallback((fn: (s: SavedSearch[]) => SavedSearch[]) => writeSearches(fn(readSearches())), []);
  return { searches, ready, update };
}
