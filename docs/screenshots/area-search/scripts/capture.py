"""Capture docs/screenshots/area-search/*.png (production build on :3000, demo backend on :8000).

Takes VIEWPORT screenshots: what the user sees after the results auto-scroll. Don't use
full_page=True with a clip here: the header is `position: sticky`, so a full-page capture
taken while scrolled paints it at the scroll offset (mid-page), and element bounding boxes
are viewport-relative while full-page clips are page-relative. Every capture is checked
before it's saved: header at the top of the frame, expected content on screen.
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parents[1]
URL = "http://localhost:3000"

CHECK = """(needle) => {
  const h = document.querySelector('header').getBoundingClientRect();
  const top = document.elementFromPoint(innerWidth / 2, 10);
  const chips = [...document.querySelectorAll('span')].find(s => s.textContent === 'Understood as');
  const c = chips ? chips.parentElement.getBoundingClientRect() : null;
  return {
    header_at_top: Math.round(h.top) === 0 && !!top.closest('header'),
    chips_visible: !!c && c.top >= h.bottom && c.bottom <= innerHeight,
    needle_visible: [...document.querySelectorAll('main, body *')].some(el => {
      if (el.children.length || !el.textContent.includes(needle)) return false;
      const r = el.getBoundingClientRect();
      return r.top >= h.bottom && r.bottom <= innerHeight && r.height > 0;
    }),
  };
}"""


def search(page: Page, query: str) -> None:
    page.goto(URL, wait_until="networkidle")
    page.get_by_placeholder(re.compile("quiet 2-room")).fill(query)
    page.get_by_role("button", name="Search", exact=True).click()
    page.wait_for_selector("text=ranked by fit")
    page.wait_for_timeout(1200)  # smooth auto-scroll to the results


def save(page: Page, name: str, needle: str) -> None:
    state = page.evaluate(CHECK, needle)
    if not all(state.values()):
        sys.exit(f"{name}: refusing to save, capture check failed: {state}")
    page.screenshot(path=OUT / name)
    print(f"{name}: ok {state}")


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    search(page, "a quiet flat in Mitte, Spandau, Lichtenberg, Treptow")
    save(page, "1_reported_query.png", "in Mitte / Spandau / Lichtenberg / Treptow")

    search(page, "quiet flat in Mitte budget €300")
    save(page, "2_budget_too_low.png", "Your budget is too low for Mitte")

    search(page, "2-room in Mitte, budget 1000")
    save(page, "3_budget_and_nearby.png", "Showing flats near Mitte")

    page.locator("[data-kind=budget_too_low] button").first.click()
    page.wait_for_selector("text=1 result")
    page.wait_for_timeout(1200)
    save(page, "4_after_one_click_budget.png", "In Mitte")
    browser.close()
