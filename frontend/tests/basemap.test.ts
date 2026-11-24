// Offline base map (ADR-0019) — `npm test`. No online tile server anywhere in the app.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import {
  BERLIN_INK_FLAVOR,
  ONLINE_TILE_PATTERNS,
  basemapAvailable,
  basemapUrl,
} from "../lib/map/basemap.ts";

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sourceFiles(p);
    return /\.(ts|tsx|css|mjs)$/.test(name) ? [p] : [];
  });
}

describe("offline base map", () => {
  test("no online tile server is used anywhere in the app", () => {
    const offenders: string[] = [];
    for (const dir of ["app", "components", "lib"]) {
      for (const file of sourceFiles(dir)) {
        if (file.endsWith(join("lib", "map", "basemap.ts"))) continue; // the pattern list itself
        const text = readFileSync(file, "utf8");
        for (const pattern of ONLINE_TILE_PATTERNS) {
          if (pattern.test(text)) offenders.push(`${file}: ${pattern}`);
        }
      }
    }
    assert.deepEqual(offenders, []);
  });

  test("no map uses Leaflet's TileLayer any more", () => {
    const users = sourceFiles("components")
      .concat(sourceFiles("app"))
      .filter((f) => /<TileLayer\b/.test(readFileSync(f, "utf8")));
    assert.deepEqual(users, []);
  });

  test("the map file comes from the API unless configured", () => {
    assert.match(basemapUrl(), /\/tiles\/berlin\.pmtiles$/);
  });

  test("the flavor defines every colour the basemap rules read", () => {
    for (const key of ["background", "earth", "water", "park_a", "buildings", "major", "highway",
      "railway", "roads_label_major", "city_label", "subplace_label_halo"]) {
      assert.ok(key in BERLIN_INK_FLAVOR, key);
    }
    assert.equal(BERLIN_INK_FLAVOR.water, "#B9C8E8"); // design token map-water
    assert.equal(BERLIN_INK_FLAVOR.earth, "#EBEEF3"); // design token map-land
  });

  test("availability is a 7-byte range request checking the PMTiles header", async () => {
    const calls: RequestInit[] = [];
    const ok = (body: string, status = 206) =>
      (async (_url: unknown, init?: RequestInit) => {
        calls.push(init ?? {});
        return new Response(body, { status });
      }) as typeof fetch;
    assert.equal(await basemapAvailable("x", ok("PMTiles")), true);
    assert.deepEqual(calls[0].headers, { Range: "bytes=0-6" });
    assert.equal(await basemapAvailable("x", ok("<html>")), false);
    assert.equal(await basemapAvailable("x", ok("", 404)), false);
    const failing = (async () => {
      throw new TypeError("network down");
    }) as typeof fetch;
    assert.equal(await basemapAvailable("x", failing), false);
  });
});
