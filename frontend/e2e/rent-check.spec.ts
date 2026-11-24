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
