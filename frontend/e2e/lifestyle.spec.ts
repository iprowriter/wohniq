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
  await page.goto("/lifestyle");
  await page.getByRole("button", { name: /Student/ }).click();
  await expect(page.getByRole("heading", { name: "Your move" })).toBeVisible();
}

async function goToResultsAsStudent(page: Page) {
  await startStudentPreset(page);
  await page.getByRole("button", { name: "skip to your profile" }).click();
  await expect(page.getByText("The Campus Explorer")).toBeVisible();
  await page.getByRole("button", { name: /show my areas/ }).click();
  await expect(page).toHaveURL(/\/lifestyle\/results$/);
  await expect(page.locator("article").first()).toBeVisible();
}

test("homepage invites users into Lifestyle Match", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Tell us how you live/ })).toBeVisible();
  await expect(page.getByText("Berlin areas scored")).toBeVisible();
  await page.getByRole("link", { name: /Try Lifestyle Match/ }).click();
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

  // Results: among the top 3, an area ≤ 20 min from TU Berlin that fits the €700 budget.
  const cards = page.locator("article");
  await expect(cards.first()).toBeVisible();
  let nearAndAffordable = 0;
  for (let i = 0; i < 3; i++) {
    const card = cards.nth(i);
    const text = await card.innerText();
    const minutes = Number(text.match(/≈ (\d+) min[^\n]*to TU Berlin/)?.[1] ?? "999");
    if (minutes <= 20 && text.includes("Fits budget")) nearAndAffordable += 1;
    // Every suggestion explains itself with data and a source.
    await expect(card.locator("li").first()).toContainText(/\d/);
    await expect(card.getByText(/· 20\d\d/).first()).toBeVisible();
  }
  expect(nearAndAffordable).toBeGreaterThan(0);

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

test("the user stays in control: tune weights, update, remove and restore areas, see flats", async ({ page }) => {
  await goToResultsAsStudent(page);
  const cards = page.locator("article");
  const firstName = (await cards.first().locator("h3").innerText()).trim();

  // Tune: raise Safety with the keyboard; nothing changes until "Update results".
  const update = page.getByRole("button", { name: /Update results|up to date/ });
  await expect(update).toHaveText("Results are up to date");
  const safety = page.getByLabel("Safety", { exact: true });
  await safety.focus();
  for (let i = 0; i < 5; i++) await safety.press("ArrowRight");
  await expect(update).toHaveText("Update results (1 change)");
  await expect(page.getByText("Set by you")).toBeVisible();
  const matchCall = page.waitForResponse((r) => r.url().endsWith("/lifestyle/match"));
  await update.click();
  const body = (await matchCall).request().postDataJSON();
  expect(body.weights).toEqual({ safety: 5 }); // only the changed weight is sent
  await expect(update).toHaveText("Results are up to date");

  // Remove the top area: it disappears, then comes back on undo.
  const top = (await cards.first().locator("h3").innerText()).trim();
  await cards.first().getByRole("button", { name: /Remove .* from my results/ }).click();
  await expect(page.locator("article h3", { hasText: top })).toHaveCount(0);
  await page.getByRole("button", { name: `${top} ↺` }).click();
  await expect(page.locator("article h3", { hasText: top })).toHaveCount(1);

  // Why this score / data behind it.
  await cards.first().getByRole("button", { name: "Why this score" }).click();
  await expect(cards.first().getByText(/adds to score/i)).toBeVisible();
  await cards.first().getByRole("button", { name: "The data behind this" }).click();
  await expect(cards.first().getByText(/^Sources$/i)).toBeVisible();

  // See flats here: a side panel that closes with Escape.
  await cards.first().getByRole("button", { name: "See flats here →" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/WohnIQ listings in/)).toBeVisible();
  await expect(dialog.getByText(/flats? located in this area/)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  expect(firstName.length).toBeGreaterThan(0);
});

test("the map shades every area and numbers the top matches", async ({ page }) => {
  await goToResultsAsStudent(page);
  await expect(page.locator(".leaflet-overlay-pane path")).toHaveCount(143);
  await expect(page.locator(".leaflet-marker-pane > div")).toHaveCount(10);
  await page.getByRole("button", { name: "All of Berlin" }).click();
  await expect(page.getByRole("button", { name: "Zoom to my matches" })).toBeVisible();
});

test("starting from scratch needs at least one preference; answers can be cleared", async ({ page }) => {
  await page.goto("/lifestyle");
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
