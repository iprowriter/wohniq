// Rent check page (F11, T9.4) end to end, against the offline demo backend.
//  * Definition of Done: address search → size, age, rent, features → a verdict with the
//    numbers, the scale and the chart; exemptions and "not legal advice" always shown.
//  * Privacy: the flat's size, rent, features and energy value are never sent to the server.

import { expect, test, type Page } from "@playwright/test";

async function pickAddress(page: Page, typed: string) {
  await page.getByPlaceholder(/Street and house number/).fill(typed);
  await page.getByRole("listbox").getByRole("option").first().click();
  await expect(page.getByTestId("address-found")).toBeVisible();
}

test("Definition of Done: check a rent for any address, with the reasons", async ({ page }) => {
  const sent: string[] = [];
  page.on("request", (r) => sent.push(r.url()));
  await page.goto("/rent-check");
  await pickAddress(page, "Choriner Str. 41");
  await expect(page.getByTestId("address-found")).toContainText("location class: good");

  const form = page.getByRole("form", { name: "Your flat" });
  await form.getByPlaceholder("61").fill("61");
  await form.locator("select").selectOption({ label: "before 1918" });
  await form.getByPlaceholder("860").fill("860");
  await form.locator("summary", { hasText: /^Kitchen/ }).click();
  await page.getByLabel(/Fitted kitchen/).check();
  await page.getByRole("button", { name: "Check this rent" }).click();

  const verdict = page.getByTestId("rent-verdict");
  await expect(verdict).toHaveAttribute("data-verdict", "above_limit");
  await expect(verdict).toContainText("€14.10/m²");
  await expect(verdict).toContainText(/a month over the limit/);
  await expect(page.getByText("Row 135: good location")).toBeVisible();
  await expect(page.getByRole("img", { name: /Rent index €7\.09 to €13\.54/ })).toBeVisible();
  await expect(page.getByText("The rent brake has exceptions:")).toBeVisible();
  await expect(page.getByText(/not legal advice/).first()).toBeVisible();

  // Around this address + Right now (offline in tests: the nearest stops).
  await expect(page.getByTestId("around-grid").locator("li")).toHaveCount(8);
  await expect(page.getByTestId("right-now")).toHaveAttribute("data-status", /live|offline/);

  // Compare: kept in this tab, shown in the table.
  await page.getByRole("button", { name: "Add to comparison" }).click();
  await expect(page.getByTestId("rent-compare").locator("tbody tr")).toHaveCount(1);

  // Nothing about the flat left the browser.
  const leaked = sent.filter((u) => /[?&](size|cold|rent|energy|kwh)=/i.test(u) || /=(860|61)\b/.test(u));
  expect(leaked).toEqual([]);
});

test("building ages follow the address: East has one 1973–1990 band", async ({ page }) => {
  await page.goto("/rent-check");
  await pickAddress(page, "Choriner Str. 41"); // former East
  const select = page.getByRole("form", { name: "Your flat" }).locator("select");
  await expect(select.locator("option", { hasText: "1973–1990" })).toHaveCount(1);
  await expect(select.locator("option", { hasText: "1973–1985" })).toHaveCount(0);
});

test("Check this rent from a listing fills the form and runs the check", async ({ page }) => {
  const map = await (await page.request.get("http://localhost:8000/api/v1/listings/map")).json();
  const detail = await (await page.request.get(`http://localhost:8000/api/v1/listings/${map[0].id}`)).json();
  await page.goto(`/listings/${map[0].id}`);
  const link = page.getByRole("link", { name: /Check this rent|Open the full rent check/ }).first();
  await link.click();
  await expect(page).toHaveURL(new RegExp(`/rent-check\\?listing=${map[0].id}$`));
  await expect(page.getByTestId("prefill-note")).toContainText(detail.listing.title);
  await expect(page.getByLabel(/Size/).first()).toHaveValue(String(detail.listing.size_m2));
  await expect(page.getByLabel(/cold rent/i).first()).toHaveValue(String(detail.listing.kaltmiete_eur));
  await expect(page.locator("#rent-result")).toContainText(/rent-brake limit|rent index|new build/i);
  // Only the sample listing's id is in the address, never the figures.
  expect(page.url()).not.toContain(String(detail.listing.kaltmiete_eur));
});
