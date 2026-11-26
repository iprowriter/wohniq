// Saved searches + download/import (T9.7) — `npm test`.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import {
  addSearch,
  buildExport,
  findSearch,
  mergeImport,
  readSearches,
  recordRun,
  removeSearch,
  renameSearch,
  searchHref,
  SEARCHES_STORAGE_KEY,
  writeSearches,
  MAX_SEARCHES,
} from "../lib/savedSearches.ts";

class Mem {
  data = new Map<string, string>();
  get length() { return this.data.size; }
  clear() { this.data.clear(); }
  key(i: number) { return [...this.data.keys()][i] ?? null; }
  getItem(k: string) { return this.data.get(k) ?? null; }
  setItem(k: string, v: string) { this.data.set(k, v); }
  removeItem(k: string) { this.data.delete(k); }
}
const mem = () => new Mem() as unknown as Storage;
const P = (q: string, extra: Partial<{ fair: boolean; sort: "fit" | "price"; budget: number }> = {}) => ({ q, fair: false, sort: "fit" as const, ...extra });
const T0 = new Date("2026-11-20T10:00:00Z");
const T1 = new Date("2026-11-26T10:00:00Z");

describe("saved searches", () => {
  test("save, read back, and the same search again updates instead of duplicating", () => {
    const s = mem();
    let list = addSearch([], P("Quiet 2 rooms in Mitte"), ["a", "b"], T0);
    writeSearches(list, s);
    list = addSearch(readSearches(s), P("  quiet 2 ROOMS in mitte ", { sort: "price" }), ["a", "b", "c"], T1);
    writeSearches(list, s);
    const back = readSearches(s);
    assert.equal(back.length, 1);
    assert.equal(back[0].sort, "price");
    assert.equal(back[0].savedAt, T0.toISOString()); // first save kept
    assert.equal(back[0].lastCount, 3);
    assert.ok(findSearch(back, { q: "Quiet 2 rooms in Mitte" }));
    assert.equal(findSearch(back, { q: "Quiet 2 rooms in Mitte", budget: 900 }), undefined); // a budget is a different search
  });

  test("broken, foreign or old data reads as empty; bad fields are repaired", () => {
    const s = mem();
    s.setItem(SEARCHES_STORAGE_KEY, "{not json");
    assert.deepEqual(readSearches(s), []);
    s.setItem(SEARCHES_STORAGE_KEY, JSON.stringify({ v: 2, searches: [] }));
    assert.deepEqual(readSearches(s), []);
    s.setItem(SEARCHES_STORAGE_KEY, JSON.stringify({ v: 1, searches: [{ id: "x", q: "Mitte", sort: "weird", lastIds: [1, "a"] }, { id: "y" }] }));
    const [only, ...rest] = readSearches(s);
    assert.equal(rest.length, 0);
    assert.equal(only.sort, "fit");
    assert.deepEqual(only.lastIds, ["a"]);
    assert.equal(only.name, "Mitte");
  });

  test("at most MAX_SEARCHES, newest first", () => {
    let list: ReturnType<typeof readSearches> = [];
    for (let i = 0; i < MAX_SEARCHES + 5; i++) list = addSearch(list, P(`search ${i}`), [], T0);
    assert.equal(list.length, MAX_SEARCHES);
    assert.equal(list[0].q, `search ${MAX_SEARCHES + 4}`);
  });

  test("new since last time: only ids not seen on the previous run", () => {
    const list = addSearch([], P("Mitte"), ["a", "b"], T0);
    const run = recordRun(list, list[0].id, ["c", "a", "d"], T1)!;
    assert.deepEqual(run.newIds, ["c", "d"]);
    assert.equal(run.previousRunAt, T0.toISOString());
    const again = recordRun(run.searches, list[0].id, ["c", "a", "d"], T1)!;
    assert.deepEqual(again.newIds, []); // seen now
  });

  test("rename (blank falls back to the query) and remove", () => {
    let list = addSearch([], P("Mitte"), [], T0);
    list = renameSearch(list, list[0].id, "  My Mitte search ");
    assert.equal(list[0].name, "My Mitte search");
    list = renameSearch(list, list[0].id, "   ");
    assert.equal(list[0].name, "Mitte");
    assert.deepEqual(removeSearch(list, list[0].id), []);
  });

  test("run link keeps the query, filter, sort and budget", () => {
    assert.equal(searchHref({ q: "2 rooms", fair: true, sort: "price", budget: 900 }), "/?q=2+rooms&fair=1&sort=price&budget=900");
  });
});

describe("download and import", () => {
  test("import only adds what's missing and never overwrites", () => {
    const mine = renameSearch(addSearch([], P("Mitte"), [], T0), addSearch([], P("Mitte"), [], T0)[0].id, "x");
    const mineNamed = renameSearch(mine, mine[0].id, "Mine");
    const file = JSON.stringify(buildExport(["f1", "f2"], [...addSearch([], P("mitte"), ["z"], T1), ...addSearch([], P("Kreuzberg"), [], T1)], T1));
    const out = mergeImport(file, ["f2", "f3"], mineNamed);
    assert.deepEqual(out.flats, ["f2", "f3", "f1"]);
    assert.equal(out.addedFlats, 1);
    assert.equal(out.addedSearches, 1); // "mitte" is already there
    assert.equal(out.searches[0].name, "Mine");
    assert.equal(out.searches[1].q, "Kreuzberg");
  });

  test("into an empty browser: everything comes back", () => {
    const searches = addSearch([], P("Mitte", { fair: true }), ["a"], T0);
    const out = mergeImport(JSON.stringify(buildExport(["f1"], searches, T0)), [], []);
    assert.deepEqual(out.flats, ["f1"]);
    assert.deepEqual(out.searches, searches);
  });

  test("files that didn't come from WohnIQ are refused", () => {
    for (const bad of ["hello", "{}", JSON.stringify({ app: "Other", kind: "wohniq-saved-items", v: 1 }), JSON.stringify({ app: "WohnIQ", kind: "wohniq-saved-items", v: 9 })]) {
      assert.throws(() => mergeImport(bad, [], []), /isn't a WohnIQ saved-items file/);
    }
  });

  test("odd flat ids in a file are dropped", () => {
    const file = JSON.stringify({ ...buildExport([], [], T0), flats: ["ok-1", "<script>", 5, "a".repeat(80)] });
    assert.deepEqual(mergeImport(file, [], []).flats, ["ok-1"]);
  });
});
