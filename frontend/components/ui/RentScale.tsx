/**
 * The rent scale from the design: the Mietspiegel range (teal), its mean, the rent-brake
 * limit (amber line) and the asked rent (accent dot), on one €/m² axis. Pure SVG, drawn to
 * scale; labels never overlap the marks they name. Values are € per m² net cold.
 */

import { rentScaleLayout, type RentScaleInput } from "@/lib/ui/rentScale";

const fmt = (v: number) => `€${v.toFixed(2)}`;

export function RentScale(props: RentScaleInput & { className?: string }) {
  const L = rentScaleLayout(props);
  const { low, mean, high, limit, asked } = props;
  const label =
    `Rent index ${fmt(low)} to ${fmt(high)} per m², mean ${fmt(mean)}` +
    (limit != null ? `, rent-brake limit ${fmt(limit)}` : ", no rent-brake limit") +
    (asked != null ? `, asked ${fmt(asked)}` : "");
  return (
    <svg
      viewBox={`0 0 ${L.width} ${L.height}`}
      className={`block h-auto w-full ${props.className ?? ""}`}
      role="img"
      aria-label={label}
    >
      <title>{label}</title>
      <rect x={L.pad} y={L.trackY} width={L.width - 2 * L.pad} height={8} rx={4} fill="var(--color-chip)" />
      <rect x={L.x(low)} y={L.trackY} width={L.x(high) - L.x(low)} height={8} rx={4} fill="var(--color-ok-bar)" />
      <line x1={L.x(mean)} x2={L.x(mean)} y1={L.trackY - 9} y2={L.trackY + 17} stroke="var(--color-ok-text)" strokeWidth={2} />
      <text x={L.meanLabel.x} y={L.meanLabel.y} textAnchor={L.meanLabel.anchor} fontSize={12} fill="var(--color-ok-text)">
        mean {fmt(mean)}
      </text>
      {limit != null && L.limitLabel && (
        <>
          <line x1={L.x(limit)} x2={L.x(limit)} y1={L.trackY - 15} y2={L.trackY + 17} stroke="var(--color-warn-text)" strokeWidth={2} />
          <text x={L.limitLabel.x} y={L.limitLabel.y} textAnchor={L.limitLabel.anchor} fontSize={12} fill="var(--color-warn-text)">
            rent-brake limit {fmt(limit)}
          </text>
        </>
      )}
      {asked != null && L.askedLabel && (
        <>
          <circle cx={L.x(asked)} cy={L.trackY + 4} r={7.5} fill="var(--color-accent)" stroke="var(--color-surface)" strokeWidth={2} />
          <text x={L.askedLabel.x} y={L.askedLabel.y} textAnchor={L.askedLabel.anchor} fontSize={12} fontWeight={600} fill="var(--color-accent)">
            asked {fmt(asked)}
          </text>
        </>
      )}
      <text x={L.x(low)} y={L.bottomY} textAnchor="middle" fontSize={12} fill="var(--color-text-muted)">{fmt(low)}</text>
      <text x={L.x(high)} y={L.bottomY} textAnchor="middle" fontSize={12} fill="var(--color-text-muted)">{fmt(high)}</text>
    </svg>
  );
}
