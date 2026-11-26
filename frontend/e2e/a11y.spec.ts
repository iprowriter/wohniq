// Accessibility pass (T9.8): automated WCAG 2.1 A/AA checks with axe on every page, at
// desktop and phone size. Manual checks (keyboard, landmarks, 44 px targets) are in the
// Stop 8 checklist. Map tiles are canvas images and are excluded (they carry no text).

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function scan(page: Page) {
  const r = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude(".leaflet-tile-pane")
    .analyze();
  return r.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length}× ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
}

const PAGES: { name: string; open: (page: Page, id: string, id2: string) => Promise<void> }[] = [
  { name: "home", open: async (p) => { await p.goto("/"); await p.locator(".leaflet-container").first().waitFor(); } },
  { name: "results", open: async (p) => { await p.goto("/?q=Quiet+2+rooms+in+Mitte+near+a+park"); await expect(p.getByTestId("results-heading")).toHaveText(/^\d+ flats? /); } },
  { name: "listing", open: async (p, id) => { await p.goto(`/listings/${id}`); await p.getByTestId("similar-card").first().waitFor(); } },
  { name: "rent check", open: async (p) => { await p.goto("/rent-check"); await p.getByRole("heading", { level: 1 }).waitFor(); } },
  { name: "lifestyle", open: async (p) => { await p.goto("/lifestyle"); await p.getByTestId("profile-cards").getByRole("button", { name: /Student/ }).click(); await p.getByTestId("area-row").first().waitFor(); } },
  { name: "lifestyle questions", open: async (p) => { await p.goto("/lifestyle/questions"); await p.getByRole("button", { name: /Student/ }).waitFor(); } },
  { name: "neighbourhoods", open: async (p) => { await p.goto("/neighborhoods"); await p.locator(".leaflet-overlay-pane path").first().waitFor(); } },
  { name: "compare", open: async (p, id, id2) => { await p.goto(`/compare?ids=${id},${id2}`); await expect(p.getByTestId("compare-column")).toHaveCount(2); } },
  { name: "saved", open: async (p) => { await p.goto("/saved?tab=searches"); await p.getByRole("heading", { name: "Saved" }).waitFor(); } },
];

for (const pg of PAGES) {
  test(`no WCAG A/AA violations: ${pg.name}`, async ({ page }) => {
    const map = await (await page.request.get("http://localhost:8000/api/v1/listings/map")).json();
    await pg.open(page, map[0].id, map[1].id);
    await page.waitForTimeout(500);
    expect(await scan(page)).toEqual([]);
  });
}
