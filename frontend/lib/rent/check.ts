/**
 * Rent check in the browser (ADR-0017): a line-by-line port of backend/berlin/rent.py, so the
 * user's rent and flat features never leave the browser. Tested against vectors the Python
 * reference writes (tests/fixtures/rent-vectors.json, tests/rent-check.test.ts).
 *
 * Steps (Mietspiegel 2026, No. 8–10): table row by location class, building age (East/West
 * for 1973–1990) and size; checklist groups netted, each net group moving 20 % of the way to
 * the range edge; rent-brake limit = comparable rent + 10 %; new builds have no limit.
 */

export type LocationClass = "simple" | "medium" | "good";

export interface Period {
  label: string;
  from: number | null;
  to: number;
  side: "east" | "west" | null;
}

export interface RentRow {
  row: number;
  location: LocationClass | string;
  period: string;
  size_min: number;
  size_max: number | null;
  low: number;
  mean: number;
  high: number;
}

export interface ChecklistItem {
  id: string;
  group: number;
  sign: "+" | "-";
  not_applicable?: string[];
  label?: string;
  text_de?: string;
  energy_kwh?: number | null;
}

export interface RentInput {
  location_class: LocationClass | string;
  east: boolean;
  year_built: number;
  size_m2: number;
  cold_rent_eur?: number | null;
  features?: string[];
  energy_kwh?: number | null;
  energy_is_demand?: boolean;
  energy_without_hot_water?: boolean;
  no_central_heating_or_bath?: boolean;
}

export type Verdict =
  | "within_limit"
  | "above_limit"
  | "below_index"
  | "new_build"
  | "not_covered"
  | "unknown";

export interface GroupResult {
  group: number;
  plus: number;
  minus: number;
  effect: -1 | 0 | 1;
}

export interface RentResult {
  covered: boolean;
  period: string | null;
  row: RentRow | null;
  low: number | null;
  mean: number | null;
  high: number | null;
  groups: GroupResult[];
  net_groups: number;
  used_checklist: boolean;
  comparable: number | null;
  limit: number | null;
  exempt: "new_build" | null;
  asked: number | null;
  verdict: Verdict;
  over_per_m2: number | null;
  over_per_month: number | null;
  ignored_features: string[];
}

export const RENT_BRAKE_FACTOR = 1.1;
export const GROUP_STEP = 0.2;
export const NEW_BUILD_FROM_YEAR = 2014;
export const NO_HEATING_OR_BATH_DEDUCTION = 0.33;
const DEMAND_FACTOR = 1.2;
const NO_HOT_WATER_SURCHARGE_KWH = 20;
const INSULATION_ITEMS = ["building-minus-08", "building-plus-08"];

/** Python's round() for these magnitudes: half-to-even on exact ties. */
function pyRound(x: number, digits = 0): number {
  const f = 10 ** digits;
  const v = x * f;
  const floor = Math.floor(v);
  const diff = v - floor;
  let r: number;
  if (Math.abs(diff - 0.5) < 1e-9) r = floor % 2 === 0 ? floor : floor + 1;
  else r = Math.round(v);
  return r / f;
}

/** berlin/rent.py `_r2`: round(x + 1e-9, 2). */
const r2 = (x: number) => pyRound(x + 1e-9, 2);

export function periodFor(year: number, east: boolean, periods: Record<string, Period>): string | null {
  const side = east ? "east" : "west";
  for (const [key, p] of Object.entries(periods)) {
    const lo = p.from ?? -Infinity;
    if (lo <= year && year <= p.to && (p.side === null || p.side === side)) return key;
  }
  return null;
}

export function findRow(rows: RentRow[], locationClass: string, period: string, size: number): RentRow | null {
  for (const r of rows) {
    if (r.location !== locationClass || r.period !== period) continue;
    if (r.size_min <= size && (r.size_max === null || size < r.size_max)) return r;
  }
  return null;
}

export function energyFeatures(kwh: number, isDemand = false, withoutHotWater = false): string[] {
  const value = kwh + (withoutHotWater ? NO_HOT_WATER_SURCHARGE_KWH : 0);
  const scale = isDemand ? DEMAND_FACTOR : 1;
  const out: string[] = [];
  for (const limit of [145, 195, 235]) if (value > limit * scale) out.push(`building-minus-energy-${limit}`);
  for (const limit of [120, 100, 80]) if (value < limit * scale) out.push(`building-plus-energy-${limit}`);
  return out;
}

export function applies(item: ChecklistItem | undefined, period: string): boolean {
  return !(item?.not_applicable ?? []).includes(period);
}

function asked(inp: RentInput): number | null {
  if (inp.cold_rent_eur == null || inp.size_m2 <= 0) return null;
  return r2(inp.cold_rent_eur / inp.size_m2);
}

export function checkRent(
  inp: RentInput,
  rows: RentRow[],
  periods: Record<string, Period>,
  checklist: ChecklistItem[],
): RentResult {
  const base: RentResult = {
    covered: false, period: null, row: null, low: null, mean: null, high: null, groups: [],
    net_groups: 0, used_checklist: false, comparable: null, limit: null, exempt: null,
    asked: asked(inp), verdict: "not_covered", over_per_m2: null, over_per_month: null,
    ignored_features: [],
  };
  const period = periodFor(inp.year_built, inp.east, periods);
  if (period === null) return { ...base, exempt: "new_build" };
  const row = findRow(rows, inp.location_class, period, inp.size_m2);
  if (row === null) return { ...base, period };

  const deduction =
    inp.no_central_heating_or_bath && (period === "pre1918" || period === "1919-1949")
      ? NO_HEATING_OR_BATH_DEDUCTION
      : 0;
  const low = row.low - deduction;
  const mean = row.mean - deduction;
  const high = row.high - deduction;

  const known = new Map(checklist.map((it) => [it.id, it]));
  let features = new Set(inp.features ?? []);
  if (inp.energy_kwh != null) {
    features = new Set([...features].filter((i) => !i.includes("-energy-") && !INSULATION_ITEMS.includes(i)));
    for (const f of energyFeatures(inp.energy_kwh, !!inp.energy_is_demand, !!inp.energy_without_hot_water)) {
      features.add(f);
    }
  }
  const ignored = [...features].filter((i) => !applies(known.get(i), period)).sort();
  for (const i of ignored) features.delete(i);

  const groups: GroupResult[] = [];
  for (let g = 1; g <= 5; g++) {
    let plus = 0;
    let minus = 0;
    for (const i of features) {
      const it = known.get(i);
      if (!it || it.group !== g) continue;
      if (it.sign === "+") plus++;
      else minus++;
    }
    groups.push({ group: g, plus, minus, effect: plus > minus ? 1 : plus < minus ? -1 : 0 });
  }
  const net = groups.reduce((s, g) => s + g.effect, 0);
  const comparable =
    net > 0 ? mean + GROUP_STEP * net * (high - mean) : net < 0 ? mean + GROUP_STEP * net * (mean - low) : mean;

  const exempt = inp.year_built >= NEW_BUILD_FROM_YEAR ? "new_build" : null;
  const limit = exempt ? null : comparable * RENT_BRAKE_FACTOR;
  const result: RentResult = {
    ...base,
    covered: true,
    period,
    row,
    low: r2(low),
    mean: r2(mean),
    high: r2(high),
    groups,
    net_groups: net,
    used_checklist: features.size > 0,
    comparable: r2(comparable),
    limit: limit !== null ? r2(limit) : null,
    exempt,
    verdict: "unknown",
    ignored_features: ignored,
  };
  const a = result.asked;
  if (a === null) result.verdict = exempt ? "new_build" : "unknown";
  else if (exempt) result.verdict = "new_build";
  else if (a < (result.low as number)) result.verdict = "below_index";
  else if (a <= (result.limit as number)) result.verdict = "within_limit";
  else {
    result.verdict = "above_limit";
    result.over_per_m2 = r2(a - (result.limit as number));
    result.over_per_month = pyRound((a - (result.limit as number)) * inp.size_m2);
  }
  return result;
}

/** The building-age choices on the form: Mietspiegel periods, split where the rules split
 * (2014: rent brake), with the year the check uses for each. East/West decides 1973–1990. */
export interface AgeOption {
  id: string;
  label: string;
  year: number;
}

export function ageOptions(east: boolean): AgeOption[] {
  const common: AgeOption[] = [
    { id: "pre1918", label: "before 1918", year: 1900 },
    { id: "1919-1949", label: "1919–1949", year: 1930 },
    { id: "1950-1964", label: "1950–1964", year: 1957 },
    { id: "1965-1972", label: "1965–1972", year: 1968 },
  ];
  const seventies: AgeOption[] = east
    ? [{ id: "1973-1990", label: "1973–1990", year: 1980 }]
    : [
        { id: "1973-1985", label: "1973–1985", year: 1980 },
        { id: "1986-1990", label: "1986–1990", year: 1988 },
      ];
  return [
    ...common,
    ...seventies,
    { id: "1991-2001", label: "1991–2001", year: 1996 },
    { id: "2002-2009", label: "2002–2009", year: 2005 },
    { id: "2010-2013", label: "2010–2013", year: 2012 },
    { id: "2014-2015", label: "2014–2015 (first let after Oct 2014)", year: 2015 },
    { id: "2016-2019", label: "2016–2019", year: 2017 },
    { id: "2020-2024", label: "2020–2024", year: 2022 },
    { id: "2025", label: "2025 or later", year: 2025 },
  ];
}

/** Index mean for every building age at this location and size (the bar chart). Computed in
 * the browser so the flat's size never leaves it. Mirrors berlin/rent.py `rent_by_period`. */
export function rentByPeriod(
  rows: RentRow[],
  locationClass: string,
  east: boolean,
  size: number,
  periods: Record<string, Period>,
): { period: string; label: string; mean: number; row: number }[] {
  const side = east ? "east" : "west";
  const out: { period: string; label: string; mean: number; row: number }[] = [];
  for (const [key, p] of Object.entries(periods)) {
    if (p.side !== null && p.side !== side) continue;
    const r = findRow(rows, locationClass, key, size);
    if (r) out.push({ period: key, label: p.label, mean: r.mean, row: r.row });
  }
  return out;
}
