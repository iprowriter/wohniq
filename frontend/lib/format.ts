/** Number formats used across the app (Berlin Ink design: €1,284 · €14.10/m² · 61 m²). */

const whole = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

/** €1,284 */
export function euro(n: number): string {
  return `€${whole.format(Math.round(n))}`;
}

/** €14.10 (per m² values keep two decimals) */
export function euro2(n: number): string {
  return `€${n.toFixed(2)}`;
}

/** 2 rooms · 1.5 rooms */
export function rooms(n: number): string {
  const v = n % 1 === 0 ? String(Math.round(n)) : n.toFixed(1);
  return `${v} ${n === 1 ? "room" : "rooms"}`;
}
