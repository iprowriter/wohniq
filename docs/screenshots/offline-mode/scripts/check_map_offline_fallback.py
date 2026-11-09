"""Option A visual check: 4 network scenarios for the listing-page map."""
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://localhost:3000/listings/f2e6195f-732e-4016-add7-02c92747b93c"
TILE = (Path(__file__).parent / "standin_tile.png").read_bytes()  # generated stand-in tile
Path("screenshots").mkdir(exist_ok=True)
OSM = re.compile(r"^https://[abc]\.tile\.openstreetmap\.org/")  # a./b./c. subdomains

def state(page):
    return {
        "offline_look": page.locator(".wohniq-map-offline").count() == 1,
        "note": (page.locator("[role=status]").inner_text() if page.locator("[role=status]").count() else None),
        "scale_bar": page.locator(".leaflet-control-scale").count() == 1,
        "dashed_ring": page.locator("path[stroke-dasharray]").count(),
        "markers": page.locator("path.leaflet-interactive").count(),
        "tiles_loaded": page.locator("img.leaflet-tile.leaflet-tile-loaded").count(),
        "tiles_not_loaded": page.locator("img.leaflet-tile:not(.leaflet-tile-loaded)").count(),
    }

def open_page(browser, route_handler=None):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    if route_handler:
        page.route(OSM, route_handler)
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_selector(".leaflet-container", timeout=15000)
    return page

def shot(page, name):
    page.locator(".leaflet-container").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    page.locator(".leaflet-container").locator("xpath=..").screenshot(path=f"screenshots/{name}")

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. Offline: OSM unreachable in this sandbox, tiles fail immediately.
    page = open_page(b)
    t0 = time.time(); page.wait_for_selector(".wohniq-map-offline", timeout=10000)
    print(f"1 offline (tiles fail): appeared after {time.time()-t0:.1f}s ->", state(page))
    shot(page, "1_offline_map.png")
    page.screenshot(path="screenshots/1_offline_full_page.png", full_page=True)
    page.close()

    # 2. Online (simulated): tiles load → unchanged look.
    page = open_page(b, lambda r: r.fulfill(status=200, content_type="image/png", body=TILE))
    page.wait_for_timeout(5000)  # past the 4 s timeout: must still look normal
    print("2 online (stand-in tiles), after 5s ->", state(page))
    shot(page, "2_online_map.png")
    page.close()

    # 3. Hanging network: tile requests never answer → offline look after ~4 s.
    page = open_page(b, lambda r: None)
    page.wait_for_timeout(2000)
    print("3 hanging network, at ~2s ->", state(page)["offline_look"])
    t0 = time.time(); page.wait_for_selector(".wohniq-map-offline", timeout=10000)
    print(f"3 hanging network: offline look after a further {time.time()-t0:.1f}s ->", state(page)["offline_look"])
    page.unroute_all(behavior="ignoreErrors")  # requests left hanging on purpose
    page.close()

    # 4. Connection comes back: tiles fail first, then succeed after panning.
    online = {"on": False}
    page = open_page(b, lambda r: r.fulfill(status=200, content_type="image/png", body=TILE) if online["on"] else r.abort())
    page.wait_for_selector(".wohniq-map-offline", timeout=10000)
    print("4 recovery, before:", state(page)["offline_look"])
    page.wait_for_timeout(1000)  # let the zoom-out to the search area finish, or the drag is ignored
    online["on"] = True
    page.locator(".leaflet-container").scroll_into_view_if_needed()  # drag must hit the map
    box = page.locator(".leaflet-container").bounding_box()
    page.mouse.move(box["x"] + 300, box["y"] + 150); page.mouse.down()
    page.mouse.move(box["x"] + 100, box["y"] + 150, steps=8); page.mouse.up()
    page.wait_for_timeout(1500)
    print("4 recovery, after panning with tiles available ->", state(page))
    print("4 map pane position:", page.locator(".leaflet-map-pane").get_attribute("style"))
    shot(page, "4_recovered_map.png")
    print("4 map pane position at screenshot:", page.locator(".leaflet-map-pane").get_attribute("style"))
    b.close()
