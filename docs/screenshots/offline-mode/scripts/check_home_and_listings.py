import sys, json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

external, failed_api, console_errors = set(), [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.on("request", lambda r: external.add(urlparse(r.url).netloc) if urlparse(r.url).hostname not in ("localhost", "127.0.0.1") and r.url.startswith("http") else None)
    page.on("response", lambda r: failed_api.append((r.status, r.url)) if "localhost:8000" in r.url and r.status >= 400 else None)
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

    page.goto("http://localhost:3000/", wait_until="networkidle")
    cards = page.locator("a[href^='/listings/']")
    print("home cards:", cards.count())
    page.wait_for_timeout(1500)
    page.screenshot(path="screenshots/home.png", full_page=True)
    hrefs = [cards.nth(i).get_attribute("href") for i in range(cards.count())]

    for i, href in enumerate(hrefs):
        page.goto("http://localhost:3000" + href, wait_until="networkidle")
        page.wait_for_selector("h1", timeout=10000)
        title = page.locator("h1").inner_text()
        badge = page.locator("text=/(Low risk|Caution|High risk) · \\d+/").first.inner_text()
        chips = page.locator("text=/^(cafes|parks|supermarket|nightlife|gym|transit) · \\d+$/").count()
        markers = page.locator("path.leaflet-interactive").count()
        photos = page.locator("main button[title='Click to enlarge']").count()
        err = page.locator(".bg-red-50.text-red-700").count()
        print(f"  detail {i}: {title!r:42} badge={badge!r:18} photos={photos} amenity_chips={chips} map_markers={markers} error={err}")
        if i == 0:
            page.wait_for_timeout(1500)
            page.screenshot(path="screenshots/detail.png", full_page=True)

    page.goto("http://localhost:3000/", wait_until="networkidle")
    page.get_by_text("Try an example").click()
    page.wait_for_selector("article", timeout=15000)
    page.wait_for_timeout(1500)
    print("search results:", page.locator("article").count(), "| chips:", page.locator("text=Understood as").count())
    page.screenshot(path="screenshots/search.png", full_page=True)
    b.close()

print("external hosts requested:", sorted(external))
print("API errors:", failed_api)
print("console errors (first 5):", console_errors[:5], "total", len(console_errors))
