// Homepage map logic — `npm test`. Zoom tiers, medians, clustering and pill stacking.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import {
  DISTRICT_LABEL_POINTS,
  PILL_H,
  PILL_W,
  TIERS,
  TIER_ZOOM,
  ZOOM,
  areaMarkers,
  formatEuro,
  listingMarkers,
  markersForZoom,
  median,
  nextTier,
  tierForZoom,
  tierStatus,
  zoomIntoCluster,
  type MapListing,
  type Project,
} from "../lib/map/listingsMap.ts";

function listing(id: string, kiez: string, district: string, lat: number, lng: number, rent: number): MapListing {
  return { id, title: `Flat ${id}`, kiez, district, lat, lng, rooms: 2, size_m2: 50, warmmiete_eur: rent };
}

const LISTINGS: MapListing[] = [
  listing("a", "Mitte", "Mitte", 52.525, 13.402, 1200),
  listing("b", "Mitte", "Mitte", 52.526, 13.404, 1400),
  listing("c", "Moabit", "Mitte", 52.53, 13.342, 900),
  listing("d", "Kreuzberg", "Friedrichshain-Kreuzberg", 52.499, 13.403, 1100),
  listing("e", "Friedrichshain", "Friedrichshain-Kreuzberg", 52.515, 13.454, 1000),
  listing("f", "Spandau", "Spandau", 52.535, 13.2, 700),
];

// Web-Mercator pixels at `zoom` (what Leaflet's map.project returns for a 256 px tile size).
function mercator(zoom: number): Project {
  const scale = 256 * 2 ** zoom;
  return (lat, lng) => {
    const s = Math.sin((lat * Math.PI) / 180);
    return {
      x: ((lng + 180) / 360) * scale,
      y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * scale,
    };
  };
}

describe("zoom tiers", () => {
  test("city ≤ 10, district 11, neighbourhood 12, listings ≥ 13", () => {
    assert.deepEqual(
      [6, 8, 9, 10, 11, 12, 13, 14, 16, 18].map(tierForZoom),
      ["city", "city", "city", "city", "district", "neighbourhood", "listing", "listing", "listing", "listing"],
    );
    assert.equal(tierForZoom(10.6), "district"); // mid-animation zooms round
  });

  test("each tier's entry zoom maps back to that tier; the map opens on listings", () => {
    for (const tier of TIERS) assert.equal(tierForZoom(TIER_ZOOM[tier]), tier);
    assert.equal(tierForZoom(ZOOM.initial), "listing");
    assert.equal(nextTier("city"), "district");
    assert.equal(nextTier("listing"), "listing");
  });

  test("median bubbles open exactly the next tier; stacks zoom to fit", () => {
    assert.equal(tierForZoom(zoomIntoCluster("city", 7)), "district");
    // A whole district fits at z13, but the click must show its neighbourhoods first.
    assert.equal(tierForZoom(zoomIntoCluster("district", 13)), "neighbourhood");
    assert.equal(tierForZoom(zoomIntoCluster("neighbourhood", 12)), "listing");
    assert.equal(zoomIntoCluster("listing", 15.4), 15);
    assert.equal(zoomIntoCluster("listing", 30), ZOOM.max);
  });
});

describe("medians", () => {
  test("odd, even (rounded) and empty", () => {
    assert.equal(median([3, 1, 2]), 2);
    assert.equal(median([1000, 1101]), 1051);
    assert.equal(median([]), 0);
  });

  test("formatEuro uses the app's German thousands separator", () => {
    assert.equal(formatEuro(1068), "€1.068");
    assert.equal(formatEuro(835), "€835");
    assert.equal(formatEuro(12500), "€12.500");
  });
});

describe("area clusters", () => {
  test("city tier: one Berlin bubble with the Berlin median", () => {
    const [berlin, ...rest] = markersForZoom(LISTINGS, 8, mercator(8));
    assert.equal(rest.length, 0);
    assert.equal(berlin.kind, "area");
    if (berlin.kind !== "area") return;
    assert.equal(berlin.name, "Berlin");
    assert.equal(berlin.count, 6);
    assert.equal(berlin.median, median(LISTINGS.map((l) => l.warmmiete_eur)));
  });

  test("district tier groups by Bezirk (Moabit counts as Mitte), at the Bezirk centre", () => {
    const byName = Object.fromEntries(areaMarkers(LISTINGS, "district").map((m) => [m.name, m]));
    assert.deepEqual(Object.keys(byName).sort(), ["Friedrichshain-Kreuzberg", "Mitte", "Spandau"]);
    assert.equal(byName.Mitte.count, 3);
    assert.equal(byName.Mitte.median, 1200);
    assert.equal(byName["Friedrichshain-Kreuzberg"].median, 1050);
    assert.deepEqual([byName.Mitte.lat, byName.Mitte.lng], DISTRICT_LABEL_POINTS.Mitte);
    // Unknown district → centroid of its listings.
    const other = areaMarkers([listing("x", "Foo", "Nowhere", 52.4, 13.1, 500)], "district")[0];
    assert.deepEqual([other.lat, other.lng], [52.4, 13.1]);
  });

  test("district bubbles don't overlap at the district zoom", () => {
    const project = mercator(TIER_ZOOM.district);
    const pts = Object.entries(DISTRICT_LABEL_POINTS).map(([name, [lat, lng]]) => ({ name, ...project(lat, lng) }));
    // Widest bubble ("Charlottenburg-Wilmersdorf") ≈ 150 px, height ≈ 42 px.
    for (let i = 0; i < pts.length; i++)
      for (let j = i + 1; j < pts.length; j++) {
        const apart = Math.abs(pts[i].x - pts[j].x) >= 120 || Math.abs(pts[i].y - pts[j].y) >= 44;
        assert.ok(apart, `${pts[i].name} / ${pts[j].name}`);
      }
  });

  test("neighbourhood tier groups by Kiez, placed at the members' centroid", () => {
    const markers = areaMarkers(LISTINGS, "neighbourhood");
    assert.equal(markers.length, 5);
    const mitte = markers.find((m) => m.name === "Mitte")!;
    assert.equal(mitte.count, 2);
    assert.equal(mitte.median, 1300);
    assert.ok(Math.abs(mitte.lat - 52.5255) < 1e-9 && Math.abs(mitte.lng - 13.403) < 1e-9);
    assert.deepEqual(mitte.bounds, { south: 52.525, west: 13.402, north: 52.526, east: 13.404 });
  });

  test("every listing is counted exactly once at every aggregate tier", () => {
    for (const zoom of [7, 11, 12]) {
      const total = markersForZoom(LISTINGS, zoom, mercator(zoom)).reduce(
        (n, m) => n + (m.kind === "area" ? m.count : 0),
        0,
      );
      assert.equal(total, LISTINGS.length);
    }
  });
});

describe("listing pills", () => {
  test("overlapping pills are stacked; distant ones stay single", () => {
    // a and b are ~170 m apart: overlapping at z13 (≈ 12 m/px), separate at z16.
    const z13 = listingMarkers(LISTINGS, 13, mercator(13));
    const stack = z13.find((m) => m.kind === "stack");
    assert.ok(stack && stack.kind === "stack");
    assert.deepEqual(stack.ids, ["a", "b"]);
    assert.equal(stack.median, 1300);
    assert.equal(z13.filter((m) => m.kind === "listing").length, 4);

    const z16 = listingMarkers(LISTINGS, 16, mercator(16));
    assert.ok(z16.every((m) => m.kind === "listing"));
    assert.equal(z16.length, LISTINGS.length);
  });

  test("no two visible markers overlap below the stacking limit", () => {
    // A dense synthetic Kiez: 60 listings within ~1 km.
    const dense = Array.from({ length: 60 }, (_, i) =>
      listing(`d${i}`, "Kreuzberg", "Friedrichshain-Kreuzberg", 52.495 + ((i * 37) % 100) / 10000, 13.4 + ((i * 61) % 100) / 6000, 900 + i * 10),
    );
    for (const zoom of [13, 14, 15]) {
      const project = mercator(zoom);
      const pts = listingMarkers([...LISTINGS, ...dense], zoom, project).map((m) => project(m.lat, m.lng));
      for (let i = 0; i < pts.length; i++)
        for (let j = i + 1; j < pts.length; j++) {
          const apart = Math.abs(pts[i].x - pts[j].x) >= PILL_W || Math.abs(pts[i].y - pts[j].y) >= PILL_H;
          assert.ok(apart, `markers ${i} and ${j} overlap at z${zoom}`);
        }
    }
  });

  test("the selected listing always keeps its own pill, drawn last", () => {
    const markers = listingMarkers(LISTINGS, 13, mercator(13), "a");
    const last = markers[markers.length - 1];
    assert.equal(last.kind, "listing");
    assert.equal(last.kind === "listing" && last.listing.id, "a");
    assert.ok(!markers.some((m) => m.kind === "stack" && m.ids.includes("a")));
    // Every listing is still represented exactly once.
    const ids = markers.flatMap((m) => (m.kind === "stack" ? m.ids : m.kind === "listing" ? [m.listing.id] : []));
    assert.deepEqual(ids.sort(), LISTINGS.map((l) => l.id).sort());
  });

  test("stacking is deterministic (same input → same keys)", () => {
    const shuffled = [...LISTINGS].reverse();
    const a = listingMarkers(LISTINGS, 13, mercator(13)).map((m) => m.key).sort();
    const b = listingMarkers(shuffled, 13, mercator(13)).map((m) => m.key).sort();
    assert.deepEqual(a, b);
  });
});

describe("status copy", () => {
  test("says which median is shown, and Berlin when zoomed out", () => {
    assert.match(tierStatus("city", 100, 0), /^Berlin median warm rent · 100 listings/);
    assert.match(tierStatus("district", 100, 0), /by district/);
    assert.match(tierStatus("neighbourhood", 100, 0), /by neighbourhood/);
    assert.equal(tierStatus("listing", 100, 42), "Showing 42 of 100 listings · zoom out for median rents");
  });
});
