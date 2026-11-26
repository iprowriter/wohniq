// Berlin Ink building blocks — `npm test`. Rent scale layout and the status badge text.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { SCALE_PAD, SCALE_WIDTH, rentScaleLayout } from "../lib/ui/rentScale.ts";
import { statusText } from "../lib/ui/status.ts";

describe("rent scale", () => {
  const cases = [
    { low: 7.01, mean: 9.27, high: 12.25, limit: 10.2, asked: 17.86 },
    { low: 7.4, mean: 9.07, high: 11.42, limit: 9.98, asked: 9.56 },
    { low: 11.31, mean: 19.04, high: 26.81, limit: null, asked: 20.25 },
    { low: 6.23, mean: 7.32, high: 9.53, limit: 8.54, asked: 3.1 },
  ];

  test("one linear axis: marks in value order, all inside the drawing", () => {
    for (const c of cases) {
      const L = rentScaleLayout(c);
      const xs = [c.low, c.mean, c.high, c.limit, c.asked].filter((v) => v != null) as number[];
      for (const v of xs) {
        assert.ok(L.x(v) >= SCALE_PAD && L.x(v) <= SCALE_WIDTH - SCALE_PAD, `${v} inside`);
      }
      assert.ok(L.x(c.low) < L.x(c.mean) && L.x(c.mean) < L.x(c.high));
    }
  });

  test("limit label sits a row above the mean label, asked below the track", () => {
    const L = rentScaleLayout(cases[1]);
    assert.ok(L.limitLabel && L.limitLabel.y < L.meanLabel.y);
    assert.ok(L.askedLabel && L.askedLabel.y > L.trackY);
    assert.equal(rentScaleLayout(cases[2]).limitLabel, null); // new build: no limit
  });

  test("labels near an edge are anchored inwards", () => {
    const L = rentScaleLayout(cases[0]); // asked far right
    assert.equal(L.askedLabel?.anchor, "end");
    const R = rentScaleLayout(cases[3]); // asked far left
    assert.equal(R.askedLabel?.anchor, "start");
  });
});

describe("status badge", () => {
  test("texts", () => {
    assert.equal(statusText({ mode: "demo", online: false }, true), "Demo data · offline");
    assert.equal(statusText({ mode: "demo", online: true }, true), "Demo data · online");
    assert.equal(statusText({ mode: "live", online: true }, true), "Live data");
    assert.equal(statusText(null, false), "Offline");
  });
});
