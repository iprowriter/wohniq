"use client";

/**
 * Right now: live departures at the nearest S/U-Bahn station and bus/tram stop when the
 * API reaches BVG; otherwise the six nearest stops with walking minutes (always correct
 * offline). Refreshes every 60 s while visible.
 */

import { useEffect, useState } from "react";
import { getRightNow } from "@/lib/api";
import type { DepartureOut, RightNowOut } from "@/lib/types";
import { StopModes, TransitIcon, type TransitMode } from "@/components/ui/TransitIcon";

function hhmm(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
}

function LineBadge({ d }: { d: DepartureOut }) {
  const mode = (["sbahn", "ubahn", "tram", "bus", "ferry", "regional"].includes(d.mode)
    ? d.mode
    : "bus") as TransitMode;
  return (
    <span className="inline-flex items-center gap-1">
      <TransitIcon mode={mode} size={18} />
      <span className="min-w-[2.2rem] font-semibold text-white">{d.line}</span>
    </span>
  );
}

export function RightNowCard({ lat, lng }: { lat: number; lng: number }) {
  const [data, setData] = useState<RightNowOut | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getRightNow(lat, lng)
        .then((d) => !cancelled && (setData(d), setFailed(false)))
        .catch(() => !cancelled && setFailed(true));
    load();
    const timer = setInterval(() => document.visibilityState === "visible" && load(), 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [lat, lng]);

  const live = data?.status === "live";
  const first = data?.stops[0];
  return (
    <section
      aria-labelledby="right-now-heading"
      className="flex flex-col gap-3 rounded-lg bg-ink p-5 text-text-on-ink-soft"
      data-testid="right-now"
      data-status={data?.status ?? "loading"}
    >
      <header className="flex items-baseline justify-between gap-3">
        <h2 id="right-now-heading" className="text-[17px] font-semibold text-white">
          Right now
        </h2>
        <span className="inline-flex items-center gap-1.5 text-[12.5px] text-text-on-ink-muted">
          <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${live ? "bg-live" : "bg-text-on-ink-muted"}`} />
          {data ? (live ? "Live" : "Offline · stops") : "Loading"}
        </span>
      </header>
      {first && (
        <p className="text-[13px] text-text-on-ink-muted">
          Nearest stop: {first.name} · {first.walk_minutes} min walk
        </p>
      )}
      {failed && !data && <p className="text-sm text-text-on-ink-muted">Couldn&apos;t load the stops.</p>}
      {live && data!.departures.length > 0 ? (
        <ul className="flex flex-col gap-2" aria-label="Departures">
          {data!.departures.map((d, i) => (
            <li key={i} className="grid grid-cols-[3.2rem_auto_1fr] items-center gap-2 text-[14px]">
              <span className="tabular-nums text-text-on-ink-soft">{hhmm(d.when)}</span>
              <LineBadge d={d} />
              <span className={`min-w-0 truncate ${d.cancelled ? "line-through opacity-60" : ""}`}>
                {d.direction}
                <span className="ml-1.5 text-[12px] text-text-on-ink-muted">
                  {d.stop.replace(/^(S\+U|U|S) /, "")}
                  {d.delay_minutes && d.delay_minutes > 0 ? ` · +${d.delay_minutes} min` : ""}
                  {d.cancelled ? " · cancelled" : ""}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Nearest stops">
          {data?.stops.map((s) => (
            <li key={s.id} className="flex items-center gap-2.5 text-[14px]">
              <StopModes modes={s.modes} size={18} />
              <span className="min-w-0 flex-1 truncate">{s.name}</span>
              <span className="font-semibold tabular-nums text-white">{s.walk_minutes} min</span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-[12px] leading-snug text-text-on-ink-muted">
        {live
          ? `${data!.note} Times from BVG, refreshed every minute.`
          : "Offline? This card shows the nearest stops and walking times instead; live departures appear when there's a connection."}
      </p>
    </section>
  );
}
