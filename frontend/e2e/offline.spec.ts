// Offline check (T9.8, design rule "offline first"): every request leaving this machine is
// blocked. Each page must still work, with the local base map, and say so where live data
// (departures) is missing.

import { expect, test, type Page } from "@playwright/test";

const LOCAL = /^(https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\/|data:|blob:)/;

async function goOffline(page: Page) {
  const blocked: string[] = [];
  const errors: string[] = [];
  await page.context().route("**/*", (route) => {
    const url = route.request().url();
    if (LOCAL.test(url)) return route.continue();
    blocked.push(new URL(url).host);
    return route.abort("internetdisconnected");
  });
  page.on("pageerror", (e) => errors.push(e.message));
  return { blocked, errors };
}

async function mapTilesDrawn(page: Page) {
  // protomaps-leaflet draws the local PMTiles into canvases; no tile images from the web.
  await expect(page.locator(".leaflet-tile-pane canvas").first()).toBeVisible({ timeout: 20_000 });
}

test("every page works with no internet, and nothing tries to leave this machine", async ({ page }) => {
  const { blocked, errors } = await goOffline(page);
  const map = await (await page.request.get("http://localhost:8000/api/v1/listings/map")).json();
  const id = map[0].id;

  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await mapTilesDrawn(page);

  await page.goto("/?q=Quiet+2+rooms+in+Mitte+near+a+park");
  await expect(page.getByTestId("results-heading")).toHaveText(/^\d+ flats? /);
  await mapTilesDrawn(page);

  await page.goto(`/listings/${id}`);
  await expect(page.getByTestId("rent-panel")).toBeVisible();
  await expect(page.getByTestId("similar-card").first()).toBeVisible();
  await mapTilesDrawn(page);

  await page.goto("/rent-check");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  await page.goto("/lifestyle");
  await page.getByTestId("profile-cards").getByRole("button", { name: /Student/ }).click();
  await expect(page.getByTestId("area-row").first()).toBeVisible();
  await mapTilesDrawn(page);

  await page.goto("/neighborhoods");
  await expect(page.locator(".leaflet-overlay-pane path").first()).toBeAttached();
  await mapTilesDrawn(page);

  await page.goto(`/compare?ids=${id},${map[1].id}`);
  await expect(page.getByTestId("compare-column")).toHaveCount(2);

  await page.goto("/saved");
  await expect(page.getByRole("heading", { name: "Saved" })).toBeVisible();

  expect(errors).toEqual([]);
  // Nothing tried to leave this machine (photos come from local copies in demo mode).
  expect([...new Set(blocked)]).toEqual([]);
});
