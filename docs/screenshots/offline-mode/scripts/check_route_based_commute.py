from playwright.sync_api import sync_playwright
OUT = "screenshots"
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 1000})
    page.goto("http://localhost:3000/", wait_until="networkidle")
    page.get_by_text("Try an example").click()
    page.wait_for_selector("article"); page.wait_for_timeout(800)
    print("note:", page.locator("p.text-xs.text-gray-500").first.inner_text())
    for a in page.locator("article").all():
        c = a.locator("span[title^='Estimated']").first
        print(f"  {a.locator('h3').inner_text():32} | {c.inner_text():30} | tooltip: {c.get_attribute('title')[:45]}…")
        print(f"  {'':32} | explanation: {[l for l in a.locator('li').all_inner_texts() if 'work' in l]}")
    text = page.inner_text("body")
    print("visible null/undefined/NaN:", [w for w in ("null", "undefined", "NaN") if w in text])
    page.evaluate("window.scrollTo(0, 380)")
    page.screenshot(path=f"{OUT}/1_example_search_alexanderplatz.png")
    boxes = page.locator("input[type=checkbox]")
    for i in range(4):
        boxes.nth(i).check()
    page.get_by_role("button", name="Compare").click(); page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}/2_comparison.png")
    b.close()
