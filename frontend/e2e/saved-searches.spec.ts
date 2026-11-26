// Saved searches (T9.7, ADR-0020): browser only, no account. Save → home row → run again,
// /saved tabs (rename, delete), "new since last time", download then import elsewhere.

import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const QUERY = "Quiet 2 rooms in Mitte near a park";
const KEY = "wohniq_saved_searches_v1";

async function searchFor(page: Page, query: string) {
  await page.goto("/");
  await page.getByPlaceholder(/2 rooms near Alexanderplatz/).fill(query);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByTestId("results-heading")).toHaveText(/^\d+ flats? /);
}

test("save a search, find it on the home page and on /saved, run it again", async ({ page }) => {
  await searchFor(page, QUERY);
  const save = page.getByTestId("save-search");
  await save.click();
  await expect(save).toHaveText("Search saved");
  // The header count covers flats and searches (desktop header; on a phone it's in the menu).
  const menu = page.getByRole("button", { name: /menu/i });
  if (await menu.isVisible()) await menu.click();
  await expect(page.getByRole("link", { name: /^Saved \(1\)/ }).first()).toBeVisible();
  if (await menu.isVisible()) await page.keyboard.press("Escape");

  // Survives a reload; the home page offers it under the search box.
  await page.goto("/");
  const row = page.getByTestId("saved-searches-row");
  await expect(row.getByRole("link", { name: QUERY })).toBeVisible();
  await row.getByRole("link", { name: QUERY }).click();
  await expect(page.getByTestId("results-heading")).toHaveText(/^\d+ flats? /);
  await expect(page.getByTestId("new-since")).toContainText("No new flats since you last ran this saved search");

  // /saved: Searches tab (via "Manage" on the home page), rename, run, delete.
  await page.goto("/");
  await page.getByTestId("saved-searches-row").getByRole("link", { name: "Manage" }).click();
  await expect(page.getByRole("tab", { name: "Searches (1)" })).toHaveAttribute("aria-selected", "true");
  const item = page.getByTestId("saved-search");
  await expect(item).toHaveCount(1);
  await item.getByRole("button", { name: /^Rename/ }).click();
  await page.getByLabel("Name of this saved search").fill("Mitte, quiet");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect(item).toContainText("Mitte, quiet");
  await expect(item).toContainText(`“${QUERY}”`);
  await item.getByRole("link", { name: "Run" }).click();
  await expect(page).toHaveURL(/\?q=Quiet/);
  await page.goto("/saved?tab=searches");
  await page.getByRole("button", { name: "Delete Mitte, quiet" }).click();
  await expect(page.getByText("No saved searches yet.")).toBeVisible();
});

test("new since last time: flats not seen on the previous run get a New badge", async ({ page }) => {
  await searchFor(page, QUERY);
  await page.getByTestId("save-search").click();
  // Pretend the previous run (a week ago) saw only the first result.
  const ids: string[] = await page.evaluate((key) => {
    const data = JSON.parse(localStorage.getItem(key)!);
    const all: string[] = data.searches[0].lastIds;
    data.searches[0].lastIds = all.slice(0, 1);
    data.searches[0].lastRunAt = "2026-11-19T10:00:00.000Z";
    localStorage.setItem(key, JSON.stringify(data));
    return all;
  }, KEY);
  expect(ids.length).toBeGreaterThan(1);
  await page.goto("/");
  await page.getByTestId("saved-searches-row").getByRole("link", { name: QUERY }).click();
  await expect(page.getByTestId("new-since")).toContainText(`${ids.length - 1} new flat`);
  await expect(page.getByTestId("new-since")).toContainText("19 Nov");
  await expect(page.getByTestId("new-badge")).toHaveCount(ids.length - 1);
  // Seen now: running it once more shows nothing new.
  await page.reload();
  await expect(page.getByTestId("new-since")).toContainText("No new flats");
});

test("download saved items, import them into an empty browser; foreign files are refused", async ({ page, browser }, info) => {
  await searchFor(page, QUERY);
  await page.getByTestId("save-search").click();
  await page.getByRole("button", { name: /^Save$/ }).first().click(); // save one flat
  await page.goto("/saved");
  await expect(page.getByRole("tab", { name: "Flats (1)" })).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download my saved items" }).click()]);
  const file = info.outputPath("saved.json");
  await download.saveAs(file);
  expect(JSON.parse(readFileSync(file, "utf8")).app).toBe("WohnIQ");

  const fresh = await (await browser.newContext()).newPage();
  await fresh.goto("/saved");
  await fresh.getByTestId("import-file").setInputFiles(file);
  await expect(fresh.getByTestId("saved-message")).toContainText("Imported 1 flat and 1 search");
  await expect(fresh.getByRole("tab", { name: "Flats (1)" })).toBeVisible();
  await expect(fresh.getByRole("tab", { name: "Searches (1)" })).toBeVisible();
  // Importing again adds nothing.
  await fresh.getByTestId("import-file").setInputFiles(file);
  await expect(fresh.getByTestId("saved-message")).toContainText("Imported 0 flats and 0 searches");
  // A file from somewhere else is refused.
  await fresh.getByTestId("import-file").setInputFiles({ name: "other.json", mimeType: "application/json", buffer: Buffer.from('{"hello":1}') });
  await expect(fresh.getByTestId("saved-message")).toContainText("isn't a WohnIQ saved-items file");
});
