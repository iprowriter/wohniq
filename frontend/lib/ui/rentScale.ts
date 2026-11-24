/**
 * Layout for the rent scale (components/ui/RentScale.tsx). Pure, so it's unit-tested:
 * one linear €/m² axis covering the range, the limit and the asked rent with a margin;
 * labels on separate rows (limit above the mean, asked below the track, range ends at the
 * bottom) and anchored so they stay inside the drawing.
 */

export type RentScaleInput = {
  low: number;
  mean: number;
  high: number;
  limit?: number | null;
  asked?: number | null;
};

export type Label = { x: number; y: number; anchor: "start" | "middle" | "end" };

export const SCALE_WIDTH = 600;
export const SCALE_PAD = 24;
const TRACK_Y = 42;
const EDGE = 70; // px from the edge within which a label is anchored to stay inside

export function rentScaleDomain({ low, high, limit, asked }: RentScaleInput): [number, number] {
  const values = [low, high, limit ?? low, asked ?? low];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const margin = Math.max((hi - lo) * 0.08, 0.5);
  return [Math.max(0, lo - margin), hi + margin];
}

function anchorFor(x: number): Label["anchor"] {
  if (x < SCALE_PAD + EDGE) return "start";
  if (x > SCALE_WIDTH - SCALE_PAD - EDGE) return "end";
  return "middle";
}

export function rentScaleLayout(input: RentScaleInput) {
  const [d0, d1] = rentScaleDomain(input);
  const x = (v: number) => SCALE_PAD + ((v - d0) / (d1 - d0)) * (SCALE_WIDTH - 2 * SCALE_PAD);
  const meanX = x(input.mean);
  const limitX = input.limit != null ? x(input.limit) : null;
  // Mean label to the left of its line, limit label to the right of its line, one row
  // higher, so the two never collide even when the limit is just above the mean.
  const meanLabel: Label = { x: meanX - 4, y: TRACK_Y - 14, anchor: "end" };
  if (meanX - 4 < SCALE_PAD + EDGE) Object.assign(meanLabel, { x: meanX + 4, anchor: "start" });
  const limitLabel: Label | null =
    limitX == null
      ? null
      : limitX > SCALE_WIDTH - SCALE_PAD - EDGE * 2
        ? { x: limitX - 4, y: TRACK_Y - 26, anchor: "end" }
        : { x: limitX + 4, y: TRACK_Y - 26, anchor: "start" };
  const askedX = input.asked != null ? x(input.asked) : null;
  const askedLabel: Label | null =
    askedX == null ? null : { x: askedX, y: TRACK_Y + 34, anchor: anchorFor(askedX) };
  return {
    width: SCALE_WIDTH,
    height: TRACK_Y + 62,
    pad: SCALE_PAD,
    trackY: TRACK_Y,
    bottomY: TRACK_Y + 54,
    domain: [d0, d1] as const,
    x,
    meanLabel,
    limitLabel,
    askedLabel,
  };
}
