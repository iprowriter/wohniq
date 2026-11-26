"use client";

import { useState } from "react";
import type { AreaDetail, CategoryDetail, NeighborhoodCatalog, SourceInfo } from "@/lib/neighborhoods/types";
import { OVERALL, rankColor, tierBadge, versusBerlin } from "@/lib/neighborhoods/logic";
import { SourceTag } from "./SourceTag";
import { CategoryIcon } from "@/components/lifestyle/explorer/icons";

interface Props {
  detail: AreaDetail;
  catalog: NeighborhoodCatalog;
  category: string;
  sources: Record<string, SourceInfo>;
  onCategory: (id: string) => void;
}

const VS_STYLE = {
  better: { dot: "bg-accent", text: "better than Berlin" },
  worse: { dot: "bg-text-faint", text: "worse than Berlin" },
  same: { dot: "bg-line-strong", text: "about Berlin's level" },
};

function CategoryBars({
  detail,
  catalog,
  active,
  onCategory,
}: {
  detail: AreaDetail;
  catalog: NeighborhoodCatalog;
  active: string;
  onCategory: (id: string) => void;
}) {
  return (
    <ul className="grid gap-1.5 sm:grid-cols-2">
      {detail.categories.map((c) => {
        const info = catalog.categories.find((x) => x.id === c.id);
        const badge = tierBadge(c.tier, info?.best_label ?? null, info?.worst_label ?? null);
        return (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => onCategory(c.id)}
              aria-label={`${c.label}: rank ${c.rank} of ${detail.total}. Rank all areas by ${c.label}`}
              className={`w-full rounded-lg px-2 py-1.5 text-left transition hover:bg-accent-tint ${c.id === active ? "bg-accent-tint ring-1 ring-accent/30" : ""}`}
            >
              <span className="flex items-baseline justify-between gap-2 text-xs">
                <span className="truncate text-text">
                  <CategoryIcon id={c.id} size={15} /> {c.label}
                </span>
                <span className="flex-shrink-0 tabular-nums text-text-muted">
                  #{c.rank}
                  {badge && (
                    <span
                      className={`ml-1 inline-block h-1.5 w-1.5 rounded-full ${c.tier === "best" ? "bg-accent" : "bg-text-faint"}`}
                    />
                  )}
                </span>
              </span>
              <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-chip">
                <span
                  className="block h-full rounded-full"
                  style={{
                    width: `${c.score}%`,
                    background: rankColor(c.rank, detail.total),
                  }}
                />
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function MetricTable({
  cat,
  catalog,
  sources,
}: {
  cat: CategoryDetail;
  catalog: NeighborhoodCatalog;
  sources: Record<string, SourceInfo>;
}) {
  const info = catalog.categories.find((c) => c.id === cat.id);
  const pending = info?.metrics.filter((m) => !m.available) ?? [];
  return (
    <div>
      <ul className="divide-y divide-line">
        {cat.metrics.map((m) => {
          const berlin = info?.metrics.find((x) => x.id === m.id)?.berlin ?? null;
          const verdict = versusBerlin(m.raw, berlin, m.higher_is_better);
          // Context metrics (not scored) get a neutral comparison, not a judgement.
          const vs =
            m.weight === 0 && verdict !== "same"
              ? { dot: "bg-text-faint", text: m.raw > (berlin ?? 0) ? "higher than Berlin" : "lower than Berlin" }
              : VS_STYLE[verdict];
          return (
            <li key={m.id} className="py-2">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-text-body">
                  {m.label}
                  {m.weight === 0 && <span className="ml-1 text-[10px] uppercase text-text-muted">context</span>}
                </span>
                <span className="flex-shrink-0 font-semibold tabular-nums text-text">{m.text}</span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-text-muted">
                <span className="flex items-center gap-1">
                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${vs.dot}`} aria-hidden="true" />
                  {vs.text} ({m.berlin_text})
                </span>
                <span className="text-text-on-ink-soft">·</span>
                <span>{m.unit}</span>
                {m.level === "district" && (
                  <span className="rounded bg-chip px-1 text-text-body">district figure</span>
                )}
                <SourceTag source={sources[m.source_id]} />
              </div>
            </li>
          );
        })}
      </ul>
      {pending.length > 0 && (
        <ul className="mt-2 space-y-1.5 rounded-lg bg-ground px-2.5 py-2 text-[11px] leading-relaxed text-text-muted">
          {pending.map((m) =>
            m.city_text ? (
              // Not published per area: say so plainly and show the Berlin-wide figure instead.
              <li key={m.id}>
                <span className="font-medium text-text-body">{m.label}:</span> {m.requires}. Berlin-wide:{" "}
                <span className="font-semibold tabular-nums text-text">{m.city_text}</span>
                {m.city_source_id && <SourceTag source={sources[m.city_source_id]} />}
                {m.city_note && <span className="mt-0.5 block text-text-muted">{m.city_note}</span>}
              </li>
            ) : (
              <li key={m.id}>
                <span className="font-medium text-text-body">⏳ {m.label}</span> — {m.requires}.
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  );
}

export function AreaDetailPanel({ detail, catalog, category, sources, onCategory }: Props) {
  const [showData, setShowData] = useState(false);
  const current = category === OVERALL ? null : (detail.categories.find((c) => c.id === category) ?? null);
  const info = current ? catalog.categories.find((c) => c.id === current.id) : null;
  const cited = Array.from(new Set(detail.categories.flatMap((c) => c.metrics.map((m) => m.source_id))));

  return (
    <div className="animate-fade-up mt-3 space-y-4 border-t border-line pt-3" data-testid="area-detail">
      <p className="text-sm text-text-body">{detail.summary}</p>
      <p className="text-xs text-text-muted">
        {detail.population.toLocaleString("en-US")} residents · {detail.area_km2.toLocaleString("en-US")} km² · part of{" "}
        {detail.area_group}, {detail.district}
      </p>

      {(detail.strengths.length > 0 || detail.watch_outs.length > 0) && (
        <div className="space-y-1.5 text-sm">
          {detail.strengths.map((h) => (
            <p key={h.category} className="flex gap-2 text-text-body">
              <span className="mt-0.5 text-accent" aria-hidden="true">
                ▲
              </span>
              <span>
                {h.text}
                <SourceTag source={sources[h.source_id]} />
              </span>
            </p>
          ))}
          {detail.watch_outs.map((h) => (
            <p key={h.category} className="flex gap-2 text-text-body">
              <span className="mt-0.5 text-text-muted" aria-hidden="true">
                ▼
              </span>
              <span>
                {h.text}
                <SourceTag source={sources[h.source_id]} />
              </span>
            </p>
          ))}
        </div>
      )}

      {current && info && (
        <div className="rounded-xl border border-line p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
            {info.label} · #{current.rank} of {detail.total}
          </p>
          <MetricTable cat={current} catalog={catalog} sources={sources} />
        </div>
      )}

      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
          Rank in every category{" "}
          <span className="font-normal normal-case tracking-normal">— tap one to re-rank Berlin by it</span>
        </p>
        <CategoryBars detail={detail} catalog={catalog} active={category} onCategory={onCategory} />
      </div>

      <div>
        <button
          type="button"
          aria-expanded={showData}
          onClick={() => setShowData((v) => !v)}
          className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${showData ? "bg-accent text-white" : "bg-chip text-text-body hover:bg-line"}`}
        >
          About this data
        </button>
        {showData && (
          <div className="animate-fade-up mt-3 space-y-3 text-xs leading-relaxed text-text-body">
            {info && <p className="rounded-lg bg-chip px-3 py-2 text-text-body">{info.caveat}</p>}
            {current && (
              <ul className="space-y-1.5">
                {current.metrics.map((m) => (
                  <li key={m.id}>
                    <span className="font-medium text-text">{m.label}:</span> {m.method}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[11px] uppercase tracking-wide text-text-muted">Sources for this area</p>
            <ul className="space-y-2">
              {cited.map((id) => {
                const s = sources[id];
                if (!s) return null;
                return (
                  <li key={id} className="rounded-xl bg-ground p-2.5">
                    <p className="font-semibold text-text">{s.title}</p>
                    <p>
                      {s.publisher} · data {s.data_year}
                      {s.licence ? ` · ${s.licence}` : ""}
                    </p>
                    {s.url && (
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent hover:underline"
                      >
                        {s.url.replace(/^https?:\/\//, "")} ↗
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
