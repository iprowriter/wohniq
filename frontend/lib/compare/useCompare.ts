"use client";

import { useCallback, useEffect, useState } from "react";
import { COMPARE_EVENT, COMPARE_STORAGE_KEY, MAX_COMPARE, readCompare, toggleIn, writeCompare } from "./list";

/** The shared compare list, in sync across components and tabs. */
export function useCompare() {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    const sync = () => setIds(readCompare());
    sync();
    const onStorage = (e: StorageEvent) => e.key === COMPARE_STORAGE_KEY && sync();
    window.addEventListener(COMPARE_EVENT, sync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(COMPARE_EVENT, sync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);
  const toggle = useCallback((id: string) => {
    const r = toggleIn(readCompare(), id);
    writeCompare(r.ids);
    return r.ok;
  }, []);
  const set = useCallback((next: string[]) => writeCompare(next), []);
  return { ids, has: (id: string) => ids.includes(id), full: ids.length >= MAX_COMPARE, toggle, set, clear: () => writeCompare([]) };
}
