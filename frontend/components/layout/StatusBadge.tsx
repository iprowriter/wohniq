"use client";

/**
 * "Demo data · offline" / "Demo data · online" / "Live data": what the app is running on.
 * Asks the API's /status once a minute; "online" means live departures are reachable.
 */

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";
import { statusText, type Status } from "@/lib/ui/status";

export function StatusBadge() {
  const [status, setStatus] = useState<Status | null>(null);
  const [reachable, setReachable] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch(`${API_BASE}/api/v1/status`)
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((s: Status) => {
          if (!cancelled) {
            setStatus(s);
            setReachable(true);
          }
        })
        .catch(() => !cancelled && setReachable(false));
    load();
    const timer = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const online = !!status?.online && reachable;
  return (
    <span
      className="hidden items-center gap-1.5 whitespace-nowrap rounded-full border border-white/20 px-2.5 py-1.5 text-[13px] text-text-on-ink-muted sm:inline-flex"
      data-testid="status-badge"
      role="status"
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${online ? "bg-live" : "bg-text-on-ink-muted"}`}
      />
      {statusText(status, reachable)}
    </span>
  );
}
