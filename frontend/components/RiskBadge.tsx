import type { RiskOut } from "@/lib/types";

const STYLES: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  caution: "bg-amber-100 text-amber-800",
  high: "bg-red-100 text-red-800",
};

const LABELS: Record<string, string> = {
  low: "Low risk",
  caution: "Caution",
  high: "High risk",
};

export function RiskBadge({ risk }: { risk?: RiskOut | null }) {
  if (!risk) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ${STYLES[risk.band] ?? STYLES.low}`}
    >
      {LABELS[risk.band] ?? "Risk"} · {risk.score}
    </span>
  );
}
