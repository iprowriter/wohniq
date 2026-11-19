// "Explore Berlin" follows the map — `npm test`. Card selection rules.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import {
  EXPLORE_COUNT,
  exploreSubtitle,
  listingsForView,
  listingsInBounds,
  mapToCardsNote,
  pickExploreCards,
  type ExploreCard,
} from "../lib/map/exploreCards.ts";
import type { MapListing } from "../lib/map/listingsMap.ts";

function listing(id: string, lat: number, lng: number): MapListing {
  return { id, title: id, kiez: "K", district: "D", lat, lng, rooms: 2, size_m2: 50, warmmiete_eur: 1000 };
}

// 20 listings on a line west→east; "area" bounds select ids by longitude.
const ALL = Array.from({ length: 20 }, (_, i) => listing(`l${i}`, 52.5, 13.0 + i * 0.01));
const POOL = [ALL[19], ALL[18], ALL[17], ALL[16], ALL[15], ALL[14], ALL[13], ALL[12]];
const area = (from: number, to: number) =>
  listingsInBounds(ALL, { south: 52.4, north: 52.6, west: 13.0 + from * 0.01 - 0.001, east: 13.0 + to * 0.01 + 0.001 });

function seeded(seed = 1) {
  let s = seed;
  return () => ((s = (s * 16807) % 2147483647) / 2147483647);
}

function pick(inView: MapListing[], previous: ExploreCard<MapListing>[] = []) {
  return pickExploreCards({ inView, pool: POOL, all: ALL, previous, random: seeded() });
}

const ids = (cards: ExploreCard<MapListing>[]) => cards.map((c) => c.listing.id);
const tags = (cards: ExploreCard<MapListing>[]) => cards.map((c) => c.tag);

describe("always six cards", () => {
  test("an area with ≥ 6 listings → 6 of them, all highlighted", () => {
    const { cards, status } = pick(area(0, 9)); // 10 in view
    assert.equal(cards.length, EXPLORE_COUNT);
    assert.ok(ids(cards).every((id) => Number(id.slice(1)) <= 9));
    assert.deepEqual(tags(cards), Array(6).fill("in-view"));
    assert.deepEqual(status, { kind: "area", inView: 10 });
  });

  test("an area with exactly 6 → all 6", () => {
    const { cards } = pick(area(0, 5));
    assert.deepEqual(ids(cards).sort(), ["l0", "l1", "l2", "l3", "l4", "l5"]);
    assert.deepEqual(tags(cards), Array(6).fill("in-view"));
  });

  test("an area with 2 → those 2 first (highlighted), then 4 fillers from elsewhere", () => {
    const { cards, status } = pick(area(3, 4));
    assert.equal(cards.length, 6);
    assert.deepEqual(ids(cards).slice(0, 2).sort(), ["l3", "l4"]);
    assert.deepEqual(tags(cards), ["in-view", "in-view", "elsewhere", "elsewhere", "elsewhere", "elsewhere"]);
    assert.deepEqual(ids(cards).slice(2), ["l19", "l18", "l17", "l16"]); // from the pool, in order
    assert.deepEqual(status, { kind: "area", inView: 2 });
  });

  test("an empty area → 6 fillers, none of them in view", () => {
    const empty = listingsInBounds(ALL, { south: 10, north: 11, west: 10, east: 11 });
    const { cards, status } = pick(empty);
    assert.equal(cards.length, 6);
    assert.deepEqual(tags(cards), Array(6).fill("elsewhere"));
    assert.deepEqual(status, { kind: "empty" });
  });

  test("fillers never come from the area, even if the pool contains area listings", () => {
    const inView = area(14, 19); // 6 in view, all of which are in the pool
    const few = inView.slice(0, 2);
    const { cards } = pickExploreCards({ inView: few, pool: POOL, all: ALL, previous: [], random: seeded() });
    const fillerIds = cards.filter((c) => c.tag === "elsewhere").map((c) => c.listing.id);
    assert.equal(cards.length, 6);
    assert.ok(fillerIds.every((id) => !few.some((l) => l.id === id)));
  });

  test("no duplicates, and the pool running out falls back to any listing", () => {
    const { cards } = pickExploreCards({ inView: area(0, 0), pool: [ALL[19]], all: ALL, previous: [], random: seeded() });
    assert.equal(cards.length, 6);
    assert.equal(new Set(ids(cards)).size, 6);
  });
});

describe("stable while panning", () => {
  test("cards still in view keep their place; only departed ones are replaced", () => {
    const first = pick(area(0, 3)).cards; // 4 in view + 2 fillers
    const firstInView = ids(first).slice(0, 4);
    const next = pick(area(1, 4), first).cards; // l0 left, l4 arrived
    const nextIds = ids(next);
    // the three that stayed keep their relative order at the front
    assert.deepEqual(nextIds.slice(0, 3), firstInView.filter((id) => id !== "l0"));
    assert.equal(nextIds[3], "l4");
    // fillers unchanged
    assert.deepEqual(nextIds.slice(4), ids(first).slice(4));
  });

  test("an identical view gives identical cards", () => {
    const first = pick(area(2, 8)).cards;
    assert.deepEqual(ids(pick(area(2, 8), first).cards), ids(first));
  });
});

describe("zoomed out to the whole city", () => {
  test("everything in view → keep the current cards, nothing highlighted", () => {
    const before = pick(area(3, 4)).cards;
    const { cards, status } = pick(ALL, before);
    assert.deepEqual(ids(cards), ids(before));
    assert.ok(cards.every((c) => c.tag === null));
    assert.deepEqual(status, { kind: "random" });
  });
});

describe("which listings count as in view", () => {
  test("at the Berlin zoom level the whole city counts, even if the screen is too narrow", () => {
    const narrow = { south: 52.49, north: 52.51, west: 13.0, east: 13.05 }; // only l0–l5
    assert.equal(listingsForView(ALL, narrow, 10).length, ALL.length); // city tier
    assert.equal(listingsForView(ALL, narrow, 11).length, 6); // district tier: the bounds
    const { status } = pickExploreCards({ inView: listingsForView(ALL, narrow, 9), pool: POOL, all: ALL, previous: [] });
    assert.deepEqual(status, { kind: "random" });
  });
});

describe("copy", () => {
  test("heading line and the note under the map", () => {
    assert.equal(exploreSubtitle({ kind: "area", inView: 42 }, 6), "6 of 42 listings in this map area");
    assert.equal(exploreSubtitle({ kind: "area", inView: 6 }, 6), "6 listings in this map area");
    assert.equal(
      exploreSubtitle({ kind: "area", inView: 2 }, 2),
      "2 listings in this map area, plus others elsewhere in Berlin",
    );
    assert.match(exploreSubtitle({ kind: "empty" }, 0), /^No listings in this part of the map/);
    assert.match(exploreSubtitle({ kind: "random" }, 0), /Move the map/);
    assert.equal(mapToCardsNote({ kind: "area", inView: 2 }, 2), "2 listings from this map area are shown in Explore Berlin above");
    assert.equal(mapToCardsNote({ kind: "area", inView: 1 }, 1), "1 listing from this map area is shown in Explore Berlin above");
    assert.equal(mapToCardsNote({ kind: "random" }, 0), null);
  });
});
