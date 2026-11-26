// Berlin Neighborhoods page logic — `npm test`. Runs against real API responses exported
// by the backend (`make neighborhoods-fixture`; a backend test fails if they go stale).

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { AreaDetail, NeighborhoodCatalog, Ranking } from "../lib/neighborhoods/types.ts";
import {
  BANDS,
  OVERALL,
  bandIndex,
  changedWeights,
  defaultWeights,
  filterAreas,
  normalize,
  orderAreas,
  orderLabel,
  pageQuery,
  parsePageState,
  parseWeightsParam,
  rankColor,
  rankTextColor,
  sameWeights,
  setWeight,
  sourceLabel,
  sourceMap,
  tierBadge,
  versusBerlin,
  weightsParam,
} from "../lib/neighborhoods/logic.ts";

function fixture<T>(name: string): T {
  return JSON.parse(readFileSync(new URL(`./fixtures/${name}`, import.meta.url), "utf-8"));
}

const catalog = fixture<NeighborhoodCatalog>("neighborhoods-catalog.json");
const overall = fixture<Ranking>("neighborhoods-ranking-overall.json");
const safety = fixture<Ranking>("neighborhoods-ranking-safety.json");
const area = fixture<AreaDetail>("neighborhoods-area.json");

describe("contract: the real API responses have what the page relies on", () => {
  test("catalog: categories with labels, metrics and Berlin figures", () => {
    assert.equal(catalog.area_count, 143);
    assert.ok(catalog.categories.length >= 10);
    for (const c of catalog.categories) {
      assert.ok(c.label && c.emoji && c.question && c.best_label && c.worst_label && c.caveat);
      assert.ok(c.default_weight >= 0 && c.default_weight <= catalog.max_weight);
      for (const m of c.metrics) assert.ok(m.available ? m.berlin_text : m.requires);
    }
    assert.equal(catalog.districts.length, 12);
  });

  test("affluence: land values available, income pending with the Berlin-wide figure", () => {
    const affluence = catalog.categories.find((c) => c.id === "affluence")!;
    const byId = Object.fromEntries(affluence.metrics.map((m) => [m.id, m]));
    assert.ok(byId.land_value.available && byId.land_value.weight > 0);
    assert.ok(byId.land_value_eur.available && byId.land_value_eur.weight === 0); // context only
    assert.equal(byId.income.available, false);
    assert.equal(byId.income.requires, "Not published per neighborhood");
    assert.equal(byId.income.city_text, "€45,161 per taxpayer (2022)");
    assert.ok(sourceMap(catalog.sources)[byId.income.city_source_id!]);
  });

  test("rankings: every area once, ranks ascending, tiers and headline figures", () => {
    for (const r of [overall, safety]) {
      assert.equal(r.areas.length, r.total);
      assert.equal(new Set(r.areas.map((a) => a.key)).size, r.total);
      const ranks = r.areas.map((a) => a.rank);
      assert.deepEqual(
        ranks,
        [...ranks].sort((a, b) => a - b),
      );
      assert.ok(r.areas.every((a) => a.centroid.length === 2 && ["best", "middle", "worst"].includes(a.tier)));
    }
    assert.equal(overall.category, OVERALL);
    assert.ok(overall.areas.every((a) => a.headline === null));
    assert.ok(safety.areas.every((a) => a.headline && a.headline.text.length > 0));
    assert.equal(safety.best_label, "Lowest crime");
  });

  test("area detail: every category, every metric sourced", () => {
    const sources = sourceMap(catalog.sources);
    assert.equal(area.categories.length, catalog.categories.length);
    for (const c of area.categories) {
      for (const m of c.metrics) {
        assert.ok(sources[m.source_id], `unknown source ${m.source_id}`);
        assert.ok(m.text && m.berlin_text && m.method);
      }
    }
    for (const h of [...area.strengths, ...area.watch_outs]) assert.ok(sources[h.source_id]);
    assert.match(area.summary, /of 143 overall/);
  });
});

describe("weights", () => {
  const defaults = defaultWeights(catalog);

  test("defaults come from the catalog", () => {
    assert.equal(defaults.safety, 2);
    assert.equal(Object.keys(defaults).length, catalog.categories.length);
  });

  test("URL round trip: sorted, so equal weights give equal URLs", () => {
    const w = { ...defaults, safety: 3, parking: 0 };
    const text = weightsParam(w);
    assert.equal(text, weightsParam({ ...w }));
    assert.deepEqual(parseWeightsParam(text, catalog), w);
    assert.ok(text.indexOf("affluence") < text.indexOf("safety"));
  });

  test("parse drops unknown ids and out-of-range values; all-zero is rejected", () => {
    const w = parseWeightsParam("safety:3,vibes:2,parking:9,transit:x", catalog);
    assert.ok(w);
    assert.equal(w!.safety, 3);
    assert.equal(w!.parking, defaults.parking);
    assert.equal(parseWeightsParam("vibes:2", catalog), null);
    const zeros = catalog.categories.map((c) => `${c.id}:0`).join(",");
    assert.equal(parseWeightsParam(zeros, catalog), null);
    assert.equal(parseWeightsParam("", catalog), null);
  });

  test("change counting and clamping", () => {
    assert.equal(changedWeights(defaults, defaults), 0);
    assert.equal(changedWeights(defaults, { ...defaults, safety: 0, transit: 3 }), 2);
    assert.ok(sameWeights(defaults, { ...defaults }));
    assert.equal(setWeight(defaults, "safety", 9, 3).safety, 3);
    assert.equal(setWeight(defaults, "safety", -2, 3).safety, 0);
  });
});

describe("URL state", () => {
  test("defaults to overall; unknown category and malformed area are ignored", () => {
    const s = parsePageState(new URLSearchParams("category=vibes&area=abc"), catalog);
    assert.deepEqual(s, { category: OVERALL, area: null, weights: null });
  });

  test("round trip keeps category, area and non-default weights only", () => {
    const state = { category: "safety", area: "036013", weights: null };
    const q = pageQuery(state, catalog);
    assert.equal(q, "?category=safety&area=036013");
    assert.deepEqual(parsePageState(new URLSearchParams(q.slice(1)), catalog), state);
    assert.equal(pageQuery({ category: OVERALL, area: null, weights: defaultWeights(catalog) }, catalog), "");
    const custom = pageQuery(
      { category: OVERALL, area: null, weights: { ...defaultWeights(catalog), transit: 3 } },
      catalog,
    );
    assert.match(custom, /^\?w=/);
  });
});

describe("filtering and ordering the list", () => {
  test("search is case- and accent-insensitive and covers wider area and district", () => {
    assert.equal(normalize("Müggelheim"), "muggelheim");
    assert.equal(normalize("Schloßstraße"), "schlossstrasse");
    const hits = filterAreas(safety.areas, { query: "muggel", district: "" });
    assert.deepEqual(
      hits.map((a) => a.name),
      ["Müggelheim"],
    );
    const kreuzberg = filterAreas(safety.areas, { query: "kreuzberg", district: "" });
    assert.ok(kreuzberg.length >= 8); // matches the district name too
  });

  test("district filter keeps Berlin-wide ranks", () => {
    const mitte = filterAreas(safety.areas, { query: "", district: "Mitte" });
    assert.equal(mitte.length, 10);
    for (const a of mitte) {
      assert.equal(a.rank, safety.areas.find((x) => x.key === a.key)!.rank);
    }
  });

  test("worst first reverses ranks; ties stay alphabetical both ways", () => {
    const best = orderAreas(safety.areas, "best");
    const worst = orderAreas(safety.areas, "worst");
    assert.equal(best[0].rank, 1);
    assert.equal(worst[0].rank, Math.max(...safety.areas.map((a) => a.rank)));
    for (const list of [best, worst]) {
      for (let i = 1; i < list.length; i++) {
        if (list[i].rank === list[i - 1].rank) assert.ok(list[i - 1].name.localeCompare(list[i].name) <= 0);
      }
    }
  });

  test("order labels use the category's wording", () => {
    assert.equal(orderLabel("best", "Lowest crime", "Highest crime"), "Lowest crime first");
    assert.equal(orderLabel("worst", "Lowest crime", "Highest crime"), "Highest crime first");
    assert.equal(orderLabel("worst", null, null), "Worst first");
  });
});

describe("colours, tiers and comparisons", () => {
  test("five rank bands: top fifth darkest, bottom fifth orange", () => {
    assert.equal(bandIndex(1, 143), 0);
    assert.equal(bandIndex(29, 143), 0);
    assert.equal(bandIndex(30, 143), 1);
    assert.equal(bandIndex(143, 143), 4);
    assert.equal(rankColor(1, 143), BANDS[0].color);
    assert.equal(rankColor(143, 143), BANDS[4].color);
    assert.equal(rankTextColor(72, 143), "#0D1321"); // lighter bands → ink text
    assert.equal(rankTextColor(143, 143), "#0D1321"); // bottom 20% is the palest blue, not an alarm colour
    assert.equal(rankTextColor(1, 143), "#ffffff");
  });

  test("badges only for the top and bottom tiers, never an 'avoid'", () => {
    assert.equal(tierBadge("middle", "Lowest crime", "Highest crime"), null);
    assert.equal(tierBadge("best", "Lowest crime", "Highest crime")!.text, "Lowest crime");
    assert.equal(tierBadge("worst", "Lowest crime", "Highest crime")!.text, "Highest crime");
    for (const c of catalog.categories) assert.doesNotMatch(`${c.best_label} ${c.worst_label}`, /avoid/i);
  });

  test("versus Berlin respects each metric's direction", () => {
    assert.equal(versusBerlin(1000, 3198, false), "better"); // less crime
    assert.equal(versusBerlin(5000, 3198, false), "worse");
    assert.equal(versusBerlin(60, 44, true), "better"); // more Abitur
    assert.equal(versusBerlin(44.5, 44, true), "same"); // within 3%
    assert.equal(versusBerlin(1, null, true), "same");
  });

  test("source labels are short and include the data period", () => {
    const s = sourceMap(catalog.sources);
    assert.equal(sourceLabel(s.pks_kriminalitaetsatlas), "Polizei Berlin · 2023–2025");
    assert.equal(sourceLabel(s.unfallatlas_2025), "Unfallatlas · 2025");
    assert.equal(sourceLabel(s.blickpunkt_schule_2026), "SenBJF schools · 2024/25"); // school year kept
    assert.equal(sourceLabel(s.mss_2023), "Senate MSS · 2022");
    assert.equal(sourceLabel(s.bodenrichtwerte_2026), "Gutachterausschuss · 2026");
    assert.equal(sourceLabel(s.afs_lohnsteuer_2022), "Statistik BB · 2022");
    assert.equal(sourceLabel(undefined), "Source");
  });
});
