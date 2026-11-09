from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
external = set()
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.on("request", lambda r: external.add(urlparse(r.url).hostname) if urlparse(r.url).hostname not in ("localhost", "127.0.0.1") and r.url.startswith("http") else None)

    page.goto("http://localhost:3000/", wait_until="networkidle"); page.wait_for_timeout(800)
    page.screenshot(path="screenshots/1_home.png", full_page=True)
    href = page.locator("a[href^='/listings/']").first.get_attribute("href")

    page.goto("http://localhost:3000" + href, wait_until="networkidle"); page.wait_for_timeout(1200)
    page.screenshot(path="screenshots/2_detail.png", full_page=True)

    page.goto("http://localhost:3000/", wait_until="networkidle")
    page.fill("input", "I work near Kreuzberg, budget €1,500, quiet neighborhood, cafes nearby")
    page.get_by_role("button", name="Search").click()
    page.wait_for_selector("article"); page.wait_for_timeout(800)
    page.evaluate("window.scrollTo(0, 380)")
    page.screenshot(path="screenshots/3_search_kreuzberg.png")
    for a in page.locator("article").all():
        print("  card:", a.locator("h3").inner_text(), "|", [t for t in a.locator("span").all_inner_texts() if "min" in t])

    boxes = page.locator("input[type=checkbox]"); [boxes.nth(i).check() for i in range(3)]
    page.get_by_role("button", name="Compare").click(); page.wait_for_timeout(800)
    page.screenshot(path="screenshots/4_compare.png")

    page.goto("http://localhost:3000/", wait_until="networkidle")
    page.get_by_text("Try an example").click()
    page.wait_for_selector("article"); page.wait_for_timeout(800)
    page.evaluate("window.scrollTo(0, 380)")
    page.screenshot(path="screenshots/5_example_no_stops.png")
    print("example note:", page.locator("p.text-xs.text-gray-500").first.inner_text())
    b.close()
print("external hosts the browser tried:", sorted(external))
