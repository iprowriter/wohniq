// Similar apartments + compare (T9.7): listing → similar flats → Compare with… → /compare
// (reloadable, shareable) → remove / add; result cards feed the same list via the bar.

import { expect, test, type Page } from "@playwright/test";

async function firstListingId(page: Page): Promise<string> {
  const res = await page.request.get("http://localhost:8000/api/v1/listings/map");
  return (await res.json())[0].id;
}

test("similar apartments explain themselves; high-risk ones carry their chip", async ({ page }) => {
  const id = await firstListingId(page);
  await page.goto(`/listings/${id}`);
  const section = page.getByTestId("similar");
  await expect(section.getByRole("heading", { name: /Similar (apartments to this|flats within the rent limit)/ })).toBeVisible();
  const cards = section.getByTestId("similar-card");
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBe(6);
  for (const card of await cards.all()) {
    if (!(await card.isVisible())) continue; // phones show three until "Show more"
    await expect(card.getByRole("list", { name: "Why it's similar" })).toContainText(/km away/);
    await expect(card.getByTestId("risk-chip")).toBeVisible();
  }
  const more = section.getByRole("button", { name: "Show more similar flats" });
  if (await more.isVisible()) {
    await more.click();
    await expect(cards.nth(5)).toBeVisible();
  }
});

test("Compare with a similar flat → /compare → remove and add → reload keeps it", async ({ page }) => {
  const id = await firstListingId(page);
  await page.goto(`/listings/${id}`);
  await expect(page.getByTestId("similar-card").first()).toBeVisible();
  const opener = page.getByTestId("compare-with");
  if (await opener.isVisible()) await opener.click();
  else await page.getByRole("button", { name: "Compare with another flat" }).click();
  const dialog = page.getByRole("dialog", { name: "Compare with…" });
  await dialog.getByRole("region", { name: "Similar flats" }).getByRole("button").first().click();

  await expect(page).toHaveURL(new RegExp(`/compare\\?ids=${id},`));
  const columns = page.getByTestId("compare-column");
  await expect(columns).toHaveCount(2);
  const table = page.getByTestId("compare-table");
  for (const label of ["Warm rent", "Rent-brake limit", "Level", "Nearest S/U-Bahn", "Schools within 1 km"]) {
    await expect(table.getByRole("rowheader", { name: label })).toBeVisible();
  }
  await expect(table.getByText("best").first()).toBeVisible();

  // Add a third flat by pasting its link, then reload: the address keeps all three.
  const res = await page.request.get("http://localhost:8000/api/v1/listings/map");
  const all: { id: string }[] = await res.json();
  const url = new URL(page.url());
  const shown = url.searchParams.get("ids")!.split(",");
  const third = all.find((x) => !shown.includes(x.id))!.id;
  await page.getByLabel(/Add another flat/).fill(`http://localhost:3000/listings/${third}`);
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(columns).toHaveCount(3);
  await page.reload();
  await expect(columns).toHaveCount(3);

  // Remove one column; the compare list follows the address.
  await columns.nth(1).getByRole("button", { name: /^Remove/ }).click();
  await expect(columns).toHaveCount(2);
  expect(new URL(page.url()).searchParams.get("ids")!.split(",")).toEqual([id, third]);
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("wohniq_compare_v1")!).ids);
  expect(stored).toEqual([id, third]);

  // A trip line appears for a place you choose.
  await page.getByLabel("Trip to a place you choose").fill("Alexanderplatz");
  await page.getByRole("button", { name: "Add trip" }).click();
  await expect(table.getByRole("rowheader", { name: "Trip to Alexanderplatz" })).toBeVisible();
});

test("result cards feed the same list; the bar opens /compare", async ({ page }) => {
  await page.goto("/?q=Quiet+2+rooms+in+Mitte+near+a+park");
  await expect(page.getByTestId("results-heading")).toHaveText(/^\d+ flats? /);
  const compareButtons = page.locator("article").getByRole("button", { name: "Compare", exact: true });
  await compareButtons.nth(0).click();
  const bar = page.getByTestId("compare-bar");
  await expect(bar).toContainText("Compare (1)");
  await compareButtons.nth(0).click(); // the next card (the first now reads "Comparing")
  await expect(bar).toContainText("Compare (2)");
  await bar.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/compare\?ids=/);
  await expect(page.getByTestId("compare-column")).toHaveCount(2);
  await expect(page.getByTestId("compare-bar")).toHaveCount(0); // not on /compare itself
  await page.getByRole("button", { name: "Clear all" }).click();
  await expect(page.getByText("Nothing to compare yet.")).toBeVisible();
});
