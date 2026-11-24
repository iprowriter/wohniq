// Berlin Neighborhoods end-to-end (M8). Runs against the offline demo backend + production build.
//
// The first test is the Definition of Done: a user opens the app, clicks "Berlin
// Neighborhoods" in the menu, sees the ranked list next to the OSM map, clicks an area on
// the map and the sidebar reacts, then switches category and the ranking changes.

import { expect, test, type Page } from "@playwright/test";

const HELMHOLTZPLATZ = "036013";
const MUGGELHEIM = "094016";

const rows = (page: Page) => page.locator("li[data-key]");
const row = (page: Page, key: string) => page.locator(`li[data-key="${key}"]`);
const firstRowName = async (page: Page) =>
  (await rows(page).first().locator("button").first().getAttribute("aria-label")) ?? "";

async function clickArea(page: Page, key: string) {
  // Leaflet draws each area as an SVG path tagged with its key (NeighborhoodsMap). Click
  // like a user would: on a visible part of the area that no marker or label covers —
  // zooming in first if the area is too small at this zoom (e.g. on a phone).
  for (let attempt = 0; attempt < 4; attempt++) {
    const point = await page.evaluate((k) => {
      const path = document.querySelector(`path.nbh-area-${k}`);
      if (!path) return null;
      const r = path.getBoundingClientRect();
      for (let i = 1; i < 10; i++) {
        for (let j = 1; j < 10; j++) {
          const x = r.left + (r.width * i) / 10;
          const y = r.top + (r.height * j) / 10;
          if (document.elementFromPoint(x, y) === path) return { x, y };
        }
      }
      return null;
    }, key);
    if (point) {
      await page.mouse.click(point.x, point.y);
      return;
    }
    await page.getByRole("button", { name: "Zoom in" }).click();
    await page.waitForTimeout(400);
  }
  throw new Error(`area ${key} is not clickable on the map`);
}

/** The main navigation; on phones it sits behind the header's menu button. */
async function mainNav(page: Page) {
  const menu = page.getByRole("button", { name: "Open menu" });
  if (await menu.isVisible()) await menu.click();
  return page.getByRole("navigation", { name: "Main" });
}

async function openFromMenu(page: Page) {
  await page.goto("/");
  await (await mainNav(page)).getByRole("link", { name: "Neighbourhoods" }).click();
  await expect(page).toHaveURL(/\/neighborhoods$/);
  await expect(rows(page)).toHaveCount(143);
}

test("Definition of Done: menu → ranked list + map → map click reacts in the sidebar → category re-ranks", async ({
  page,
}) => {
  await openFromMenu(page);

  // List and map side by side (stacked on mobile); the list is ranked.
  await expect(page.getByTestId("neighborhoods-map")).toBeVisible();
  await expect(page.locator("path.nbh-area")).toHaveCount(143);
  await expect(rows(page).first()).toContainText("1");
  const overallFirst = await firstRowName(page);
  expect(overallFirst).toMatch(/^#1 /);

  // Click an area on the map → the sidebar selects, expands and shows it.
  await clickArea(page, HELMHOLTZPLATZ);
  const selected = row(page, HELMHOLTZPLATZ);
  await expect(selected.locator("button").first()).toHaveAttribute("aria-expanded", "true");
  await expect(selected.getByTestId("area-detail")).toBeVisible();
  await expect(selected.getByTestId("area-detail")).toContainText("of 143 overall");
  await expect(selected).toBeInViewport();
  await expect(page).toHaveURL(new RegExp(`area=${HELMHOLTZPLATZ}`));

  // Switch category → re-ranked, with the category's own labels and figures.
  await page
    .getByRole("button", { name: /Safety/ })
    .first()
    .click();
  await expect(page).toHaveURL(/category=safety/);
  await expect(page.getByRole("heading", { name: /Where is reported crime lowest/ })).toBeVisible();
  await expect.poll(() => firstRowName(page)).not.toBe(overallFirst);
  await expect(rows(page).first()).toContainText("Lowest crime");
  await expect(rows(page).first()).toContainText("per 100,000 residents");

  // …and which areas have the most crime.
  await page.getByRole("button", { name: "Highest crime first" }).click();
  await expect(rows(page).first()).toContainText("Highest crime");
  const worstRank = Number((await firstRowName(page)).match(/^#(\d+)/)?.[1]);
  expect(worstRank).toBeGreaterThan(130);
});

test("list → map: selecting a row outlines the area on the map", async ({ page }) => {
  await page.goto("/neighborhoods?category=safety");
  await expect(rows(page)).toHaveCount(143);
  await row(page, MUGGELHEIM).locator("button").first().click();
  await expect(row(page, MUGGELHEIM).getByTestId("area-detail")).toBeVisible();
  await expect(page.locator(`path.nbh-area-${MUGGELHEIM}`)).toHaveAttribute("stroke", "#111827");
  // Tapping the row again collapses it.
  await row(page, MUGGELHEIM).locator("button").first().click();
  await expect(row(page, MUGGELHEIM).getByTestId("area-detail")).toHaveCount(0);
});

test("search and district filter keep Berlin-wide ranks", async ({ page }) => {
  await page.goto("/neighborhoods?category=safety");
  await expect(rows(page)).toHaveCount(143);
  const rankBefore = await row(page, MUGGELHEIM).locator("button").first().getAttribute("aria-label");

  await page.getByPlaceholder("Find an area…").fill("muggel");
  await expect(rows(page)).toHaveCount(1);
  await expect(row(page, MUGGELHEIM).locator("button").first()).toHaveAttribute("aria-label", rankBefore!);

  await page.getByPlaceholder("Find an area…").fill("");
  await page.getByLabel("District").selectOption("Mitte");
  await expect(rows(page)).toHaveCount(10);
  await expect(page.getByText("Showing 10 of 143")).toBeVisible();

  await page.getByPlaceholder("Find an area…").fill("zzz");
  await expect(page.getByText(/No area matches/)).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(rows(page)).toHaveCount(143);
});

test("weights change the overall ranking and are kept in the URL", async ({ page }) => {
  await page.goto("/neighborhoods");
  await expect(rows(page)).toHaveCount(143);
  const before = await firstRowName(page);

  await page.getByRole("button", { name: /Adjust what matters/ }).click();
  await page.getByLabel(/Safety/).fill("0");
  await page.getByLabel(/Affordability/).fill("3");
  await expect(page.getByText("2 changes not applied yet")).toBeVisible();
  await page.getByRole("button", { name: "Update ranking" }).click();

  await expect(page).toHaveURL(/w=.*affordability%3A3|w=.*affordability:3/);
  await expect.poll(() => firstRowName(page)).not.toBe(before);
  await expect(page.getByText("Ranking is up to date")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Your weighted ranking/ })).toBeVisible();
});

test("a shared link opens the same category and area; categories in the detail re-rank", async ({ page }) => {
  await page.goto(`/neighborhoods?category=education&area=${HELMHOLTZPLATZ}`);
  await expect(page.getByRole("button", { name: /Education/ }).first()).toHaveAttribute("aria-pressed", "true");
  const detail = row(page, HELMHOLTZPLATZ).getByTestId("area-detail");
  await expect(detail).toBeVisible();
  await expect(detail).toContainText("School leavers with Abitur");
  await expect(detail).toContainText("district figure");

  await detail.getByRole("button", { name: /Parking: rank/ }).click();
  await expect(page).toHaveURL(/category=parking/);
  await expect(page.getByRole("heading", { name: /easiest to park/ })).toBeVisible();

  await detail.getByRole("button", { name: "About this data" }).click();
  await expect(detail.getByText("Sources for this area")).toBeVisible();
});

test("no horizontal overflow and the menu entry is reachable", async ({ page }) => {
  await page.goto("/neighborhoods");
  await expect(rows(page)).toHaveCount(143);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await expect((await mainNav(page)).getByRole("link", { name: "Neighbourhoods" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

test("affluence: land values per area, income shown Berlin-wide until district data exists", async ({ page }) => {
  const GRUNEWALD = "044007";
  await page.goto(`/neighborhoods?category=affluence&area=${GRUNEWALD}`);
  const detail = row(page, GRUNEWALD).getByTestId("area-detail");
  await expect(detail).toBeVisible();
  await expect(row(page, GRUNEWALD)).toContainText("Highest status"); // top 20% since the land values
  await expect(detail).toContainText("Land-value index");
  await expect(detail).toContainText("Typical land value");
  await expect(detail).toContainText("Gutachterausschuss · 2026");
  await expect(detail).toContainText("Income per taxpayer");
  await expect(detail).toContainText("Not published per neighborhood. Berlin-wide: €45,161 per taxpayer (2022)");
  await expect(detail).not.toContainText("on request");
});
