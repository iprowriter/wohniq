// Homepage search (area-aware, ADR-0014) and "See on the map". Runs against the offline
// demo backend + production build, like the other journeys.
//
// The first tests are the Definitions of Done:
//  * "a quiet flat in Mitte, Spandau, Lichtenberg, Treptow" only returns flats in those
//    areas, each explained; too-low budgets say so and offer a minimum; nothing in an
//    area → labelled nearby flats.
//  * The map under "Explore Berlin" shows prices; a click opens a card (photo, price,
//    location, rooms, m²) and marks the pill; zooming out shows neighbourhood, district
//    and finally Berlin medians.

import { expect, test, type Page } from "@playwright/test";

const REPORTED = "a quiet flat in Mitte, Spandau, Lichtenberg, Treptow";
const AREAS = ["Mitte", "Spandau", "Lichtenberg", "Treptow"];

async function searchFor(page: Page, query: string) {
  await page.goto("/");
  await page.getByPlaceholder(/quiet 2-room/).fill(query);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText(/ranked by fit/)).toBeVisible();
}

test("Definition of Done: districts in the query are respected and every match is explained", async ({ page }) => {
  await searchFor(page, REPORTED);
  await expect(page.getByText("in Mitte / Spandau / Lichtenberg / Treptow")).toBeVisible();

  const badges = page.getByTestId("area-badge");
  await expect(badges.first()).toBeVisible();
  const labels = await badges.allInnerTexts();
  expect(labels.length).toBeGreaterThan(0);
  for (const label of labels) expect(AREAS.some((a) => label.trim() === `In ${a}`)).toBe(true);

  // No bare "A strong match for your search." — the summary says why.
  const summaries = await page.locator("article p.font-medium").allInnerTexts();
  for (const s of summaries) {
    expect(s).not.toMatch(/^A (strong|solid|partial) (match|fit)( for your search)?\.?$/);
    expect(s).toMatch(/in (Mitte|Spandau|Lichtenberg|Treptow)/);
  }
});

test("Definition of Done: a too-low budget is explained, with a one-click minimum budget", async ({ page }) => {
  await searchFor(page, "quiet flat in Mitte budget €300");
  const notice = page.locator("[data-kind=budget_too_low]");
  await expect(notice).toContainText("Your budget is too low for Mitte");
  await expect(notice).toContainText("raise your budget to at least");
  await expect(page.getByText("0 results")).toBeVisible();

  await notice.getByRole("button", { name: /^Search with €/ }).click();
  await expect(page.getByText(/^1 result|^\d+ results/)).toBeVisible();
  await expect(page.getByTestId("area-badge").first()).toHaveText("In Mitte");
  await expect(page.locator("[data-kind=budget_too_low]")).toHaveCount(0);
});

test("Definition of Done: nothing in the area → nearby flats, labelled with their distance", async ({ page }) => {
  await searchFor(page, "flat in Wilmersdorf");
  await expect(page.locator("[data-kind=nearby_results]")).toContainText("No listings in Wilmersdorf right now");
  const labels = await page.getByTestId("area-badge").allInnerTexts();
  expect(labels.length).toBeGreaterThan(0);
  for (const label of labels) expect(label).toMatch(/^Near Wilmersdorf · \d+\.\d km$/);
});

test("after the auto-scroll to results, the header stays on top and doesn't cover the chips", async ({ page }) => {
  await searchFor(page, REPORTED);
  await page.waitForTimeout(800); // smooth scroll to the results
  const layout = await page.evaluate(() => {
    const header = document.querySelector("header")!.getBoundingClientRect();
    const label = [...document.querySelectorAll("span")].find((s) => s.textContent === "Understood as")!;
    const chips = label.parentElement!.getBoundingClientRect();
    const hit = document.elementFromPoint(chips.left + 40, chips.top + chips.height / 2)!;
    return {
      scrolled: window.scrollY > 0,
      headerTop: Math.round(header.top),
      chipsBelowHeader: chips.top >= header.bottom,
      chipsHitTestable: !hit.closest("header"),
    };
  });
  expect(layout).toEqual({ scrolled: true, headerTop: 0, chipsBelowHeader: true, chipsHitTestable: true });
});

// --- See on the map ---------------------------------------------------------------------

async function openMap(page: Page) {
  await page.goto("/");
  const map = page.getByTestId("listings-map");
  await map.scrollIntoViewIfNeeded();
  await expect(page.getByTestId("map-pill").first()).toBeAttached();
  return map;
}

/** A marker whose centre is inside the map and not covered by anything else. */
async function clickableInMap(page: Page, selector: string) {
  const handle = await page.evaluateHandle((sel) => {
    const map = document.querySelector("[data-testid=listings-map] .leaflet-container")!.getBoundingClientRect();
    return [...document.querySelectorAll<HTMLElement>(sel)].find((el) => {
      const r = el.getBoundingClientRect();
      const x = r.left + r.width / 2;
      const y = r.top + r.height / 2;
      const inside = x > map.left + 40 && x < map.right - 60 && y > map.top + 80 && y < map.bottom - 60;
      return inside && el.contains(document.elementFromPoint(x, y));
    });
  }, selector);
  return handle.asElement()!;
}

async function zoomOut(page: Page, tier: string) {
  await page.locator(".leaflet-control-zoom-out").click();
  await expect(page.getByTestId("listings-map")).toHaveAttribute("data-tier", tier);
}

test("Definition of Done: the map under Explore Berlin shows prices; a click opens the listing card", async ({
  page,
}) => {
  const map = await openMap(page);

  // Placed right after the "Explore Berlin" listings.
  const headings = await page.locator("h2").allInnerTexts();
  expect(headings.indexOf("See on the map")).toBe(headings.indexOf("Explore Berlin") + 1);

  await expect(map).toHaveAttribute("data-tier", "listing");
  await expect(page.getByTestId("map-status")).toContainText(/Showing \d+ of 140 listings/);
  const pill = await clickableInMap(page, "[data-testid=map-pill]");
  const price = (await pill.innerText()).trim();
  expect(price).toMatch(/^€\d{1,3}(\.\d{3})?$/); // just the rent

  await pill.click();
  const card = page.getByTestId("map-card");
  await expect(card).toBeVisible();
  await expect(card).toContainText(price);
  await expect(card).toContainText(/\d+(\.\d)? rooms? • \d+ m²/);
  await expect(card.getByRole("img")).toBeVisible(); // photo (or its placeholder offline)
  await expect(card.getByRole("link", { name: "View listing" })).toHaveAttribute("href", /^\/listings\//);

  // The clicked pill is marked as selected; after closing it stays marked as visited.
  await expect(page.locator(".wq-pill--selected")).toHaveText(price);
  await card.getByRole("button", { name: "Close" }).click();
  await expect(card).toHaveCount(0);
  await expect(page.locator(".wq-pill--visited")).toHaveText(price);
});

test("Definition of Done: zooming out clusters into neighbourhood, district and Berlin medians", async ({ page }) => {
  await openMap(page);

  await zoomOut(page, "neighbourhood");
  await expect(page.locator("[data-testid=map-area][data-tier=neighbourhood]").first()).toBeAttached();
  await expect(page.locator("[data-testid=map-area][data-name=Kreuzberg]")).toContainText(/€[\d.]+ median/);
  await expect(page.getByTestId("map-pill")).toHaveCount(0);

  await zoomOut(page, "district");
  await expect(page.locator("[data-testid=map-area][data-name=Friedrichshain-Kreuzberg]")).toContainText(/median/);

  await zoomOut(page, "city");
  const berlin = page.locator("[data-testid=map-area][data-tier=city]");
  await expect(berlin).toHaveCount(1);
  await expect(berlin).toContainText("Berlin median rent");
  await expect(berlin).toContainText("140 listings");
  await expect(page.getByTestId("map-status")).toContainText("Berlin median warm rent");

  // And back in: the Berlin bubble opens the districts.
  await berlin.click();
  await expect(page.getByTestId("listings-map")).toHaveAttribute("data-tier", "district");
});

// --- Explore Berlin follows the map ------------------------------------------------------

async function exploreCards(page: Page) {
  return page.getByTestId("explore-card").evaluateAll((els) =>
    els.map((e) => ({ id: (e as HTMLElement).dataset.id!, tag: (e as HTMLElement).dataset.tag! })),
  );
}

/** Ids of listings whose price pill is inside the visible map. */
async function pillIdsInView(page: Page) {
  return page.evaluate(() => {
    const m = document.querySelector("[data-testid=listings-map] .leaflet-container")!.getBoundingClientRect();
    return [...document.querySelectorAll<HTMLElement>("[data-testid=map-pill]")]
      .filter((e) => {
        const r = e.getBoundingClientRect();
        const x = r.left + r.width / 2;
        const y = r.top + r.height / 2;
        return x > m.left && x < m.right && y > m.top && y < m.bottom;
      })
      .map((e) => e.dataset.id!);
  });
}

async function mapTopInPage(page: Page) {
  return page.evaluate(() =>
    Math.round(document.querySelector("[data-testid=listings-map]")!.getBoundingClientRect().top + window.scrollY),
  );
}

test("Explore Berlin: 6 random cards on load, unchanged until the user moves the map", async ({ page }) => {
  await openMap(page);
  await expect(page.getByTestId("explore-card")).toHaveCount(6);
  const before = await exploreCards(page);
  expect(before.every((c) => c.tag === "none")).toBe(true);
  await expect(page.getByTestId("explore-subtitle")).toContainText("A random selection");
  await page.waitForTimeout(1000); // the map's own initial view must not re-pick the cards
  expect(await exploreCards(page)).toEqual(before);
  await expect(page.getByTestId("map-cards-note")).toHaveCount(0);
});

test("Explore Berlin follows the map: area listings first and highlighted, always 6, map never moves", async ({
  page,
}) => {
  await openMap(page);
  const mapTop = await mapTopInPage(page);

  // Zoom into a small area: a few listings in view, the rest filled from elsewhere.
  for (let i = 0; i < 3; i++) {
    await page.locator(".leaflet-control-zoom-in").click();
    await page.waitForTimeout(400);
  }
  await expect(page.getByTestId("map-cards-note")).toBeVisible();
  // Updates are debounced: wait until the cards match the final view's pills.
  await expect
    .poll(async () => {
      const inView = (await exploreCards(page)).filter((c) => c.tag === "in-view").map((c) => c.id);
      const pills = await pillIdsInView(page);
      return pills.length <= 6
        ? [...inView].sort().join() === [...pills].sort().join()
        : inView.length === 6 && inView.every((id) => pills.includes(id));
    })
    .toBe(true);
  const cards = await exploreCards(page);
  expect(cards).toHaveLength(6);
  const inView = cards.filter((c) => c.tag === "in-view");
  expect(inView.length).toBeGreaterThan(0);
  // in-view cards come first, fillers after
  expect(cards.map((c) => c.tag)).toEqual([
    ...Array(inView.length).fill("in-view"),
    ...Array(6 - inView.length).fill(inView.length < 6 ? "elsewhere" : "in-view"),
  ]);
  // fillers are never listings whose pills are on the map
  const pills = await pillIdsInView(page);
  for (const f of cards.filter((c) => c.tag === "elsewhere")) expect(pills).not.toContain(f.id);
  await expect(page.getByTestId("explore-subtitle")).toContainText("in this map area");
  expect(await mapTopInPage(page)).toBe(mapTop); // cards updated above, map didn't jump

  // Opening a price card auto-pans the map; the cards must not change.
  const pill = await clickableInMap(page, "[data-testid=map-pill]");
  await pill.click();
  await expect(page.getByTestId("map-card")).toBeVisible();
  await page.waitForTimeout(800);
  expect(await exploreCards(page)).toEqual(cards);
  await page.getByTestId("map-card").getByRole("button", { name: "Close" }).click();

  // Zoomed out to all of Berlin: nothing to highlight, still 6 cards.
  for (let i = 0; i < 6; i++) {
    await page.locator(".leaflet-control-zoom-out").click();
    await page.waitForTimeout(300);
  }
  await expect(page.getByTestId("listings-map")).toHaveAttribute("data-tier", "city");
  await expect(page.getByTestId("explore-subtitle")).toContainText("A random selection");
  const zoomedOut = await exploreCards(page);
  expect(zoomedOut).toHaveLength(6);
  expect(zoomedOut.every((c) => c.tag === "none")).toBe(true);
  expect(await mapTopInPage(page)).toBe(mapTop);
});

test("the note under the map scrolls up to Explore Berlin", async ({ page }) => {
  await openMap(page);
  await page.locator(".leaflet-control-zoom-in").click();
  await page.getByTestId("map-cards-note").click();
  await expect
    .poll(() => page.getByTestId("explore").evaluate((e) => Math.round(e.getBoundingClientRect().top)))
    .toBeLessThan(120);
  await expect(page.getByTestId("explore")).toBeInViewport();
});

test("the homepage never gets wider than the screen, also after the cards follow the map", async ({ page }) => {
  // A wider page makes phones zoom out, which also made taps on price pills miss.
  await openMap(page);
  const fits = () =>
    page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  expect(await fits()).toBe(true);
  await page.locator(".leaflet-control-zoom-in").click();
  await expect(page.getByTestId("map-cards-note")).toBeVisible();
  expect(await fits()).toBe(true);
});
