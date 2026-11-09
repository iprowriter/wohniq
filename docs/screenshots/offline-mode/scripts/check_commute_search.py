from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 1000})
    page.goto("http://localhost:3000/", wait_until="networkidle")
    page.get_by_text("Try an example").click()
    page.wait_for_selector("article", timeout=15000)
    page.wait_for_timeout(800)
    note = page.locator("p.text-xs.text-gray-500").first.inner_text()
    print("note:", note)
    for a in page.locator("article").all():
        title = a.locator("h3").inner_text()
        commute = a.locator("span[title^='Estimated']").first
        print(f"  {title:34} | {commute.inner_text():22} | reasons: {a.locator('li').all_inner_texts()[:3]}")
    page.locator("article").first.scroll_into_view_if_needed()
    page.evaluate("window.scrollTo(0, 380)")
    page.screenshot(path="screenshots/search_commute.png")
    boxes = page.locator("input[type=checkbox]")
    boxes.nth(0).check(); boxes.nth(1).check(); boxes.nth(2).check()
    page.get_by_role("button", name="Compare").click()
    page.wait_for_timeout(800)
    page.screenshot(path="screenshots/compare.png")
    print("null shown anywhere:", "null" in page.content().lower().replace("nullable",""))
    b.close()
