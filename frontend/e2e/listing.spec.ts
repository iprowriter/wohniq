// Listing page (T9.5) end to end, against the offline demo backend.
//  * Definition of Done: opened from a search, the page shows the fit from that search, the
//    rent check with its scale, the scam risk with its checks, Around this flat (8 measures),
//    Right now, and a way back to the same results.

import { expect, test } from "@playwright/test";

test("Definition of Done: the listing page explains the flat, opened from a search", async ({ page }) => {
  await page.goto("/?q=" + encodeURIComponent("2 rooms in Kreuzberg"));
  const first = page.getByTestId("result-card").first();
  const fit = (await first.locator("text=/\\d+ fit/").innerText()).match(/\d+/)![0];
  await first.getByRole("link", { name: "View dossier" }).click();

  const verdicts = page.getByTestId("verdicts");
  await expect(verdicts).toContainText("Fit for your search");
  await expect(verdicts).toContainText(fit);
  await expect(verdicts).toContainText("Rent check");
  await expect(verdicts).toContainText("Scam risk");
  await expect(page.getByTestId("listing-location")).toContainText("Friedrichshain-Kreuzberg");

  await expect(page.getByTestId("rent-panel")).toContainText("Mietspiegel 2026 range");
  await expect(page.getByTestId("rent-panel").getByRole("img", { name: /Rent index/ })).toBeVisible();
  await expect(page.getByTestId("rent-panel")).toContainText("not legal advice");
  await expect(page.getByTestId("risk-panel")).toContainText(/Why the risk is low|What to ask/);
  await expect(page.getByTestId("around-grid").first().locator("li")).not.toHaveCount(0);
  await expect(page.getByTestId("right-now").first()).toHaveAttribute("data-status", /live|offline/);
  await expect(page.getByTestId("stops-map")).toBeVisible();

  // Request a viewing opens the safety checklist; Escape closes it.
  await page.getByRole("button", { name: /Request (a )?viewing/ }).first().click();
  await expect(page.getByRole("dialog", { name: "Before you request a viewing" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("without a search the fit says so, and the page has no horizontal overflow", async ({ page, isMobile }) => {
  await page.goto("/");
  const card = page.getByTestId("explore-card").first();
  await card.click();
  await expect(page.getByTestId("verdicts")).toContainText("Search to see the fit");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  if (isMobile) await expect(page.getByTestId("phone-bar")).toBeVisible();
  else await expect(page.getByTestId("price-card")).toBeVisible();
});
