// Lifestyle Match end-to-end (T7.7). Runs against the offline demo backend + production build.
//
// The first test is the Definition of Done: a student using the preset is offered an area
// near TU Berlin within a typical student budget, with reasons — and their answers are
// not stored or put anywhere that could be logged (URL, cookies, localStorage).

import { expect, test, type Page, type Request } from "@playwright/test";

const API = "/api/v1/lifestyle/";

/** Record every Lifestyle Match API call the page makes. */
function recordApiCalls(page: Page): Request[] {
  const calls: Request[] = [];
  page.on("request", (r) => {
    if (r.url().includes(API)) calls.push(r);
  });
  return calls;
}

async function startStudentPreset(page: Page) {
  await page.goto("/lifestyle/questions");
  await page.getByRole("button", { name: /Student/ }).click();
  await expect(page.getByRole("heading", { name: "Your move" })).toBeVisible();
}

/** The explorer settings: the left column on desktop, the "Adjust" drawer on a phone. */
async function openSettings(page: Page) {
  const adjust = page.getByRole("button", { name: "Adjust" });
  if (await adjust.isVisible()) {
    await adjust.click();
    return page.getByRole("dialog", { name: "Adjust your match" });
  }
  return page.getByTestId("lifestyle-settings");
}

async function closeSettings(page: Page) {
  const done = page.getByRole("button", { name: "Show results" });
  if (await done.isVisible()) await done.click();
}

/** Explorer (T9.6): pick the Student profile card on the first visit. */
async function exploreAsStudent(page: Page) {
  await page.goto("/lifestyle");
  await page.getByTestId("profile-cards").getByRole("button", { name: /Student/ }).click();
  await expect(page.getByTestId("area-row").first()).toBeVisible();
}

test("homepage invites users into Lifestyle Match", async ({ page }) => {
  await page.goto("/");
  // Berlin Ink homepage (T9.4): one of the three entry cards under the hero.
  const card = page.getByTestId("entry-card").filter({ hasText: "Lifestyle match" });
  await expect(card).toContainText("Start the match");
  await card.click();
  await expect(page).toHaveURL(/\/lifestyle$/);
  await expect(page.getByRole("heading", { name: /Start with a profile/ })).toBeVisible();
});

test("Definition of Done: student preset → area near TU Berlin within budget, with reasons, nothing stored", async ({
  page,
  context,
}) => {
  const calls = recordApiCalls(page);
  await startStudentPreset(page);

  // The preset pre-fills a typical student budget and flat.
  await expect(page.getByLabel("Budget in euros")).toHaveValue("700");
  await expect(page.getByText("Avg. Berlin WG room")).toBeVisible();

  // Walk every page (the user can change anything on the way).
  for (const heading of ["Your days", "Evenings & weekends", "Your neighbourhood"]) {
    await page.getByRole("button", { name: "Next →" }).click();
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "TU Berlin" })).toBeHidden(); // days page is behind us
  await page.getByRole("button", { name: "See my lifestyle →" }).click();

  // Summary: a fun, respectful prediction + "did we get this right?"
  await expect(page.getByText("The Campus Explorer")).toBeVisible();
  await expect(page.getByText("Did we capture your lifestyle?")).toBeVisible();
  await page.getByRole("button", { name: /show my areas/ }).click();

  // The questions end in the explorer: among the top 3, an area ≤ 20 min from TU Berlin
  // that fits the €700 budget.
  await expect(page).toHaveURL(/\/lifestyle$/);
  const rows = page.getByTestId("area-row");
  await expect(rows.first()).toBeVisible();
  let nearAndAffordable = 0;
  for (let i = 0; i < 3; i++) {
    const text = await rows.nth(i).innerText();
    const minutes = Number(text.match(/(\d+) min\s+to TU Berlin/)?.[1] ?? "999");
    if (minutes <= 20 && text.includes("fits budget")) nearAndAffordable += 1;
  }
  expect(nearAndAffordable).toBeGreaterThan(0);
  // Every suggestion explains itself with data and a source.
  await rows.first().getByRole("button").first().click();
  const detail = page.getByTestId("area-detail");
  await expect(detail.locator("li").first()).toContainText(/\d/);
  await expect(detail.getByText(/· 20\d\d/).first()).toBeVisible();

  // Privacy: answers never in the URL, cookies or localStorage; only POST bodies.
  expect(page.url()).not.toMatch(/700|tu_berlin|student/);
  expect(await context.cookies()).toEqual([]);
  expect(await page.evaluate(() => Object.keys(window.localStorage))).toEqual([]);
  const withAnswers = calls.filter((r) => r.url().match(/(profile|match|listings)$/));
  expect(withAnswers.length).toBeGreaterThan(0);
  for (const r of withAnswers) expect(r.method()).toBe("POST");
  for (const r of calls.filter((c) => c.method() === "GET")) expect(new URL(r.url()).search).toBe("");
  const matchResponse = await withAnswers.find((r) => r.url().endsWith("match"))!.response();
  expect(matchResponse?.headers()["cache-control"]).toBe("no-store");
});

test("the explorer re-ranks live: weights, budget, remove and restore, compare, see flats", async ({ page }) => {
  await exploreAsStudent(page);
  const rows = page.getByTestId("area-row");
  await expect(page.getByTestId("live-summary")).toContainText("143 areas ranked");
  await expect(page.getByTestId("persona")).toContainText("The Campus Explorer");

  // A weight change re-ranks without a button; only the changed weight is sent.
  let settings = await openSettings(page);
  await settings.getByRole("button", { name: /more things to weigh/ }).click();
  const matchCall = page.waitForResponse((r) => r.url().endsWith("/lifestyle/match") && r.request().postDataJSON().weights?.safety === 5);
  await settings.getByRole("radio", { name: "Safety: 5 of 5" }).click();
  expect((await matchCall).request().postDataJSON().weights).toEqual({ safety: 5 });
  await expect(settings.getByRole("radio", { name: "Safety: 5 of 5" })).toHaveAttribute("aria-checked", "true");
  await closeSettings(page);

  // Not for me: the area leaves the list, then comes back from "Removed areas".
  const top = (await rows.first().getAttribute("data-key"))!;
  const topName = (await rows.first().locator("h3 span.block").first().innerText()).trim();
  await rows.first().getByRole("button").first().click();
  await page.getByRole("button", { name: `Remove ${topName} from my results` }).click();
  await expect(page.locator(`[data-testid=area-row][data-key="${top}"]`)).toHaveCount(0);
  settings = await openSettings(page);
  await settings.getByRole("button", { name: `Bring back ${topName}` }).click();
  await closeSettings(page);
  await expect(page.locator(`[data-testid=area-row][data-key="${top}"]`)).toHaveCount(1);

  // Compare two areas side by side.
  await rows.nth(0).getByRole("button").first().click();
  await page.getByTestId("area-detail").getByRole("button", { name: "Compare" }).click();
  await rows.nth(1).getByRole("button").first().click();
  await page.getByTestId("area-detail").getByRole("button", { name: "Compare" }).click();
  const compare = page.getByTestId("compare-areas");
  await expect(compare).toBeVisible();
  await expect(compare.getByRole("rowheader", { name: "Trip to TU Berlin" })).toBeVisible();

  // The data behind it, then See flats here: a side panel that closes with Escape.
  const detail = page.getByTestId("area-detail");
  await detail.getByRole("button", { name: "The data behind this" }).click();
  await expect(detail.getByText(/^Sources$/)).toBeVisible();
  await detail.getByRole("button", { name: "See flats here" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/WohnIQ listings in/)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  // The budget re-ranks too, and nothing is put in the URL.
  settings = await openSettings(page);
  await settings.getByLabel("Budget in euros").fill("1400");
  await closeSettings(page);
  await expect(page.getByTestId("live-summary")).not.toContainText("updating");
  expect(page.url()).not.toMatch(/1400|budget/);
});

test("the map shades every area, numbers the top 10 and marks the destination", async ({ page }) => {
  await exploreAsStudent(page);
  await expect(page.locator(".leaflet-overlay-pane path")).toHaveCount(143);
  await expect(page.locator(".leaflet-marker-pane .lm-rank")).toHaveCount(10);
  await expect(page.locator(".leaflet-marker-pane .lm-dest")).toHaveCount(1);
  await page.locator(".lm-rank", { hasText: /^3$/ }).click();
  await expect(page.getByTestId("map-card")).toContainText("match");
  await page.getByRole("button", { name: "Details below" }).click();
  await expect(page.getByTestId("area-detail")).toBeVisible();
  await page.getByRole("button", { name: "All of Berlin" }).click();
  await expect(page.getByRole("button", { name: "All of Berlin" })).toHaveAttribute("aria-pressed", "true");
});

test("the old results address redirects to the explorer; no emoji on Lifestyle", async ({ page }) => {
  await page.goto("/lifestyle/results");
  await expect(page).toHaveURL(/\/lifestyle$/);
  await expect(page.getByRole("heading", { name: "Start with a profile" })).toBeVisible();
  const text = await page.locator("body").innerText();
  // Emoji-style characters (not ©, which the map credits use).
  expect(text).not.toMatch(/\p{Emoji_Presentation}|\uFE0F/u);
});

test("on a phone the map comes first and the settings sit behind Adjust", async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await exploreAsStudent(page);
  await expect(page.getByTestId("lifestyle-settings")).toBeHidden();
  await page.getByRole("button", { name: "Adjust" }).click();
  const drawer = page.getByRole("dialog", { name: "Adjust your match" });
  await expect(drawer.getByLabel("Budget in euros")).toBeVisible();
  await drawer.getByRole("button", { name: "Show results" }).click();
  await expect(drawer).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("starting from scratch needs at least one preference; answers can be cleared", async ({ page }) => {
  await page.goto("/lifestyle/questions");
  await page.getByRole("button", { name: /Start from scratch/ }).click();
  for (let i = 0; i < 4; i++) await page.getByRole("button", { name: /Next →|See my lifestyle →/ }).click();
  await expect(page.getByText("Tell us at least one thing you care about")).toBeVisible();
  await expect(page.getByRole("button", { name: /show my areas/ })).toBeDisabled();

  // Jump back via "Change", answer one question, and matching becomes possible.
  await page.getByRole("button", { name: "← Change answers" }).click();
  await page.getByRole("button", { name: "Next →" }).click();
  await page.getByRole("button", { name: "Next →" }).click();
  await page.getByText("Out most nights — bars, gigs, clubs").click();
  await page.getByRole("button", { name: "Next →" }).click();
  await page.getByRole("button", { name: "See my lifestyle →" }).click();
  await expect(page.getByText("The Night Owl")).toBeVisible();
  await expect(page.getByRole("button", { name: /show my areas/ })).toBeEnabled();

  // Clear my answers: back to the start, nothing left in this tab.
  await page.getByRole("button", { name: "Clear my answers" }).click();
  await expect(page.getByRole("heading", { name: /Start with a profile/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: /Start with a profile/ })).toBeVisible();
});
