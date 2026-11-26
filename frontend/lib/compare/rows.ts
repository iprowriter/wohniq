/**
 * /compare rows (T9.7): price, rent check, scam risk, the flat, location, around. Every value
 * comes from the listing's own data or its Berlin profile (golden rule 3). The best value per
 * row is marked calmly, only where "better" is not a matter of taste, and never for crime
 * or accidents ("describe areas, don't judge them").
 */

import type { ListingDetailResponse, PlaceProfile } from "../types.ts";
import { euro, euro2, rooms } from "../format.ts";

export interface CompareFlat {
  detail: ListingDetailResponse;
  around?: PlaceProfile | null;
  trip?: { minutes: number; label: string } | null;
}

export interface CompareRow {
  label: string;
  values: string[];
  best: number[];
}

export interface CompareGroup {
  title: string;
  rows: CompareRow[];
}

type Num = number | null | undefined;

/** Columns holding the best value; none when fewer than two values or all equal. */
export function bestOf(nums: Num[], higher: boolean): number[] {
  const valid = nums.filter((n): n is number => typeof n === "number" && Number.isFinite(n));
  if (valid.length < 2) return [];
  const target = higher ? Math.max(...valid) : Math.min(...valid);
  if (valid.every((n) => n === target)) return [];
  return nums.flatMap((n, i) => (n === target ? [i] : []));
}

const measure = (f: CompareFlat, key: string) => f.around?.measures.find((m) => m.key === key);
const dash = "–";

function row(label: string, flats: CompareFlat[], text: (f: CompareFlat) => string, num?: (f: CompareFlat) => Num, higher = false): CompareRow {
  return { label, values: flats.map(text), best: num ? bestOf(flats.map(num), higher) : [] };
}

const RISK_WORD = { low: "Low", caution: "Some signals", high: "High" } as const;
const SIGNAL_WORD: Record<string, string> = {
  price_below_index: "rent far below the index",
  price_below_market: "rent far below the area",
  photo_reuse: "photos used on another listing",
  off_platform_payment: "payment off the platform",
  payment_before_viewing: "payment before a viewing",
  landlord_unavailable: "landlord abroad",
  urgency_pressure: "pressure to decide",
  no_anmeldung: "no registration",
};

export function compareGroups(flats: CompareFlat[], tripTo?: string): CompareGroup[] {
  const L = (f: CompareFlat) => f.detail.listing;
  const perM2 = (f: CompareFlat) => (L(f).size_m2 ? L(f).kaltmiete_eur / L(f).size_m2 : null);
  const rent = (f: CompareFlat) => f.detail.rent;
  const groups: CompareGroup[] = [
    {
      title: "Price",
      rows: [
        row("Warm rent", flats, (f) => `${euro(L(f).warmmiete_eur)} / month`, (f) => L(f).warmmiete_eur),
        row("Cold rent", flats, (f) => euro(L(f).kaltmiete_eur), (f) => L(f).kaltmiete_eur),
        row("Cold per m²", flats, (f) => (perM2(f) == null ? dash : `${euro2(perM2(f)!)}/m²`), perM2),
        row("Deposit", flats, (f) => (L(f).deposit_eur == null ? dash : euro(L(f).deposit_eur!)), (f) => L(f).deposit_eur),
      ],
    },
    {
      title: "Rent check",
      rows: [
        row("Index range", flats, (f) => {
          const r = rent(f);
          return r?.low != null && r?.high != null ? `${euro2(r.low)}–${euro2(r.high)}/m²` : dash;
        }),
        row("Rent-brake limit", flats, (f) => (rent(f)?.limit != null ? `${euro2(rent(f)!.limit!)}/m²` : dash)),
        row("Verdict", flats, (f) => rent(f)?.verdict_text ?? dash, (f) => {
          const r = rent(f);
          if (!r || r.verdict === "new_build" || r.verdict === "not_covered") return null;
          return r.over_per_month ?? 0; // within the limit = 0 over
        }),
      ],
    },
    {
      title: "Scam risk",
      rows: [
        row("Level", flats, (f) => (f.detail.risk ? `${RISK_WORD[f.detail.risk.band]} (${f.detail.risk.score}/100)` : dash), (f) => f.detail.risk?.score),
        row("Signals", flats, (f) => {
          const s = f.detail.risk?.signals ?? [];
          return s.length ? s.map((x) => SIGNAL_WORD[x.name] ?? x.name.replace(/_/g, " ")).join(", ") : "No warning signs";
        }),
      ],
    },
    {
      title: "The flat",
      rows: [
        row("Rooms", flats, (f) => rooms(L(f).rooms)),
        row("Size", flats, (f) => `${L(f).size_m2} m²`, (f) => L(f).size_m2, true),
        row("Floor", flats, (f) => (L(f).floor == null ? dash : L(f).total_floors ? `${L(f).floor} of ${L(f).total_floors}` : String(L(f).floor))),
        row("Built", flats, (f) => (L(f).year_built ? String(L(f).year_built) : dash)),
        row("Furnished", flats, (f) => (L(f).furnished ? "Yes" : "No")),
        row("Available from", flats, (f) => (L(f).available_from ? new Date(L(f).available_from!).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : dash)),
      ],
    },
    {
      title: "Location",
      rows: [
        row("Area", flats, (f) => [L(f).kiez, L(f).district].filter(Boolean).join(" · ")),
        row("Nearest S/U-Bahn", flats, (f) => {
          const loc = f.detail.location;
          return loc?.rail_stop ? `${loc.rail_stop} · ${loc.rail_walk_minutes} min walk` : dash;
        }, (f) => f.detail.location?.rail_walk_minutes),
        ...(tripTo
          ? [row(`Trip to ${tripTo}`, flats, (f) => f.trip?.label ?? dash, (f) => f.trip?.minutes)]
          : []),
      ],
    },
    {
      title: "Around",
      rows: [
        row("Schools within 1 km", flats, (f) => measure(f, "schools")?.headline ?? dash, (f) => measure(f, "schools")?.value, true),
        row("Kitas within 500 m", flats, (f) => measure(f, "kitas")?.headline ?? dash, (f) => measure(f, "kitas")?.value, true),
        row("Parks and playgrounds", flats, (f) => measure(f, "green")?.headline ?? dash, (f) => measure(f, "green")?.value),
        row("Air quality", flats, (f) => measure(f, "air")?.headline ?? dash, (f) => measure(f, "air")?.value),
        row("Road accidents", flats, (f) => measure(f, "accidents")?.headline ?? dash),
      ],
    },
  ];
  return groups;
}
