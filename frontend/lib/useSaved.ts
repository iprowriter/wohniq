"use client";

import { useCallback, useEffect, useState } from "react";
import { readSaved, SAVED_EVENT, SAVED_STORAGE_KEY, toggleSaved } from "./saved";

/** Saved listing ids, kept in sync with other components and tabs. */
export function useSaved() {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    const sync = () => setIds(readSaved());
    sync();
    const onStorage = (e: StorageEvent) => e.key === SAVED_STORAGE_KEY && sync();
    window.addEventListener(SAVED_EVENT, sync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(SAVED_EVENT, sync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);
  const toggle = useCallback((id: string) => toggleSaved(id), []);
  return { ids, has: (id: string) => ids.includes(id), toggle };
}
